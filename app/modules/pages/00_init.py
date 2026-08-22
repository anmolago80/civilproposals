# modules/pages/00_init.py -- one segment of the CivilProposals app script.
# App configuration, environment, SaaS mode, Stripe checkout redirect handling, login gate, provider help text.
#
# HOW THIS FILE RUNS: app.py executes the files in modules/pages/ in order,
# in ONE shared script namespace (see app.py's loader) -- exactly as when
# all of this was a single 315KB app.py, just split along its natural seams
# so each area of the app lives in its own reviewable file. Code here is
# UNCHANGED from the pre-split app.py; names defined in earlier segments
# (helpers, current_user, _access, the tabs list) are used directly, and
# st.session_state remains the single shared state, same as before.
# Deliberately NOT a function-per-page refactor: that would change scoping
# and evaluation order (the thing a mid-tender regression hides in), and is
# better done tab-by-tab with live click-through testing.
"""
app.py

Tender Response Pack Generator -- Streamlit prototype.

A guided, 10-step workflow: Project Setup -> Upload Documents -> AI Provider
Settings -> Tender Analysis -> Proposal Structure -> Page Allocation ->
Draft Responses -> Graphics & Design -> Fee Estimate -> Export Pack.

Design intent: simple and hard to get lost in. Each tab tells you in one
line what it needs from the previous step, buttons are disabled until their
prerequisites are met, and the sidebar shows a running checklist so you
always know where you are.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# Loads a local .env file (if one exists next to app.py) into the process's
# environment variables -- this is how the AI Provider Settings tab can come
# up already configured on every launch instead of asking you to paste your
# API key in each time (see ANTHROPIC_API_KEY below). A missing .env file, or
# a missing python-dotenv package, is not an error -- both just mean nothing
# gets pre-filled and the tab behaves exactly as before.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
_ENV_ANTHROPIC_KEY = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
_ENV_PATH = Path(__file__).resolve().parent / ".env"


def _save_anthropic_key_to_env(key: str) -> None:
    """Persist the Claude API key to the local .env file next to app.py (creating
    it if it doesn't exist yet) so load_dotenv() above picks it up automatically
    on every future launch -- this is the sidebar "Remember this key" checkbox's
    only effect. Only ever touches the single ANTHROPIC_API_KEY= line; every
    other line in the file (if any) is left exactly as it was."""
    key = (key or "").strip()
    if not key:
        return
    lines = _ENV_PATH.read_text(encoding="utf-8").splitlines() if _ENV_PATH.exists() else []
    new_lines, found = [], False
    for line in lines:
        if line.strip().startswith("ANTHROPIC_API_KEY="):
            new_lines.append(f"ANTHROPIC_API_KEY={key}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"ANTHROPIC_API_KEY={key}")
    _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

from modules import (
    analytics,
    document_processor,
    package_intake,
    returnable_schedules,
    ai_interface,
    tender_analyser,
    weighting_engine,
    page_allocation,
    proposal_structure,
    guidance_generator,
    compliance_matrix,
    gap_analysis,
    draft_generator,
    executive_summary as executive_summary_module,
    team_intro as team_intro_module,
    experience_intro as experience_intro_module,
    pitch_review as pitch_review_module,
    graphics_engine,
    fee_estimation_engine,
    fee_history,
    export_docx,
    export_i18n,
    divider_designer,
    team_bios,
    program_schedule,
    project_store,
    local_project_store,
    cloud_project_store,
    resourcing,
    org_chart,
    org_chart_pptx,
    org_chart_render,
    methodology_pptx,
    methodology_render,
    methodology_stages,
    firm_profile,
    risk_register,
    program_pptx,
    program_render,
    artifact_download_gate,
    proposal_library,
    reference_library,
    reference_projects as reference_projects_module,
    db,
    auth,
    billing,
    branding,
    job_queue,
    limits,
    i18n,
)

AUTOSAVE_INTERVAL_SECONDS = 20

# Throttle for billing.refresh_subscription_status() and
# billing.create_customer_portal_session() -- both make a live Stripe API
# call, and both used to run unconditionally on every single Streamlit
# rerun (which fires on nearly every click/keystroke across the whole app,
# not just billing-related ones). For a subscriber that meant every
# interaction anywhere in the app cost a live network round trip to Stripe
# before the page could even render, and made subscribers -- the paying
# customers -- the ones with the slowest experience. Neither check needs
# to be that fresh: subscription status changes at most a few times a
# month (a payment failing, a billing period rolling over), so re-checking
# every few minutes of active use is still fast enough to show a stale
# status for at most that long, in exchange for cutting the Stripe call
# rate from "every rerun" to "at most once per interval."
SUBSCRIPTION_REFRESH_INTERVAL_SECONDS = 300

_PAGE_ICON_PATH = Path(__file__).resolve().parent / "assets" / "brand" / "logo_mark_32.png"
st.set_page_config(
    # "Beta" used to be in the browser tab title too -- one more repetition
    # of the same disclosure the nav badge (branding.brand_html's
    # show_beta) already makes on every screen, right at the moment
    # someone's paying $120/mo. The nav badge, the pricing section's beta
    # note, and the security FAQ answer are the three places this audit
    # asked to keep; this was one of the ones to cut.
    page_title="CivilProposals",
    page_icon=str(_PAGE_ICON_PATH) if _PAGE_ICON_PATH.exists() else "📐",
    layout="wide",
)

# ---------------------------------------------------------------------------
# SaaS gate: login, trial/subscription access, Stripe checkout redirect.
#
# SAAS_MODE defaults on (this is the hosted civilproposals.com deployment).
# Set SAAS_MODE=false only for the original single-user local prototype
# behaviour (no login, no trial limit, BYO AI key) -- see README_SAAS.md.
# ---------------------------------------------------------------------------
IS_SAAS_MODE = os.environ.get("SAAS_MODE", "true").strip().lower() != "false"

# Used at ~11 gating points across the app when st.session_state.ai_config's
# api_key is empty. In the desktop/BYOK build this correctly points at the
# sidebar's "Anthropic API key" field -- but that field only renders when
# `not IS_SAAS_MODE` (see the `if not IS_SAAS_MODE:` gate in the sidebar
# further down), so telling a SaaS customer to go set it there was pointing
# them at a control they can't see, left over from before this app had a
# SaaS mode at all. In a correctly configured SaaS deploy this branch
# should never actually fire -- ANTHROPIC_API_KEY is set server-side and
# auto-fills ai_config at session start (see _ENV_ANTHROPIC_KEY above) -- so
# if it does fire, the server-side key is missing/misconfigured, which a
# customer can't fix themselves; the message points them at support instead
# of a UI control that doesn't exist for them.
_AI_HINT_CLAUSE = (
    "set an AI provider in the sidebar first" if not IS_SAAS_MODE
    else "try again in a moment -- if it keeps happening, email hello@civilproposals.com"
)
_AI_HINT_SENTENCE = (
    "Configure an AI provider in the sidebar first." if not IS_SAAS_MODE
    else "AI features aren't available right now -- please email hello@civilproposals.com so we can look into it."
)
# Shown at every downstream/auxiliary AI feature gated on
# _current_project_already_paid() (see that function's docstring) instead
# of the account-wide "You're out of bids" message -- "out of bids" would
# often be flat-out wrong here (the account may have plenty of capacity;
# it just hasn't been spent on THIS project yet), and would send someone
# to go buy a bid they don't actually need instead of just running
# analysis.
_PROJECT_NOT_PAID_HINT = "Run Tender Analysis for this project first (that's what uses a bid) -- everything else unlocks once it has."

# A misconfigured SaaS deploy (ANTHROPIC_API_KEY missing/blank in Railway)
# used to boot completely silently -- every AI feature would just be
# disabled for every single customer, with no signal anywhere that
# anything was actually wrong versus working as designed. This fires on
# every rerun for as long as it stays broken, which is the point: it's
# meant to be impossible to miss in the deploy/runtime logs, not a
# one-time startup message that could scroll away before anyone looks.
_MISSING_SERVER_AI_KEY = IS_SAAS_MODE and not _ENV_ANTHROPIC_KEY
if _MISSING_SERVER_AI_KEY:
    print(
        "[STARTUP] SAAS_MODE is on but ANTHROPIC_API_KEY is not set -- every AI "
        "feature in the app is disabled for every customer until this is fixed "
        "in Railway's Variables tab (civilproposals AND civilproposals-worker "
        "services) and both services are redeployed.",
        file=sys.stderr,
    )


def _show_error(action: str, exc: Exception) -> None:
    """Shared by every AI/upload/export failure path in this file (~19
    call sites). Used to be `st.error(f"{{action}}: {{exc}}")` at each one --
    showing a customer the raw exception straight from whatever failed
    (an AI provider's raw API error body, a library's internal message, a
    stack-trace fragment) instead of something they can actually act on.
    Full detail still goes to stderr (visible in Railway's Deploy Logs),
    just not onto a page a paying customer is looking at."""
    print(f"[{action}] {exc}", file=sys.stderr)
    # AIConfigError messages are written FOR the user -- "switch to a model
    # with a larger output budget", "your API key was rejected", "the
    # selected model was cut off". Flattening those into "please try again"
    # threw away the only sentence that told someone what to do, and left
    # them retrying a thing that could not work. Everything else stays
    # generic: a provider's raw API error body or a library's internal
    # message is not something a customer can act on.
    if isinstance(exc, ai_interface.AIConfigError):
        st.error(f"**{action}.** {exc}")
        return
    st.error(f"{action} -- please try again. If it keeps happening, email hello@civilproposals.com and we'll take a look.")

# Design pass: hide Streamlit's default chrome (hamburger menu, "Deploy"
# button, footer) so the app reads as a branded product, then layer on a
# "modern & confident" visual language -- bolder headings, a punchier
# primary button treatment, a cleaner sidebar, and tabs that read as real
# navigation rather than the Streamlit default. Uses data-testid selectors
# where possible since those are more stable across Streamlit versions than
# internal class names. Purely cosmetic -- no effect on functionality.
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header [data-testid="stToolbar"] {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Same typeface as the landing page (landing/index.html), so the
       marketing site and the product read as one consistent brand instead
       of two different fonts stitched together. */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Bolder, tighter headings across the app */
    h1, h2, h3 {
        font-weight: 800 !important;
        letter-spacing: -0.01em;
        color: #0F172A;
    }
    h3 { font-size: 1.3rem !important; }

    /* Sidebar: subtle separation from the main canvas, and fixed -- no
       option to collapse it. Streamlit doesn't expose a config flag for
       this, so it's CSS: hide the collapse arrow inside the sidebar
       (stSidebarCollapseButton) and the "expand" arrow that appears in its
       place if the sidebar is ever collapsed some other way
       (stExpandSidebarButton, e.g. keyboard shortcut) -- so there's no
       control left to collapse it with, and nothing to click back open
       even if it somehow did. */
    [data-testid="stSidebarCollapseButton"], [data-testid="stExpandSidebarButton"] {
        display: none !important;
    }
    /* stSidebarHeader is the ~60px strip that normally holds the collapse
       button and a logo spacer -- with the collapse button hidden above,
       nothing else uses it, and it was leaving a dead gap that pushed the
       menu icon/logo down from the sidebar's top edge. Hiding it lets
       stSidebarUserContent (the menu icon, logo, and step list) sit flush
       at the very top instead. */
    [data-testid="stSidebarHeader"] {
        display: none !important;
    }
    [data-testid="stSidebar"] {
        border-right: 1px solid #E2E8F0;
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2 {
        font-size: 1.05rem !important;
    }

    /* Buttons: bolder weight, confident rounded corners, a real hover lift
       on primary actions so CTAs (Upgrade, Run Analysis, Export) feel
       tappable rather than flat. */
    .stButton button, .stDownloadButton button, .stLinkButton a {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: transform .12s ease, box-shadow .12s ease;
    }
    button[kind="primary"], [data-testid="stBaseButton-primary"] {
        box-shadow: 0 2px 10px rgba(29, 78, 216, 0.25);
    }
    button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(29, 78, 216, 0.32);
    }

    /* Rounder, calmer alert/info/success boxes */
    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    /* Metric-style callouts (used for the trial/plan status) get a touch
       more breathing room */
    [data-testid="stSidebar"] div[data-testid="stAlert"] {
        padding: 0.6rem 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

current_user = None
_access = {
    "allowed": True, "subscribed": True, "past_due": False, "trial_remaining": 999, "trial_limit": 999,
    "bid_credits": 0, "subscription_bids_remaining": 999, "subscription_bid_limit": 3,
}
# Trial upload limits (Part 1) + the AI-spend/rate-limit backstop (Parts
# 2-3) -- see modules/limits.py. Non-SaaS/local use (this default) always
# passes: no tiers, no limits, matching every other _access-based gate.
_account_ai_cost = 0.0
_ai_gate_msg = None

if IS_SAAS_MODE:
    db.init_db()

    # Stripe redirects back here with ?checkout=success&session_id=... after
    # a successful Checkout -- verify with Stripe directly (never trust the
    # query string alone) and activate the subscription. This URL is
    # revisitable (browser history, refresh, back button) and
    # handle_checkout_redirect() is itself idempotent against replays (see
    # db.ProcessedCheckoutSession) -- but a real error verifying with Stripe
    # (network blip, Stripe outage, a DB hiccup) must NEVER be swallowed
    # here: someone who was just charged and hits that error deserves a
    # clear message and a way to recover, not a silently-cleared URL that
    # looks like nothing happened. See DEPLOY.md/support notes -- if this
    # keeps failing for a real paying customer, reconcile manually in Stripe
    # + the admin panel using the session_id shown in the error.
    _qp = st.query_params
    if _qp.get("checkout") == "success" and _qp.get("session_id"):
        _checkout_session_id = _qp.get("session_id")
        _checkout_error = None
        try:
            _checkout_user, _checkout_kind = billing.handle_checkout_redirect(_checkout_session_id)
        except Exception as _exc:
            _checkout_user, _checkout_kind = None, None
            _checkout_error = str(_exc)

        if _checkout_user is not None:
            st.query_params.clear()
            # Round 3, Part 7e: a project pass top-up gets its own specific
            # confirmation (passes_topup_success was defined in the i18n
            # catalogs but never actually shown anywhere) instead of the
            # generic "payment confirmed" toast every other purchase kind
            # still gets -- see billing.handle_checkout_redirect()'s
            # purchase_kind return value.
            if _checkout_kind == "topup":
                st.toast(i18n.t("passes_topup_success"), icon="✅")
            else:
                st.toast(i18n.t("init_payment_confirmed_toast"), icon="✅")
        elif _checkout_error is not None:
            # A genuine verification error, not just "this session wasn't
            # actually paid" -- keep the query params so refreshing the page
            # retries, and tell the customer exactly what to do if it keeps
            # happening instead of leaving them with no signal at all.
            st.error(i18n.t("init_checkout_confirm_failed_error", session_id=_checkout_session_id))
        else:
            # handle_checkout_redirect() returned None without raising --
            # e.g. the Checkout Session genuinely wasn't paid (someone
            # revisiting a cancelled/expired checkout link). Nothing to
            # apply, nothing to warn about -- just drop the query params.
            st.query_params.clear()

    # Stripe's cancel_url (see billing.create_checkout_session /
    # create_bid_checkout_session) -- someone who backed out of Checkout
    # instead of paying. Previously this param was never read at all, so
    # backing out landed the user back on the app with the ?checkout=
    # cancelled param just sitting in the URL bar (surviving refresh/
    # bookmarking) and no acknowledgement that anything happened -- easy to
    # read as "did that... do something?" Nothing to apply here, just a
    # low-key confirmation and clearing the param so it doesn't linger.
    elif _qp.get("checkout") == "cancelled":
        st.query_params.clear()
        st.toast(i18n.t("init_checkout_cancelled_toast"), icon="ℹ️")

    # Password-reset link (see auth.request_password_reset /
    # render_password_reset_screen) -- checked BEFORE require_login()
    # deliberately: someone resetting a forgotten password is, by
    # definition, not logged in and can't get past that gate normally.
    # render_password_reset_screen() always st.stop()s, so it fully
    # replaces the rest of this script run when a reset_token is present.
    if _qp.get("reset_token"):
        auth.render_password_reset_screen(_qp.get("reset_token"))

    current_user = auth.require_login()  # renders login/signup and st.stop()s if not logged in

    if _MISSING_SERVER_AI_KEY:
        # See _MISSING_SERVER_AI_KEY's definition above for the stderr side
        # of this -- that's for Andrew; this is for whoever's actually
        # logged in right now, since "every AI button is just silently
        # disabled" with no on-screen explanation is its own broken
        # experience even once the server-side log exists.
        st.error(i18n.t("init_ai_unavailable_error"))

    # Throttled per SUBSCRIPTION_REFRESH_INTERVAL_SECONDS (see that
    # constant's comment) -- was an unconditional live Stripe call on every
    # single rerun. "_sub_refresh_ts" is keyed to this browser tab's
    # session, not persisted, so a brand new session (fresh login, or the
    # first rerun after a deploy) always refreshes once immediately.
    _now_ts = time.time()
    if _now_ts - st.session_state.get("_sub_refresh_ts", 0.0) >= SUBSCRIPTION_REFRESH_INTERVAL_SECONDS:
        current_user = billing.refresh_subscription_status(current_user)
        st.session_state["_sub_refresh_ts"] = _now_ts
    _access = auth.get_access_status(current_user)

    # Computed once per script run, same pattern as _access itself, so the
    # dozen-plus downstream AI-feature gates (see _current_project_already_
    # paid() and _ai_block_reason() in 10_state_helpers.py) don't each
    # re-query the database / rate-limit store on every rerun. Trial-tier
    # only: is_paid_tier() (unlimited/subscribed/past_due/bid_credits) is
    # never blocked by either check. account_ai_cost() itself degrades to
    # 0.0 on any DB hiccup (see its docstring) -- fails open, never locks a
    # legitimate account out on a transient error.
    _account_ai_cost = (
        db.account_ai_cost(current_user.id)
        if current_user and not limits.is_paid_tier(_access) else 0.0
    )
    _ai_spend_blocked_msg = limits.ai_spend_block_reason(
        current_user.id if current_user else None, _access, _account_ai_cost,
    )
    # Read-only peek (doesn't consume a rate-limit slot) -- the actual
    # per-click "this call counts" recording happens at each AI feature's
    # own click handler via limits.record_ai_call(), not here (this file
    # reruns on every interaction across the whole app, not just AI ones).
    # UNLIMITED_ACCOUNTS bypass the rate gate entirely (Audit Round 2, Part
    # 8) -- ai_rate_limit_peek() only knows trial-vs-paid (it takes a bare
    # is_trial bool, not the access dict), so before this fix an unlimited
    # account was still capped at PAID_AI_CALLS_PER_5MIN like any other paid
    # tier, contradicting the "unlimited bypasses every gate" rule and the
    # comment at 30_setup_upload_analysis.py's Tender Analysis block, which
    # claimed _ai_gate_msg was "already None" for unlimited when it wasn't.
    # Matches the bypass pattern in 10_state_helpers.py's
    # _current_project_already_paid() (`if _access.get("unlimited"): return
    # True`, checked before anything else).
    _ai_rate_blocked_msg = (
        None if _access.get("unlimited") else
        limits.ai_rate_limit_peek(
            current_user.id if current_user else None, not limits.is_paid_tier(_access),
        )
    )
    # Spend ceiling takes priority in the message (worth explaining --
    # "upgrade"); the rate limit is purely transient ("try again shortly").
    _ai_gate_msg = _ai_spend_blocked_msg or _ai_rate_blocked_msg


def _lib_user_id() -> str:
    """User id to scope the Proposal Library / Project Reference Library to.
    'local' is a fixed placeholder used only when SAAS_MODE is off
    (single-user prototype)."""
    return current_user.id if IS_SAAS_MODE and current_user else "local"


def _get_or_create_checkout_url(user, kind: str, topup_project_key: str | None = None) -> str:
    """Returns a live Stripe Checkout URL for kind ("sub" or "bid"), reusing
    one cached in st.session_state for up to SUBSCRIPTION_REFRESH_INTERVAL_
    SECONDS instead of creating a brand new Checkout Session on every single
    call. _render_upgrade_buttons() renders at up to two call sites (the
    top-right popover -- which itself can re-render on essentially any
    click anywhere in the app -- and the Tender Analysis tab's inline
    prompt), so "eagerly, every render" meant up to two live Stripe API
    calls, for both button kinds, on nearly every rerun for every
    non-subscribed user -- exactly the per-keystroke Stripe traffic problem
    that was just fixed for subscribers' status/portal calls elsewhere,
    reintroduced here and worse (uncapped, since anyone can trigger a
    rerun just by using the app). Cached per-kind, not per key_prefix,
    since both render sites want the same underlying session for the same
    user -- no reason to mint two. A Checkout Session's URL keeps working
    for a day even if this cache goes stale sooner, so serving the same one
    for a few minutes is harmless.

    topup_project_key (audit fix Part 1a/8): when given, the "bid" session
    is created WITH that project attached (see
    billing.create_bid_checkout_session's topup_project_key -- this is what
    lets a $50 purchase unlock/top-up the SPECIFIC project the user is
    stuck on, rather than landing as a generic account credit). Cached
    under its own key (a short hash of the project key, not the whole
    string) so a project-specific URL never collides with, or gets served
    in place of, the plain "buy a bid for a new project" URL."""
    _project_suffix = ""
    if topup_project_key:
        _project_suffix = "_" + hashlib.sha256(topup_project_key.strip().lower().encode("utf-8")).hexdigest()[:12]
    cache_key = f"_checkout_url_{kind}{_project_suffix}"
    ts_key = f"_checkout_url_{kind}{_project_suffix}_ts"
    now_ts = time.time()
    cached_url = st.session_state.get(cache_key)
    cached_ts = st.session_state.get(ts_key, 0.0)
    if cached_url and (now_ts - cached_ts) < SUBSCRIPTION_REFRESH_INTERVAL_SECONDS:
        return cached_url
    if kind == "sub":
        url = billing.create_checkout_session(user)
    else:
        url = billing.create_bid_checkout_session(user, topup_project_key=topup_project_key)
    st.session_state[cache_key] = url
    st.session_state[ts_key] = now_ts
    return url


def _render_upgrade_buttons(user, key_prefix: str, already_subscribed: bool = False,
                             topup_project_key: str | None = None) -> None:
    """Ways to keep going once the free trial (or, for an already-subscribed
    account, this billing period's bid quota -- see
    auth.SUBSCRIPTION_MONTHLY_BID_LIMIT) is used up. Reused at several call
    sites (the top-right Upgrade popover, the Tender Analysis tab's inline
    upgrade prompt, and -- when a specific project is stuck, see
    topup_project_key below -- that same tab's blocked-repeat-run prompt)
    so the checkout flows can't drift out of sync. Subscribe: $120/month,
    4 bids per billing period (see billing.create_checkout_session) --
    hidden when already_subscribed, since subscribing again makes no
    sense. Buy 1 bid: $50 one-time.

    topup_project_key (audit fix Part 1a): when the buy-a-bid button is
    being shown BECAUSE a specific project is stuck (its one free trial
    pass already spent, or its paid pass allowance exhausted), pass that
    project's key here so the $50 purchase actually unlocks THAT project
    (see auth.apply_project_bid_topup()) instead of landing as an unrelated
    account-level bid_credit that leaves the stuck project exactly as
    stuck as before. None (the default) is the plain "start a new project"
    purchase, unchanged.

    Each option is a single st.link_button straight to the Stripe Checkout
    URL. This used to be a two-step flow (a plain st.button that, once
    clicked, rendered a SECOND st.link_button below it) -- that had a real
    bug: the link_button only ever existed on the exact script run where the
    first button was clicked, because Streamlit reruns the whole script on
    every interaction. The instant anything else caused a rerun (including
    this same component re-rendering inside the top-right popover, which
    can close and reopen on its own), the "Continue to payment" link
    vanished with no trace and no visible next step -- maximum friction at
    the exact moment someone was trying to pay. A single link_button
    removes that round trip entirely: one click opens Stripe directly. The
    URL itself comes from _get_or_create_checkout_url() above, which caches
    it instead of creating a fresh live Checkout Session on every render."""
    _bid_label = i18n.t("init_buy_bid_unlock_project_button") if topup_project_key else i18n.t("init_buy_bid_button")

    if already_subscribed:
        try:
            bid_url = _get_or_create_checkout_url(user, "bid", topup_project_key=topup_project_key)
            st.link_button(_bid_label, bid_url, key=f"{key_prefix}_bid_btn", type="primary")
        except Exception as exc:
            # debug_key_info() used to be shown here via st.caption() --
            # useful while Andrew was first wiring up Stripe, but it's
            # internal setup diagnostics (masked key/price-ID info), not
            # something a customer hitting a checkout error should ever
            # see. Logged server-side instead; see debug_key_info()'s own
            # docstring if this needs diagnosing again later.
            print(f"[checkout] {exc} | {billing.debug_key_info()}", file=sys.stderr)
            st.error(i18n.t("init_checkout_start_failed_error"))
        return

    ucol1, ucol2 = st.columns(2)
    with ucol1:
        try:
            sub_url = _get_or_create_checkout_url(user, "sub")
            st.link_button(i18n.t("init_subscribe_button"), sub_url, key=f"{key_prefix}_sub_btn", type="primary")
            # Audit fix Part 6: subscription_bid_limit_caption was defined
            # but never rendered anywhere -- the Subscribe button is exactly
            # where a shopper needs to know what the $120/month actually
            # includes before clicking through to Stripe.
            st.caption(i18n.t("subscription_bid_limit_caption", limit=auth.SUBSCRIPTION_MONTHLY_BID_LIMIT))
        except Exception as exc:
            print(f"[checkout] {exc} | {billing.debug_key_info()}", file=sys.stderr)
            st.error(i18n.t("init_checkout_start_failed_error"))
    with ucol2:
        try:
            bid_url = _get_or_create_checkout_url(user, "bid", topup_project_key=topup_project_key)
            st.link_button(_bid_label, bid_url, key=f"{key_prefix}_bid_btn")
        except Exception as exc:
            print(f"[checkout] {exc} | {billing.debug_key_info()}", file=sys.stderr)
            st.error(i18n.t("init_checkout_start_failed_error"))


def _extract_plain_text_from_bytes(file_bytes: bytes, filename: str):
    """Same dispatch document_processor.extract_plain_text_from_file() does
    (pdf/docx/txt -> the right extractor, text-only/fast), but for bytes
    already sitting in the database (a Proposal Library / Project Reference
    Library entry) rather than a fresh st.file_uploader object -- there's
    no UploadedFile to hand it, just raw bytes and a filename."""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if extension == "pdf":
            return document_processor.extract_text_from_pdf(file_bytes, filename, include_structure=False)
        elif extension == "docx":
            return document_processor.extract_text_from_docx(file_bytes, filename)
        elif extension == "txt":
            return document_processor.extract_text_from_txt(file_bytes, filename)
        else:
            return document_processor.ExtractedDocument(
                filename=filename, text="", warning=f"Unsupported file type '.{extension}'.",
            )
    except Exception as exc:
        return document_processor.ExtractedDocument(filename=filename, text="", warning=f"Could not read '{filename}': {exc}")

# Also doubles as the Proposal Library's folder taxonomy (see
# modules/proposal_library.py) -- an archived proposal is filed under
# library/<one of these names>/, so this list is a closed taxonomy on
# purpose, not free text.
PROJECT_TYPES = [
    "Structural Engineering",
    "Geotechnical Engineering",
    "Transportation Engineering",
    "Water Resources & Hydraulic Engineering",
    "Environmental Engineering",
    "Construction Engineering & Management",
    "Coastal & Ocean Engineering",
    "Surveying & Geomatics Engineering",
    "Infrastructure & Urban Engineering",
    "Civil Engineering Materials",
    "Earthquake Engineering",
    "Forensic Engineering",
]
PROPOSAL_THEMES = ["Corporate", "Modern", "Government", "Infrastructure", "Minimalist"]

# Which underlying pipeline shape a proposal uses -- content-agnostic either way; the
# difference is purely structural (a small brief still gets scope/team/fees/program the
# same way a large one does, just in a shorter pack with fewer sections).
# See modules/proposal_structure.py's build_proposal_structure() for the branch itself.
# Internal keys ("formal"/"letter") are unchanged -- only the user-facing labels below
# renamed away from "formal"/"letter" wording, which read as jargon.
PROPOSAL_FORMAT_LABELS = {"formal": "Large Scope Proposal Response Pack", "letter": "Small Scope Proposal Response Pack"}
PROPOSAL_FORMAT_KEYS = {v: k for k, v in PROPOSAL_FORMAT_LABELS.items()}

# Where to get an API key for each provider -- shown as an in-app expander in AI Provider
# Settings so nobody has to leave the app to figure this out. Kept in sync with the matching
# "Getting an API key" section in README.md; update both together if a provider's console UI
# changes. Every provider bills the key's own account, not any Claude/Cowork subscription.
PROVIDER_SETUP_STEPS = {
    "OpenAI": """
1. Go to **[platform.openai.com](https://platform.openai.com/)** and sign up or log in.
2. Add a payment method / purchase credits under **Settings → Billing** -- API usage is billed separately from a ChatGPlus subscription and won't work without credits loaded.
3. Go to **[platform.openai.com/api-keys](https://platform.openai.com/api-keys)**.
4. Click **Create new secret key**, name it (e.g. "Tender Response Pack Generator"), and copy it immediately -- it's only shown once.
5. Paste it into the API key field below. The Model field can stay `gpt-4o`, or any other model you have access to.
""",
    "Azure OpenAI": """
1. You need an Azure subscription -- **[azure.microsoft.com](https://azure.microsoft.com/pricing/purchase-options/azure-account)** for a free one if you don't have one. Access to Azure OpenAI can require an approval/onboarding step in some subscriptions.
2. In the **[Azure Portal](https://portal.azure.com/)**: **Create a resource** → search **Azure OpenAI** → **Create**. Fill in subscription, resource group, region, a name, and pricing tier (Standard), then **Review + create**.
3. In **[Microsoft Foundry](https://ai.azure.com/)**: find your resource → **Deployments** → **+ Deploy model** → pick a model (e.g. `gpt-4o`) → give it a **deployment name** → **Deploy**.
4. Back in the Azure Portal, open your resource → **Keys and Endpoint** → copy **Key 1** and the **Endpoint** URL.
5. Paste the key into the API key field, the endpoint into the Azure endpoint URL field, and the **deployment name you chose** (not the underlying model name) into the Model field below -- Azure OpenAI calls use the deployment name, not the model name.
""",
    "Anthropic Claude": """
1. Go to **[platform.claude.com](https://platform.claude.com/)** and sign up or log in.
2. Add a payment method and purchase credits -- API usage is billed separately from any Claude.ai subscription.
3. Go to **[platform.claude.com/settings/keys](https://platform.claude.com/settings/keys)** (Settings → API Keys).
4. Click **Create Key**, name it, and copy it immediately -- it's only shown once.
5. Paste it into the API key field below. The Model field can stay as the current default, or any Claude model you have access to.
""",
    "Google Gemini": """
1. Go to **[aistudio.google.com/apikey](https://aistudio.google.com/apikey)** and sign in with a Google account.
2. Accept the Terms of Service if this is your first time. A default Google Cloud project is created for you automatically (existing Google Cloud users can import an existing project instead).
3. Click **Create API key** and copy it.
4. Paste it into the API key field below. There's a free tier with rate limits; check Google's current pricing page if you need higher throughput.
""",
}

COMPANY_MATERIAL_CATEGORIES = {
    "company_profile": "Company profile",
    "previous_proposals": "Previous proposals",
    "project_references": "Project references",
    "cv_library": "CV library",
    "boilerplate_content": "Boilerplate content",
}


