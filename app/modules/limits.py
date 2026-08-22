"""
limits.py -- trial vs paid tier limits for CivilProposals: upload counts/
pages, the AI-spend backstop, and the fair-use AI-call rate limit. Single
source of truth so these numbers (and the messages that explain them) don't
drift across the dozen-plus places that enforce them.

## Cost basis (see the "FIX BRIEF ... trial upload limits + AI spend
backstop" this module implements)

Estimated from the app's real call patterns (12k-char analysis chunks,
6k-char company-material caps, 60k-char reference cap) at Claude Sonnet
pricing (~$3/MTok in, $15/MTok out, ~700 tokens/page):
  - Brief analysis: ~$0.65-0.80 per 100 pages -- the dominant cost.
  - Each CV: ~$0.03-0.05 -- the only per-FILE cost.
  - Previous proposals / profile / boilerplate: ~$0 marginal (6k-char
    prompt cap; extra files never reach the AI).
  - Reference projects: ~$0.09 per drafting run total (60k cap).
  - Photos / branding: $0 (never sent to AI).
  - Drafting + exec summary + reviews: ~$0.7-1.0 per bid, upload-independent.
  - Typical full trial bid: ~$1.50-2.50; worst case inside these limits
    ~$4.
Implication: the brief-page cap and CV count are the limits that protect
real money; the rest are UX hygiene. TRIAL_AI_SPEND_CEILING_USD (below)
covers ~2 honest bids of tokens, so legitimate trial users never hit it --
which is why the messages below can afford to be generous in tone: the
ceiling, not the per-item counts, is the true protection.
"""
from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Part 1 -- tiered upload limits
# ---------------------------------------------------------------------------

UPLOAD_LIMITS = {
    # key: (trial_limit, paid_limit)
    "tender_files":        (3, 10),    # brief + addenda file count
    "tender_pages":        (100, 300), # combined analysed pages (hard for trial; paid warns at 200 as today)
    "cv_library":          (5, 25),
    "previous_proposals":  (2, 10),
    "project_references":  (5, 25),
    "company_profile":     (2, 5),
    "boilerplate_content": (2, 5),
    "project_photos":      (10, 30),   # no AI cost -- size guard only
    "branding_images":     (10, 30),
}

# Human label for each key's items -- used to build the "we've used the
# first N of these" messages below without repeating labels at every call site.
UPLOAD_LABELS = {
    "tender_files": "brief/addendum file(s)",
    "tender_pages": "page(s)",
    "cv_library": "CV(s)",
    "previous_proposals": "previous proposal file(s)",
    "project_references": "project reference file(s)",
    "company_profile": "company profile file(s)",
    "boilerplate_content": "boilerplate content file(s)",
    "project_photos": "project photo(s)",
    "branding_images": "branding image(s)",
}

# TODO A2 i18n: PAID_PLAN_UPGRADE_NOTE is a module-level string constant, so it
# can't safely call i18n.t() here (that needs session_state, which isn't live
# at import time). It stays hardcoded English -- to translate it, it would
# need to become a function (e.g. paid_plan_upgrade_note()) called at each use
# site, or be looked up directly at each call site instead of via this shared
# constant. Left as-is; not restructured as part of this pass.
PAID_PLAN_UPGRADE_NOTE = "See pricing on the homepage to upgrade."


def is_paid_tier(access: dict | None) -> bool:
    """True for any account that isn't purely trial-with-nothing-else:
    unlimited, an active/past-due subscription, or holding pay-as-you-go
    bid credits. Kept separate from _access['allowed'] (which only means
    "has some capacity right now") because upload limits and the spend
    ceiling key off the trial/paid SPLIT itself, not momentary capacity --
    a trial account that has already used its one free bid is still
    trial-tier for these purposes, not "blocked" in a way that changes
    which upload limits apply."""
    if not access:
        return False
    return bool(
        access.get("unlimited")
        or access.get("subscribed")
        or access.get("past_due")
        or (access.get("bid_credits") or 0) > 0
    )


