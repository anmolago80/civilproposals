"""
ai_interface.py

Provider-agnostic AI abstraction. Every other module in this app calls
`call_ai()` (or `call_ai_json()`) and never touches a provider SDK directly --
that's what lets the AI provider be swapped or added to without rewriting
the rest of the app.

Supported providers: OpenAI, Azure OpenAI, Anthropic Claude, Google Gemini,
and Microsoft 365 Copilot (Preview) -- the last one is a materially
different integration (OAuth sign-in via modules/copilot_client.py rather
than a pasted API key, and a grounded-chat API rather than a general
completion endpoint) -- see that module's docstring and README.md's
"A note on Microsoft 365 Copilot" for the full picture, including why it
may not reliably handle this app's large structured-extraction prompts.

API keys/tokens are read from a config dict (normally built from
`st.session_state["ai_config"]` in app.py) and are never written to disk.
"""

from __future__ import annotations

import contextvars
import json
import random
import re
import sys
import time


class AIConfigError(Exception):
    """Raised when the AI provider is not configured well enough to call."""


class AIProviderNotImplemented(Exception):
    """Raised when a listed-but-not-yet-wired provider is selected."""


DEFAULT_MODELS = {
    "OpenAI": "gpt-4o",
    "Azure OpenAI": "",  # deployment name is tenant-specific; user must supply it
    # Verified against platform.claude.com's model-ids-and-versions docs
    # (Aug 2026): dateless IDs like this are the CURRENT pinned-snapshot
    # convention (not an evergreen alias) for this model generation, so
    # this is correct as-is, not something that drifts.
    "Anthropic Claude": "claude-sonnet-5",
    # Was "gemini-1.5-pro" -- Google fully shut that model family down on
    # 2025-09-29 (confirmed via ai.google.dev/gemini-api/docs/changelog),
    # so every BYOK/desktop-mode user who'd left this at its default was
    # getting a hard failure on every single Gemini call, not a slow
    # response. "gemini-3.1-pro-preview" is the current, live, confirmed-
    # working Pro-tier identifier as of Aug 2026 -- Google's Pro-tier naming
    # has been through a fast churn of "-preview" suffixed releases lately,
    # so if this starts failing again, check
    # https://ai.google.dev/gemini-api/docs/changelog for whatever the
    # current Pro-tier id is before assuming something else broke.
    "Google Gemini": "gemini-3.1-pro-preview",
    "Microsoft 365 Copilot (Preview)": "",  # no model name -- Copilot doesn't take one
}

PROVIDERS = list(DEFAULT_MODELS.keys())


# ---------------------------------------------------------------------------
# Per-call cost logging (see db.AiCallLog)
#
# Every provider adapter below calls _record_usage() with the token counts
# its response reported. Attribution (who/which project) comes from a
# contextvar set via set_usage_context() -- a contextvar (not a module
# global) because the Streamlit web process serves many users' script runs
# from one process, and the RQ worker sets it per-job (see
# job_queue.run_*_job). Logging is strictly best-effort: any failure here is
# printed to stderr and swallowed, because a cost-accounting hiccup must
# never fail a user's actual AI call mid-tender.
# ---------------------------------------------------------------------------

_usage_context: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "ai_usage_context", default=None
)

# Approximate USD per MILLION tokens (input, output). These are estimates
# for internal cost visibility only -- update them when provider pricing
# changes; an unknown model logs its token counts with cost NULL rather
# than guessing. Last reviewed: Aug 2026.
MODEL_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-5": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-opus-4-6": (15.00, 75.00),
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    # Google
    "gemini-3.1-pro-preview": (1.25, 10.00),
}


def set_usage_context(user_id: str | None = None, project_key: str = "",
                      project_name: str = "", purpose: str = "") -> None:
    """Attribute subsequent call_ai() calls (in this thread/task) to a
    user + project for cost logging. Call with no arguments to clear."""
    if not any([user_id, project_key, project_name, purpose]):
        _usage_context.set(None)
    else:
        _usage_context.set({
            "user_id": user_id,
            "project_key": project_key or "",
            "project_name": project_name or "",
            "purpose": purpose or "",
        })


