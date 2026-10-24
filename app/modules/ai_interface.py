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

# Per-call attribution that is NOT part of the user/project context above:
# which feature made the call (purpose), which step of it (step, e.g. the
# tender analysis's "map" vs "reduce") and whether it is a retry (attempt:
# "json_retry" = call_ai_json re-asking after an unparseable answer,
# "empty_retry" = _call_with_resilience re-asking after an empty one).
# Set around one call_ai() by its keyword arguments, read by _record_usage().
_call_overrides: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "ai_call_overrides", default=None
)

# Approximate USD per MILLION tokens (input, output). These are estimates
# for internal cost visibility only -- update them when provider pricing
# changes; an unknown model logs its token counts with cost NULL rather
# than guessing. Last reviewed: 25 Oct 2026.
#
# Anthropic rows are from https://platform.claude.com/docs/en/about-claude/pricing
# (base input / output, no caching or batch discount -- this app uses neither).
# claude-sonnet-5 was carried here at (3.00, 15.00), which overstated every
# Sonnet 5 call by 50%: Anthropic's own bill for 23 Oct UTC was US$1.88, which is
# exactly the York Region tokens (206,431 in / 146,745 out) at (2.00, 10.00);
# the admin panel showed $2.82. claude-opus-4-6 was (15, 75) -- the retired
# Opus 4 / 4.1 price; Opus 4.5 through 5 are (5, 25).
# OpenAI / Google rows are NOT from the providers' own pages (third-party
# trackers only -- re-check against platform.openai.com / ai.google.dev).
MODEL_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic -- Claude 5 family
    "claude-fable-5-1": (10.00, 50.00),
    "claude-fable-5": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),     # prompts up to 100k tokens; see LONG_PROMPT_PRICES
    # Anthropic -- Claude 4.x
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-opus-4-6": (5.00, 25.00),
    "claude-opus-4-5": (5.00, 25.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    # Google (standard rate, prompts up to 200k tokens)
    "gemini-3.1-pro-preview": (2.00, 12.00),
}

# Models whose rate steps up for a long PROMPT: {model: (threshold input
# tokens, (input, output) price once a single call's input exceeds it)}.
# Claude Haiku 5.5 is the only one in the table above.
LONG_PROMPT_PRICES: dict[str, tuple[int, tuple[float, float]]] = {
    "claude-haiku-5-5": (100_000, (0.50, 2.50)),
}


# ---------------------------------------------------------------------------
# Thinking control (Anthropic)
#
# claude-sonnet-5 THINKS BY DEFAULT (adaptive, effort "high"), and thinking
# tokens are billed as output AND counted inside max_tokens. For extraction /
# structured-JSON work that is pure cost: on 23 Oct a York Region run showed 6
# of 7 map calls stopping at exactly their 1,200 cap (notes truncated) and the
# reduce taking 4 attempts (about US$1.00 of the US$1.88 bill was failed
# attempts). Calls that don't need reasoning pass thinking="off".
#
# What "off" means per model (Anthropic's thinking-support table):
#   claude-sonnet-5, claude-opus-5, claude-haiku-5-5 -> {"type": "disabled"}
#   claude-sonnet-5-5                                -> {"type": "between_tools"}
#   always-on models (opus-5-5, fable, mythos) and the 4.x models (off unless
#   asked) -> no parameter is sent.
# ---------------------------------------------------------------------------

THINKING_OFF_PARAM: dict[str, dict] = {
    "claude-sonnet-5": {"type": "disabled"},
    "claude-opus-5": {"type": "disabled"},
    "claude-haiku-5-5": {"type": "disabled"},
    "claude-sonnet-5-5": {"type": "between_tools"},
}

# Models the API has REJECTED a thinking parameter for in this process (a
# 400) -- never sent again, so one bad guess costs one retry, not one per call.
_thinking_param_rejected: set[str] = set()

# The stop_reason of the most recent provider call in this thread/context, so
# callers of call_ai() (which returns only text) can tell a truncated answer
# ("max_tokens") from a finished one.
_last_stop_reason: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "ai_last_stop_reason", default=None
)


def last_stop_reason() -> str | None:
    """stop_reason of the last provider call made in this context (e.g.
    "end_turn", "max_tokens"), or None if unknown."""
    return _last_stop_reason.get()