def limits_for(user, access: dict | None) -> dict:
    """The active {key: limit} dict for this account -- trial column unless
    subscribed/credits/unlimited (see is_paid_tier). `user` isn't currently
    needed (the tier lives entirely in `access`) but is accepted per the
    brief's own signature, and so a future per-account override has
    somewhere to hook in without changing every call site."""
    paid = is_paid_tier(access)
    return {key: (paid_limit if paid else trial_limit) for key, (trial_limit, paid_limit) in UPLOAD_LIMITS.items()}


def upgrade_clause(key: str, access: dict | None) -> str:
    """' Paid accounts go up to N <label>.' -- empty string for any
    already-paid tier (nothing to upgrade to). Public so callers building
    their own over-limit message (e.g. the company-material uploaders,
    which merge new files with what's already stored rather than fitting
    enforce_count_limit()'s single-batch shape) can reuse the same
    upgrade-path wording as enforce_count_limit() itself."""
    if is_paid_tier(access):
        return ""
    _, paid_limit = UPLOAD_LIMITS[key]
    label = UPLOAD_LABELS.get(key, key)
    from modules import i18n
    return " " + i18n.t("limits_upgrade_clause", paid_limit=paid_limit, label=label)


def enforce_count_limit(items: list, key: str, access: dict | None, item_label_fn=None) -> tuple[list, str | None]:
    """Trim `items` (anything with a usable name, e.g. st.file_uploader
    UploadedFile objects) to this account's active limit for `key`.
    Returns (kept, message): `message` is None when nothing was dropped,
    else a warm, specific explanation of how many were used and what the
    paid tier offers -- files are never silently dropped without saying so.

    Callers must check auth.UNLIMITED_ACCOUNTS / access['unlimited']
    THEMSELVES before calling this (mirroring every other gate in the app)
    -- this function only knows the trial/paid split, not the separate
    real-unlimited-account bypass."""
    limit = limits_for(None, access)[key]
    if len(items) <= limit:
        return items, None
    label = UPLOAD_LABELS.get(key, key)
    kept = items[:limit]
    dropped = items[limit:]
    name_fn = item_label_fn or (lambda f: getattr(f, "name", None) or "unnamed file")
    shown = ", ".join(name_fn(f) for f in dropped[:5])
    if len(dropped) > 5:
        shown += f", and {len(dropped) - 5} more"
    from modules import i18n
    tier = i18n.t("limits_tier_paid") if is_paid_tier(access) else i18n.t("limits_tier_trial")
    msg = (
        i18n.t("limits_count_limit_message", tier=tier, limit=limit, label=label, shown=shown)
        + upgrade_clause(key, access)
    )
    return kept, msg


def tender_page_cap_message(page_count: int, access: dict | None) -> str | None:
    """Trial only: a HARD block once the combined brief+addenda page count
    exceeds the trial cap -- unlike every other limit above, there's no
    sane way to 'process up to the limit' for page count (truncating
    extracted text mid-document would corrupt the analysis), so this
    blocks the Tender Analysis action itself rather than trimming
    anything. Returns None when clear to proceed (including for any paid
    tier -- paid keeps the existing separate 200-page soft warn, unrelated
    to this hard cap)."""
    if is_paid_tier(access):
        return None
    trial_limit, _ = UPLOAD_LIMITS["tender_pages"]
    if page_count <= trial_limit:
        return None
    from modules import i18n
    return (
        i18n.t(
            "limits_tender_page_cap_message",
            page_count=page_count, trial_limit=trial_limit,
            paid_limit=UPLOAD_LIMITS["tender_pages"][1],
        )
        + " " + PAID_PLAN_UPGRADE_NOTE
    )


# ---------------------------------------------------------------------------
# Part 2 -- AI spend backstop
# ---------------------------------------------------------------------------

TRIAL_AI_SPEND_CEILING_USD = 5.00