def estimate_cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """None when the model has no entry in MODEL_PRICES_PER_MTOK (unknown
    cost is a different fact from zero cost) or when neither token count is
    available."""
    prices = MODEL_PRICES_PER_MTOK.get((model or "").strip())
    if not prices or (input_tokens is None and output_tokens is None):
        return None
    in_price, out_price = prices
    return round(
        (input_tokens or 0) / 1_000_000 * in_price
        + (output_tokens or 0) / 1_000_000 * out_price,
        6,
    )


def _record_usage(provider: str, model: str,
                  input_tokens: int | None, output_tokens: int | None) -> None:
    """Best-effort write of one AI call's usage to db.AiCallLog. Never
    raises -- see the section comment above."""
    try:
        from modules import db
        ctx = _usage_context.get() or {}
        _project_key = ctx.get("project_key", "")
        db.log_ai_call(
            user_id=ctx.get("user_id"),
            project_key=_project_key,
            project_name=ctx.get("project_name", ""),
            purpose=ctx.get("purpose", ""),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
        )
        # Non-trial/unlimited accounts are never blocked by AI spend (see
        # limits.ai_spend_block_reason) -- but a single project running
        # unusually high is still worth a server-side line in the logs.
        # Never shown to any customer; best-effort, same as the logging
        # above (a failure here must never affect the AI call that just
        # succeeded).
        if _project_key:
            from modules import limits
            _project_cost = db.project_ai_cost(_project_key, ctx.get("user_id"))
            limits.maybe_alert_admin_on_project_cost(
                _project_key, ctx.get("project_name", ""), _project_cost.get("cost_usd", 0.0),
            )
    except Exception as exc:
        print(f"[ai_interface] cost logging failed (ignored): {exc}", file=sys.stderr)


def _safe_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def call_ai(prompt: str, system_message: str | None = None, config: dict | None = None,
            max_tokens: int = 4000, temperature: float = 0.3) -> str:
    """
    Send a prompt to whichever AI provider is configured and return the text response.

    `config` shape: {"provider": str, "api_key": str, "model": str, "endpoint": str}
    If `config` is omitted, this tries to read `st.session_state["ai_config"]`.
    """
    config = config or _get_config_from_session_state()
    provider = (config or {}).get("provider")

    if not config or not provider:
        raise AIConfigError(
            "No AI provider is configured yet. Set one up via the sidebar's ☰ menu."
        )

    if provider == "OpenAI":
        return _call_openai(prompt, system_message, config, max_tokens, temperature)
    elif provider == "Azure OpenAI":
        return _call_azure_openai(prompt, system_message, config, max_tokens, temperature)
    elif provider == "Anthropic Claude":
        return _call_anthropic(prompt, system_message, config, max_tokens, temperature)
    elif provider == "Google Gemini":
        return _call_gemini(prompt, system_message, config, max_tokens, temperature)
    elif provider.startswith("Microsoft 365 Copilot"):
        return _call_copilot(prompt, system_message, config)
    else:
        raise AIConfigError(f"Unknown AI provider '{provider}'.")


JSON_MAX_TOKENS_CEILING = 16000


# Set on a result dict that had to be salvaged from a truncated response.
# Callers that surface data to a user should check it (see was_repaired).
REPAIRED_FLAG = "_ai_response_was_repaired"


def was_repaired(data) -> bool:
    return bool(isinstance(data, dict) and data.get(REPAIRED_FLAG))