def thinking_off_param(model: str) -> dict | None:
    """The request parameter that turns thinking off for `model`, or None when
    there is nothing to send (see the table above)."""
    model = _canonical_model_id(model)
    if model in _thinking_param_rejected:
        return None
    return THINKING_OFF_PARAM.get(model)


def _is_thinking_param_error(exc: Exception) -> bool:
    """The API (or an old SDK) refusing the thinking parameter itself."""
    text = str(exc).lower()
    if isinstance(exc, TypeError) and "unexpected keyword argument" in text and "thinking" in text:
        return True
    return getattr(exc, "status_code", None) == 400 and "thinking" in text


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


def _canonical_model_id(model: str) -> str:
    """The pricing-table key for a model id as the API reports it: trimmed,
    lower-cased, and without a trailing date snapshot ("-20261001") so a dated
    id prices the same as its alias."""
    model = (model or "").strip().lower()
    stripped = re.sub(r"-\d{8}$", "", model)
    return stripped if stripped in MODEL_PRICES_PER_MTOK else model


def estimate_cost_usd(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """None when the model has no entry in MODEL_PRICES_PER_MTOK (unknown
    cost is a different fact from zero cost) or when neither token count is
    available."""
    model = _canonical_model_id(model)
    prices = MODEL_PRICES_PER_MTOK.get(model)
    if not prices or (input_tokens is None and output_tokens is None):
        return None
    long_rule = LONG_PROMPT_PRICES.get(model)
    if long_rule and (input_tokens or 0) > long_rule[0]:
        prices = long_rule[1]
    in_price, out_price = prices
    return round(
        (input_tokens or 0) / 1_000_000 * in_price
        + (output_tokens or 0) / 1_000_000 * out_price,
        6,
    )


def _caller_module_purpose() -> str:
    """Last-resort purpose for a call nobody labelled: the module that made it
    ("team_bios", "risk_register" ...), so no AiCallLog row is ever blank."""
    try:
        frame = sys._getframe(1)
        while frame is not None:
            name = frame.f_globals.get("__name__", "")
            if name and name != __name__:
                return name.rsplit(".", 1)[-1] or "unattributed"
            frame = frame.f_back
    except Exception:
        pass
    return "unattributed"


def _thinking_tokens_of(usage) -> int | None:
    """Tokens the model spent thinking, as reported in
    usage.output_tokens_details.thinking_tokens (a SUBSET of output_tokens, so
    already billed and counted there). None when the SDK/model doesn't say."""
    details = getattr(usage, "output_tokens_details", None)
    if details is None and isinstance(usage, dict):
        details = usage.get("output_tokens_details")
    if isinstance(details, dict):
        return _safe_int(details.get("thinking_tokens"))
    return _safe_int(getattr(details, "thinking_tokens", None))


def _record_usage(provider: str, model: str,
                  input_tokens: int | None, output_tokens: int | None,
                  max_tokens: int | None = None, thinking_tokens: int | None = None,
                  stop_reason: str | None = None) -> None:
    """Best-effort write of ONE provider call's usage to db.AiCallLog -- every
    attempt is its own row (a retry is a new call and a new row, with its own
    requested max_tokens). Never raises -- see the section comment above."""
    try:
        from modules import db
        ctx = _usage_context.get() or {}
        over = _call_overrides.get() or {}
        _project_key = ctx.get("project_key", "")
        purpose = over.get("purpose") or ctx.get("purpose", "") or _caller_module_purpose()
        if max_tokens and output_tokens and output_tokens > max_tokens:
            # Should be impossible: max_tokens is a hard cap on thinking + text
            # for one call. If it ever happens the per-call rows in the admin
            # breakdown are the evidence to take to Anthropic.
            print(
                f"[ai_interface] WARNING output_tokens {output_tokens} > requested max_tokens "
                f"{max_tokens} (model={model}, purpose={purpose}, step={over.get('step', '')})",
                file=sys.stderr,
            )
        db.log_ai_call(
            user_id=ctx.get("user_id"),
            project_key=_project_key,
            project_name=ctx.get("project_name", ""),
            purpose=purpose,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
            max_tokens=max_tokens,
            thinking_tokens=thinking_tokens,
            stop_reason=stop_reason,
            step=over.get("step", ""),
            attempt=over.get("attempt", ""),
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
            max_tokens: int = 4000, temperature: float = 0.3,
            purpose: str | None = None, step: str | None = None,
            thinking: str | None = None, _attempt: str | None = None) -> str:
    """
    Send a prompt to whichever AI provider is configured and return the text response.

    `config` shape: {"provider": str, "api_key": str, "model": str, "endpoint": str}
    If `config` is omitted, this tries to read `st.session_state["ai_config"]`.

    `purpose` / `step` label the call in db.AiCallLog (which feature made it,
    and which step of it); every call site should pass a purpose -- a call that
    doesn't is labelled with its calling module's name rather than left blank.

    `thinking="off"` turns the model's thinking off where the model supports
    that (see THINKING_OFF_PARAM) -- for extraction / structured-JSON calls that
    don't need reasoning. None leaves the model's default (thinking stays on for
    claude-sonnet-5).
    """
    prior = _call_overrides.get()
    merged = dict(prior or {})
    if purpose:
        merged["purpose"] = purpose
    if step:
        merged["step"] = step
    if _attempt:
        merged["attempt"] = _attempt
    if thinking:
        merged["thinking"] = thinking
    token = _call_overrides.set(merged or None)
    try:
        return _call_ai_inner(prompt, system_message, config, max_tokens, temperature)
    finally:
        _call_overrides.reset(token)


def _call_ai_inner(prompt, system_message, config, max_tokens, temperature) -> str:
    _last_stop_reason.set(None)      # never report a previous call's stop reason
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


# ---------------------------------------------------------------------------
# Per-project cache of structured-JSON results
#
# A structured feature (reference-project drafting, methodology stages, risk
# register, discipline re-scan, CV names / profile fields, staffing
# suggestions) asked the same question twice -- same prompt, which already
# folds in the brief, the analysis and every input it reads -- gets the saved
# answer instead of a second paid call. It lives in st.session_state and is
# saved with the project (project_store.PLAIN_KEYS), so it survives a reload;
# change any input and the prompt, hence the key, changes: that is the whole
# invalidation rule. Opted into per call with cache=True -- NOT for anything a
# person expects to come out different when they press it again (drafts,
# pitch review, executive summary, fee refresh).
# ---------------------------------------------------------------------------

JSON_CACHE_SESSION_KEY = "ai_json_cache"
JSON_CACHE_MAX_ENTRIES = 60


def _json_cache_store() -> dict | None:
    """The cache dict for this browser session, or None outside a Streamlit
    script run (the RQ worker, scripts): a process-wide dict there would be
    shared between users."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is None:
            return None
        store = st.session_state.get(JSON_CACHE_SESSION_KEY)
        if not isinstance(store, dict):
            store = {}
            st.session_state[JSON_CACHE_SESSION_KEY] = store
        return store
    except Exception:
        return None


def _json_cache_key(prompt: str, system_message: str | None, config: dict | None, purpose: str | None) -> str:
    import hashlib
    cfg = config or {}
    blob = json.dumps([purpose or "", cfg.get("provider", ""), cfg.get("model", ""), system_message or "", prompt],
                      ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _json_cache_put(store: dict, key: str, purpose: str | None, result) -> None:
    from datetime import datetime, timezone
    store[key] = {"purpose": purpose or "", "at": datetime.now(timezone.utc).isoformat(), "result": result}
    if len(store) > JSON_CACHE_MAX_ENTRIES:
        for old_key in sorted(store, key=lambda k: store[k].get("at", ""))[: len(store) - JSON_CACHE_MAX_ENTRIES]:
            del store[old_key]


def _is_truncated(stop_reason: str | None) -> bool:
    return (stop_reason or "") in ("max_tokens", "length")


def call_ai_json(prompt: str, system_message: str | None = None, config: dict | None = None,
                  max_tokens: int = 4000, purpose: str | None = None, step: str | None = None,
                  thinking: str | None = None, cache: bool = False) -> dict:
    """
    Same as call_ai(), but instructs the model to return JSON only and parses
    the result.

    BUDGET: every JSON call starts at JSON_MAX_TOKENS_CEILING (16,000)
    whatever `max_tokens` the caller passed (it is only a floor now) -- unused
    cap is not billed, and starting small was expensive: a reduce that needed
    ~12,000 tokens was attempted at 4,000, 8,000 and 8,000 first, each a full
    paid call that re-sent the whole prompt (about US$1.00 of a US$1.88 York
    Region bill).

    RETRY: at most ONE, and only for a genuine parse failure -- the model
    answered but not with parseable JSON. A reply that stopped at the cap
    ("max_tokens") is not retried: the same budget would truncate again, so it
    goes straight to the truncated-JSON repair below.

    `thinking="off"` -- see call_ai(). `cache=True` -- see the cache section
    above: an identical prompt for this project returns the saved result.

    Raises a clear, actionable AIConfigError if it still can't be read.
    """
    store = _json_cache_store() if cache else None
    cache_key = _json_cache_key(prompt, system_message, config, purpose) if store is not None else None
    if cache_key is not None:
        hit = store.get(cache_key)
        if isinstance(hit, dict) and "result" in hit:
            print(f"[ai_cache] hit purpose={purpose} -- saved result reused, no AI call", file=sys.stderr)
            return hit["result"]

    json_instruction = (
        "\n\nRespond with ONLY valid JSON. No markdown code fences, no commentary "
        "before or after the JSON, no trailing commas."
    )
    budget = max(max_tokens, JSON_MAX_TOKENS_CEILING)

    raw = call_ai(prompt + json_instruction, system_message, config, budget, temperature=0.1,
                  purpose=purpose, step=step, thinking=thinking)
    parsed = _try_parse_json(raw)
    last_raw = raw
    if parsed is None and not _is_truncated(last_stop_reason()):
        # A genuine parse failure (prose, wrong shape): one corrective retry.
        corrective = (
            f"Your previous response could not be parsed as JSON. Here is what you returned:\n\n"
            f"{last_raw[:2000]}\n\n"
            f"Return ONLY a complete, valid JSON object for this request:\n\n{prompt}"
            f"{json_instruction}"
        )
        last_raw = call_ai(corrective, system_message, config, budget, temperature=0.1,
                           purpose=purpose, step=step, thinking=thinking, _attempt="json_retry")
        parsed = _try_parse_json(last_raw)
    if parsed is not None:
        if cache_key is not None:
            _json_cache_put(store, cache_key, purpose, parsed)
        return parsed

    # Still unreadable. Last resort: try to repair the last response (close
    # off a truncated object) rather than failing outright.
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
        "The AI's response could not be read as valid data, even after one retry. This "
        "usually means the selected model was cut off before it "
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
            max_tokens=tokens,
        )
        _finish = getattr(response.choices[0], "finish_reason", None)
        _last_stop_reason.set("max_tokens" if _finish == "length" else _finish)
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
            max_tokens=tokens,
        )
        _finish = getattr(response.choices[0], "finish_reason", None)
        _last_stop_reason.set("max_tokens" if _finish == "length" else _finish)
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
        off = thinking_off_param(model) if (_call_overrides.get() or {}).get("thinking") == "off" else None
        create_kwargs = dict(
            model=model, max_tokens=tokens, system=system_message or "",
            messages=[{"role": "user", "content": prompt}], **kwargs,
        )
        try:
            response = client.messages.create(**create_kwargs, **({"thinking": off} if off else {}))
        except Exception as exc:
            if not off or not _is_thinking_param_error(exc):
                raise
            # The API / SDK doesn't accept our thinking parameter for this
            # model: remember that, and make the call the old way rather than
            # fail a customer's step over a cost optimisation.
            print(f"[ai_interface] thinking parameter rejected for {model} ({exc}); "
                  f"sending without it from now on", file=sys.stderr)
            _thinking_param_rejected.add(_canonical_model_id(model))
            response = client.messages.create(**create_kwargs)
        _last_stop_reason.set(getattr(response, "stop_reason", None))
        usage = getattr(response, "usage", None)
        _record_usage(
            "Anthropic Claude", model,
            _safe_int(getattr(usage, "input_tokens", None)),
            _safe_int(getattr(usage, "output_tokens", None)),
            max_tokens=tokens, thinking_tokens=_thinking_tokens_of(usage),
            stop_reason=getattr(response, "stop_reason", None),
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
            max_tokens=tokens,
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
        prior = _call_overrides.get()
        token = _call_overrides.set({**(prior or {}), "attempt": "empty_retry"})
        try:
            text = _attempt_with_temperature_fallback(bigger)
        finally:
            _call_overrides.reset(token)
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