# A single project's estimated cost above this is unusual enough that it's
# worth a look even for a paying/unlimited account -- printed to stderr
# (visible in Railway's Deploy Logs) ONLY, never shown to the customer, and
# never blocks anything for a non-trial account.
ADMIN_PROJECT_COST_ALERT_USD = 25.00

# TODO A2 i18n: TRIAL_SPEND_CEILING_MESSAGE is a module-level string constant,
# so it can't safely call i18n.t() here (that needs session_state, which isn't
# live at import time). It stays hardcoded English -- ai_spend_block_reason()
# below builds its own translated version at call time instead of returning
# this constant. Left as-is (unused internally now) rather than restructured,
# per this pass's scope; a future pass could turn it into a function or drop it.
TRIAL_SPEND_CEILING_MESSAGE = (
    "Your free trial's AI allowance is used up -- upgrade to keep going; your work is saved. "
    + PAID_PLAN_UPGRADE_NOTE
)


def ai_spend_block_reason(user_id: str | None, access: dict | None, account_ai_cost) -> str | None:
    """None when clear to run an AI feature; the warm ceiling message when
    a trial-tier account has hit/exceeded TRIAL_AI_SPEND_CEILING_USD.
    `account_ai_cost` is passed in (a float, or a zero-arg callable
    returning one) rather than computed here so callers can cache/reuse a
    single db.account_ai_cost() query across many gate points in one
    script run instead of re-querying per button. Never blocks a
    non-trial/unlimited account (see is_paid_tier)."""
    if not user_id or is_paid_tier(access):
        return None
    cost = account_ai_cost() if callable(account_ai_cost) else account_ai_cost
    if (cost or 0.0) >= TRIAL_AI_SPEND_CEILING_USD:
        from modules import i18n
        return i18n.t("limits_trial_spend_ceiling_message") + " " + PAID_PLAN_UPGRADE_NOTE
    return None