def call_ai_json(prompt: str, system_message: str | None = None, config: dict | None = None,
                  max_tokens: int = 4000) -> dict:
    """
    Same as call_ai(), but instructs the model to return JSON only and parses
    the result. If the first response doesn't parse, it retries with a
    corrective follow-up AND a progressively larger output budget.

    The budget escalation matters: the single most common reason a response
    won't parse in this app is not that the model wrote prose instead of JSON,
    but that it got *cut off mid-JSON* because the output budget ran out --
    especially with "reasoning" models, which silently spend a chunk of that
    budget on hidden internal reasoning before emitting a single visible
    character. A truncated object has no closing brace, so nothing parses.
    Re-asking with the same small budget just truncates again; re-asking with
    a bigger budget usually fixes it. `_try_parse_json` also tries to repair a
    truncated object as a last resort before we give up on a given attempt.

    Raises a clear, actionable AIConfigError if every attempt fails.
    """
    json_instruction = (
        "\n\nRespond with ONLY valid JSON. No markdown code fences, no commentary "
        "before or after the JSON, no trailing commas."
    )

    # Escalating output budgets: the requested size, then double, then the
    # ceiling -- deduped and kept in ascending order.
    budgets = sorted({
        max_tokens,
        min(max_tokens * 2, JSON_MAX_TOKENS_CEILING),
        JSON_MAX_TOKENS_CEILING,
    })

    last_raw = ""
    for attempt_index, budget in enumerate(budgets):
        if attempt_index == 0:
            attempt_prompt = prompt + json_instruction
        else:
            attempt_prompt = (
                f"Your previous response could not be parsed as JSON (it may have been cut "
                f"off before it finished). Here is what you returned:\n\n{last_raw[:2000]}\n\n"
                f"Return ONLY a complete, valid JSON object for this request:\n\n{prompt}"
                f"{json_instruction}"
            )
        raw = call_ai(attempt_prompt, system_message, config, budget, temperature=0.1)
        parsed = _try_parse_json(raw)
        if parsed is not None:
            return parsed
        last_raw = raw

    # Every budget exhausted. Last resort: try to repair the biggest response
    # we got (close off a truncated object) rather than failing outright.
    repaired = _try_parse_json(last_raw, repair=True)
    if repaired is not None:
        # A repaired parse closes off a TRUNCATED object, so trailing fields
        # can be missing entirely -- and the result looks exactly like a
        # clean one to every caller. Flagging it lets the UI say "this was
        # recovered from a cut-off response, check it" instead of presenting
        # a possibly-incomplete answer as if it were whole.
        if isinstance(repaired, dict):
            repaired[REPAIRED_FLAG] = True
        return repaired

    raise AIConfigError(
        "The AI's response could not be read as valid data, even after retrying with a "
        "larger output budget. This usually means the selected model was cut off before it "
        "finished, or isn't reliably returning structured output. If you're using a newer "
        "'reasoning' model (e.g. an OpenAI o-series or GPT-5 model), it can spend most of its "
        "output budget on hidden internal reasoning and get truncated. Switch to a standard "
        "model in the sidebar's ☰ menu -- the app's default, claude-sonnet-5, and "
        "gpt-4o both work reliably here."
    )


def get_default_model(provider: str) -> str:
    return DEFAULT_MODELS.get(provider, "")


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------

def _call_openai(prompt, system_message, config, max_tokens, temperature) -> str:
    from openai import OpenAI

    api_key = config.get("api_key")
    if not api_key:
        raise AIConfigError("OpenAI is selected but no API key has been entered.")
    model = config.get("model") or DEFAULT_MODELS["OpenAI"]

    client = OpenAI(api_key=api_key)
    messages = _build_messages(prompt, system_message)

    def _create_and_extract(tokens, **kwargs):
        response = _openai_chat_create(client, model, messages, tokens, kwargs)
        usage = getattr(response, "usage", None)
        _record_usage(
            "OpenAI", model,
            _safe_int(getattr(usage, "prompt_tokens", None)),
            _safe_int(getattr(usage, "completion_tokens", None)),
        )
        return response.choices[0].message.content or ""

    return _call_with_resilience(_create_and_extract, temperature, max_tokens)


def _call_azure_openai(prompt, system_message, config, max_tokens, temperature) -> str:
    from openai import AzureOpenAI

    api_key = config.get("api_key")
    endpoint = config.get("endpoint")
    deployment = config.get("model")
    if not api_key or not endpoint or not deployment:
        raise AIConfigError(
            "Azure OpenAI needs an API key, an endpoint URL, and a deployment name "
            "(entered as the 'model' field) — one is missing."
        )

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=config.get("api_version", "2024-08-01-preview"),
    )
    messages = _build_messages(prompt, system_message)

    def _create_and_extract(tokens, **kwargs):
        response = _openai_chat_create(client, deployment, messages, tokens, kwargs)
        usage = getattr(response, "usage", None)
        _record_usage(
            "Azure OpenAI", deployment,
            _safe_int(getattr(usage, "prompt_tokens", None)),
            _safe_int(getattr(usage, "completion_tokens", None)),
        )
        return response.choices[0].message.content or ""

    return _call_with_resilience(_create_and_extract, temperature, max_tokens)


def _call_anthropic(prompt, system_message, config, max_tokens, temperature) -> str:
    import anthropic

    api_key = config.get("api_key")
    if not api_key:
        raise AIConfigError("Anthropic Claude is selected but no API key has been entered.")
    model = config.get("model") or DEFAULT_MODELS["Anthropic Claude"]

    client = anthropic.Anthropic(api_key=api_key)

    def _create_and_extract(tokens, **kwargs):
        # `temperature` is dropped here, not passed through: anthropic-sdk-python
        # 1.x removed it from Messages.create()'s signature entirely (confirmed by
        # inspecting the installed package -- there is no longer a single
        # reference to "temperature" anywhere in it), and requirements.txt pins
        # anthropic>=0.34 with no upper bound, so a fresh build always gets
        # whatever is newest. Passing it raised a bare TypeError ("unexpected
        # keyword argument") that _is_temperature_unsupported_error() didn't
        # recognise (it was written for the API rejecting the value at runtime,
        # not the SDK rejecting the keyword at call time), so every Anthropic
        # call failed outright. Silently dropping it here means both old and new
        # SDK versions work; losing the quality knob is the same acceptable
        # trade-off _call_with_resilience's own fallback already makes below.
        kwargs.pop("temperature", None)
        response = client.messages.create(
            model=model, max_tokens=tokens, system=system_message or "",
            messages=[{"role": "user", "content": prompt}], **kwargs,
        )
        usage = getattr(response, "usage", None)
        _record_usage(
            "Anthropic Claude", model,
            _safe_int(getattr(usage, "input_tokens", None)),
            _safe_int(getattr(usage, "output_tokens", None)),
        )
        parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return "\n".join(parts)

    return _call_with_resilience(_create_and_extract, temperature, max_tokens)


def _call_gemini(prompt, system_message, config, max_tokens, temperature) -> str:
    import google.generativeai as genai

    api_key = config.get("api_key")
    if not api_key:
        raise AIConfigError("Google Gemini is selected but no API key has been entered.")
    model_name = config.get("model") or DEFAULT_MODELS["Google Gemini"]

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name, system_instruction=system_message or None)

    def _create_and_extract(tokens, **kwargs):
        response = model.generate_content(prompt, generation_config={"max_output_tokens": tokens, **kwargs})
        usage = getattr(response, "usage_metadata", None)
        _record_usage(
            "Google Gemini", model_name,
            _safe_int(getattr(usage, "prompt_token_count", None)),
            _safe_int(getattr(usage, "candidates_token_count", None)),
        )
        return response.text or ""

    return _call_with_resilience(_create_and_extract, temperature, max_tokens)