def maybe_alert_admin_on_project_cost(project_key: str, project_name: str, project_cost_usd: float) -> None:
    """Non-trial/unlimited accounts are never blocked by spend -- but a
    single project running unusually high (ADMIN_PROJECT_COST_ALERT_USD)
    is worth a server-side line in the logs. Never shown to any customer;
    never raises."""
    try:
        if (project_cost_usd or 0.0) > ADMIN_PROJECT_COST_ALERT_USD:
            import sys
            print(
                f"[ai-cost] project '{project_name}' ({project_key}) is at "
                f"${project_cost_usd:.2f} estimated AI spend -- over the "
                f"${ADMIN_PROJECT_COST_ALERT_USD:.2f} admin-alert threshold.",
                file=sys.stderr,
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Part 3 -- AI-call rate limit (cheap insurance)
#
# Mirrors auth.py's login-attempt throttle exactly: a Redis fixed-window
# counter (same REDIS_URL the job queue and login throttle use) with a
# per-process in-memory fallback when Redis isn't configured or is down.
# Every failure path here degrades to "allow the call" -- a rate limiter
# outage must never block a legitimate user mid-bid.
#
# Counted per NEW top-level AI feature invocation (one button click = one
# call), not per underlying provider request -- a single "Run Tender
# Analysis" on a 100-page trial brief alone makes ~20+ chunked API calls
# (see tender_analyser.analyse_tender), so counting at that granularity
# would trip this "cheap insurance" limit on every ordinary large trial
# brief and contradict the page-cap limit that's supposed to be the real
# per-brief protection. record_ai_call() is called once, right when a
# button's own click-handler begins real work -- see the pages/*.py call
# sites.
# ---------------------------------------------------------------------------

TRIAL_AI_CALLS_PER_5MIN = 20
PAID_AI_CALLS_PER_5MIN = 60
_AI_RATE_WINDOW_SECONDS = 5 * 60

_AI_RATE_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_ai_rate_redis_client = None
# In-memory fallback: {key: (count, window_expiry_ts)}
_ai_rate_local: dict[str, tuple[int, float]] = {}

# TODO A2 i18n: AI_RATE_LIMIT_MESSAGE / AI_RATE_LIMIT_MESSAGE_PAID are
# module-level string constants, so they can't safely call i18n.t() here
# (that needs session_state, which isn't live at import time). They stay
# hardcoded English -- record_ai_call() and ai_rate_limit_peek() below build
# their own translated version at call time instead of returning these
# constants. Left as-is (unused internally now) rather than restructured,
# per this pass's scope; a future pass could turn them into functions or drop
# them.
AI_RATE_LIMIT_MESSAGE = "Give it a few minutes -- the trial has a fair-use speed limit."
AI_RATE_LIMIT_MESSAGE_PAID = "Give it a few minutes -- there's a brief fair-use speed limit."


def _ai_rate_redis():
    global _ai_rate_redis_client
    if not _AI_RATE_REDIS_URL:
        return None
    if _ai_rate_redis_client is None:
        try:
            import redis as _redis
            _ai_rate_redis_client = _redis.Redis.from_url(
                _AI_RATE_REDIS_URL, socket_timeout=2, socket_connect_timeout=2,
            )
        except Exception:
            return None
    return _ai_rate_redis_client


def _ai_rate_key(user_id: str) -> str:
    digest = hashlib.sha256((user_id or "").encode("utf-8")).hexdigest()[:24]
    return f"cp:airate:{digest}"


def record_ai_call(user_id: str | None, is_trial: bool) -> str | None:
    """Registers one new AI-feature invocation for this account and
    returns None if still within the rolling 5-minute cap, or a friendly
    'slow down' message if this call pushed it over. The call that tips
    the account over the cap still counts (same fixed-window shape as
    auth.py's login throttle) -- callers should treat a non-None return as
    'don't start this AI call', not retroactively undo one already
    dispatched. Never raises; degrades to allow (returns None) on any
    Redis/infra failure. `user_id` of None (non-SaaS/local use) always
    returns None without touching any counter."""
    if not user_id:
        return None
    cap = TRIAL_AI_CALLS_PER_5MIN if is_trial else PAID_AI_CALLS_PER_5MIN
    key = _ai_rate_key(user_id)
    now = time.time()
    r = _ai_rate_redis()
    count = None
    if r is not None:
        try:
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.expire(key, _AI_RATE_WINDOW_SECONDS)
            count = int(pipe.execute()[0])
        except Exception:
            count = None
    if count is None:
        prev_count, window_until = _ai_rate_local.get(key, (0, 0.0))
        if window_until < now:
            prev_count = 0
        count = prev_count + 1
        _ai_rate_local[key] = (count, now + _AI_RATE_WINDOW_SECONDS)
        if len(_ai_rate_local) > 5000:
            _ai_rate_local.clear()
    if count > cap:
        from modules import i18n
        return i18n.t("limits_ai_rate_limit_trial") if is_trial else i18n.t("limits_ai_rate_limit_paid")
    return None


def ai_rate_limit_peek(user_id: str | None, is_trial: bool) -> str | None:
    """Read-only version of record_ai_call() -- checks the CURRENT count
    against the cap without incrementing anything. Safe to call on every
    Streamlit rerun (e.g. to disable a button pre-emptively); the actual
    click handler should still call record_ai_call() once it truly starts
    an AI call, since a peek alone never advances the window. Never
    raises; degrades to allow (returns None) on any failure."""
    if not user_id:
        return None
    cap = TRIAL_AI_CALLS_PER_5MIN if is_trial else PAID_AI_CALLS_PER_5MIN
    key = _ai_rate_key(user_id)
    now = time.time()
    r = _ai_rate_redis()
    count = None
    if r is not None:
        try:
            raw = r.get(key)
            count = int(raw) if raw is not None else 0
        except Exception:
            count = None
    if count is None:
        prev_count, window_until = _ai_rate_local.get(key, (0, 0.0))
        count = prev_count if window_until >= now else 0
    if count >= cap:
        from modules import i18n
        return i18n.t("limits_ai_rate_limit_trial") if is_trial else i18n.t("limits_ai_rate_limit_paid")
    return None