def _call_copilot(prompt, system_message, config) -> str:
    """
    Real call against the Microsoft 365 Copilot Chat API (Preview) via
    modules/copilot_client.py. Unlike the other four providers, this needs
    an access token obtained through an interactive OAuth sign-in (done in
    app.py's sidebar ☰ menu, not here) rather than a pasted API
    key -- `config["access_token"]` must already be populated by the time
    this is called.

    The Chat API has no separate "system message" parameter, so it's folded
    into the message text. It also ignores max_tokens/temperature (the API
    doesn't expose either) -- those two call_ai() parameters are accepted
    upstream for interface uniformity but have no effect on this provider.
    """
    from modules.copilot_client import chat_once, CopilotAPIError

    access_token = config.get("access_token")
    if not access_token:
        raise AIConfigError(
            "Microsoft 365 Copilot is selected but you haven't signed in yet — "
            "use the 'Sign in with Microsoft' button in the sidebar's ☰ menu."
        )

    full_prompt = f"{system_message.strip()}\n\n{prompt}" if system_message else prompt
    # The Copilot Chat API reports no token usage, so the call is logged
    # with unknown (NULL) counts -- the admin rollup still sees it happened.
    _record_usage("Microsoft 365 Copilot", "", None, None)
    try:
        # Same transient-error retry as the other four providers (see
        # _call_with_retry) -- applied here too, not just inside
        # _call_with_resilience, so a rate limit/server hiccup partway
        # through a long analysis doesn't throw away every chunk processed
        # so far no matter which provider is selected.
        return _call_with_retry(chat_once, access_token, full_prompt)
    except CopilotAPIError as exc:
        raise AIConfigError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MAX_TOKENS_RETRY_CEILING = 16000


def _openai_chat_create(client, model, messages, tokens, extra_kwargs):
    """
    Call chat.completions.create, transparently handling the two ways newer
    OpenAI models differ from the classic Chat Completions contract:

    - `max_tokens` is rejected in favour of `max_completion_tokens` (the whole
      o-series and GPT-5 family). We try the classic parameter first (so older
      models and Azure deployments keep working) and only switch on the
      specific error, so we don't second-guess models that are still fine.

    `extra_kwargs` carries `temperature` when it's being sent; the temperature
    fallback in _call_with_resilience is what strips it back out if the model
    rejects that too.
    """
    try:
        return client.chat.completions.create(
            model=model, messages=messages, max_tokens=tokens, **extra_kwargs
        )
    except Exception as exc:
        if _is_max_tokens_unsupported_error(exc):
            return client.chat.completions.create(
                model=model, messages=messages, max_completion_tokens=tokens, **extra_kwargs
            )
        raise


def _is_max_tokens_unsupported_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if "max_completion_tokens" in text:
        return True
    return "max_tokens" in text and (
        "not supported" in text or "unsupported" in text or "unrecognized" in text
        or "instead" in text or "deprecated" in text
    )


MAX_TRANSIENT_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 2.0


def _is_transient_error(exc: Exception) -> bool:
    """True for rate-limit (429), Anthropic's "overloaded" (529), and
    common server-side/network transience (500/502/503/504, timeouts,
    connection resets) -- signals that retrying the exact same request
    after a short wait is likely to succeed, as opposed to a real
    configuration/input problem (bad key, bad model name, malformed
    request) that retrying would just repeat forever. Checked via
    status_code first where the SDK exposes one (openai and anthropic both
    do), falling back to the message text since google.generativeai's
    exception types aren't as consistently shaped."""
    status_code = getattr(exc, "status_code", None)
    if status_code in (429, 500, 502, 503, 504, 529):
        return True
    text = str(exc).lower()
    return any(s in text for s in (
        "429", "rate limit", "rate_limit", "too many requests",
        "529", "overloaded",
        "500", "502", "503", "504", "server_error", "bad gateway", "service unavailable",
        "timeout", "timed out", "connection reset", "connection error", "temporarily unavailable",
    ))


def _call_with_retry(fn, *args, **kwargs):
    """Retries fn(*args, **kwargs) with exponential backoff + jitter on a
    transient error (see _is_transient_error) before giving up. Without
    this, a single 429/529 partway through a long tender analysis (which
    makes one AI call per chunk, up to 17+ for a long brief) used to fail
    the WHOLE analysis outright -- every chunk successfully processed
    before that point thrown away -- even though the exact same request
    almost always succeeds a few seconds later. A non-transient error (bad
    API key, unknown model, malformed request) raises immediately on the
    first attempt instead: retrying those would just waste time repeating
    a failure that isn't going to change."""
    last_exc = None
    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if not _is_transient_error(exc) or attempt == MAX_TRANSIENT_RETRIES:
                raise
            last_exc = exc
            delay = BASE_RETRY_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 1)
            print(
                f"[ai_interface] transient error (attempt {attempt + 1}/{MAX_TRANSIENT_RETRIES + 1}), "
                f"retrying in {delay:.1f}s: {exc}",
                file=sys.stderr,
            )
            time.sleep(delay)
    raise last_exc  # pragma: no cover -- loop above always returns or raises


def _call_with_resilience(create_and_extract_fn, temperature: float, max_tokens: int) -> str:
    """
    Wraps a provider call with three resilience layers that apply across all
    four API-key providers, in order:

    0. Every actual provider call below goes through _call_with_retry(),
       which retries transient failures (rate limits, "overloaded",
       server-side 5xx, timeouts) with exponential backoff before this
       function's own retry layers below ever see the exception -- see that
       function's docstring.

    1. Some newer/reasoning-mode models stop accepting a custom `temperature`
       at all (OpenAI's o-series is the well-known case; other providers have
       shipped models with the same restriction) and the call fails with a
       plain 400 rather than silently ignoring it. If that happens, retry once
       with temperature omitted entirely -- it's a minor quality knob here
       (nudges toward more literal, less creative output), losing it for one
       call is a far smaller problem than the whole step failing outright.

    2. If the model still returns an EMPTY response, retry once more with
       max_tokens doubled (capped at MAX_TOKENS_RETRY_CEILING) before giving
       up. This is the fix for a real failure seen in this app: a
       reasoning/thinking-capable model spent its entire output budget on
       internal reasoning and left nothing for the actual answer -- the call
       "succeeded" with empty text, which used to surface many steps later as
       an opaque "AI did not return valid JSON" error instead of the real
       cause. If a bigger budget still doesn't produce anything, raise a
       clear, actionable error instead of returning "" and letting a
       downstream JSON-parse failure hide what actually went wrong.

    create_and_extract_fn(tokens, **kwargs) must create the request AND pull
    the text out of the provider's response shape (each provider's response
    object is different, so extraction has to happen inside the same
    try/except as the call, not in a caller that only sees a return value).
    """
    def _attempt(tokens: int, include_temperature: bool) -> str:
        kwargs = {"temperature": temperature} if include_temperature else {}
        return _call_with_retry(create_and_extract_fn, tokens, **kwargs)

    def _attempt_with_temperature_fallback(tokens: int) -> str:
        try:
            return _attempt(tokens, include_temperature=True)
        except Exception as exc:
            if _is_temperature_unsupported_error(exc):
                return _attempt(tokens, include_temperature=False)
            raise

    text = _attempt_with_temperature_fallback(max_tokens)
    if text.strip():
        return text

    bigger = min(max_tokens * 2, MAX_TOKENS_RETRY_CEILING)
    if bigger > max_tokens:
        text = _attempt_with_temperature_fallback(bigger)
        if text.strip():
            return text

    raise AIConfigError(
        "The model returned an empty response, even after retrying with a larger output "
        "budget. This is a known failure mode for some newer 'reasoning' models, which can "
        "spend their entire token budget on internal reasoning and leave nothing for the "
        "actual answer. Try a different model in the sidebar's ☰ menu -- the app's "
        "default (claude-sonnet-5) does not have this issue."
    )


def _is_temperature_unsupported_error(exc: Exception) -> bool:
    text = str(exc).lower()
    if "temperature" not in text:
        return False
    if "deprecated" in text or "not supported" in text or "unsupported" in text \
            or "does not support" in text or "unrecognized" in text:
        return True
    # A provider SDK's own method signature rejecting the keyword outright
    # (a plain Python TypeError -- "...() got an unexpected keyword argument
    # 'temperature'") is a different failure shape than the API rejecting an
    # accepted parameter's *value* at runtime, but it calls for the exact same
    # recovery: drop temperature and retry. This is what should have caught the
    # anthropic-sdk-python 1.x break (see _call_anthropic) before that call site
    # was fixed to never send temperature to that provider at all -- kept here
    # as defense-in-depth against the same class of SDK drift in any of the
    # other three providers (OpenAI, Azure OpenAI, Gemini) in the future.
    return isinstance(exc, TypeError) and "unexpected keyword argument" in text


def _build_messages(prompt: str, system_message: str | None) -> list[dict]:
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    return messages


def _try_parse_json(raw: str, repair: bool = False):
    """
    Best-effort parse of a model response into a JSON object/array. Handles, in
    order: clean JSON, JSON wrapped in ``` fences, and JSON preceded/followed by
    prose. When `repair` is True, it will also try to salvage JSON that was cut
    off before it finished (truncated) -- that's a last resort, off by default,
    because a repaired object can be missing fields, so we'd rather retry with a
    bigger budget and get a complete one. Returns the parsed value, or None.
    """
    if not raw:
        return None
    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if the model added them anyway.
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # 1. Straight parse.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Find the first JSON value in the text and decode just that, ignoring
    #    any trailing prose. raw_decode stops at the end of the first complete
    #    value, which also tolerates commentary AFTER the JSON.
    start = _first_json_start(text)
    if start is None:
        return None
    candidate = text[start:]
    try:
        value, _ = json.JSONDecoder().raw_decode(candidate)
        return value
    except json.JSONDecodeError:
        pass

    # 3. Only if explicitly asked: the value looks truncated (started fine,
    #    never closed). Try to repair it by closing open strings/brackets.
    if repair:
        return _recover_truncated_json(candidate)
    return None


def _first_json_start(text: str) -> int | None:
    positions = [p for p in (text.find("{"), text.find("[")) if p != -1]
    return min(positions) if positions else None


def _recover_truncated_json(candidate: str):
    """
    Attempt to salvage a truncated JSON object/array by walking it, closing any
    open string, then closing open brackets in the right order. If the naive
    close fails (truncation landed mid-token), progressively trim back to the
    last structurally safe point and retry. Returns the parsed value or None.
    """
    stack = []
    in_string = False
    escaped = False
    last_safe = None  # index just after a completed top-of-stack element

    for i, ch in enumerate(candidate):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
        elif ch == "," and len(stack) >= 1:
            # A comma at the current depth means everything before it is a
            # complete element -- a safe place to trim to if we need to.
            last_safe = i

    # First try: close the string (if any) and all open brackets as-is.
    attempts = []
    closing = ("" if not in_string else '"') + "".join(reversed(stack))
    attempts.append(candidate + closing)

    # Fallback: trim to the last complete element (drop the partial trailing
    # one) and close from there.
    if last_safe is not None:
        head = candidate[:last_safe]
        # Re-derive what's still open for the trimmed head.
        trimmed_stack = _open_brackets(head)
        if trimmed_stack:
            attempts.append(head + "".join(reversed(trimmed_stack)))

    for attempt in attempts:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    return None


def _open_brackets(text: str) -> list[str]:
    stack = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
    return stack


def _get_config_from_session_state() -> dict | None:
    try:
        import streamlit as st
        return st.session_state.get("ai_config")
    except Exception:
        return None
