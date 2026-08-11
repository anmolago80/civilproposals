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

import os
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
    document_processor,
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
    export_docx,
    divider_designer,
    team_bios,
    program_schedule,
    project_store,
    local_project_store,
    cloud_project_store,
    resourcing,
    org_chart,
    org_chart_pptx,
    methodology_pptx,
    program_pptx,
    proposal_library,
    reference_library,
    reference_projects as reference_projects_module,
    db,
    auth,
    billing,
    branding,
    job_queue,
)

AUTOSAVE_INTERVAL_SECONDS = 20

_PAGE_ICON_PATH = Path(__file__).resolve().parent / "assets" / "brand" / "logo_mark_32.png"
st.set_page_config(
    page_title="CivilProposals (Beta)",
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

if IS_SAAS_MODE:
    db.init_db()

    # Stripe redirects back here with ?checkout=success&session_id=... after
    # a successful Checkout -- verify with Stripe directly (never trust the
    # query string alone) and activate the subscription.
    _qp = st.query_params
    if _qp.get("checkout") == "success" and _qp.get("session_id"):
        try:
            billing.handle_checkout_redirect(_qp.get("session_id"))
        except Exception:
            pass
        st.query_params.clear()

    # Password-reset link (see auth.request_password_reset /
    # render_password_reset_screen) -- checked BEFORE require_login()
    # deliberately: someone resetting a forgotten password is, by
    # definition, not logged in and can't get past that gate normally.
    # render_password_reset_screen() always st.stop()s, so it fully
    # replaces the rest of this script run when a reset_token is present.
    if _qp.get("reset_token"):
        auth.render_password_reset_screen(_qp.get("reset_token"))

    current_user = auth.require_login()  # renders login/signup and st.stop()s if not logged in
    current_user = billing.refresh_subscription_status(current_user)
    _access = auth.get_access_status(current_user)


def _lib_user_id() -> str:
    """User id to scope the Proposal Library / Project Reference Library to.
    'local' is a fixed placeholder used only when SAAS_MODE is off
    (single-user prototype)."""
    return current_user.id if IS_SAAS_MODE and current_user else "local"


def _render_upgrade_buttons(user, key_prefix: str, already_subscribed: bool = False) -> None:
    """Ways to keep going once the free trial (or, for an already-subscribed
    account, this billing period's 3-bid quota -- see
    auth.SUBSCRIPTION_MONTHLY_BID_LIMIT) is used up. Reused at both call
    sites (the top-right Upgrade popover and the Tender Analysis tab's
    inline upgrade prompt) so the checkout flows can't drift out of sync.
    Subscribe: $120/month, 3 bids per billing period (see
    billing.create_checkout_session) -- hidden when already_subscribed,
    since subscribing again makes no sense. Buy 1 bid: $50 one-time, adds a
    single db.User.bid_credits (see billing.create_bid_checkout_session) --
    works on top of either the trial or an active subscription's quota."""
    if already_subscribed:
        if st.button("Buy 1 bid -- $50", key=f"{key_prefix}_bid_btn"):
            try:
                url = billing.create_bid_checkout_session(user)
                st.link_button("Continue to payment →", url, type="primary")
            except Exception as exc:
                st.error(f"Couldn't start checkout: {exc}")
                st.caption(billing.debug_key_info())
        return

    ucol1, ucol2 = st.columns(2)
    with ucol1:
        if st.button("Subscribe -- $120/mo", key=f"{key_prefix}_sub_btn", type="primary"):
            try:
                url = billing.create_checkout_session(user)
                st.link_button("Continue to payment →", url, type="primary")
            except Exception as exc:
                st.error(f"Couldn't start checkout: {exc}")
                st.caption(billing.debug_key_info())
    with ucol2:
        if st.button("Buy 1 bid -- $50", key=f"{key_prefix}_bid_btn"):
            try:
                url = billing.create_bid_checkout_session(user)
                st.link_button("Continue to payment →", url, type="primary")
            except Exception as exc:
                st.error(f"Couldn't start checkout: {exc}")
                st.caption(billing.debug_key_info())


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


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "project_name": "", "client_name": "", "tender_name": "",
        "submission_date_input": "", "bidder_name": "", "proposal_theme": "Corporate",
        "project_type": PROJECT_TYPES[0],
        "tender_extracted": None,
        "company_material_text": {},
        "company_material_files": {},  # {category: {filename: extracted_text}} -- per-file, so a
                                        # re-upload can update/remove individual files (see the
                                        # Upload Documents tab) instead of replacing the whole category.
        "company_uploaded_flags": {},
        "project_photo_bytes": [],
        "branding_bytes": [],
        # Pre-filled from ANTHROPIC_API_KEY in a local .env file, if present (see
        # load_dotenv() at the top of this file) -- so this tab doesn't need to be
        # re-filled in on every launch. Still fully editable/overridable below.
        "ai_config": {
            "provider": "Anthropic Claude",
            "api_key": _ENV_ANTHROPIC_KEY,
            "model": ai_interface.get_default_model("Anthropic Claude") if _ENV_ANTHROPIC_KEY else "",
            "endpoint": "",
        },
        "copilot_client_id": "", "copilot_tenant_id": "",
        "copilot_access_token": "", "copilot_token_cache": "", "copilot_username": "",
        # Whether the sidebar's Claude API key field should persist to the local
        # .env file -- defaults to on if a key was already loaded from .env at
        # startup (i.e. it was remembered before), off otherwise.
        "_remember_claude_key": bool(_ENV_ANTHROPIC_KEY),
        "analysis": None,
        "weighted_criteria": None,
        "allocations": None,
        "sections": None,
        "guidance_notes": None,
        "compliance_items": None,
        "gap_items": None,
        "drafts": None,
        "executive_summary": None,
        "team_intro": None,
        "experience_intro": None,
        "project_differentiator": "",
        "project_sales_pitch": "",
        "pitch_review": None,
        "pitch_questions": None,
        "tender_summary_buffer": None,
        "graphics": None,
        "weighting_chart_png": None,
        "fee_estimates": None,
        "docx_buffer": None,
        "quotes": [],
        "section_divider_config": {},
        "divider_images": {},
        "cover_hero_png": None,
        # Small Scope pack (short, brief-driven response pack) -- one more option within
        # the same pipeline, not a separate app. See PROPOSAL_FORMAT_LABELS above.
        "proposal_format": "formal",
        # Which proposal_format st.session_state.sections was actually built under --
        # see _structure_format_stale(). None until Proposal Structure (tab 4) is
        # generated at least once.
        "_sections_built_format": None,
        # Sign-off details only -- the cover page/footer already carry project, client,
        # and bidder details, so no separate recipient/ref/date/subject fields are needed.
        "letter_sender_name": "", "letter_sender_title": "",
        "letter_sender_phone": "", "letter_sender_email": "",
        "terms_of_engagement_text": "",
        "team_members": [],
        "team_photos": {},
        "team_bio_warnings": [],
        # Resourcing plan + org chart (Team & Resourcing tab). resource_plan is a
        # list of resourcing.ResourceAssignment; org_chart_png is the generated PNG.
        "resource_plan": [],
        "resource_extra_names": [],
        "dismissed_disciplines": [],
        # AI-suggested "include in proposal" verdicts for the Key Personnel pen pics
        # (Team & Resourcing tab) -- {slot: {"recommended": bool, "reason": str}},
        # from resourcing.suggest_proposal_inclusion(). Empty until the "Suggest
        # which personnel to include" button is run; purely advisory -- the actual
        # include/exclude state lives on each ResourceAssignment.include_in_proposal.
        "personnel_inclusion_suggestions": {},
        "cv_library_filenames": [],
        "cv_extracted_names": [],
        "org_chart_png": None,
        "body_font": "Arial",
        # Key-personnel headshots (Team & Resourcing tab), keyed by person_name --
        # same pattern as team_photos. None means "not run yet" is not applicable
        # here (it's always a dict, possibly empty).
        "personnel_photos": {},
        # Reference projects (Upload Documents tab) -- structured Section 2 content
        # drafted/revised from the "Project references" upload; see
        # modules/reference_projects.py. None means the drafting step hasn't run
        # yet (distinct from "ran and found nothing"); reference_project_photos is
        # always a dict, keyed by reference project title.
        "reference_projects": None,
        "reference_project_photos": {},
        "reference_project_warnings": [],
        # First-pass manual discipline fee build-up (Fee tab). List of
        # resourcing.DisciplineFeeLine; always includes Project Management.
        "discipline_fee_lines": [],
        # Disciplines the user explicitly removed from the Fee Estimate table --
        # never re-added by the brief-sync merge (separate from
        # dismissed_disciplines, which is the Team & Resourcing tab's own list).
        "dismissed_fee_disciplines": [],
        # Bump counters folded into the discipline/scope-item fee data_editor
        # widget keys below -- st.data_editor with a fixed key ignores its
        # `data` argument on every rerun after the first (the widget owns its
        # state once created), so merging a newly-extracted discipline or
        # scope item into the underlying session_state list alone is not
        # enough: the editor keeps showing whatever it first rendered,
        # forever, even across a fresh Tender Analysis run. Bumping the
        # version whenever a genuinely new row gets merged in forces a fresh
        # widget instance (which picks up the merged data) without touching
        # the key on every ordinary rerun, which would instead throw away
        # in-progress edits. See the merge blocks on the Fee Estimate tab.
        "_discipline_fee_editor_version": 0,
        "_scope_fee_editor_version": 0,
        "_large_scope_fee_editor_version": 0,
        # Cache for the discipline fee tables' Excel export + pie chart, so a
        # fragment rerun that doesn't change the underlying hours/rates
        # doesn't waste time (or widen the edit-commit race window) redoing
        # that work -- see the discipline fee table fragments below.
        "_disc_fee_cache_sig": None,
        "_disc_fee_cache_xlsx": None,
        "_disc_fee_cache_pie": None,
        "_letter_disc_fee_cache_sig": None,
        "_letter_disc_fee_cache_xlsx": None,
        "_letter_disc_fee_cache_pie": None,
        # Deferred-apply state for the discipline fee tables -- the rebuild
        # (dedup/dismiss logic) and the cache above only run when the user
        # explicitly ticks a "done entering data" box, rather than on every
        # keystroke-commit. See the checkbox handling in the discipline fee
        # table fragments below for why.
        "_disc_fee_apply_tick": False,
        "_disc_fee_apply_tick_seen": False,
        "_disc_fee_last_applied_editor_sig": None,
        "_letter_disc_fee_apply_tick": False,
        "_letter_disc_fee_apply_tick_seen": False,
        "_letter_disc_fee_last_applied_editor_sig": None,
        # Same deferred-apply pattern, extended to the other three fee-editing
        # tables (scope item / deliverable fee build-up, both pack sizes, and
        # the discipline fee % split, both pack sizes).
        "_scope_fee_apply_tick": False,
        "_scope_fee_apply_tick_seen": False,
        "_scope_fee_last_applied_editor_sig": None,
        "_large_scope_fee_apply_tick": False,
        "_large_scope_fee_apply_tick_seen": False,
        "_large_scope_fee_last_applied_editor_sig": None,
        "_pct_fee_apply_tick": False,
        "_pct_fee_apply_tick_seen": False,
        "_pct_fee_last_applied_editor_sig": None,
        "_letter_pct_fee_apply_tick": False,
        "_letter_pct_fee_apply_tick_seen": False,
        "_letter_pct_fee_last_applied_editor_sig": None,
        "scope_item_fees": [],
        "fee_seed_total": 0.0,
        # Manually-entered total project fee for the indicative benchmark split
        # below -- overrides the brief's stated fee cap (if any) so the user can
        # still see a $ split even when the brief never states a ceiling.
        "fee_estimate_manual_total": 0.0,
        # Small Scope pack's own total for its "Discipline fee split (%)" table --
        # separate from fee_estimate_manual_total (Large Scope's own, unrelated
        # override) since this one auto-prepopulates from the discipline fee
        # build-up total the first time it's used (0.0 = "not yet set"), then
        # stays independently editable. See the Fee Estimate tab.
        "letter_fee_total_override": 0.0,
        "program_num_weeks": 6,
        "program_schedule": {},
        "program_week_labels": [],
        # Save/Load Project bookkeeping (sidebar) -- not project content itself.
        "_project_save_bytes": None,
        "_last_loaded_project_name": "",
        "_autosave_enabled": True,
        "_last_autosave_ts": 0.0,
        "_last_autosave_path": "",
        "_last_autosave_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _run_job_or_inline(job_type, func, args=(), kwargs=None, progress=None,
                        queued_text="Queued...", running_text="Working...",
                        inline_extra_kwargs=None):
    """
    Runs func(*args, **kwargs) either in the background job queue (see
    modules/job_queue.py) or inline in this process, and either way blocks
    until it's done and returns func's return value -- every call site
    keeps its existing "click button, wait, see result" behaviour. The only
    thing that changes is WHERE the AI-call/CPU time is actually spent.

    The queue is used only when all of these are true: this is a logged-in
    SaaS user (current_user is set -- local/dev use with SAAS_MODE=false
    has no account to own a job), AND a Redis-backed queue is actually
    configured (job_queue.redis_available()) -- i.e. the worker service
    from DEPLOY.md's "Background jobs" section has been deployed. Otherwise
    this falls back to calling func directly, exactly as every one of these
    call sites always worked before background jobs existed, using
    inline_extra_kwargs for anything that only makes sense in-process (a
    live progress_callback closure can't be pickled across the process
    boundary to a worker, so it's never passed to the queued path).

    Deliberately never a hard dependency on the queue: turning it on is
    just setting REDIS_URL and deploying the worker service, nothing here
    has to change, and this app never breaks just because that hasn't
    happened yet.
    """
    kwargs = kwargs or {}
    use_queue = IS_SAAS_MODE and current_user and job_queue.redis_available()

    if not use_queue:
        return func(*args, **kwargs, **(inline_extra_kwargs or {}))

    job_id = job_queue.enqueue(current_user.id, job_type, func, *args, **kwargs)
    if progress:
        progress.progress(0.05, text=queued_text)

    elapsed = 0.0
    poll_interval = 1.5
    while True:
        status = job_queue.get_status(job_id, current_user.id)
        if status["status"] == "finished":
            return status["result"]
        if status["status"] in ("failed", "not_found"):
            raise RuntimeError(status["error"] or "The background job failed.")
        if progress:
            # Indeterminate-ish: creeps toward 90% over ~3 minutes rather
            # than claiming a precision this polling loop doesn't have --
            # queued jobs have no live per-chunk/per-section count to show
            # (see this function's docstring), just "still working".
            progress.progress(min(0.05 + elapsed / 180.0, 0.9), text=running_text)
        time.sleep(poll_interval)
        elapsed += poll_interval


def _project_info() -> dict:
    return {
        "project_name": st.session_state.project_name,
        "client_name": st.session_state.client_name,
        "tender_name": st.session_state.tender_name,
        "submission_date": st.session_state.submission_date_input,
        "bidder_name": st.session_state.bidder_name,
        "proposal_theme": st.session_state.proposal_theme,
        "project_type": st.session_state.project_type,
    }


def _company_materials_flags() -> dict:
    flags = {f"has_{k}": bool(st.session_state.company_material_text.get(k)) for k in COMPANY_MATERIAL_CATEGORIES}
    flags["has_project_photos"] = bool(st.session_state.project_photo_bytes)
    flags["has_company_image_library"] = bool(st.session_state.branding_bytes)
    return flags


def _rebuild_structure():
    """Re-derive weighting -> pages -> sections -> guidance notes as one consistent chain.
    proposal_format only changes which branch build_proposal_structure() takes at the end --
    weighting and page allocation are always derived the same way from the same brief."""
    analysis = st.session_state.analysis
    weighted = weighting_engine.apply_weighting(analysis)
    allocations = page_allocation.allocate_pages(weighted, analysis)
    sections = proposal_structure.build_proposal_structure(
        analysis, weighted, allocations, proposal_format=st.session_state.proposal_format,
    )
    st.session_state.weighted_criteria = weighted
    st.session_state.allocations = allocations
    st.session_state.sections = sections
    st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(sections)
    # Remember which format these sections were built for -- see
    # _structure_format_stale() below. Without this, switching the Proposal
    # format selector (tab 1) after already generating structure leaves
    # st.session_state.sections holding the OLD format's section titles
    # (e.g. "Executive Summary"/"Relevant Experience" instead of "Project
    # Understanding"/"Methodology and Deliverables"), so _draftable_sections()
    # silently matches nothing -- drafting "succeeds" against an empty list
    # and the user sees "Draft generation complete" with nothing to show for
    # it, no error anywhere.
    st.session_state["_sections_built_format"] = st.session_state.proposal_format


def _reset_downstream_from_brief() -> None:
    """Resets every piece of state derived from the tender brief -- call this
    whenever the brief itself is replaced or cleared (see the Upload Docs
    tab: a fresh upload that changes the file signature, or the "Clear all"
    button). Without this, replacing the brief only reset tender_extracted
    itself, leaving Tender Analysis, Structure, Page Allocation, Draft
    Responses, Graphics & Design, Team & Resourcing, and Fee Estimate all
    still holding the PREVIOUS brief's results -- so the sidebar stepper
    kept showing those steps as done (green) for a brand new project that
    hadn't actually gone through them yet. Deliberately leaves Project
    Setup fields (project/client/tender name, etc.) and firm-level company
    materials (CV library, past proposals, branding) untouched -- neither
    is derived from the brief itself, so there's no reason to clear them
    when the brief changes."""
    downstream_defaults = {
        "analysis": None,
        "weighted_criteria": None,
        "allocations": None,
        "sections": None,
        "guidance_notes": None,
        "compliance_items": None,
        "gap_items": None,
        "drafts": None,
        "executive_summary": None,
        "team_intro": None,
        "experience_intro": None,
        "pitch_review": None,
        "pitch_questions": None,
        "tender_summary_buffer": None,
        "graphics": None,
        "weighting_chart_png": None,
        "fee_estimates": None,
        "docx_buffer": None,
        "divider_images": {},
        "cover_hero_png": None,
        "_sections_built_format": None,
        "resource_plan": [],
        "discipline_fee_lines": [],
        "scope_item_fees": [],
        "org_chart_png": None,
        "reference_projects": None,
        "reference_project_photos": {},
        "reference_project_warnings": [],
        "program_schedule": {},
        "program_week_labels": [],
        "personnel_photos": {},
        "personnel_inclusion_suggestions": {},
        "dismissed_disciplines": [],
        "dismissed_fee_disciplines": [],
        "fee_seed_total": 0.0,
        "fee_estimate_manual_total": 0.0,
        "letter_fee_total_override": 0.0,
    }
    for key, value in downstream_defaults.items():
        st.session_state[key] = value


def _structure_format_stale() -> bool:
    """True when sections exist but were generated under a different Proposal
    format than the one currently selected -- see the comment in
    _rebuild_structure() above for why this matters."""
    return (
        st.session_state.sections is not None
        and st.session_state.get("_sections_built_format") != st.session_state.proposal_format
    )


def _is_letter() -> bool:
    return st.session_state.proposal_format == "letter"


# Small Scope pack sections that are actually free text to be AI-drafted-then-edited, same as
# every section in the Large Scope pack. The other sections (Scope of Work, Project Team, Fees,
# Program) are built from structured data the user supplies directly (scope_items already
# extracted from the brief, CV-drafted team bios, the fee table, the program grid) -- running
# them through the generic AI drafter would just waste calls on content nothing downstream uses.
LETTER_DRAFTABLE_TITLES = {"Project Understanding", "Methodology and Deliverables"}


def _draftable_sections(sections: list) -> list:
    if st.session_state.proposal_format == "letter":
        return [s for s in sections if s.title in LETTER_DRAFTABLE_TITLES]
    return sections


def _project_identifier() -> str:
    """What a local auto-save file / "Recent projects" entry gets named after.
    See local_project_store.project_identifier() -- prefers the descriptive
    project name over the tender/EOI name, which is often left generic."""
    return local_project_store.project_identifier(st.session_state.project_name, st.session_state.tender_name)


def _files_signature(files) -> tuple:
    """A cheap identity for a set of uploaded files (name + size), so we can tell
    when the uploads have actually changed and avoid re-extracting the same files
    on every Streamlit rerun (reruns fire on nearly every interaction, and
    re-parsing large PDFs each time is what makes the app feel frozen)."""
    return tuple((getattr(f, "name", ""), getattr(f, "size", None)) for f in (files or []))


def _render_resource_rows(kind: str, known_names: list) -> None:
    """Render the assign-a-person rows for the Team & Resourcing tab, for either
    the 'management' roles or the 'discipline' leads. Each row lets the user pick
    a known (CV-derived or typed) name or choose '(type a name)' to enter someone
    ad hoc; discipline rows can also be removed. Mutates st.session_state.resource_plan
    in place.

    For 'discipline' rows only, a lead can also carry any number of support
    members underneath it (e.g. "Ryan Swagemakers" added under the "Structural"
    lead, "Mat Williams") -- each with their own free-text title for this
    project (e.g. "Bridge Engineer"), since a support member's title is rarely
    just the discipline name. Support rows always render immediately after
    their lead (see resourcing.normalize_plan_disciplines, which keeps the plan
    grouped that way), indented with an "under <lead>" caption."""
    TYPE_SENTINEL = "— type a name —"
    UNASSIGNED = "(unassigned)"
    options = [UNASSIGNED] + known_names + [TYPE_SENTINEL]
    remove_index = None
    add_support_after = None  # index of the lead row to add a new support row under
    plan = st.session_state.resource_plan
    for i, a in enumerate(plan):
        if a.slot_kind != kind:
            continue
        is_support = kind == "discipline" and not a.is_lead
        cols = st.columns([3, 3, 1, 1]) if kind == "discipline" else st.columns([3, 3, 1])
        with cols[0]:
            if is_support:
                st.caption(f"↳ under {a.slot}")
                a.custom_title = st.text_input(
                    "Title", value=a.custom_title, key=f"res_title_{kind}_{i}",
                    label_visibility="collapsed",
                    placeholder="Their title on this project, e.g. Bridge Engineer",
                )
            else:
                st.markdown(f"**{a.slot}**")
        with cols[1]:
            current = (a.person_name or "").strip()
            if current and current in known_names:
                idx = options.index(current)
            elif current:
                idx = options.index(TYPE_SENTINEL)
            else:
                idx = 0
            choice = st.selectbox(
                "Assigned to", options, index=idx,
                key=f"res_sel_{kind}_{i}", label_visibility="collapsed",
            )
            if choice == TYPE_SENTINEL:
                typed = st.text_input(
                    "Name", value=current if current not in known_names else "",
                    key=f"res_txt_{kind}_{i}", label_visibility="collapsed",
                    placeholder="Type the person's name",
                )
                a.person_name = typed.strip()
                a.from_cv = False
            elif choice == UNASSIGNED:
                a.person_name = ""
                a.from_cv = False
            else:
                a.person_name = choice
                a.from_cv = choice in known_names
        if kind == "discipline":
            with cols[2]:
                if not is_support and st.button(
                    "+ member", key=f"res_addsup_{kind}_{i}", help="Add a team member under this lead",
                 type="primary"):
                    add_support_after = i
            with cols[3]:
                if st.button(
                    "✕", key=f"res_del_{kind}_{i}",
                    help="Remove this discipline (and anyone added under it)" if not is_support else "Remove this team member",
                 type="primary"):
                    remove_index = i
    if add_support_after is not None:
        lead = plan[add_support_after]
        # Insert right after the lead's existing block (the lead plus any
        # support rows already under it), so the plan stays grouped/contiguous
        # for every downstream reader (org chart, Small Scope Project Team,
        # resourcing.discipline_groups/normalize_plan_disciplines).
        insert_at = add_support_after + 1
        while (insert_at < len(plan) and plan[insert_at].slot_kind == "discipline"
               and not plan[insert_at].is_lead and plan[insert_at].slot == lead.slot):
            insert_at += 1
        plan.insert(insert_at, resourcing.ResourceAssignment(slot=lead.slot, slot_kind="discipline", is_lead=False))
        st.rerun()
    if remove_index is not None:
        removed = plan.pop(remove_index)
        if removed.is_lead:
            # Cascade: a removed lead's support rows have nothing left to be
            # nested under, so they go too rather than becoming orphans.
            plan[:] = [x for x in plan if not (x.slot_kind == "discipline" and not x.is_lead and x.slot == removed.slot)]
            # Remember the removal so the brief re-sync doesn't immediately re-add it.
            label = resourcing.canonical_discipline(removed.slot)
            if label and label not in st.session_state.dismissed_disciplines:
                st.session_state.dismissed_disciplines.append(label)
        st.rerun()


# The six "Done entering data -- refresh ..." deferred-apply fee tables (see
# _render_large_discipline_fee_table() and its siblings) each track their own
# "*_last_applied_editor_sig" -- None means "never applied yet, bypass the
# tick requirement on the very next render." That bypass can fire once
# *before* a project is ever loaded (e.g. against the empty/default project
# these tables briefly render against right after account creation, seeded
# with nothing but the always-included "Project Management" line), which
# permanently consumes it with a near-empty baseline. Loading a real project
# afterwards then makes every one of these tables look permanently "pending"
# (mismatched against that stale one-row baseline) even though the user
# hasn't touched anything -- confirmed via a debug probe showing exactly this
# for the large-scope "Indicative fee split by discipline" table. Resetting
# all of them here, alongside the loaded values, gives a freshly (re)loaded
# project a genuine first-load bypass keyed to its own real data.
_FEE_TABLE_APPLY_STATE_PREFIXES = (
    "_disc_fee_", "_letter_disc_fee_",
    "_scope_fee_", "_large_scope_fee_",
    "_pct_fee_", "_letter_pct_fee_",
)


def _apply_loaded_project(loaded_state: dict, source_label: str) -> None:
    """Shared by both the local 'Open' button and the manual zip uploader --
    overwrites every project_store-managed session_state key with the loaded
    values, resets save/export bookkeeping that no longer applies to the
    newly-loaded project, and reruns so every tab reflects it immediately."""
    for k, v in loaded_state.items():
        st.session_state[k] = v
    st.session_state._project_save_bytes = None
    st.session_state.docx_buffer = None
    for prefix in _FEE_TABLE_APPLY_STATE_PREFIXES:
        st.session_state[f"{prefix}last_applied_editor_sig"] = None
        st.session_state[f"{prefix}apply_tick"] = False
        st.session_state[f"{prefix}apply_tick_seen"] = False
    st.success(f"Loaded project from {source_label}. Re-enter your AI provider settings in the sidebar to continue.")
    st.rerun()


def _maybe_autosave() -> None:
    """Called once per script run, after every tab has had a chance to mutate
    session_state. Debounced by AUTOSAVE_INTERVAL_SECONDS rather than saving
    on literally every rerun (Streamlit reruns on most widget interactions,
    including every single data_editor cell edit in the Fees & Program tab --
    writing a multi-MB zip to disk that often would be wasteful and could lag
    the UI). Silently skipped if there's no project name yet, so a blank
    session doesn't create a stray 'untitled_project' file.

    In SAAS_MODE, saves to the database under the logged-in user's account
    (cloud_project_store) instead of the server's local disk -- otherwise
    every user's in-progress work (uploaded briefs, drafts, team CVs) exists
    ONLY in that one browser tab's live session, and is lost outright on any
    page refresh, dropped connection, or redeploy, with no way to recover it
    (see the "My projects" sidebar section, which reads from the same
    table). local_project_store is kept for the non-SaaS local prototype."""
    if not st.session_state._autosave_enabled:
        return
    project_id = _project_identifier()
    if not project_id:
        return
    now = time.time()
    if now - st.session_state._last_autosave_ts < AUTOSAVE_INTERVAL_SECONDS:
        return
    try:
        if IS_SAAS_MODE and current_user:
            slug = cloud_project_store.save_cloud(current_user.id, st.session_state, project_id)
            st.session_state._last_autosave_ts = now
            st.session_state._last_autosave_path = slug
            st.session_state._last_autosave_error = ""
        else:
            path = local_project_store.save_local(st.session_state, project_id)
            st.session_state._last_autosave_ts = now
            st.session_state._last_autosave_path = path
            st.session_state._last_autosave_error = ""
    except Exception as exc:
        # Auto-save is a convenience, not a step the user is waiting on -- a failure here
        # (e.g. disk full, folder permissions, a transient DB hiccup) shouldn't interrupt
        # whatever they were doing, so this still doesn't raise/stop the script. But it
        # used to swallow the error completely (bare `except: pass`), which is exactly
        # how a real problem -- like the DATABASE_URL misconfiguration found and fixed
        # earlier -- could silently fail every single save with the user having no way
        # to know, only discovering it later when a project they thought was saved
        # wasn't there. Recording it here lets the "My projects" section surface a
        # visible warning instead (see the sidebar code that reads
        # _last_autosave_error), and _last_autosave_ts is deliberately NOT updated on
        # failure, so the very next rerun retries immediately rather than waiting out
        # the normal debounce interval.
        st.session_state._last_autosave_error = str(exc) or exc.__class__.__name__


def _ensure_divider_config(sections) -> None:
    """Give every current section a sensible default divider design (layout + which
    uploaded photo, if any) the first time it's seen, without clobbering choices the
    user already made. Called each time the Graphics & Design tab renders."""
    photos = st.session_state.project_photo_bytes
    config = st.session_state.section_divider_config
    for i, s in enumerate(sections):
        if s.title not in config:
            layout = "Photo + gradient" if photos else "Solid colour"
            config[s.title] = {
                "layout": layout,
                "photo_index": (i % len(photos)) if photos else None,
                "quote_index": None,
                "photo_caption": "",
            }
        else:
            # Back-fill for configs created before "photo_caption" existed
            # (older saved/autosaved projects) -- never clobber a value
            # that's already there.
            config[s.title].setdefault("photo_caption", "")
    # Drop config for sections that no longer exist (e.g. after a structure rebuild).
    current_titles = {s.title for s in sections}
    for stale in [t for t in config if t not in current_titles]:
        del config[stale]


_init_state()


# ---------------------------------------------------------------------------
# Workflow progress -- computed here (before the sidebar renders) so the
# vertical step list below can use it. Purely a "what's been done so far"
# indicator: Streamlit's st.tabs() never tells the Python side which tab is
# currently being viewed (every tab's content runs on every rerun regardless
# of which one is visually active), so this can't highlight a "current"
# step -- only done vs. not-yet-done.
# ---------------------------------------------------------------------------

_stepper_steps = [
    {"label": "Project Setup", "done": bool(_project_identifier())},
    {"label": "Upload Docs", "done": st.session_state.tender_extracted is not None},
    {"label": "Tender Analysis", "done": st.session_state.analysis is not None},
    {"label": "Structure", "done": st.session_state.sections is not None},
    {"label": "Page Allocation", "done": st.session_state.allocations is not None},
    {"label": "Draft Responses", "done": bool(st.session_state.drafts)},
    {"label": "Graphics & Design", "done": bool(st.session_state.divider_images) or bool(st.session_state.cover_hero_png)},
    {"label": "Team & Resourcing", "done": any(
        # Not a plain truthiness check on purpose: as soon as Tender Analysis
        # runs, the Team & Resourcing tab's own code (which also runs every
        # rerun regardless of which tab is visually open) auto-populates
        # resource_plan with one empty slot per discipline detected in the
        # brief -- before the user has assigned a single real person. Require
        # an actual assigned name so this only lights up once someone's
        # really been staffed.
        (getattr(a, "person_name", "") or "").strip() for a in (st.session_state.resource_plan or [])
    )},
    {"label": "Fee Estimate", "done": (
        # Not a plain truthiness check on purpose: the Fee Estimate tab's own
        # reconcile-on-every-rerun logic (see _reconcile_estimates() further
        # down) always leaves fee_estimates as a non-empty list of zero-value
        # placeholder rows, one per discipline, even with zero user input --
        # and since Streamlit runs every tab's code on every rerun regardless
        # of which tab is visually open, that list is non-empty from the very
        # first page load. Requiring an actual nonzero figure is what
        # distinguishes "the user entered something" from "the tab merely
        # rendered once".
        any((getattr(e, "fee_percentage", 0) or 0) > 0 for e in (st.session_state.fee_estimates or []))
        or any((getattr(l, "fee_amount", 0) or 0) > 0 for l in (st.session_state.discipline_fee_lines or []))
        or any((getattr(f, "fee_amount", 0) or 0) > 0 for f in (st.session_state.scope_item_fees or []))
    )},
    {"label": "Export Pack", "done": bool(st.session_state.docx_buffer)},
]


# ---------------------------------------------------------------------------
# Sidebar -- a clean left rail: top-right Upgrade/Log out actions, brand +
# account status, the step list (the app's real navigation), then project
# file management (My projects, export/import) directly in the flow below --
# nothing hidden behind a menu.
# ---------------------------------------------------------------------------

with st.sidebar:
    # Upgrade/Manage billing and Log out used to live here, pinned to the
    # sidebar's own top corner. Moved to a page-level fixed bar in the top
    # right of the browser window instead (see "_topright_actions" below,
    # rendered in the main content area right before the tabs) -- the user
    # asked for these to be static in the window's top right, not just the
    # top of the (left-hand) sidebar column.
    st.markdown(branding.brand_html(logo_size=30, wordmark_size="1.05rem", show_beta=IS_SAAS_MODE,
                                     href="https://civilproposals.com"),
                unsafe_allow_html=True)

    if IS_SAAS_MODE and current_user:
        st.caption(f"Signed in as **{current_user.email}**")
        if _access.get("unlimited"):
            # UNLIMITED_ACCOUNTS (see auth.get_access_status) -- never
            # blocked, never shown a trial/upgrade banner at all.
            st.success("Unlimited access")
        elif _access["past_due"]:
            st.warning("Payment past due -- update your card to keep access.")
        elif _access["subscribed"]:
            # Active subscription -- capped at SUBSCRIPTION_MONTHLY_BID_LIMIT
            # (3) bids per real Stripe billing period, not fully unlimited
            # (see auth.get_access_status); bid_credits still work on top of
            # that quota once it runs out, same as for a non-subscriber.
            if _access["subscription_bids_remaining"] > 0:
                st.success(
                    f"Plan: Active subscription -- {_access['subscription_bids_remaining']} of "
                    f"{_access['subscription_bid_limit']} bid(s) left this cycle"
                )
            elif _access.get("bid_credits", 0) > 0:
                st.info(f"Monthly bids used -- {_access['bid_credits']} pay-as-you-go credit(s) available")
            else:
                st.markdown(
                    '<div style="background:#FFF3E0;color:#B8600A;border:1px solid #F3D9AE;'
                    'border-radius:8px;padding:10px 14px;font-size:.9rem;font-weight:600;">'
                    'Monthly bids used -- buy a bid to keep going, or wait for renewal.</div>',
                    unsafe_allow_html=True,
                )
        elif _access["limit_reached"]:
            st.markdown(
                '<div style="background:#FFF3E0;color:#B8600A;border:1px solid #F3D9AE;'
                'border-radius:8px;padding:10px 14px;font-size:.9rem;font-weight:600;">'
                'Maximum number of free bids reached -- upgrade to keep going.</div>',
                unsafe_allow_html=True,
            )
        elif _access["trial_remaining"] <= 0 and _access.get("bid_credits", 0) > 0:
            # Free trial used up, but they've bought pay-as-you-go bid(s)
            # (see billing.create_bid_checkout_session) -- not the same as
            # limit_reached, so a different, non-alarming message.
            st.info(f"Pay-as-you-go: {_access['bid_credits']} bid credit(s) available")
        else:
            st.info(f"Free trial: {_access['trial_remaining']} of {_access['trial_limit']} bid(s) left")

    # Vertical progress list -- the sidebar's main focus (see
    # branding.vertical_steps_component_html()). It's also the app's real
    # navigation -- the native tab strip is
    # hidden (see the [data-testid="stTabs"] [role="tablist"] rule further
    # down, right before the tabs are created) and these rows take over
    # clicking between sections. Rendered via components.html (a real
    # iframe), not st.markdown -- see the docstring on
    # vertical_steps_component_html() for why that distinction actually
    # matters here (st.markdown() silently drops onclick handlers). Height
    # is sized for the row count plus a little breathing room; it doesn't
    # need to be exact -- a few px of empty space or an internal scrollbar
    # is harmless.
    components.html(
        branding.vertical_steps_component_html(_stepper_steps),
        height=max(1, len(_stepper_steps)) * 44 + 16,
    )
    # Same wording as the signup-time terms and the accept-terms gate
    # (see auth.TERMS_TEXT) -- one copy of this disclaimer, reused
    # everywhere it needs to appear instead of several that could drift.
    st.caption(auth.TERMS_TEXT)
    # "My projects" / "This computer" and "Export / import a file" used to
    # live here, stacked below the steps. Moved into two popovers in the
    # fixed top-right banner instead (see _render_my_projects_popover() and
    # _render_export_import_popover(), called from there) -- the user asked
    # for them up in the banner alongside Upgrade/Log out rather than taking
    # up permanent vertical space in the sidebar.

    if not IS_SAAS_MODE:
        st.divider()
        st.markdown("**Claude API key**")
        _current_claude_key = (
            st.session_state.ai_config.get("api_key", "")
            if st.session_state.ai_config.get("provider") == "Anthropic Claude" else ""
        )
        sidebar_claude_key = st.text_input(
            "Anthropic API key", type="password", key="_sidebar_claude_key",
            value=_current_claude_key,
            help="Same key used everywhere in the app -- this is just a shortcut to the field on the "
                 "AI Provider Settings tab.",
        )
        st.checkbox(
            "Remember this key on this computer", key="_remember_claude_key",
            help="Saves the key to a local .env file next to the app so it's already filled in next "
                 "time you launch it. Left unticked, it's only kept for this session, like before.",
        )
        if sidebar_claude_key:
            prev_model = st.session_state.ai_config.get("model") \
                if st.session_state.ai_config.get("provider") == "Anthropic Claude" else None
            st.session_state.ai_config = {
                "provider": "Anthropic Claude",
                "api_key": sidebar_claude_key,
                "model": prev_model or ai_interface.get_default_model("Anthropic Claude"),
                "endpoint": "",
            }
            if st.session_state._remember_claude_key:
                _save_anthropic_key_to_env(sidebar_claude_key)
                st.caption("Remembered -- this key will be pre-filled automatically next time you open the app.")
        else:
            st.caption("Paste your Anthropic Claude API key here to enable AI-powered steps across the app.")

        with st.expander("Other AI providers (OpenAI, Azure, Gemini, Microsoft 365 Copilot)"):
            st.caption(
                "Only needed if you're not using Anthropic Claude. Picking a provider here replaces "
                "the key above for the rest of this session. Sign-in tokens are never written to disk."
            )
            _other_providers = [p for p in ai_interface.PROVIDERS if p != "Anthropic Claude"]
            _current_other_provider = st.session_state.ai_config.get("provider", "")
            # "Anthropic Claude" is deliberately not one of the choices in THIS dropdown (it has its
            # own field above) -- but that means whenever Claude is the active provider, none of
            # these options match it, so the widget has to default its on-screen selection to
            # _other_providers[0] just to render something. That default must stay purely cosmetic:
            # picking up this section (even collapsed -- Streamlit still executes this code every
            # rerun) must NEVER by itself switch the active provider away from a working Claude
            # config. Only an api_key the user actually typed below (or a completed Copilot
            # sign-in) may overwrite st.session_state.ai_config -- see the two branches below,
            # both gated on real user input, never on this selectbox's mere current value.
            _other_provider_index = (
                _other_providers.index(_current_other_provider) if _current_other_provider in _other_providers else 0
            )
            provider = st.selectbox("AI provider", _other_providers, key="provider_select", index=_other_provider_index)
            # Only pre-fill the fields below from session state when THIS provider is already the
            # active one -- otherwise show blank fields, both so a provider you haven't switched to
            # doesn't silently inherit another provider's secret key into its text box, and so an
            # empty field here can't be mistaken for "this provider is configured".
            _other_provider_is_active = _current_other_provider == provider

            if provider.startswith("Microsoft 365 Copilot"):
                with st.expander("Before you sign in -- one-time setup your organisation's Entra admin needs to do", expanded=not st.session_state.copilot_client_id):
                    st.markdown(
                        "Copilot doesn't take a pasted API key -- it authenticates the signed-in user "
                        "through your organisation's Microsoft Entra ID, and it requests broad delegated "
                        "read access (mail, Teams chats/channels, meeting transcripts, SharePoint sites), "
                        "not just proposal drafting. Someone with Entra admin rights needs to, once:\n\n"
                        "1. Go to **entra.microsoft.com** → App registrations → New registration.\n"
                        "2. Under **Redirect URI**, choose platform **Mobile and desktop applications** "
                        "and add `http://localhost` exactly as written (no port number).\n"
                        "3. Under **API permissions** → Add a permission → Microsoft Graph → **Delegated "
                        "permissions**, add all seven: `Sites.Read.All`, `Mail.Read`, `People.Read.All`, "
                        "`OnlineMeetingTranscript.Read.All`, `Chat.Read`, `ChannelMessage.Read.All`, "
                        "`ExternalItem.Read.All`.\n"
                        "4. Click **Grant admin consent** for your organisation (a tenant admin has to do "
                        "this step -- individual users can't self-consent to these scopes).\n"
                        "5. Copy the **Application (client) ID** and **Directory (tenant) ID** from the "
                        "app's Overview page into the two fields below.\n\n"
                        "Every user who signs in also needs their own Microsoft 365 Copilot add-on licence. "
                        "Sign-in opens your system browser -- it needs a real display, so it won't work "
                        "over a headless/remote connection."
                    )
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Application (client) ID", key="copilot_client_id")
                with col2:
                    st.text_input("Directory (tenant) ID", key="copilot_tenant_id")

                # Access tokens expire in roughly an hour; try a silent refresh from the cached
                # refresh token on every rerun rather than making the user re-click "Sign in"
                # mid-session. Never prompts/opens a browser -- silently does nothing if it can't.
                if st.session_state.copilot_token_cache and st.session_state.copilot_client_id:
                    from modules.copilot_client import get_token_silent
                    refreshed = get_token_silent(
                        st.session_state.copilot_client_id, st.session_state.copilot_tenant_id,
                        st.session_state.copilot_token_cache,
                    )
                    if refreshed:
                        st.session_state.copilot_access_token = refreshed

                sign_in_ready = bool(st.session_state.copilot_client_id and st.session_state.copilot_tenant_id)
                if st.session_state.copilot_access_token:
                    st.success(f"Signed in as {st.session_state.copilot_username}.")
                    if st.button("Sign out", type="primary"):
                        st.session_state.copilot_access_token = ""
                        st.session_state.copilot_token_cache = ""
                        st.session_state.copilot_username = ""
                        st.rerun()
                else:
                    if st.button("Sign in with Microsoft", type="primary", disabled=not sign_in_ready):
                        from modules.copilot_client import sign_in_interactive, CopilotAuthError
                        with st.spinner("Opening your browser to sign in and consent..."):
                            try:
                                result = sign_in_interactive(st.session_state.copilot_client_id, st.session_state.copilot_tenant_id)
                                st.session_state.copilot_access_token = result["access_token"]
                                st.session_state.copilot_token_cache = result["cache"]
                                st.session_state.copilot_username = result["username"]
                                st.success(f"Signed in as {result['username']}.")
                            except CopilotAuthError as exc:
                                st.error(str(exc))
                    if not sign_in_ready:
                        st.info("Enter the Application (client) ID and Directory (tenant) ID above to enable sign-in.")

                # Only switch the active provider to Copilot once sign-in has actually completed --
                # never just because this branch happened to render (see the note above the
                # selectbox for why that would otherwise silently clobber a working Claude config).
                if st.session_state.copilot_access_token:
                    st.session_state.ai_config = {
                        "provider": provider, "api_key": "", "model": "", "endpoint": "",
                        "access_token": st.session_state.copilot_access_token,
                    }
                st.warning(
                    "Even once signed in: Microsoft's own docs describe this API as grounded chat, not a "
                    "general completion endpoint -- text-only replies, no guaranteed structured output, "
                    "and prone to timeouts on long requests. This app's Tender Analysis and Draft "
                    "Responses steps send large, strict-JSON-expecting prompts, which is exactly the kind "
                    "of request that API is documented to struggle with. If a step fails or times out, "
                    "switch providers for that step rather than assuming something else is broken."
                )
            else:
                has_key_already = bool(st.session_state.ai_config.get("api_key")) and _other_provider_is_active
                with st.expander(f"How to get an API key from {provider}", expanded=not has_key_already):
                    st.markdown(PROVIDER_SETUP_STEPS.get(provider, "Steps not available for this provider."))

                api_key = st.text_input(
                    "API key", type="password", key="api_key_input",
                    value=st.session_state.ai_config.get("api_key", "") if _other_provider_is_active else "",
                )
                default_model = ai_interface.get_default_model(provider)
                model = st.text_input(
                    "Model" + (" / deployment name" if provider == "Azure OpenAI" else ""),
                    value=(st.session_state.ai_config.get("model") if _other_provider_is_active else "") or default_model,
                    key="model_input",
                )
                endpoint = ""
                if provider == "Azure OpenAI":
                    endpoint = st.text_input(
                        "Azure endpoint URL", key="endpoint_input",
                        value=st.session_state.ai_config.get("endpoint", "") if _other_provider_is_active else "",
                        placeholder="https://your-resource.openai.azure.com",
                    )
                # Only switch the active provider once the user has actually typed a key for THIS
                # provider -- rendering this section (even just by expanding it) must never by
                # itself replace a working Claude (or other provider's) config with an empty one.
                if api_key:
                    st.session_state.ai_config = {"provider": provider, "api_key": api_key, "model": model, "endpoint": endpoint}
                    st.success(f"{provider} configured for this session.")
                elif _other_provider_is_active:
                    st.warning(f"{provider} API key cleared -- enter it again to keep using {provider} this session.")
                else:
                    st.caption(f"Enter an API key above to switch this session to {provider}.")
    # In SAAS_MODE, nothing renders here at all -- AI drafting runs on
    # the account's own server-side ANTHROPIC_API_KEY (see the module
    # docstring at the top of this file), so there's no API key
    # concept to surface to a subscriber. The "never invents..." disclaimer
    # used to live here, at the very bottom of the sidebar -- moved to sit
    # immediately under the step list instead (see above), per the user's
    # request to have it read right alongside the workflow steps rather
    # than below everything else.
# This CSS is deliberately injected here -- after auth.require_login() has
# already returned above, meaning a user is definitely signed in by this
# point -- rather than in the unconditional page-wide <style> block near
# the top of the file. require_login()'s own login/signup screen also uses
# st.tabs() (the "Log in" / "Create account" pair), and both instances
# share the exact same data-testid -- Streamlit has no way to distinguish
# "the main workflow's tabs" from "some other tabs" in CSS. Injecting the
# hide rule only from here means it's never even present in the page while
# the login tabs are what's showing, so it can't accidentally hide those
# too (confirmed the hard way: an earlier version of this rule in the
# global block broke the "Create account" tab). The sidebar's own nav-row
# styling (hover/active) lives inside vertical_steps_component_html()'s
# iframe instead of here -- a components.html iframe can't see this
# page's stylesheet, so that CSS has to travel with the HTML it styles.
st.markdown(
    """
    <style>
    /* The native tab strip is hidden -- navigation now happens entirely
       through the vertical step list in the sidebar (see
       branding.vertical_steps_component_html(), rendered above). The tabs
       themselves are NOT removed from the underlying code: st.tabs()
       still renders every section's content on every rerun exactly as
       before (several tabs rely on that -- e.g. Team & Resourcing
       auto-seeding, Fee Estimate reconciliation -- see the comments on
       _stepper_steps above), so this is a purely visual change: the real
       tab buttons still exist and still work, just hidden, and get
       "clicked" programmatically by the sidebar's JS bridge instead of by
       the user directly. */
    [data-testid="stTabs"] [role="tablist"] {
        display: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def _render_my_projects_popover_body() -> None:
    """Contents of the top banner's "My Proposals" popover -- the same
    autosave-status + recent-projects-open/delete UI that used to sit
    permanently in the sidebar (see the comment left in its place there),
    just now tucked behind a click instead of always taking up vertical
    space. Local-disk vs. DB-backed branch exactly as before. Also hosts
    the "Export / Import" section (see _render_export_import_popover_body)
    at the bottom, folded in here so the top banner only needs one popover
    for project-level actions instead of two."""
    if not IS_SAAS_MODE:
        # Local-disk autosave -- only correct for the original single-user
        # desktop prototype. In SAAS_MODE this is replaced by the DB-backed
        # branch below (see cloud_project_store.py): writing to a
        # 'projects/' folder on the *server's* disk in a hosted,
        # multi-tenant deployment would be shared across every logged-in
        # user's browser sessions (a real data leak, not just a rough edge),
        # and Railway's container disk is wiped on every redeploy regardless.
        st.checkbox(
            "Auto-save as I work", key="_autosave_enabled",
            help=f"Saves to a 'projects' folder next to the app, at most every {AUTOSAVE_INTERVAL_SECONDS}s "
                 "of activity -- only once a project name is entered (Project Setup).",
        )
        if st.session_state._last_autosave_path:
            st.caption(f"Last saved {datetime.fromtimestamp(st.session_state._last_autosave_ts).strftime('%H:%M:%S')}")
        elif not _project_identifier():
            st.caption("Enter a project or tender name (Project Setup) to enable auto-save.")

        local_projects = local_project_store.list_local_projects()
        if local_projects:
            options = [p["display_name"] for p in local_projects]
            chosen = st.selectbox("Recent projects", options, key="_local_project_pick")
            chosen_entry = next(p for p in local_projects if p["display_name"] == chosen)
            lcol1, lcol2 = st.columns(2)
            with lcol1:
                if st.button("Open", key="_open_local_project", type="primary"):
                    try:
                        loaded_state = local_project_store.load_local(chosen_entry["path"])
                        _apply_loaded_project(loaded_state, f"'{chosen_entry['display_name']}'")
                    except project_store.ProjectLoadError as exc:
                        st.error(str(exc))
            with lcol2:
                if st.button("Delete", key="_delete_local_project", type="primary"):
                    local_project_store.delete_local(chosen_entry["path"])
                    st.rerun()
        else:
            st.caption("No local saves yet.")

    elif current_user:
        # DB-backed equivalent of the local-disk branch above, scoped to
        # this user's account (see cloud_project_store.py) -- so uploads,
        # brief analysis, drafts, and team assignments survive a page
        # refresh, a dropped connection, or the app being redeployed,
        # instead of living only in this one browser tab's live session.
        st.checkbox(
            "Auto-save as I work", key="_autosave_enabled",
            help=f"Saves to your account, at most every {AUTOSAVE_INTERVAL_SECONDS}s of activity -- "
                 "only once a project name is entered (Project Setup). Lets you pick back up later, even "
                 "after closing the tab or a refresh.",
        )
        if st.session_state._last_autosave_error:
            st.warning(
                f"Auto-save failed: {st.session_state._last_autosave_error} -- your work in this "
                "tab is NOT saved to your account yet. Use \"Export / Import\" below as a backup, "
                "and let support know if this keeps happening."
            )
        elif st.session_state._last_autosave_path:
            st.caption(f"Last saved {datetime.fromtimestamp(st.session_state._last_autosave_ts).strftime('%H:%M:%S')}")
        elif not _project_identifier():
            st.caption("Enter a project or tender name (Project Setup) to enable auto-save.")

        cloud_projects = cloud_project_store.list_cloud_projects(current_user.id)
        if cloud_projects:
            options = [p["display_name"] for p in cloud_projects]
            chosen = st.selectbox("Recent projects", options, key="_cloud_project_pick")
            chosen_entry = next(p for p in cloud_projects if p["display_name"] == chosen)
            lcol1, lcol2 = st.columns(2)
            with lcol1:
                if st.button("Open", key="_open_cloud_project", type="primary"):
                    try:
                        loaded_state = cloud_project_store.load_cloud(current_user.id, chosen_entry["id"])
                        _apply_loaded_project(loaded_state, f"'{chosen_entry['display_name']}'")
                    except project_store.ProjectLoadError as exc:
                        st.error(str(exc))
            with lcol2:
                if st.button("Delete", key="_delete_cloud_project", type="primary"):
                    cloud_project_store.delete_cloud(current_user.id, chosen_entry["id"])
                    st.rerun()
        else:
            st.caption("No saved projects yet -- one will appear here shortly after you start "
                       "one (auto-save kicks in once you enter a project name on Project Setup).")

    st.divider()
    with st.expander("⇅ Export / Import"):
        _render_export_import_popover_body()


def _render_export_import_popover_body() -> None:
    """Contents of the "Export / Import" section nested inside the "My
    Proposals" popover (see _render_my_projects_popover_body) -- unchanged
    behaviour from when this was its own top-banner popover, just folded
    in one level so the top banner only shows My Proposals / Proposal
    Library / Project Reference Library."""
    st.caption("For sharing a project or keeping a backup outside this computer.")
    loaded_file = st.file_uploader("Load a project file", type=["zip"], key="project_loader")
    if loaded_file is not None and st.session_state._last_loaded_project_name != loaded_file.name:
        try:
            loaded_state = project_store.load_project(loaded_file.getvalue())
            st.session_state._last_loaded_project_name = loaded_file.name
            _apply_loaded_project(loaded_state, f"'{loaded_file.name}'")
        except project_store.ProjectLoadError as exc:
            st.error(str(exc))

    if st.button("Prepare project save file", type="primary"):
        st.session_state._project_save_bytes = project_store.save_project(st.session_state)
    if st.session_state._project_save_bytes:
        save_filename = (st.session_state.tender_name or "untitled_project").replace(" ", "_")
        st.download_button(
            "💾 Download project file", data=st.session_state._project_save_bytes,
            file_name=f"{save_filename}.tenderproj.zip", mime="application/zip",
         type="primary")


def _render_proposal_library_popover_body() -> None:
    """Contents of the top banner's "Proposal Library" popover -- upload,
    browse, and download full proposal packs, organised by discipline.
    Entries land here either automatically (Export Pack tab -> 'Archive to
    Library') or via direct upload (below). Used to live as an
    always-collapsed expander at the bottom of Project Setup; moved up here
    (same popover treatment as "My Proposals" / "Project Reference Library")
    so it's reachable from any tab."""
    with st.expander("⬆️ Upload a proposal to the Library"):
        st.caption(
            "Add a finished proposal (.docx) straight into the Library, filed under "
            "whichever discipline you choose below -- the same place proposals land "
            "automatically via Export Pack -> 'Archive to Library'."
        )
        _lib_up_file = st.file_uploader(
            "Proposal file (.docx)", type=["docx"], key="lib_upload_proposal_file",
        )
        _lib_up_col1, _lib_up_col2 = st.columns(2)
        with _lib_up_col1:
            _lib_up_type = st.selectbox("Discipline", PROJECT_TYPES, key="lib_upload_proposal_type")
        with _lib_up_col2:
            _lib_up_pack = st.selectbox("Pack size", ["Large Scope", "Small Scope"], key="lib_upload_proposal_pack")
        _lib_up_name = st.text_input(
            "Project name (optional -- defaults to the filename)", key="lib_upload_proposal_name",
        )
        if st.button("Add to Library", key="lib_upload_proposal_btn", disabled=_lib_up_file is None, type="primary"):
            try:
                _default_name = _lib_up_file.name.rsplit(".", 1)[0] if _lib_up_file else ""
                proposal_library.archive_proposal(
                    _lib_user_id(),
                    _lib_up_file.getvalue(),
                    project_type=_lib_up_type,
                    pack_type="small_scope" if _lib_up_pack == "Small Scope" else "large_scope",
                    project_name=(_lib_up_name or "").strip() or _default_name,
                )
                st.success(f"Added '{_lib_up_file.name}' to the Proposal Library under {_lib_up_type}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Couldn't upload: {exc}")

    st.divider()
    st.caption(
        "Browse proposals in the Library -- archived from Export Pack, or uploaded "
        "directly above. Download any entry, or add it as reference material to "
        "the project you're currently working on."
    )
    _lib_pack_type = "small_scope" if _is_letter() else "large_scope"
    _lib_pack_label = "Small Scope" if _is_letter() else "Large Scope"
    _lib_type_filter = st.selectbox(
        "Filter by discipline", ["All"] + PROJECT_TYPES, key="lib_setup_type_filter",
    )
    st.caption(
        f"Showing **{_lib_pack_label}** proposals for "
        f"**{'all disciplines' if _lib_type_filter == 'All' else _lib_type_filter}** -- "
        "matches the proposal format currently selected in Project Setup ('Which does "
        "this pursuit need?'). Switch that to see the other pack size's archive instead."
    )
    _lib_entries = proposal_library.list_library(
        _lib_user_id(),
        None if _lib_type_filter == "All" else _lib_type_filter,
        pack_type=_lib_pack_type,
    )
    if not _lib_entries:
        st.caption(
            "Nothing in the Library yet" + ("" if _lib_type_filter == "All" else f" for {_lib_type_filter}")
            + f" ({_lib_pack_label})."
        )
    else:
        for _e in _lib_entries:
            _client_bit = f" | client: {_e['client_name']}" if _e.get("client_name") else ""
            st.markdown(
                f"**{_e.get('project_name') or _e.get('tender_name') or 'Untitled'}** -- "
                f"{_e.get('project_type', '')} | archived {_e.get('archived_at', '')}"
                f"{_client_bit}"
            )
            _lcol1, _lcol2 = st.columns(2)
            _lib_bytes = None
            with _lcol1:
                try:
                    _lib_bytes = proposal_library.read_entry_bytes(_lib_user_id(), _e["path"])
                    st.download_button(
                        "Download", data=_lib_bytes, file_name=_e.get("filename", "proposal.docx"),
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"lib_dl_{_e.get('path')}", width="stretch",
                     type="primary")
                except Exception:
                    st.caption("File unavailable")
            with _lcol2:
                # "Add as reference to project" -- pulls this proposal's text into
                # the CURRENT project's "Previous proposals" company material
                # (Upload Docs), same effect as uploading it there by hand. Used
                # to be its own picker buried in Upload Docs; moved here so it
                # sits right next to the entry it applies to.
                if st.button("Add as reference to project", key=f"lib_addref_{_e.get('path')}", width="stretch", type="primary"):
                    try:
                        _bytes_for_ref = _lib_bytes if _lib_bytes is not None else proposal_library.read_entry_bytes(_lib_user_id(), _e["path"])
                        _doc = document_processor.extract_text_from_docx(_bytes_for_ref, _e.get("filename", "proposal.docx"))
                        if _doc.text:
                            _key = "previous_proposals"
                            _existing = st.session_state.company_material_files.get(_key, {})
                            st.session_state.company_material_files[_key] = document_processor.merge_extracted_material(
                                _existing, {_e.get("filename", "proposal.docx"): _doc.text},
                            )
                            st.session_state.company_material_text[_key] = "\n\n".join(
                                st.session_state.company_material_files[_key].values()
                            )
                            st.success(f"Added '{_e.get('filename')}' as a reference to the current project.")
                            st.rerun()
                        else:
                            st.warning("Couldn't extract any text from that file.")
                    except Exception as exc:
                        st.error(f"Couldn't add as reference: {exc}")
            st.divider()


def _render_project_reference_library_popover_body() -> None:
    """Contents of the top banner's "Project Reference Library" popover --
    a separate library from Proposal Library, for firm reference-project
    writeups/case studies (PDF, DOCX, or TXT) uploaded directly, organised
    by discipline the same way Proposal Library is. Nothing lands here
    automatically -- there's no "generate a reference project" step in the
    app to archive from, so upload is the only way in."""
    with st.expander("⬆️ Upload a reference project"):
        st.caption(
            "Add a firm reference project / case study (PDF, DOCX, or TXT) to the "
            "Library, filed under whichever discipline you choose below."
        )
        _ref_up_file = st.file_uploader(
            "Reference project file", type=["pdf", "docx", "txt"], key="reflib_upload_file",
        )
        _ref_up_type = st.selectbox("Discipline", PROJECT_TYPES, key="reflib_upload_type")
        _ref_up_title = st.text_input(
            "Title (optional -- defaults to the filename)", key="reflib_upload_title",
        )
        if st.button("Add to Reference Library", key="reflib_upload_btn", disabled=_ref_up_file is None, type="primary"):
            try:
                _default_title = _ref_up_file.name.rsplit(".", 1)[0] if _ref_up_file else ""
                reference_library.upload_reference(
                    _lib_user_id(),
                    _ref_up_file.getvalue(),
                    project_type=_ref_up_type,
                    filename=_ref_up_file.name,
                    title=(_ref_up_title or "").strip() or _default_title,
                )
                st.success(f"Added '{_ref_up_file.name}' to the Project Reference Library under {_ref_up_type}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Couldn't upload: {exc}")

    st.divider()
    st.caption(
        "Browse uploaded reference projects. Download any entry, or add it as "
        "reference material to the project you're currently working on."
    )
    _ref_type_filter = st.selectbox(
        "Filter by discipline", ["All"] + PROJECT_TYPES, key="reflib_type_filter",
    )
    _ref_entries = reference_library.list_library(
        _lib_user_id(),
        None if _ref_type_filter == "All" else _ref_type_filter,
    )
    if not _ref_entries:
        st.caption(
            "Nothing in the Reference Library yet"
            + ("" if _ref_type_filter == "All" else f" for {_ref_type_filter}") + "."
        )
    else:
        for _e in _ref_entries:
            st.markdown(
                f"**{_e.get('title') or _e.get('filename') or 'Untitled'}** -- "
                f"{_e.get('project_type', '')} | uploaded {_e.get('uploaded_at', '')}"
            )
            _rcol1, _rcol2 = st.columns(2)
            _ref_bytes = None
            with _rcol1:
                try:
                    _ref_bytes = reference_library.read_entry_bytes(_lib_user_id(), _e["path"])
                    st.download_button(
                        "Download", data=_ref_bytes, file_name=_e.get("filename", "reference_project"),
                        key=f"reflib_dl_{_e.get('path')}", width="stretch",
                     type="primary")
                except Exception:
                    st.caption("File unavailable")
            with _rcol2:
                # "Add to project references" -- pulls this reference project's text
                # into the CURRENT project's "Project references" company material
                # (Upload Docs), same effect as uploading it there by hand.
                if st.button("Add to project references", key=f"reflib_addref_{_e.get('path')}", width="stretch", type="primary"):
                    try:
                        _bytes_for_ref = _ref_bytes if _ref_bytes is not None else reference_library.read_entry_bytes(_lib_user_id(), _e["path"])
                        _doc = _extract_plain_text_from_bytes(_bytes_for_ref, _e.get("filename", "reference_project"))
                        if _doc.text:
                            _key = "project_references"
                            _existing = st.session_state.company_material_files.get(_key, {})
                            st.session_state.company_material_files[_key] = document_processor.merge_extracted_material(
                                _existing, {_e.get("filename", "reference_project"): _doc.text},
                            )
                            st.session_state.company_material_text[_key] = "\n\n".join(
                                st.session_state.company_material_files[_key].values()
                            )
                            st.success(f"Added '{_e.get('filename')}' to the current project's references.")
                            st.rerun()
                        else:
                            st.warning(_doc.warning or "Couldn't extract any text from that file.")
                    except Exception as exc:
                        st.error(f"Couldn't add to project references: {exc}")
            st.divider()


# Top banner -- static in the browser window's top right corner (per the
# user's request), not just the top of the left-hand sidebar column.
# Rendered here in the MAIN content area (not inside `with st.sidebar:`)
# specifically so `position: fixed` anchors to the whole viewport rather
# than the sidebar's own stacking context -- no JS-driven position syncing
# needed this time (unlike the old sidebar version), since a viewport
# corner is a fixed target and doesn't move as content scrolls. A little
# top padding is added to the tab content below so the fixed bar never
# overlaps a tab's own heading.
#
# "My Proposals" (which also folds in "Export / Import" as a nested
# expander -- see _render_my_projects_popover_body), "Proposal Library" and
# "Project Reference Library" live here too now, as three compact popovers
# -- laid out horizontally alongside Upgrade/Log out (a flex row, see the
# CSS below) rather than stacked as separate always-expanded sections down
# the sidebar, which was pushing the banner-worthy actions out of easy
# reach and growing the sidebar's height for content most visits don't
# need. Rendered unconditionally (both SaaS and local-disk mode) so the
# popovers are always available; only Upgrade/Manage billing and Log out
# stay gated to signed-in SaaS accounts.
with st.container(key="_topright_actions"):
    with st.popover("📁 My Proposals", width="content"):
        _render_my_projects_popover_body()
    with st.popover("📁 Proposal Library", width="content"):
        _render_proposal_library_popover_body()
    with st.popover("📁 Project Reference Library", width="content"):
        _render_project_reference_library_popover_body()
    if IS_SAAS_MODE and current_user:
        if _access["subscribed"] or _access["past_due"]:
            # past_due means there's already a real Stripe subscription, just
            # with a failing card -- "Manage" (Stripe's Customer Portal,
            # where they can update payment details) is what actually fixes
            # that. It used to fall into the "Upgrade" branch below instead,
            # which offered to start a SECOND subscription and never
            # surfaced the one place that lets them fix the first one.
            portal_url = billing.create_customer_portal_session(current_user)
            if portal_url:
                st.link_button("Manage", portal_url, type="primary")
        else:
            with st.popover("Upgrade", width="content"):
                _render_upgrade_buttons(current_user, key_prefix="_topright")
        if st.button("Log out", key="_topright_logout_btn"):
            auth.log_out()
            st.rerun()
st.markdown(
    """<style>
    .st-key-_topright_actions {
        /* z-index has to clear Streamlit's own header/toolbar bar
           (data-testid="stHeader"), which sits at z-index: 999990 --
           invisible in this app (see the `header [data-testid="stToolbar"]
           {visibility: hidden}` rule near the top of the file) but still
           present and still stacked above ordinary page content, so
           without this our fixed bar renders UNDER it and never appears. */
        position: fixed !important; top: 0.75rem; right: 1.5rem; z-index: 1000000;
        display: flex !important; flex-direction: row !important; gap: 8px;
        align-items: flex-start;
        justify-content: flex-end;
        /* Streamlit's own emotion-cache classes on this container default
           it to width: 100% (fine in normal flow, but once position:fixed
           takes it out of flow that stretches it across the whole
           viewport, pushing its flex-start-aligned children to the LEFT
           edge instead of the right). Shrink it back to its content so
           "right: 1.5rem" actually reads as "hug the right edge". */
        width: fit-content !important; left: auto !important;
        background: transparent;
    }
    /* Compact the popover trigger + Upgrade/Log out buttons so the row
       stays a single slim horizontal strip instead of growing the banner
       -- smaller padding and font than Streamlit's default button size. */
    .st-key-_topright_actions button {
        padding: 0.25rem 0.7rem !important;
        font-size: 0.82rem !important;
        min-height: 0 !important;
    }
    .st-key-_topright_upgrade_btn button, .st-key-_topright_upgrade_btn a {
        background-color: #2563EB !important; color: #fff !important;
        border-color: #2563EB !important;
    }
    .st-key-_topright_upgrade_btn button:hover, .st-key-_topright_upgrade_btn a:hover {
        background-color: #1D4ED8 !important; border-color: #1D4ED8 !important;
    }
    .st-key-_topright_logout_btn button {
        background-color: #DC2626 !important; color: #fff !important;
        border-color: #DC2626 !important;
    }
    .st-key-_topright_logout_btn button:hover {
        background-color: #B91C1C !important; border-color: #B91C1C !important;
    }
    /* Reserve room up top so the fixed bar never sits over a tab's own
       heading -- applied to the main content block specifically, not
       the sidebar, which keeps its own normal top spacing. */
    [data-testid="stAppViewContainer"] > .main [data-testid="stMainBlockContainer"] {
        padding-top: 3.5rem;
    }
    </style>""",
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "1 · Project Setup", "2 · Upload Documents",
    "3 · Tender Analysis", "4 · Proposal Structure", "5 · Page Allocation",
    "6 · Draft Responses", "7 · Graphics & Design", "8 · Team & Resourcing",
    "9 · Fee Estimate", "10 · Export Pack",
])


# ---------------------------------------------------------------------------
# Tab 1: Project Setup
# ---------------------------------------------------------------------------

with tabs[0]:
    st.subheader("Project Setup")
    st.caption("Basic project details -- used throughout the workflow and on the cover page of the exported pack.")

    st.markdown("**Proposal format**")
    st.caption(
        "The tool is agnostic to what the project actually is -- scope, team, and fees always "
        "come from what you upload, never from the format you pick. This only changes the shape "
        "of the output: a bound Large Scope pack with named sections and page limits, or a "
        "shorter Small Scope pack with the same sections just leaner (typical for a small "
        "brief, or an email-based request from the client)."
    )
    format_label = st.selectbox(
        "Which does this pursuit need?",
        list(PROPOSAL_FORMAT_LABELS.values()),
        index=list(PROPOSAL_FORMAT_LABELS.keys()).index(st.session_state.proposal_format),
        key="proposal_format_select",
    )
    st.session_state.proposal_format = PROPOSAL_FORMAT_KEYS[format_label]

    # Guards against a stale value from an older save/autosave (or the previous
    # project type list) that no longer matches PROJECT_TYPES -- the selectbox
    # below errors if its bound session_state value isn't one of its options.
    if st.session_state.get("project_type") not in PROJECT_TYPES:
        st.session_state.project_type = PROJECT_TYPES[0]

    with st.form("project_setup_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Project name", key="project_name")
            st.text_input("Client name", key="client_name")
            st.text_input("Tender / EOI name", key="tender_name")
            st.text_input("Submission date", key="submission_date_input", placeholder="e.g. 14 July 2026")
        with col2:
            st.text_input("Bidder / company name", key="bidder_name")
            st.selectbox("Project type", PROJECT_TYPES, key="project_type")
            st.selectbox("Proposal theme", PROPOSAL_THEMES, key="proposal_theme")
        submitted = st.form_submit_button("Save project details", type="primary")
        if submitted:
            st.success("Project details saved.")

    if _is_letter():
        st.divider()
        st.markdown("#### Sign-off details")
        st.caption(
            "Who signs this pack off -- shown in the closing \"Regards\" block at the end of "
            "the document. The cover page and footer already carry the project/client/bidder "
            "details entered above, so nothing else is needed here."
        )
        scol1, scol2 = st.columns(2)
        with scol1:
            st.text_input("Sender name", key="letter_sender_name", placeholder="e.g. Jane Smith")
            st.text_input("Sender title", key="letter_sender_title", placeholder="e.g. Project Director")
        with scol2:
            st.text_input("Sender phone", key="letter_sender_phone")
            st.text_input("Sender email", key="letter_sender_email")


# ---------------------------------------------------------------------------
# Tab 2: Upload Documents
# ---------------------------------------------------------------------------

with tabs[1]:
    st.subheader("Upload Documents")
    st.caption("The tender brief is required. Everything else is optional but strongly improves draft quality.")

    st.markdown(
        "**Tender brief (required)** -- PDF, DOCX, or TXT. Sometimes a brief arrives as several "
        "separate documents (e.g. the main RFT plus addenda, schedules, or annexures) -- upload "
        "all of them here and they'll be combined into one brief. If you've already highlighted/"
        "commented on any of them while reading, upload those marked-up copies -- your notes get read too."
    )
    if st.session_state.get("_tender_uploader_version") is None:
        st.session_state._tender_uploader_version = 0
    tender_files = st.file_uploader(
        "Upload the tender document(s)", type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key=f"tender_uploader_{st.session_state._tender_uploader_version}",
    )
    # Only (re)extract when the uploaded files actually change -- not on every rerun.
    if tender_files and _files_signature(tender_files) != st.session_state.get("_tender_files_sig"):
        with st.spinner("Extracting text..." if len(tender_files) == 1 else f"Extracting text from {len(tender_files)} files..."):
            per_file = [document_processor.extract_text_from_file(f) for f in tender_files]
            extracted = document_processor.combine_extracted_documents(per_file)
        st.session_state._tender_files_sig = _files_signature(tender_files)
        if extracted.warning and not extracted.text:
            st.session_state._tender_extract_error = extracted.warning
        else:
            # A genuinely new/changed brief invalidates everything derived
            # from the old one -- see _reset_downstream_from_brief(). Runs
            # before setting the new tender_extracted so the stepper never
            # shows a stale "done" for steps that haven't run against this
            # brief yet.
            _reset_downstream_from_brief()
            st.session_state.tender_extracted = extracted
            st.session_state._tender_extract_error = None

    if st.session_state.get("_tender_extract_error"):
        st.error(st.session_state._tender_extract_error)

    _ext = st.session_state.tender_extracted
    if _ext is not None and _ext.text:
        if _ext.warning:
            st.warning(_ext.warning)
        tcol1, tcol2 = st.columns([8, 1])
        with tcol1:
            st.success(
                f"Tender brief loaded -- {len(_ext.text):,} characters"
                + (f" across {_ext.page_count} pages" if _ext.page_count else "")
                + f". Found {len(_ext.headings)} candidate headings, {len(_ext.tables)} table(s), "
                + f"and {len(_ext.annotations)} existing annotation(s)."
            )
        with tcol2:
            if st.button("Clear all", key="clear_tender", help="Remove the uploaded tender document(s) and start over", type="primary"):
                _reset_downstream_from_brief()
                st.session_state.tender_extracted = None
                st.session_state._tender_extract_error = None
                st.session_state._tender_files_sig = None
                st.session_state._tender_uploader_version += 1
                st.rerun()
        if not tender_files:
            st.caption("↩︎ Retained from your saved project (or an earlier upload). Re-upload only if the brief has changed.")
        if _ext.annotations:
            with st.expander(f"Preview {len(_ext.annotations)} annotation(s) found in the PDF(s)"):
                for a in _ext.annotations[:30]:
                    source = f"{a['source_file']}, " if a.get("source_file") else ""
                    st.markdown(f"- **{source}p.{a['page']}** ({a['type']}): _{a.get('comment') or '(highlight only)'}_ — \"{a.get('highlighted_text','')[:150]}\"")

    st.divider()
    st.markdown("**Optional company material** -- upload as many files as you like per category. Multiple files per category are combined.")

    LEGACY_MATERIAL_KEY = "(previously uploaded files)"

    def _sync_material_text(key: str) -> None:
        """Recompute the combined text blob for a category from its per-file
        store -- call this after any add/remove/clear so every reader of
        company_material_text (draft generation, CV matching, etc.) sees the
        current set without needing to know about the per-file breakdown."""
        files_for_key = st.session_state.company_material_files.get(key, {})
        st.session_state.company_material_text[key] = "\n\n".join(files_for_key.values())

    def _clear_material_category(key: str) -> None:
        """Fully reset one company-material category: drop the per-file store, the
        combined text blob, and (for the CV library) the filename list. Also bumps
        that category's uploader widget version so the file chips shown in the
        uploader itself disappear too, not just the stored-text status line below
        it. This is a clean slate for that category -- used by the per-category
        'Clear all' button."""
        st.session_state.company_material_files[key] = {}
        st.session_state.company_material_text[key] = ""
        if key == "cv_library":
            st.session_state.cv_library_filenames = []
        # Reset the signature too -- otherwise re-uploading the exact same file(s)
        # into the fresh widget below would look unchanged and never re-extract.
        st.session_state[f"_matsig_{key}"] = None
        st.session_state[f"_matuploader_version_{key}"] = st.session_state.get(f"_matuploader_version_{key}", 0) + 1

    for key, label in COMPANY_MATERIAL_CATEGORIES.items():
        if st.session_state.get(f"_matuploader_version_{key}") is None:
            st.session_state[f"_matuploader_version_{key}"] = 0
        files = st.file_uploader(
            label, type=["pdf", "docx", "txt"], accept_multiple_files=True,
            key=f"upload_{key}_{st.session_state[f'_matuploader_version_{key}']}",
            help="Uploading adds/updates these files; anything already stored for this category "
                 "is kept, not replaced. Use 'Clear all' below to wipe the category and start over.",
        )
        sig_key = f"_matsig_{key}"
        if files and _files_signature(files) != st.session_state.get(sig_key):
            with st.spinner(f"Extracting {label}..."):
                updates = {}
                for f in files:
                    doc = document_processor.extract_plain_text_from_file(f)
                    if doc.warning and not doc.text:
                        st.warning(doc.warning)
                    elif doc.text:
                        updates[getattr(f, "name", "")] = doc.text
            existing_files_for_key = st.session_state.company_material_files.get(key, {})
            if not existing_files_for_key:
                # Migration for a project saved before per-file tracking existed: it only has
                # one big combined blob, with no per-file breakdown. Seed that blob in as a
                # single legacy entry BEFORE merging the new upload, so uploading just 1-2
                # files doesn't wipe out everyone else's already-extracted text.
                legacy_text = (st.session_state.company_material_text.get(key) or "").strip()
                if legacy_text:
                    existing_files_for_key = {LEGACY_MATERIAL_KEY: legacy_text}
            st.session_state.company_material_files[key] = document_processor.merge_extracted_material(
                existing_files_for_key, updates,
            )
            _sync_material_text(key)
            if key == "cv_library":
                # Grow the filename-suggestion list with the newly uploaded names (union,
                # not replace); the legacy bookkeeping key is never a real filename.
                st.session_state.cv_library_filenames = list(dict.fromkeys(
                    list(st.session_state.cv_library_filenames or []) + list(updates.keys())
                ))
            st.session_state[sig_key] = _files_signature(files)

        if key == "previous_proposals":
            st.caption(
                "📁 To pull in a proposal you've already archived, use the 'Add as reference to "
                "project' button in the Proposal Library popover (top banner) instead of "
                "re-uploading it here."
            )
        if key == "project_references":
            st.caption(
                "📁 To pull in a firm reference project you've uploaded to the Project Reference "
                "Library, use its 'Add to project references' button in the top banner instead "
                "of re-uploading it here."
            )

        # The uploaded files themselves are shown by Streamlit's own uploader widget above
        # (each with its own x). Here we only show a one-line status of what's stored plus a
        # single 'Clear all' button to wipe the category -- no duplicate filename list.
        stored_files = st.session_state.company_material_files.get(key, {})
        existing = (st.session_state.company_material_text.get(key) or "").strip()
        if existing:
            n_files = len([f for f in stored_files if f != LEGACY_MATERIAL_KEY])
            count_bit = f"{n_files} file(s), " if n_files else ""
            scol1, scol2 = st.columns([8, 1])
            with scol1:
                st.caption(f"✅ {label}: {count_bit}{len(existing):,} characters stored.")
            with scol2:
                if st.button("Clear all", key=f"clear_{key}", help=f"Remove all {label.lower()} and start over", type="primary"):
                    _clear_material_category(key)
                    st.rerun()

    if st.session_state.get("_photo_uploader_version") is None:
        st.session_state._photo_uploader_version = 0
    photo_files = st.file_uploader(
        "Project photos", type=["png", "jpg", "jpeg"], accept_multiple_files=True,
        key=f"upload_photos_{st.session_state._photo_uploader_version}",
    )
    if photo_files and _files_signature(photo_files) != st.session_state.get("_photo_files_sig"):
        st.session_state.project_photo_bytes = [f.getvalue() for f in photo_files]
        st.session_state._photo_files_sig = _files_signature(photo_files)
    if st.session_state.project_photo_bytes:
        retained = " (retained from saved project)" if not photo_files else ""
        pcol1, pcol2 = st.columns([8, 1])
        with pcol1:
            st.caption(f"✅ {len(st.session_state.project_photo_bytes)} project photo(s) loaded -- the first is the cover image{retained}.")
        with pcol2:
            if st.button("Clear all", key="clear_photos", help="Remove all project photos and start over", type="primary"):
                st.session_state.project_photo_bytes = []
                st.session_state._photo_files_sig = None
                st.session_state._photo_uploader_version += 1
                st.rerun()

    if st.session_state.get("_branding_uploader_version") is None:
        st.session_state._branding_uploader_version = 0
    branding_files = st.file_uploader(
        "Company branding / image library", type=["png", "jpg", "jpeg"], accept_multiple_files=True,
        key=f"upload_branding_{st.session_state._branding_uploader_version}",
    )
    if branding_files and _files_signature(branding_files) != st.session_state.get("_branding_files_sig"):
        st.session_state.branding_bytes = [f.getvalue() for f in branding_files]
        st.session_state._branding_files_sig = _files_signature(branding_files)
    if st.session_state.branding_bytes:
        retained = " (retained from saved project)" if not branding_files else ""
        bcol1, bcol2 = st.columns([8, 1])
        with bcol1:
            st.caption(f"✅ {len(st.session_state.branding_bytes)} branding image(s) loaded{retained}.")
        with bcol2:
            if st.button("Clear all", key="clear_branding", help="Remove all branding images and start over", type="primary"):
                st.session_state.branding_bytes = []
                st.session_state._branding_files_sig = None
                st.session_state._branding_uploader_version += 1
                st.rerun()

    st.divider()
    st.markdown("#### Reference projects (Relevant Experience section)")
    st.caption(
        "Draft, then review and edit, the distinct past projects the exported pack will show in "
        "Relevant Experience -- revised for consistent tone and relevance to THIS tender, not the "
        "raw uploaded text pasted in. Add a photo per project if you have one, and confirm which "
        "of your key personnel worked on each -- that feeds the Section 2 x Section 3 "
        "cross-reference table automatically. Best done here, early, so it's ready before Export."
    )
    raw_refs_text = (st.session_state.company_material_text.get("project_references") or "").strip()
    if not raw_refs_text:
        st.info("Upload 'Project references' material above to draft reference projects from it, or add one manually below.")
    elif not st.session_state.reference_projects:
        # Uploading the raw material only extracts its text -- it does NOT
        # automatically turn into reference project entries. That second
        # step (the button right below) is easy to miss, since the upload
        # widget itself shows a reassuring green "X file(s) stored"
        # confirmation that looks like the whole job is done. Called out
        # explicitly here so "I uploaded my references but nothing's
        # happening" has an obvious next step instead of looking broken.
        st.info(
            "Material uploaded and read. Click **Draft reference projects from uploaded material** "
            "below to have the AI turn it into the individual project entries shown further down -- "
            "uploading alone doesn't create them yet."
        )

    refs_ai_ready = bool(st.session_state.ai_config.get("api_key")) and bool(raw_refs_text)
    if st.button("Draft reference projects from uploaded material", disabled=not refs_ai_ready,
                 help=None if refs_ai_ready else "Upload 'Project references' material above and set an AI provider in the sidebar first.", type="primary"):
        with st.spinner("Reading project reference material and drafting revised, relevance-led entries..."):
            try:
                analysis_for_context = st.session_state.analysis
                drafted, warnings = reference_projects_module.draft_reference_projects(
                    raw_refs_text,
                    project_scope=(analysis_for_context.project_scope if analysis_for_context else ""),
                    disciplines=(analysis_for_context.disciplines_involved if analysis_for_context else []),
                    config=st.session_state.ai_config,
                )
                st.session_state.reference_projects = drafted
                st.session_state.reference_project_warnings = warnings
                st.success(f"Drafted {len(drafted)} reference project(s). Review and edit every field below before export.")
                if not analysis_for_context:
                    st.info("Tender Analysis hasn't run yet -- re-run this once it has, so relevance can be tailored to the actual brief.")
            except Exception as exc:
                st.error(f"Reference project drafting failed: {exc}")

    if st.session_state.reference_project_warnings:
        st.warning("\n\n".join(st.session_state.reference_project_warnings))

    if st.session_state.reference_projects is None:
        st.session_state.reference_projects = []

    _known_personnel_names = resourcing.cv_derived_names(
        st.session_state.team_members,
        list(st.session_state.cv_extracted_names)
        + resourcing.names_from_filenames(st.session_state.cv_library_filenames)
        + list(st.session_state.resource_extra_names)
        + [a.person_name for a in st.session_state.resource_plan if (a.person_name or "").strip()],
    )

    _remove_ref_index = None
    for i, proj in enumerate(st.session_state.reference_projects):
        with st.expander(f"{proj.title or f'Reference project {i + 1}'}" + (f" -- {proj.client}" if proj.client else ""), expanded=False):
            proj.title = st.text_input("Project title", value=proj.title, key=f"ref_title_{i}")
            proj.client = st.text_input("Client", value=proj.client, key=f"ref_client_{i}")
            proj.description = st.text_area("Description (revised for consistency/relevance)", value=proj.description, key=f"ref_desc_{i}", height=110)
            proj.relevance_text = st.text_area("Relevance to this tender", value=proj.relevance_text, key=f"ref_rel_{i}", height=70)
            options = sorted(set(_known_personnel_names) | set(proj.personnel_involved))
            proj.personnel_involved = st.multiselect(
                "Key personnel who worked on this project", options,
                default=[n for n in proj.personnel_involved if n in options], key=f"ref_pers_{i}",
            )
            photo = st.file_uploader("Project photo (optional)", type=["png", "jpg", "jpeg"], key=f"ref_photo_{i}")
            if photo is not None:
                st.session_state.reference_project_photos[proj.title] = photo.getvalue()
            existing_ref_photo = st.session_state.reference_project_photos.get(proj.title)
            if existing_ref_photo:
                st.image(existing_ref_photo, width=160)
            if st.button("Remove this reference project", key=f"ref_remove_{i}", type="primary"):
                _remove_ref_index = i
    if _remove_ref_index is not None:
        st.session_state.reference_projects.pop(_remove_ref_index)
        st.rerun()

    with st.form("add_reference_project_form", clear_on_submit=True):
        st.markdown("**Add a reference project manually**")
        new_ref_title = st.text_input("Project title")
        new_ref_client = st.text_input("Client")
        if st.form_submit_button("Add reference project", type="primary") and new_ref_title.strip():
            st.session_state.reference_projects.append(
                reference_projects_module.ReferenceProject(title=new_ref_title.strip(), client=new_ref_client.strip())
            )
            st.rerun()


# ---------------------------------------------------------------------------
# Tab 3: Tender Analysis
# ---------------------------------------------------------------------------

with tabs[2]:
    st.subheader("Tender Analysis")
    st.caption("Extracts scope, objectives, mandatory requirements, evaluation criteria, weightings, page limits, deliverables, forms, and risks from the uploaded brief.")

    ready = st.session_state.tender_extracted is not None and bool(st.session_state.ai_config.get("api_key"))
    if not ready:
        st.info("Upload a tender brief (Upload Docs) and configure an AI provider in the sidebar to run analysis.")

    # This is the metered action: the first time a given project runs Tender
    # Analysis, it consumes the account's free trial bid(s) (see
    # auth.record_proposal_usage; auth.DEFAULT_TRIAL_LIMIT -- 1, see
    # auth.get_access_status). Re-running analysis on the SAME project (same
    # project/tender/client name) never counts twice. Once the trial is used
    # up, the button is replaced with an upgrade prompt instead of silently
    # doing nothing -- except for auth.UNLIMITED_ACCOUNTS, who never hit
    # limit_reached at all (see get_access_status) so never see this prompt.
    _project_key = f"{st.session_state.project_name}|{st.session_state.tender_name}|{st.session_state.client_name}".strip("|")
    _already_counted = False
    if IS_SAAS_MODE and current_user:
        with db.get_session() as _s:
            _already_counted = _s.query(db.ProposalUsage).filter(
                db.ProposalUsage.user_id == current_user.id,
                db.ProposalUsage.project_key == _project_key.lower(),
            ).first() is not None
    _trial_blocked = IS_SAAS_MODE and current_user and not _access["allowed"] and not _already_counted

    if _trial_blocked or (IS_SAAS_MODE and current_user and _access["limit_reached"] and not _already_counted):
        if _access["past_due"]:
            # Same monthly quota as an active subscriber (see
            # auth.get_access_status), but the actionable fix here is fixing
            # payment, not buying more -- lead with that.
            st.warning(
                "Your payment is past due, and you've also used this cycle's "
                f"{_access['subscription_bid_limit']} included bid(s). Update your payment method to keep "
                "your subscription active, or buy a pay-as-you-go bid to keep going right now."
            )
        elif _access["subscribed"]:
            st.warning(
                f"You've used all {_access['subscription_bid_limit']} bid(s) included in this billing "
                "cycle's Monthly plan. Buy a pay-as-you-go bid to keep going now, or wait for renewal."
            )
        else:
            st.warning(
                f"You've used all {_access['trial_limit']} free trial bid(s). "
                "Upgrade to keep going -- pay per bid, or subscribe monthly. See pricing on the homepage."
            )
        _render_upgrade_buttons(current_user, key_prefix="_tab3",
                                 already_subscribed=_access["subscribed"] or _access["past_due"])

    if st.button("Run Tender Analysis", type="primary", disabled=not ready or _trial_blocked):
        extracted = st.session_state.tender_extracted
        progress = st.progress(0.0, text="Analysing...")

        def _progress_cb(done, total):
            progress.progress((done + 1) / max(total, 1), text=f"Analysing part {done + 1}/{total}...")

        try:
            # Runs on the background job worker for logged-in SaaS users
            # once REDIS_URL is configured (see modules/job_queue.py and
            # DEPLOY.md's "Background jobs" section) -- this is the
            # single slowest AI call in the app for a long brief, and
            # running it inline in the main web process was blocking
            # every other concurrently-connected user's Streamlit session
            # while it ran. Falls back to running inline (same as always)
            # with the same granular per-chunk progress bar when the
            # queue isn't available yet -- see _run_job_or_inline.
            analysis = _run_job_or_inline(
                "tender_analysis", tender_analyser.analyse_tender,
                args=(extracted.text, extracted.annotations, st.session_state.ai_config),
                progress=progress,
                queued_text="Queued for analysis...", running_text="Analysing...",
                inline_extra_kwargs={"progress_callback": _progress_cb},
            )
            st.session_state.analysis = analysis
            progress.progress(1.0, text="Done.")
            st.success("Tender analysis complete.")
            if IS_SAAS_MODE and current_user:
                auth.record_proposal_usage(current_user, _project_key, st.session_state.project_name)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")

    analysis = st.session_state.analysis
    if analysis:
        st.markdown("#### Project scope")
        st.write(analysis.project_scope or "_not extracted_")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Client objectives")
            st.write(analysis.client_objectives or "_none extracted_")
            st.markdown("#### Mandatory requirements")
            st.write(analysis.mandatory_requirements or "_none extracted_")
            st.markdown("#### Deliverables")
            st.write(analysis.deliverables or "_none extracted_")
        with col2:
            st.markdown(f"**Submission date:** {analysis.submission_date or '_not stated_'}")
            st.markdown(f"**Total page limit:** {analysis.total_page_limit or '_not stated_'}")
            st.markdown(f"**Fee cap:** {analysis.fee_cap or '_not stated_'}")
            st.markdown(f"**Uses named selection criteria (SC1/SC2 style):** {'Yes' if analysis.uses_named_selection_criteria else 'No'}")
            st.markdown("#### Required forms / schedules")
            st.write(analysis.required_forms or "_none extracted_")

        st.markdown("#### Evaluation / selection criteria")
        if analysis.evaluation_criteria:
            st.dataframe(
                [{
                    "Code": c.criterion_code or "-", "Name": c.name,
                    "Weighting": f"{c.detected_weighting:.0f}%" if c.detected_weighting is not None else ("Mandatory gate" if c.is_mandatory_gate else "-"),
                    "Page limit": c.page_limit or "-", "Format rules": c.format_requirements or "-",
                } for c in analysis.evaluation_criteria],
                use_container_width=True,
            )
        else:
            st.write("_No evaluation criteria extracted._")

        if analysis.user_flagged_items:
            st.markdown("#### Items you flagged via annotations")
            for item in analysis.user_flagged_items:
                st.markdown(f"- **p.{item.get('page','?')}:** {item.get('note')} — _{item.get('context','')[:150]}_")

        if analysis.risks:
            st.markdown("#### Risks noted in the brief")
            st.write(analysis.risks)

        if analysis.analysis_warnings:
            st.warning("Extraction warnings -- verify these manually against the brief:\n\n" + "\n".join(f"- {w}" for w in analysis.analysis_warnings))


# ---------------------------------------------------------------------------
# Tab 4: Proposal Structure
# ---------------------------------------------------------------------------

with tabs[3]:
    st.subheader("Proposal Structure")
    st.caption("If the brief names its own selection criteria, the structure mirrors those exactly. Otherwise it falls back to the standard skeleton, ordered by weighting.")

    ready = st.session_state.analysis is not None
    if not ready:
        st.info("Run Tender Analysis first.")

    if st.button("Generate Proposal Structure", type="primary", disabled=not ready):
        _rebuild_structure()
        st.success(f"Generated {len(st.session_state.sections)} section(s).")

    if _structure_format_stale():
        st.warning(
            "You changed the Proposal format (Project Setup) after these sections were generated, so "
            "the list below is still built for the *previous* format and won't match what "
            "drafting/export expect (e.g. no 'Project Understanding' section for a Small Scope "
            "pack). Click **Generate Proposal Structure** above again to refresh it."
        )

    sections = st.session_state.sections
    if sections:
        st.dataframe(
            [{
                "#": s.section_number, "Title": s.title, "Fixed": "Yes" if s.is_fixed else "No",
                "Weighting": f"{s.weighting:.0f}%" if s.weighting else "-",
                "Weighting source": s.weighting_source, "Pages": s.allocated_pages,
                "Page source": s.page_limit_source,
            } for s in sections],
            use_container_width=True,
        )

        with st.expander("Manually override a section's weighting"):
            criteria = st.session_state.weighted_criteria
            names = [c.criterion_name for c in criteria if not c.is_mandatory_gate]
            if names:
                target = st.selectbox("Section", names, key="weight_override_target")
                new_weight = st.number_input("New weighting (%)", 0.0, 100.0, step=1.0, key="weight_override_value")
                if st.button("Apply weighting override", type="primary"):
                    updated = weighting_engine.apply_manual_override(criteria, {target: new_weight})
                    st.session_state.weighted_criteria = updated
                    allocations = page_allocation.allocate_pages(updated, st.session_state.analysis)
                    new_sections = proposal_structure.build_proposal_structure(
                        st.session_state.analysis, updated, allocations, proposal_format=st.session_state.proposal_format,
                    )
                    st.session_state.allocations = allocations
                    st.session_state.sections = new_sections
                    st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(new_sections)
                    st.success(f"Weighting for '{target}' set to {new_weight:.0f}%. Structure recalculated.")
                    st.rerun()

        st.divider()
        st.markdown("#### Compliance matrix")
        if st.button("Generate Compliance Matrix", type="primary"):
            st.session_state.compliance_items = compliance_matrix.build_compliance_matrix(
                st.session_state.analysis, sections, _company_materials_flags(),
            )
        if st.session_state.compliance_items:
            st.dataframe(
                [{
                    "ID": i.requirement_id, "Description": i.description, "Type": i.requirement_type,
                    "Mapped section": i.mapped_section or "-", "Priority": i.priority, "Status": i.status,
                } for i in st.session_state.compliance_items],
                use_container_width=True,
            )

        st.markdown("#### Gap analysis")
        if st.button("Generate Gap Analysis", disabled=st.session_state.compliance_items is None, type="primary"):
            st.session_state.gap_items = gap_analysis.analyse_gaps(
                st.session_state.analysis, st.session_state.compliance_items,
                st.session_state.weighted_criteria, _company_materials_flags(),
            )
        if st.session_state.gap_items:
            st.dataframe(
                [{
                    "Risk": g.risk_level, "Issue": g.issue, "Impact": g.impact,
                    "Recommended action": g.recommended_action, "Section": g.mapped_section or "-",
                } for g in st.session_state.gap_items],
                use_container_width=True,
            )


# ---------------------------------------------------------------------------
# Tab 5: Page Allocation
# ---------------------------------------------------------------------------

with tabs[4]:
    st.subheader("Page Allocation")
    st.caption("Priority order: brief's exact section limit > weighted share of a stated total > default template.")
    if _is_letter():
        st.info(
            "The Small Scope pack doesn't carry a stated page limit to mirror, so this step is "
            "indicative only -- its actual section lengths come from the Sections table (tab "
            "4), not from page allocation."
        )

    allocations = st.session_state.allocations
    if not allocations:
        st.info("Generate the Proposal Structure first.")
    else:
        st.dataframe(
            [{
                "Section": a.section_name, "Weighting": f"{a.weighting:.0f}%",
                "Source": a.page_limit_source, "Allocated pages": a.allocated_pages, "Reason": a.reason,
            } for a in allocations],
            use_container_width=True,
        )
        with st.expander("Manually override a section's page count"):
            section_names = [a.section_name for a in allocations]
            target = st.selectbox("Section", section_names, key="page_override_target")
            new_pages = st.number_input("New page count", 1, 50, value=2, step=1, key="page_override_value")
            if st.button("Apply page override", type="primary"):
                updated = page_allocation.apply_manual_page_override(allocations, {target: int(new_pages)})
                st.session_state.allocations = updated
                new_sections = proposal_structure.build_proposal_structure(
                    st.session_state.analysis, st.session_state.weighted_criteria, updated,
                    proposal_format=st.session_state.proposal_format,
                )
                st.session_state.sections = new_sections
                st.session_state.guidance_notes = guidance_generator.generate_all_guidance_notes(new_sections)
                st.success(f"'{target}' set to {new_pages} page(s). Structure updated.")
                st.rerun()


# ---------------------------------------------------------------------------
# Tab 6: Draft Responses
# ---------------------------------------------------------------------------

with tabs[5]:
    st.subheader("Draft Responses")
    if _is_letter():
        st.caption(
            "The Small Scope pack has two sections that are genuinely free text -- Introduction "
            "and Methodology and Deliverables, both drafted below. Scope of Work comes straight "
            "from the brief, Project Team/Fees/Program have their own dedicated steps "
            "(Team & Resourcing / Fee Estimate), and Terms of Engagement further down is "
            "always your own wording, never AI-drafted."
        )
    else:
        st.caption("First-pass draft content per section, with red guidance notes and a list of what still needs real user input.")

    ready = st.session_state.sections is not None and bool(st.session_state.ai_config.get("api_key"))
    if not ready:
        st.info("Generate the Proposal Structure and configure an AI provider in the sidebar first.")

    if _structure_format_stale():
        st.warning(
            "The Proposal format (Project Setup) was changed after the current sections were generated. "
            "Go to Structure and click **Generate Proposal Structure** again before drafting, or "
            "this will silently draft nothing for the sections that only exist in this format."
        )

    if st.button("Generate First-Pass Drafts", type="primary", disabled=not ready):
        targets = _draftable_sections(st.session_state.sections)
        if not targets:
            st.error(
                "Nothing to draft -- the current sections don't match any of this format's "
                "AI-drafted section titles. This usually means the Proposal format (Project Setup) was "
                "changed after Proposal Structure was generated. Go to Structure and click "
                "**Generate Proposal Structure** again, then retry this."
            )
            st.stop()
        progress = st.progress(0.0, text="Drafting...")

        def _progress_cb(done, total, title):
            # generate_all_drafts() now runs sections concurrently and calls
            # this AFTER each one finishes (done is already a 1-indexed
            # completed-count, not "about to start section done+1" like the
            # old sequential version) -- sections may complete out of their
            # original order, so `title` here is whichever one just finished,
            # not necessarily done'th in the list.
            progress.progress(done / max(total, 1), text=f"Drafted '{title}' ({done}/{total})...")

        try:
            # Keep excluded personnel (unticked via "Include in proposal" on the
            # Team & Resourcing tab -- e.g. because their CV wasn't provided)
            # out of the material fed to the AI, not just the nominated-team
            # list: their own CV text would otherwise still let the drafting
            # model surface their name in section prose.
            _excluded_names = resourcing.excluded_personnel_names(st.session_state.resource_plan)
            _material_for_draft = dict(st.session_state.company_material_text)
            if _excluded_names:
                _cv_files = st.session_state.company_material_files.get("cv_library", {})
                _excluded_cv_files = team_bios.cv_filenames_for_names(_excluded_names, _cv_files)
                if _excluded_cv_files:
                    _kept_cv_files = {
                        fn: text for fn, text in _cv_files.items() if fn not in _excluded_cv_files
                    }
                    _material_for_draft["cv_library"] = "\n\n".join(_kept_cv_files.values())

            # Same background-job pattern as Tender Analysis (see that call
            # site's comment and _run_job_or_inline) -- this is the other
            # genuinely slow, heavy operation in the app (up to
            # MAX_CONCURRENT_DRAFTS AI calls in flight at once for a big
            # pack), so it gets the same treatment.
            new_drafts = _run_job_or_inline(
                "draft_generation", draft_generator.generate_all_drafts,
                args=(targets, st.session_state.analysis, _material_for_draft, st.session_state.ai_config),
                kwargs={"team_context": draft_generator.format_team_context(st.session_state.resource_plan)},
                progress=progress,
                queued_text="Queued for drafting...", running_text="Drafting...",
                inline_extra_kwargs={"progress_callback": _progress_cb},
            )
            st.session_state.drafts = {**(st.session_state.drafts or {}), **new_drafts}
            progress.progress(1.0, text="Done.")
            st.success("Draft generation complete.")
        except Exception as exc:
            st.error(f"Draft generation failed: {exc}")

    st.markdown("---")
    st.caption(
        "**Differentiator & sales pitch** -- write these in your own words: what sets this "
        "firm apart for this bid, and the pitch for why it should win. AI review is optional "
        "-- it comments on the text as written and offers a tightened, re-angled rewrite tied "
        "to this brief's real scope, but only ever works with what you've written here, never "
        "invents new claims."
    )
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.text_area(
            "Differentiator", key="project_differentiator", height=140,
            placeholder="What sets this firm apart for this bid?",
        )
    with dcol2:
        st.text_area(
            "Sales pitch", key="project_sales_pitch", height=140,
            placeholder="The pitch for why this firm should win.",
        )
    _pitch_ready = bool(st.session_state.ai_config.get("api_key")) and (
        st.session_state.project_differentiator.strip() or st.session_state.project_sales_pitch.strip()
    )
    if st.button("Review with AI", disabled=not _pitch_ready, key="review_pitch_btn", type="primary"):
        with st.spinner("Reviewing differentiator & sales pitch..."):
            try:
                st.session_state.pitch_review = pitch_review_module.review_pitch(
                    st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                    st.session_state.analysis, _project_info(), st.session_state.ai_config,
                )
                st.success("Review complete.")
            except Exception as exc:
                st.error(f"Pitch review failed: {exc}")
    if not st.session_state.ai_config.get("api_key"):
        st.caption("Configure an AI provider in the sidebar first.")

    st.markdown("**Sharpen further with follow-up questions**")
    st.caption(
        "Generates a few targeted questions about whatever's still vague or unsupported in what "
        "you've written above (up to 4 per field), then folds your answers straight into a sharper "
        "rewrite -- same rule as everywhere else on this page, nothing added beyond what you type. "
        "Only runs when you click the button, never automatically."
    )
    if st.button("Get sharpening questions", disabled=not _pitch_ready, key="get_pitch_questions_btn"):
        with st.spinner("Coming up with follow-up questions..."):
            try:
                for i in range(4):
                    st.session_state.pop(f"diff_qa_{i}", None)
                    st.session_state.pop(f"pitch_qa_{i}", None)
                st.session_state.pitch_questions = pitch_review_module.generate_pitch_questions(
                    st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                    st.session_state.analysis, _project_info(), st.session_state.ai_config,
                )
            except Exception as exc:
                st.error(f"Couldn't generate questions: {exc}")

    if st.session_state.pitch_questions:
        pq = st.session_state.pitch_questions
        if not pq.differentiator_questions and not pq.sales_pitch_questions:
            st.caption("Both already read specific and concrete -- no follow-up questions needed.")
        else:
            qcol1, qcol2 = st.columns(2)
            with qcol1:
                if pq.differentiator_questions:
                    st.markdown("*Differentiator*")
                    for i, q in enumerate(pq.differentiator_questions):
                        st.text_input(q, key=f"diff_qa_{i}")
            with qcol2:
                if pq.sales_pitch_questions:
                    st.markdown("*Sales pitch*")
                    for i, q in enumerate(pq.sales_pitch_questions):
                        st.text_input(q, key=f"pitch_qa_{i}")

            if st.button("Sharpen with my answers", key="sharpen_with_answers_btn", type="primary"):
                with st.spinner("Sharpening with your answers..."):
                    try:
                        _diff_qa = [
                            (q, st.session_state.get(f"diff_qa_{i}", ""))
                            for i, q in enumerate(pq.differentiator_questions)
                        ]
                        _pitch_qa = [
                            (q, st.session_state.get(f"pitch_qa_{i}", ""))
                            for i, q in enumerate(pq.sales_pitch_questions)
                        ]
                        st.session_state.pitch_review = pitch_review_module.review_pitch(
                            st.session_state.project_differentiator, st.session_state.project_sales_pitch,
                            st.session_state.analysis, _project_info(), st.session_state.ai_config,
                            differentiator_qa=_diff_qa, sales_pitch_qa=_pitch_qa,
                        )
                        st.success("Sharpened using your answers -- see the rewrite below.")
                    except Exception as exc:
                        st.error(f"Sharpening failed: {exc}")

    if st.session_state.pitch_review:
        pr = st.session_state.pitch_review

        def _apply_differentiator_rewrite():
            # Widget-bound session_state keys can only be reassigned from a
            # callback (which runs BEFORE the next script run instantiates the
            # text_area again) -- reassigning inline after the widget has
            # already rendered in the current run raises a StreamlitAPIException.
            st.session_state.project_differentiator = st.session_state.pitch_review.differentiator_refined

        def _apply_sales_pitch_rewrite():
            st.session_state.project_sales_pitch = st.session_state.pitch_review.sales_pitch_refined

        rcol1, rcol2 = st.columns(2)
        with rcol1:
            if pr.differentiator_comment or pr.differentiator_refined:
                st.markdown("**Differentiator -- AI comment**")
                st.write(pr.differentiator_comment)
                st.markdown("**Suggested rewrite**")
                st.write(pr.differentiator_refined)
                if pr.differentiator_refined:
                    st.button(
                        "Use this rewrite", key="use_diff_rewrite", on_click=_apply_differentiator_rewrite,
                     type="primary")
        with rcol2:
            if pr.sales_pitch_comment or pr.sales_pitch_refined:
                st.markdown("**Sales pitch -- AI comment**")
                st.write(pr.sales_pitch_comment)
                st.markdown("**Suggested rewrite**")
                st.write(pr.sales_pitch_refined)
                if pr.sales_pitch_refined:
                    st.button(
                        "Use this rewrite", key="use_pitch_rewrite", on_click=_apply_sales_pitch_rewrite,
                     type="primary")

    st.markdown("---")
    st.caption(
        "**Executive summary** -- an unweighted page that goes straight after the cover, "
        "before the scored sections (Large Scope pack) or straight after the cover (Small "
        "Scope pack). No score of its own, but it's the evaluators' first impression, so it's "
        "drafted warm and sales-forward rather than dry -- catchy titles, short readable "
        "blocks, grounded in the real brief and the real (included) nominated team."
    )
    if st.button("Generate Executive Summary (AI)", disabled=not ready, type="primary"):
        with st.spinner("Drafting executive summary..."):
            try:
                _excluded_names = resourcing.excluded_personnel_names(st.session_state.resource_plan)
                _team_context = draft_generator.format_team_context(st.session_state.resource_plan)
                st.session_state.executive_summary = executive_summary_module.draft_executive_summary(
                    st.session_state.analysis, _project_info(), _team_context, st.session_state.ai_config,
                )
                st.success("Executive summary drafted.")
            except Exception as exc:
                st.error(f"Executive summary generation failed: {exc}")

    if st.session_state.executive_summary:
        with st.expander("Executive summary", expanded=False):
            es = st.session_state.executive_summary
            if es.intro:
                st.write(es.intro)
            for block in es.blocks:
                st.markdown(f"**{block.title}**")
                st.write(block.body)

    if not _is_letter():
        st.markdown("---")
        st.caption(
            "**Team introduction** -- a short sales-forward pitch at the very start of Key "
            "Personnel, before the org chart and pen pics: a catchy headline and a couple of "
            "paragraphs connecting the nominated (included) team's real past projects to this "
            "brief's real challenges, closing with a pull-quote line. Grounded entirely in "
            "each person's own value-to-project write-up and relevant projects, entered on the "
            "Team & Resourcing tab -- never invented."
        )
        _team_ready = ready and bool(st.session_state.resource_plan)
        if st.button("Generate Team Introduction (AI)", disabled=not _team_ready, type="primary"):
            with st.spinner("Drafting team introduction..."):
                try:
                    _included_people = [
                        e for e in resourcing.personnel_profiles_deduped(st.session_state.resource_plan)
                        if (e.get("name") or "").strip()
                        and getattr(e["assignment"], "include_in_proposal", True)
                    ]
                    st.session_state.team_intro = team_intro_module.draft_team_intro(
                        _included_people, st.session_state.analysis, _project_info(), st.session_state.ai_config,
                    )
                    st.success("Team introduction drafted.")
                except Exception as exc:
                    st.error(f"Team introduction generation failed: {exc}")
        if not st.session_state.resource_plan:
            st.caption("Assign at least one person on the Team & Resourcing tab first.")

        if st.session_state.team_intro:
            with st.expander("Team introduction", expanded=False):
                ti = st.session_state.team_intro
                if ti.heading:
                    st.markdown(f"**{ti.heading}**")
                for para in ti.paragraphs:
                    st.write(para)
                if ti.pullquote:
                    st.markdown(f"*{ti.pullquote}*")

        st.markdown("---")
        st.caption(
            "**Project experience introduction** -- a short sales-forward paragraph at the "
            "start of Relevant Project Experience, before the individual project cards: "
            "names the strongest 2-4 comparable reference projects and states plainly why "
            "they prove this firm can deliver the brief, replacing the generic 'selected "
            "past projects' note. Grounded entirely in the real reference projects entered "
            "and drafted in Upload Docs -- never invented."
        )
        _experience_ready = ready and bool(st.session_state.reference_projects)
        if st.button("Generate Project Experience Introduction (AI)", disabled=not _experience_ready,
                     help=None if _experience_ready else "Needs at least one drafted reference project -- see below.", type="primary"):
            with st.spinner("Drafting project experience introduction..."):
                try:
                    st.session_state.experience_intro = experience_intro_module.draft_experience_intro(
                        st.session_state.reference_projects, st.session_state.analysis,
                        _project_info(), st.session_state.ai_config,
                    )
                    st.success("Project experience introduction drafted.")
                except Exception as exc:
                    st.error(f"Project experience introduction generation failed: {exc}")
        if not st.session_state.reference_projects:
            # Uploading reference material (Upload Docs) only extracts its text --
            # it still needs "Draft reference projects from uploaded material"
            # clicked there before any entries exist for this button to use. A
            # bare "add a reference project" caption reads as if uploading alone
            # should have been enough, which is exactly the confusing part.
            st.caption(
                "No drafted reference projects yet. Go to Upload Docs, upload 'Project references' "
                "material if you haven't, then click **Draft reference projects from uploaded "
                "material** there -- or add one manually on that same step."
            )

        if st.session_state.experience_intro:
            with st.expander("Project experience introduction", expanded=False):
                st.write(st.session_state.experience_intro.paragraph)

    if st.session_state.drafts:
        for section in _draftable_sections(st.session_state.sections or []):
            draft = st.session_state.drafts.get(section.title)
            note = st.session_state.guidance_notes.get(section.title) if st.session_state.guidance_notes else None
            with st.expander(f"{section.section_number}. {section.title}", expanded=False):
                if note and not _is_letter():
                    st.markdown(f":red[**[{note.marker}]**]")
                    st.markdown(f":red[Page limit: {note.page_limit_text}]")
                    st.markdown(f":red[Evaluation weighting: {note.weighting_text}]")
                    st.markdown(f":red[Formatting: {note.format_requirements_text}]")
                if draft:
                    st.markdown(f"**{draft.draft_heading}**")
                    st.write(draft.draft_text)
                    if draft.required_user_inputs:
                        st.markdown("**Still needs from you:**")
                        for r in draft.required_user_inputs:
                            st.markdown(f"- {r}")

    if _is_letter():
        st.divider()
        st.markdown("#### Terms of Engagement")
        st.caption(
            "Always your own text -- this tool never invents or guesses which contract/commercial "
            "conditions apply, since getting that wrong is a real legal risk."
        )
        st.text_area(
            "Terms of Engagement", key="terms_of_engagement_text", height=150,
            placeholder="e.g. This offer is made under our current Master Services Agreement with Townsville City Council, reference ...",
            label_visibility="collapsed",
        )


# ---------------------------------------------------------------------------
# Tab 7: Graphics & Design
# ---------------------------------------------------------------------------

with tabs[6]:
    if _is_letter():
        st.subheader("Project Team")
        st.caption(
            "Built entirely from the Team & Resourcing tab (step 8) -- the same people, the same "
            "CV-drafted bios, and the same 'include in proposal' ticks used there also drive this "
            "pack's Project Team section, so there's only one place to build your team, whichever "
            "pack size you're preparing. Head to step 8 to assign people, draft bios from the CV "
            "library, add a team member under a discipline lead (with their own title), and tick "
            "who's included. This is a read-only preview of what the exported pack will show."
        )
        entries = resourcing.letter_team_entries(st.session_state.resource_plan)
        if not entries:
            st.info(
                "No one is assigned and ticked 'Include in proposal' yet -- head to step 8 "
                "(Team & Resourcing) to build the team."
            )
        else:
            for entry in entries:
                marker = "↳ " if entry["indent"] else ""
                name = entry["name"] or "[not assigned]"
                st.markdown(f"{marker}**{name}** -- {entry['role_label']}")
    else:
        st.subheader("Graphics & Design")
        st.caption(
            "Real, generated divider banners and cover art built from your own uploaded photos and "
            "typed quotes -- never invented imagery. Everything this tool can't build for real "
            "(org charts, methodology diagrams, programme timelines) stays a clearly marked placeholder below."
        )

    ready = st.session_state.sections is not None
    if not ready:
        st.info("Generate the Proposal Structure first.")
    elif _is_letter():
        pass  # Project Team preview above already covers this pack size -- nothing else to render here.
    else:
        _ensure_divider_config(st.session_state.sections)
        photos = st.session_state.project_photo_bytes
        theme_name = st.session_state.proposal_theme

        st.markdown("#### 1. Pull-quotes / testimonials (optional)")
        st.caption("Only real quotes you type in here -- nothing is invented or pulled from the web.")
        with st.form("add_quote_form", clear_on_submit=True):
            qcol1, qcol2 = st.columns(2)
            with qcol1:
                q_text = st.text_area("Quote", placeholder="e.g. \"The team delivered a technically excellent outcome...\"", height=80)
            with qcol2:
                q_attr = st.text_input("Attributed to", placeholder="e.g. J. Smith, Project Director, XYZ Council")
                q_project = st.text_input("Project (optional)", placeholder="e.g. Burnett River Bridge")
            if st.form_submit_button("Add quote", type="primary") and q_text.strip():
                st.session_state.quotes.append({"text": q_text.strip(), "attribution": q_attr.strip(), "project": q_project.strip()})

        if st.session_state.quotes:
            for i, q in enumerate(st.session_state.quotes):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"_{q['text']}_ — **{q['attribution'] or 'unattributed'}**" + (f" ({q['project']})" if q['project'] else ""))
                with col2:
                    if st.button("Remove", key=f"remove_quote_{i}", type="primary"):
                        st.session_state.quotes.pop(i)
                        st.rerun()

        st.divider()
        st.markdown("#### 2. Divider design per section")
        if not photos:
            st.info("No project photos uploaded (Upload Docs) -- sections default to the 'Solid colour' layout. Upload photos there to unlock photo-based layouts.")

        available_layouts = ["Solid colour"] + (["Photo + gradient", "Photo + quote", "Split (colour + photo)"] if photos else [])
        config = st.session_state.section_divider_config

        for section in st.session_state.sections:
            cfg = config[section.title]
            with st.expander(f"{section.section_number}. {section.title}"):
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    layout = st.selectbox(
                        "Layout", available_layouts,
                        index=available_layouts.index(cfg["layout"]) if cfg["layout"] in available_layouts else 0,
                        key=f"layout_{section.title}",
                    )
                with c2:
                    photo_options = ["(none)"] + [f"Photo {i+1}" for i in range(len(photos))]
                    photo_idx = cfg["photo_index"]
                    photo_choice = st.selectbox(
                        "Photo", photo_options,
                        index=(photo_idx + 1) if photo_idx is not None else 0,
                        key=f"photo_{section.title}", disabled=not photos,
                    )
                with c3:
                    quote_options = ["(none)"] + [f"{q['attribution'] or 'Quote'} {i+1}" for i, q in enumerate(st.session_state.quotes)]
                    quote_idx = cfg["quote_index"]
                    quote_choice = st.selectbox(
                        "Quote", quote_options,
                        index=(quote_idx + 1) if quote_idx is not None else 0,
                        key=f"quote_{section.title}", disabled=not st.session_state.quotes,
                    )
                with c4:
                    photo_caption = st.text_input(
                        "Photo title", value=cfg.get("photo_caption", ""),
                        placeholder="e.g. Mangaweka Bridge",
                        key=f"photo_caption_{section.title}", disabled=not photos,
                        help="Shown bottom-right of the photo itself, not the coloured band. "
                             "Only used when this section has a photo.",
                    )
                cfg["layout"] = layout
                cfg["photo_index"] = None if photo_choice == "(none)" else int(photo_choice.split()[-1]) - 1
                cfg["quote_index"] = None if quote_choice == "(none)" else quote_options.index(quote_choice) - 1
                cfg["photo_caption"] = photo_caption.strip()

                existing = st.session_state.divider_images.get(section.title)
                if existing:
                    st.image(existing, caption="Current banner for this section", use_container_width=True)

        st.divider()
        st.markdown("#### 3. Document font")
        st.selectbox(
            "Body & heading font", ["Arial", "Calibri", "Helvetica", "Times New Roman", "Georgia", "Verdana"],
            key="body_font", help="Applied to the exported Word document and the divider text.",
        )

        st.markdown("#### 4. Generate")
        if st.button("Generate Graphics Package", type="primary"):
            new_divider_images = {}
            for section in st.session_state.sections:
                cfg = config[section.title]
                photo_bytes = photos[cfg["photo_index"]] if cfg["photo_index"] is not None and photos else None
                _quote_idx = cfg.get("quote_index")
                _picked_quote = (
                    st.session_state.quotes[_quote_idx]
                    if _quote_idx is not None and _quote_idx < len(st.session_state.quotes) else None
                )
                png = divider_designer.render_full_page_divider(
                    section.title, cfg["layout"], theme_name, photo_bytes=photo_bytes,
                    section_label=str(section.section_number),
                    quote_text=_picked_quote["text"] if _picked_quote else None,
                    quote_attribution=_picked_quote["attribution"] if _picked_quote else None,
                    photo_caption=cfg.get("photo_caption") or None,
                )
                if png:
                    new_divider_images[section.title] = png
            st.session_state.divider_images = new_divider_images

            if not st.session_state.project_photo_bytes:
                st.session_state.cover_hero_png = divider_designer.render_banner(
                    st.session_state.tender_name or "Tender Response Pack", "Solid colour", theme_name,
                )
            else:
                st.session_state.cover_hero_png = None

            flags = _company_materials_flags()
            st.session_state.graphics = graphics_engine.recommend_graphics(
                st.session_state.sections, flags["has_project_photos"], flags["has_company_image_library"],
                divider_image_sections=set(new_divider_images.keys()),
                cover_generated=bool(st.session_state.project_photo_bytes or st.session_state.cover_hero_png),
            )
            if st.session_state.weighted_criteria:
                st.session_state.weighting_chart_png = graphics_engine.generate_weighting_chart(st.session_state.weighted_criteria)
            st.success(f"Generated {len(new_divider_images)} divider banner(s) and {len(st.session_state.graphics)} graphic recommendation(s).")

    if st.session_state.graphics:
        st.divider()
        st.markdown("#### Remaining placeholders overview")
        st.dataframe(
            [{
                "Graphic": g.graphic_title, "Type": g.graphic_type, "Placement": g.suggested_placement,
                "Source needed": g.source_data_required, "Status": g.status,
            } for g in st.session_state.graphics],
            use_container_width=True,
        )
        if st.session_state.weighting_chart_png:
            st.markdown("#### Evaluation weighting dashboard (generated)")
            st.image(st.session_state.weighting_chart_png)


# ---------------------------------------------------------------------------
# Tab 8: Team & Resourcing
# ---------------------------------------------------------------------------

with tabs[7]:
    st.subheader("Team & Resourcing")
    st.caption(
        "Identify who staffs each discipline the brief calls for, plus the standing "
        "management roles every job carries, then generate a project org chart for the "
        "Key Personnel section. Names come from your uploaded CV library where possible, "
        "but you can also type in anyone you haven't uploaded a CV for."
    )

    if st.session_state.analysis is None:
        st.info("Run the Tender Analysis first -- the required disciplines come from the brief.")
    else:
        for _k in ("resource_extra_names", "cv_library_filenames", "cv_extracted_names", "dismissed_disciplines"):
            if st.session_state.get(_k) is None:
                st.session_state[_k] = []

        brief_disciplines = st.session_state.analysis.disciplines_involved or []
        # Project Management is deliberately excluded here -- it's staffed by the
        # Project Manager management role above, not a separate discipline lead.
        # (It still gets its own line in the fee estimate tab.)
        required = resourcing.resourcing_disciplines(brief_disciplines)
        dismissed = {d.lower() for d in st.session_state.dismissed_disciplines}

        # Coerce None -> [] for projects saved before this feature existed (those
        # load these keys back as None under the "not run yet" convention).
        if not st.session_state.resource_plan:
            st.session_state.resource_plan = resourcing.build_resource_plan(brief_disciplines)
        else:
            # Drop any Project Management discipline-lead row left over from a
            # project saved before this was de-duplicated against the Project
            # Manager management role.
            st.session_state.resource_plan = [
                a for a in st.session_state.resource_plan
                if not (a.slot_kind == "discipline" and resourcing.canonical_discipline(a.slot) == resourcing.ALWAYS_INCLUDED_DISCIPLINE)
            ]
            # Add any newly-detected disciplines without wiping existing assignments --
            # but never re-add a discipline the user has explicitly removed.
            existing_disc_slots = {a.slot for a in st.session_state.resource_plan if a.slot_kind == "discipline"}
            for disc in required:
                if disc not in existing_disc_slots and disc.lower() not in dismissed:
                    st.session_state.resource_plan.append(
                        resourcing.ResourceAssignment(slot=disc, slot_kind="discipline", is_lead=True)
                    )
        # Merge any duplicate/variant disciplines (e.g. two 'Structural ...' rows).
        st.session_state.resource_plan = resourcing.normalize_plan_disciplines(st.session_state.resource_plan)

        # The dropdown name pool, from every available source: names extracted from
        # the CV text by AI, names inferred from CV filenames, any bios already
        # drafted, and anyone typed in manually. All merged and de-duplicated.
        filename_names = resourcing.names_from_filenames(st.session_state.cv_library_filenames)
        known_names = resourcing.cv_derived_names(
            st.session_state.team_members,
            list(st.session_state.cv_extracted_names) + filename_names + list(st.session_state.resource_extra_names),
        )

        # Pull accurate names straight from the CV library text (AI).
        cv_text = st.session_state.company_material_text.get("cv_library", "")
        ai_ready = bool(st.session_state.ai_config.get("api_key")) and bool(cv_text.strip())
        ncol1, ncol2 = st.columns([2, 3])
        with ncol1:
            if st.button("Load names from CV library", disabled=not ai_ready,
                         help=None if ai_ready else "Upload a CV library (Upload Docs) and set an AI provider in the sidebar first.", type="primary"):
                with st.spinner("Reading the whole CV library for names (a few seconds per batch)..."):
                    try:
                        names, warns = team_bios.extract_person_names(cv_text, st.session_state.ai_config)
                        st.session_state.cv_extracted_names = resourcing.dedupe_names(names)
                        if st.session_state.cv_extracted_names:
                            st.success(f"Found {len(st.session_state.cv_extracted_names)} name(s): " + ", ".join(st.session_state.cv_extracted_names))
                        for w in warns:
                            st.warning(w)
                    except Exception as exc:
                        st.error(f"Could not read names from the CV library: {exc}")
                st.rerun()
        with ncol2:
            if known_names:
                st.caption("Available names: " + ", ".join(known_names))
            else:
                st.caption("No names yet -- click 'Load names from CV library', or add people manually below.")

        # The most reliable name source is the CV filenames (one file = one
        # person). A project loaded from an older save won't have them, so nudge
        # the user to re-upload the CV library for instant, complete names.
        if cv_text.strip() and not st.session_state.cv_library_filenames:
            st.caption(
                "💡 Tip: for the most complete and accurate list, re-upload your CV library files "
                "in Upload Docs -- each filename gives one person's full name instantly, "
                "with no AI guesswork. (Your loaded project kept the CV text but not the filenames.)"
            )

        st.markdown("#### Management roles")
        st.caption("Always present on the chart: the client's PM at the top, then your Project Director, Project Manager and Design Manager.")
        _render_resource_rows("management", known_names)

        st.divider()
        st.markdown("#### Discipline leads")
        st.caption(
            "One per discipline the brief requires. Add or remove disciplines as needed. "
            "Project Management isn't listed here -- it's staffed by the Project Manager role "
            "above -- but it still gets its own line in the fee estimate tab."
        )
        _render_resource_rows("discipline", known_names)

        # Focused re-scan of the brief for disciplines -- catches ones the main
        # analysis missed and infers those the scope implies (e.g. environmental,
        # constructability, rail) without re-running the whole analysis.
        brief_text = st.session_state.tender_extracted.text if st.session_state.tender_extracted else ""
        rescan_ready = bool(st.session_state.ai_config.get("api_key")) and bool(brief_text.strip())
        rcol1, rcol2 = st.columns([2, 3])
        with rcol1:
            if st.button("Re-scan brief for disciplines", disabled=not rescan_ready,
                         help=None if rescan_ready else "Needs the tender brief (Upload Docs) and an AI provider in the sidebar.", type="primary"):
                with st.spinner("Re-reading the brief for every discipline the scope implies..."):
                    try:
                        detected = tender_analyser.detect_disciplines_from_text(brief_text, st.session_state.ai_config)
                        existing = {a.slot for a in st.session_state.resource_plan if a.slot_kind == "discipline"}
                        dismissed_now = {d.lower() for d in st.session_state.dismissed_disciplines}
                        added = []
                        for d in detected:
                            label = resourcing.canonical_discipline(d)
                            # Project Management is never added here -- it's staffed by
                            # the Project Manager management role, not a discipline lead.
                            if (label and label != resourcing.ALWAYS_INCLUDED_DISCIPLINE
                                    and label not in existing and label.lower() not in dismissed_now):
                                st.session_state.resource_plan.append(
                                    resourcing.ResourceAssignment(slot=label, slot_kind="discipline", is_lead=True)
                                )
                                existing.add(label)
                                added.append(label)
                        st.session_state.resource_plan = resourcing.normalize_plan_disciplines(st.session_state.resource_plan)
                        if added:
                            st.success("Added: " + ", ".join(added))
                        else:
                            st.info("No new disciplines found beyond what's already listed.")
                    except Exception as exc:
                        st.error(f"Discipline re-scan failed: {exc}")
                st.rerun()
        with rcol2:
            st.caption("Reads the brief and infers disciplines the scope implies (environmental, constructability, rail, survey, etc.), even if they weren't named explicitly.")

        with st.form("add_discipline_resource_form", clear_on_submit=True):
            acol1, acol2 = st.columns([3, 1])
            with acol1:
                new_disc = st.text_input("Add a discipline", placeholder="e.g. Landscaping, Surveying, Constructability")
            with acol2:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.form_submit_button("Add discipline", type="primary") and new_disc.strip():
                    label = resourcing.canonical_discipline(new_disc.strip())
                    if label == resourcing.ALWAYS_INCLUDED_DISCIPLINE:
                        st.warning(
                            "Project Management is staffed by the Project Manager role above, "
                            "not added here as a separate discipline. It still has its own line "
                            "in the fee estimate tab."
                        )
                    else:
                        # Un-dismiss if it was previously removed, so re-adding sticks.
                        st.session_state.dismissed_disciplines = [
                            d for d in st.session_state.dismissed_disciplines if d.lower() != label.lower()
                        ]
                        if label not in {a.slot for a in st.session_state.resource_plan if a.slot_kind == "discipline"}:
                            st.session_state.resource_plan.append(
                                resourcing.ResourceAssignment(slot=label, slot_kind="discipline", is_lead=True)
                            )
                    st.rerun()

        st.divider()
        st.markdown("#### Add someone without a CV")
        st.caption("Names you type here become available in every dropdown above -- for people you want on the chart who don't have a CV uploaded.")
        with st.form("add_extra_name_form", clear_on_submit=True):
            ncol1, ncol2 = st.columns([3, 1])
            with ncol1:
                extra_name = st.text_input("Person's name", label_visibility="collapsed", placeholder="e.g. Jordan Lee")
            with ncol2:
                if st.form_submit_button("Add name", type="primary") and extra_name.strip():
                    if extra_name.strip() not in st.session_state.resource_extra_names:
                        st.session_state.resource_extra_names.append(extra_name.strip())
                    st.rerun()

        st.divider()
        st.markdown("#### Key personnel profile details")
        st.caption(
            "Feeds the numbered Key Personnel profiles in the exported pack -- Project Director, "
            "Project Manager, Design Manager, then discipline leads, in that order. Everything here "
            "is optional, user-entered text (never guessed): leave a field blank and the export "
            "shows a clearly marked placeholder instead."
        )
        # One entry per unique person (roles merged) -- so someone leading two disciplines
        # gets a single profile/editor, not duplicates. Matches the deduped export exactly.
        _profile_entries = resourcing.personnel_profiles_deduped(st.session_state.resource_plan)
        _assigned_profile_names = [e["name"] for e in _profile_entries if e["name"]]
        _profile_fill_ready = bool(st.session_state.ai_config.get("api_key")) and bool(cv_text.strip()) and bool(_assigned_profile_names)
        _overwrite_profiles = st.checkbox(
            "Overwrite existing values (re-read from CVs, replacing what's there)",
            value=False, key="_profile_fill_overwrite",
            help="Off (default): only fills blank fields, protecting anything you've typed. "
                 "On: re-reads every assigned person's CV and replaces the current values -- "
                 "use this to fix wrong details left over from an earlier run.",
        )
        pfcol1, pfcol2 = st.columns([2, 3])
        with pfcol1:
            if st.button(
                "Fill profile fields from CVs", disabled=not _profile_fill_ready,
                help=None if _profile_fill_ready else "Assign people to roles above, upload a CV library (Upload Docs), and set an AI provider in the sidebar first.",
             type="primary"):
                with st.spinner("Reading each person's CV for registration status, experience and relevance (a few seconds per batch)..."):
                    try:
                        cv_profiles, warns = team_bios.extract_personnel_profile_fields(
                            cv_text, _assigned_profile_names, st.session_state.ai_config,
                            cv_files=st.session_state.company_material_files.get("cv_library"),
                        )
                        filled = []
                        for entry in _profile_entries:
                            a = entry["assignment"]  # write to the person's primary slot
                            key = (entry.get("name") or "").strip().lower()
                            if not key or key not in cv_profiles:
                                continue
                            found = cv_profiles[key]
                            changed = False
                            # The Details expander below renders each field via a keyed
                            # st.text_input/st.text_area (e.g. key=f"prof_qual_{ekey}"). Once a
                            # widget with a given key has rendered once, Streamlit ignores any
                            # future `value=` we pass it and keeps showing its own cached
                            # session_state entry -- so writing straight to `a.field` here is
                            # not enough; the widget's cached copy must be updated too, or the
                            # next rerun (the widget line itself does `a.field = st.text_input(
                            # ..., value=a.field, key=...)`) silently overwrites our fresh value
                            # back to the stale one before the user ever sees it.
                            ekey = (entry.get("name") or "").strip() or a.slot
                            # Default: only fill a blank field (protects the user's own typing).
                            # Overwrite mode: replace the field whenever the CV yielded a value,
                            # so a wrong value left over from an earlier run can be corrected.
                            for field, widget_key in (
                                ("qualification", f"prof_qual_{ekey}"),
                                ("rpeq_status", f"prof_rpeq_{ekey}"),
                                ("years_experience", f"prof_years_{ekey}"),
                                ("value_to_project", f"prof_value_{ekey}"),
                            ):
                                found_val = (found.get(field) or "").strip()
                                cur_val = (getattr(a, field) or "").strip()
                                if found_val and (_overwrite_profiles or not cur_val) and found_val != cur_val:
                                    setattr(a, field, found_val)
                                    st.session_state[widget_key] = found_val
                                    changed = True
                            found_projects = [str(p).strip() for p in (found.get("relevant_projects") or []) if str(p).strip()]
                            cur_projects = getattr(a, "relevant_projects", None) or []
                            if found_projects and (_overwrite_profiles or not cur_projects) and found_projects != cur_projects:
                                a.relevant_projects = found_projects
                                st.session_state[f"prof_relproj_{ekey}"] = "\n".join(found_projects)
                                changed = True
                            if changed:
                                filled.append(entry["name"])
                        if filled:
                            verb = "Updated" if _overwrite_profiles else "Filled"
                            st.success(f"{verb} profile details for: {', '.join(filled)}. Review before exporting -- fields left blank mean the CV didn't clearly state that fact.")
                        elif _overwrite_profiles:
                            st.info("No profile details found in the CVs to write -- the CVs don't clearly state these facts, or no assigned person could be matched to a CV file.")
                        else:
                            st.info("No new profile details found -- existing entries were left as-is. Tick 'Overwrite existing values' to re-read and replace them.")
                        for w in warns:
                            st.warning(w)
                    except Exception as exc:
                        st.error(f"Could not fill profile fields from CVs: {exc}")
                st.rerun()
        with pfcol2:
            st.caption(
                "Reads each assigned person's own CV file (in isolation, so no one's details get mixed up "
                "with another person's) for their registration/membership status and stated years of "
                "experience, and drafts an \"On this project, [name] will...\" line from their real background."
            )

        st.markdown("---")
        st.caption(
            "**Include in proposal** -- tick which pen pics actually make it into the exported Key "
            "Personnel section. A full photo + write-up profile takes real page space, so when a "
            "page-limited section is full, untick anyone whose profile isn't essential to include -- "
            "they're still on the job (still in the org chart and fee build-up), they just won't get "
            "a dedicated profile. Project Director/Manager/Design Manager are always recommended "
            "(project leadership), every other tick can be pre-set from an AI read of this project's "
            "scope below, and you can always override any tick by hand."
        )
        _suggest_ready = bool(st.session_state.ai_config.get("api_key")) and bool(st.session_state.resource_plan)
        if st.button(
            "Suggest which personnel to include (AI)", disabled=not _suggest_ready,
            help=None if _suggest_ready else "Assign roles above and set an AI provider in the sidebar first.",
         type="primary"):
            with st.spinner("Reading this project's scope to judge which discipline profiles are worth including..."):
                try:
                    suggestions = resourcing.suggest_proposal_inclusion(
                        st.session_state.resource_plan, st.session_state.analysis, st.session_state.ai_config,
                    )
                    st.session_state.personnel_inclusion_suggestions = suggestions
                    # Apply the recommendation to each MERGED profile's tick, keyed on the
                    # primary assignment's own slot (the same "a" the checkbox below reads/
                    # writes for a deduped person) -- not every raw plan row, since someone
                    # holding two slots would otherwise get two different verdicts fighting
                    # over the one checkbox they actually see. Same widget-caching gotcha as
                    # "Fill profile fields from CVs" above: also write the checkbox's own
                    # session_state key, since a widget that's already rendered once ignores a
                    # fresh `value=` and keeps showing its cached copy otherwise.
                    for entry in _profile_entries:
                        a = entry["assignment"]
                        verdict = suggestions.get(a.slot)
                        if verdict is None:
                            continue
                        a.include_in_proposal = bool(verdict["recommended"])
                        person_label = (entry.get("name") or "").strip() or "[unassigned]"
                        ekey_for_entry = person_label if entry.get("name") else a.slot
                        st.session_state[f"prof_include_{ekey_for_entry}"] = a.include_in_proposal
                    st.success("Recommendations applied -- review the ticks and reasons below, then adjust by hand as needed.")
                except Exception as exc:
                    st.error(f"Could not get AI recommendations: {exc}")
            st.rerun()

        for entry in _profile_entries:
            a = entry["assignment"]  # profile fields are read/written on the primary slot
            person_label = (entry.get("name") or "").strip() or "[unassigned]"
            role_label = ", ".join(entry.get("roles") or [])
            # A stable per-entry key: the person's name if assigned (so one editor per
            # person even across multiple roles), else the slot for an unassigned row.
            ekey = person_label if entry.get("name") else a.slot
            name = (entry.get("name") or "").strip()

            # A header row shown ABOVE the expander (not inside it), with a per-person
            # "Refresh from CV" button next to the name -- this is deliberately outside
            # the collapsed expander so a person whose pen pic came out empty can be
            # re-read from their own CV file in one click, without opening every row or
            # re-running "Fill profile fields from CVs" for everyone else. Re-uses the
            # same single-person, per-file matching path as that batch button (see
            # team_bios.extract_personnel_profile_fields), just scoped to one name, and
            # always overwrites -- an explicit refresh click means the current values
            # (if any) are what the user is trying to fix.
            # Result of the last "Refresh from CV" click, if any, stashed in
            # session_state so it survives the st.rerun() below. A message shown
            # via st.success/warning/error and then immediately followed by
            # st.rerun() only flashes for an instant in Streamlit -- the rerun
            # starts a brand-new script execution before the person has a chance
            # to read it, which looks exactly like "nothing happened" even when
            # the click worked (or failed) correctly. Stashing it and rendering
            # it on the NEXT run (then clearing it) makes the outcome durable.
            result_key = f"prof_refresh_result_{ekey}"

            hcol1, hcol_tick, hcol2 = st.columns([4, 1.5, 1.3])
            with hcol1:
                st.markdown(f"**{role_label} -- {person_label}**")
            with hcol_tick:
                a.include_in_proposal = st.checkbox(
                    "Include in proposal", value=a.include_in_proposal, key=f"prof_include_{ekey}",
                )
            with hcol2:
                refresh_ready = bool(st.session_state.ai_config.get("api_key")) and bool(name) and bool(cv_text.strip())
                if st.button(
                    "Refresh from CV", key=f"prof_refresh_{ekey}", disabled=not refresh_ready,
                    help=None if refresh_ready else "Assign a name, upload a CV library (Upload Docs), and set an AI provider in the sidebar first.",
                 type="primary"):
                    messages = []  # [(level, text), ...] -- rendered after the rerun, see result_key above
                    with st.spinner(f"Re-reading {name}'s CV..."):
                        try:
                            cv_profiles, warns = team_bios.extract_personnel_profile_fields(
                                cv_text, [name], st.session_state.ai_config,
                                cv_files=st.session_state.company_material_files.get("cv_library"),
                            )
                            found = cv_profiles.get(name.lower())
                            changed = False
                            if found:
                                # As below in the batch "Fill profile fields from CVs" handler:
                                # the Details expander's widgets (key=f"prof_qual_{ekey}" etc.)
                                # cache their own value once rendered, so setting `a.field` alone
                                # gets silently overwritten back to the stale widget value on the
                                # very next rerun unless we also update session_state for that
                                # widget's exact key here.
                                for field, widget_key in (
                                    ("qualification", f"prof_qual_{ekey}"),
                                    ("rpeq_status", f"prof_rpeq_{ekey}"),
                                    ("years_experience", f"prof_years_{ekey}"),
                                    ("value_to_project", f"prof_value_{ekey}"),
                                ):
                                    val = (found.get(field) or "").strip()
                                    if val:
                                        setattr(a, field, val)
                                        st.session_state[widget_key] = val
                                        changed = True
                                found_projects = [str(p).strip() for p in (found.get("relevant_projects") or []) if str(p).strip()]
                                if found_projects:
                                    a.relevant_projects = found_projects
                                    st.session_state[f"prof_relproj_{ekey}"] = "\n".join(found_projects)
                                    changed = True
                            if changed:
                                messages.append(("success", f"Refreshed {name} from their own CV file."))
                            elif found is not None:
                                # Matched to a CV file, AI call succeeded, but every field came back
                                # empty -- almost always means the CV TEXT on file for this person is
                                # thin/stale (e.g. it was uploaded and extracted before a recent fix to
                                # how CVs are read, so what's cached here is mostly empty template
                                # boilerplate), not that the button failed. Re-uploading their CV in
                                # tab 2 re-extracts it with the current logic and fixes this.
                                messages.append((
                                    "warning",
                                    f"Read {name}'s CV file but found no details to fill in. This usually means the "
                                    f"text stored for their CV is incomplete (e.g. it was uploaded before a recent "
                                    f"extraction fix) rather than the CV genuinely being empty -- try re-uploading "
                                    f"{name}'s CV file in Upload Docs, then refresh again."
                                ))
                            else:
                                messages.append((
                                    "warning",
                                    f"Couldn't find/re-read {name}'s CV file -- check their filename "
                                    "derives to this exact name, or that their CV is in the library (Upload Docs)."
                                ))
                            for w in warns:
                                messages.append(("warning", w))
                        except Exception as exc:
                            messages.append(("error", f"Could not refresh {name} from their CV: {exc}"))
                    st.session_state[result_key] = messages
                    st.rerun()

            pending_messages = st.session_state.pop(result_key, None)
            if pending_messages:
                for level, text in pending_messages:
                    getattr(st, level)(text)

            # The reason behind the current tick -- fixed for the firm's three
            # leadership roles (no scope judgement needed there), or from the last
            # "Suggest which personnel to include" run for a discipline lead. Shown
            # even if the user has since overridden the tick by hand, so they can see
            # what the recommendation was.
            if a.slot in resourcing.FIRM_MANAGEMENT_ROLES:
                st.caption(f"AI note: {resourcing.FIRM_LEADERSHIP_REASON}")
            else:
                _verdict = st.session_state.personnel_inclusion_suggestions.get(a.slot)
                if _verdict:
                    _stance = "Recommended" if _verdict.get("recommended") else "Not essential"
                    st.caption(f"AI note ({_stance}): {_verdict.get('reason', '')}")

            with st.expander("Details", expanded=False):
                if not (entry.get("name") or "").strip():
                    st.caption("Assign a name to this role above before adding profile details.")
                a.qualification = st.text_input("Qualification", value=a.qualification, key=f"prof_qual_{ekey}")
                a.rpeq_status = st.text_input("RPEQ / registration status", value=a.rpeq_status, key=f"prof_rpeq_{ekey}")
                a.years_experience = st.text_input("Years of experience", value=a.years_experience, key=f"prof_years_{ekey}")
                a.value_to_project = st.text_area(
                    f"On this project, {person_label} will...", value=a.value_to_project,
                    key=f"prof_value_{ekey}", height=70,
                )
                relevant_projects_text = st.text_area(
                    "Relevant project experience (one per line)",
                    value="\n".join(a.relevant_projects), key=f"prof_relproj_{ekey}", height=70,
                )
                a.relevant_projects = [line.strip() for line in relevant_projects_text.splitlines() if line.strip()]
                local_exp_text = st.text_area(
                    "Local district experience (one per line)",
                    value="\n".join(a.local_experience), key=f"prof_local_{ekey}", height=70,
                )
                a.local_experience = [line.strip() for line in local_exp_text.splitlines() if line.strip()]
                photo = st.file_uploader(
                    "Headshot (optional)", type=["png", "jpg", "jpeg"], key=f"prof_photo_{ekey}",
                    disabled=not (entry.get("name") or "").strip(),
                )
                if photo is not None and (entry.get("name") or "").strip():
                    st.session_state.personnel_photos[entry["name"]] = photo.getvalue()
                existing_profile_photo = st.session_state.personnel_photos.get((entry.get("name") or "").strip())
                if existing_profile_photo:
                    st.image(existing_profile_photo, width=120)

        st.divider()
        st.markdown("#### Project organisation chart")
        assigned = sum(1 for a in st.session_state.resource_plan if (a.person_name or "").strip())
        st.caption(f"{assigned} of {len(st.session_state.resource_plan)} slots assigned. Unassigned slots show as '[to be assigned]'.")
        if st.button("Generate org chart", type="primary"):
            png = org_chart.render_org_chart(
                st.session_state.resource_plan,
                theme_name=st.session_state.proposal_theme,
                project_title=st.session_state.tender_name or st.session_state.project_name or None,
            )
            st.session_state.org_chart_png = png
            if png:
                st.success("Org chart generated. It will be included in the Key Personnel area of the exported pack.")
            else:
                st.error("Could not render the org chart. Check that at least one role/discipline is present.")
        if st.session_state.org_chart_png:
            st.image(st.session_state.org_chart_png, use_container_width=True)


# ---------------------------------------------------------------------------
# Tab 9: Fee Estimate
# ---------------------------------------------------------------------------

with tabs[8]:
    st.subheader("Fees & Program" if _is_letter() else "Fee Estimate")

    if _is_letter():
        st.caption(
            "The discipline fee build-up ($ total) and discipline fee split (%) below, plus "
            "the delivery program, go straight into the pack (Export Pack). The scope-item fee "
            "table just below is for your own internal tracking only -- it is not exported."
        )
        analysis = st.session_state.analysis
        scope_items = analysis.scope_items if analysis else []
        if not scope_items:
            st.info("Run Tender Analysis to extract scope items first.")
        else:
            @st.fragment
            def _render_letter_scope_fee_table():
                # Same fragment-wrap rationale as the discipline table below -- see
                # _render_large_discipline_fee_table(). scope_items/analysis are
                # cheap to recompute here rather than relying on the outer
                # script's locals, since this fragment can rerun independently.
                analysis = st.session_state.analysis
                scope_items = analysis.scope_items if analysis else []
                st.markdown("#### Scope item fees")
                st.caption(fee_estimation_engine.SCOPE_FEE_SEED_NOTE)
                st.caption(
                    "How the starting figures are seeded: each scope item gets a weight of "
                    "1 + however many tasks it lists (so even a bare item with no tasks gets a "
                    "base share), then the ballpark total below is split across items in "
                    "proportion to that weight and rounded to the nearest $50. It's a rough "
                    "task-count proxy for effort, not a real estimate -- edit every row before "
                    "relying on it. This table is for your own internal tracking only; it is "
                    "**not** included in the exported pack -- the discipline fee split further "
                    "down (which mirrors the fee build-up table) is what's exported."
                )
                seed_col1, seed_col2 = st.columns([2, 1])
                with seed_col1:
                    st.number_input("Ballpark total project value ($, excl. GST)", min_value=0.0, step=500.0, key="fee_seed_total")
                with seed_col2:
                    st.write("")
                    if st.button("Seed fee table from total", type="primary"):
                        st.session_state.scope_item_fees = fee_estimation_engine.seed_scope_item_fees(
                            scope_items, st.session_state.fee_seed_total,
                        )

                if not st.session_state.scope_item_fees:
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                        fee_estimation_engine.seed_scope_item_fees(scope_items, None)
                    )
                    st.session_state._scope_fee_editor_version += 1
                else:
                    # Add any newly-extracted scope items (e.g. after a Tender Analysis
                    # re-run) without wiping rows the user has already priced, added, or
                    # renamed -- same "merge in new, never clobber edits" pattern as the
                    # discipline fee table below.
                    existing_titles = {f.item_title.strip().lower() for f in st.session_state.scope_item_fees}
                    for item in scope_items:
                        if item.title.strip().lower() not in existing_titles:
                            st.session_state.scope_item_fees.append(
                                fee_estimation_engine.ScopeItemFee(item_title=item.title, fee_amount=0.0,
                                                                   notes="Enter fee -- no estimate seeded")
                            )
                            # Force the data_editor below to actually pick up this new row --
                            # it ignores its `data` argument once its widget state already
                            # exists under a given key, so a merge alone would silently never
                            # show up until the key itself changes. See the state-defaults
                            # comment for _scope_fee_editor_version.
                            st.session_state._scope_fee_editor_version += 1
                    # Project Management is a fixed line item, additional to whatever
                    # deliverables Tender Analysis extracts -- re-add it if a fresh
                    # Tender Analysis run reset the list without it (first-time seed
                    # above already guarantees it; this covers older projects/state).
                    if not any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                               for f in st.session_state.scope_item_fees):
                        st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                            st.session_state.scope_item_fees
                        )
                        st.session_state._scope_fee_editor_version += 1

                # Built from st.session_state.scope_item_fees itself (not re-derived from
                # scope_items every rerun) so rows the user adds, renames, or deletes via
                # the editor below actually persist -- deliverables/activities aren't
                # locked to exactly what Tender Analysis extracted.
                fee_rows = [
                    {"item_title": f.item_title, "fee_amount": f.fee_amount, "notes": f.notes}
                    for f in st.session_state.scope_item_fees
                ]
                edited_fees = st.data_editor(
                    fee_rows, key=f"scope_fee_editor_v{st.session_state._scope_fee_editor_version}",
                    use_container_width=True, hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        "item_title": st.column_config.TextColumn("Scope item / deliverable", required=True),
                        "fee_amount": st.column_config.NumberColumn("Fee ($, excl. GST)", min_value=0.0, step=50.0, format="$%.0f"),
                        "notes": st.column_config.TextColumn("Notes"),
                    },
                )
                st.caption(
                    "To delete a row: tick the checkbox on its left, then either press "
                    "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
                    "above the table."
                )
                # Deferred apply -- same pattern as the discipline fee build-up
                # table's checkbox (see the comment there for the full
                # rationale). Rebuilding the model and re-adding Project
                # Management only happens once the user ticks the box, so
                # reruns while typing stay cheap.
                _scope_raw_sig = tuple(
                    (str(r.get("item_title") or ""), r.get("fee_amount"), str(r.get("notes") or ""))
                    for r in edited_fees
                )
                _scope_first_load = st.session_state.get("_scope_fee_last_applied_editor_sig") is None
                _scope_pending = _scope_raw_sig != st.session_state.get("_scope_fee_last_applied_editor_sig")
                _scope_tick_val = st.session_state.get("_scope_fee_apply_tick", False)
                _scope_tick_seen = st.session_state.get("_scope_fee_apply_tick_seen", False)
                if _scope_pending and _scope_tick_val and _scope_tick_seen:
                    st.session_state["_scope_fee_apply_tick"] = False
                scope_apply_now = st.checkbox(
                    "Done entering data -- refresh total",
                    key="_scope_fee_apply_tick",
                )
                st.session_state["_scope_fee_apply_tick_seen"] = scope_apply_now

                if _scope_first_load or (scope_apply_now and _scope_pending):
                    rebuilt_scope_fees = [
                        fee_estimation_engine.ScopeItemFee(
                            item_title=str(r.get("item_title") or "").strip(),
                            fee_amount=float(r.get("fee_amount") or 0), notes=str(r.get("notes") or ""),
                        )
                        for r in edited_fees
                        if str(r.get("item_title") or "").strip()
                    ]
                    # Project Management is a fixed line item -- if the user deleted it via
                    # the editor's own row-delete control, silently re-add it (mirrors the
                    # discipline fee table's "always re-add Project Management" behaviour).
                    _had_pm = any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                                  for f in rebuilt_scope_fees)
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(rebuilt_scope_fees)
                    if not _had_pm:
                        st.session_state._scope_fee_editor_version += 1
                        st.info("Project Management is a fixed line item and has been re-added.")
                    st.session_state._scope_fee_last_applied_editor_sig = _scope_raw_sig
                else:
                    st.caption(
                        "The total below is from the last time you ticked the box above -- "
                        "tick it again to bring it up to date."
                        if _scope_pending else
                        "The total below reflects the ticked data above."
                    )

                total = sum(f.fee_amount for f in st.session_state.scope_item_fees)
                st.markdown(f"**Total: ${total:,.0f}**")
                if any(f.fee_amount <= 0 for f in st.session_state.scope_item_fees):
                    st.warning("At least one scope item still has no fee entered -- the exported pack flags this in red until every row is priced.")

            _render_letter_scope_fee_table()

            st.divider()
            @st.fragment
            def _render_letter_discipline_fee_table():
                # Same fragment-wrap rationale as the Large Scope discipline
                # table -- see _render_large_discipline_fee_table().
                st.markdown("#### First-pass discipline fee build-up")
                st.caption(
                    "Your own first-pass fee per discipline, built from hours x rate -- the same "
                    "build-up as the Large Scope pack's Fee Estimate tab, and the same figures if "
                    "you switch a project between pack sizes. The table is seeded from the "
                    "disciplines the brief calls for, plus Project Management (always included). "
                    "Enter total hours and an hourly rate per discipline -- the Total column is "
                    "calculated automatically. A per-discipline total (not the hours/rates "
                    "themselves) is included in the exported pack's Fees section."
                )
                letter_brief_disc = st.session_state.analysis.disciplines_involved if st.session_state.analysis else []
                if st.session_state.get("dismissed_fee_disciplines") is None:
                    st.session_state.dismissed_fee_disciplines = []
                letter_dismissed_fee = {d.lower() for d in st.session_state.dismissed_fee_disciplines}

                if not st.session_state.discipline_fee_lines:
                    st.session_state.discipline_fee_lines = resourcing.seed_discipline_fee_lines(letter_brief_disc)
                    st.session_state._discipline_fee_editor_version += 1
                else:
                    existing_fee_discs = {resourcing.canonical_discipline(l.discipline) for l in st.session_state.discipline_fee_lines}
                    for disc in resourcing.required_disciplines(letter_brief_disc):
                        if disc not in existing_fee_discs and disc.lower() not in letter_dismissed_fee:
                            st.session_state.discipline_fee_lines.append(resourcing.DisciplineFeeLine(discipline=disc))
                            # Force the data_editor below to re-seed from the underlying
                            # data model -- it otherwise ignores its `data` argument once
                            # its widget state already exists under a given key. See the
                            # state-defaults comment for _discipline_fee_editor_version.
                            st.session_state._discipline_fee_editor_version += 1

                letter_disc_fee_rows = [
                    {
                        "discipline": l.discipline,
                        "total_hours": l.total_hours,
                        "rate_per_hour": l.rate_per_hour,
                        "total": l.fee_amount,
                        "note": l.note,
                    }
                    for l in st.session_state.discipline_fee_lines
                ]
                letter_before_discs = {r["discipline"].strip() for r in letter_disc_fee_rows if r["discipline"].strip()}

                letter_edited_disc_fees = st.data_editor(
                    letter_disc_fee_rows,
                    key=f"letter_discipline_fee_editor_v{st.session_state._discipline_fee_editor_version}",
                    use_container_width=True,
                    hide_index=True, num_rows="dynamic",
                    column_config={
                        "discipline": st.column_config.TextColumn("Discipline", required=True),
                        "total_hours": st.column_config.NumberColumn("Total hours", min_value=0.0, step=1.0, format="%.1f"),
                        "rate_per_hour": st.column_config.NumberColumn("Rate per hour ($)", min_value=0.0, step=5.0, format="$%.0f"),
                        "total": st.column_config.NumberColumn("Total ($, excl. GST)", format="$%.0f", disabled=True,
                                                                help="Calculated automatically -- total hours x rate per hour."),
                        "note": st.column_config.TextColumn("Note"),
                    },
                )
                st.caption(
                    "To delete a row: tick the checkbox on its left, then either press "
                    "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
                    "above the table."
                )
                # Deferred apply -- same rationale as the Large Scope discipline
                # table's checkbox (see the comment there): the rebuild and the
                # Excel/chart cache below only run once the user explicitly
                # ticks "done", instead of on every keystroke-commit, so most
                # reruns while typing stay cheap and the value-loss race has a
                # much smaller window to land in.
                letter_raw_sig = tuple(
                    (str(r.get("discipline") or ""), r.get("total_hours"), r.get("rate_per_hour"), str(r.get("note") or ""))
                    for r in letter_edited_disc_fees
                )
                letter_first_load = st.session_state.get("_letter_disc_fee_last_applied_editor_sig") is None
                letter_pending = letter_raw_sig != st.session_state.get("_letter_disc_fee_last_applied_editor_sig")
                # See the _disc_tick_seen comment on the Large Scope discipline
                # table for why this edge-detection flag is needed.
                letter_tick_val = st.session_state.get("_letter_disc_fee_apply_tick", False)
                letter_tick_seen = st.session_state.get("_letter_disc_fee_apply_tick_seen", False)
                if letter_pending and letter_tick_val and letter_tick_seen:
                    st.session_state["_letter_disc_fee_apply_tick"] = False
                letter_apply_now = st.checkbox(
                    "Done entering data -- refresh totals & chart",
                    key="_letter_disc_fee_apply_tick",
                )
                st.session_state["_letter_disc_fee_apply_tick_seen"] = letter_apply_now

                if letter_first_load or (letter_apply_now and letter_pending):
                    letter_rebuilt = [
                        resourcing.DisciplineFeeLine(
                            discipline=str(r.get("discipline") or "").strip(),
                            total_hours=float(r.get("total_hours") or 0),
                            rate_per_hour=float(r.get("rate_per_hour") or 0),
                            note=str(r.get("note") or ""),
                        )
                        for r in letter_edited_disc_fees
                        if str(r.get("discipline") or "").strip()
                    ]

                    letter_after_discs = {l.discipline for l in letter_rebuilt}
                    letter_removed_now = letter_before_discs - letter_after_discs
                    if letter_removed_now:
                        letter_newly_dismissed = {resourcing.canonical_discipline(d) for d in letter_removed_now if resourcing.canonical_discipline(d)}
                        st.session_state.dismissed_fee_disciplines = list(dict.fromkeys(
                            list(st.session_state.dismissed_fee_disciplines) + list(letter_newly_dismissed)
                        ))

                    letter_present = [l.discipline for l in letter_rebuilt]
                    letter_missing_always = set(resourcing.ensure_project_management_present(letter_present)) - set(letter_present)
                    for missing in letter_missing_always:
                        letter_rebuilt.append(resourcing.DisciplineFeeLine(discipline=missing,
                                                                            note="Always included -- re-added automatically"))
                    if letter_missing_always:
                        # The user deleted Project Management via the editor's row-delete
                        # control -- it's being silently re-added to the data model, but the
                        # editor widget itself won't show it again until its key changes.
                        st.session_state._discipline_fee_editor_version += 1
                    st.session_state.discipline_fee_lines = letter_rebuilt
                    st.session_state._letter_disc_fee_last_applied_editor_sig = letter_raw_sig
                else:
                    st.caption(
                        "Totals, the chart, and the Excel export below are from the last time "
                        "you ticked the box above -- tick it again to bring them up to date."
                        if letter_pending else
                        "Totals, the chart, and the Excel export below reflect the ticked data above."
                    )

                # Always display from the applied model (session_state) -- see
                # the same note on the Large Scope discipline table.
                letter_rebuilt = st.session_state.discipline_fee_lines

                letter_disc_total = sum(l.fee_amount for l in letter_rebuilt)
                letter_total_hours_all = sum(l.total_hours for l in letter_rebuilt)
                letter_avg_rate = (letter_disc_total / letter_total_hours_all) if letter_total_hours_all else None
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    st.markdown(f"**Discipline fee total: ${letter_disc_total:,.0f}**")
                with bcol2:
                    st.markdown(f"**Average rate across project: {f'${letter_avg_rate:,.0f}/hr' if letter_avg_rate else '-- (enter hours to calculate)'}**")
                if not any(resourcing.canonical_discipline(l.discipline) == resourcing.ALWAYS_INCLUDED_DISCIPLINE
                           or l.discipline.strip().lower() == resourcing.ALWAYS_INCLUDED_DISCIPLINE.lower()
                           for l in letter_rebuilt):
                    st.info("Project Management is always part of the fee build-up and has been re-added.")

                # Cached the same way as the Large Scope discipline table --
                # see the comment on _disc_fee_cache_sig there for why (skips
                # redoing the Excel/chart work when the figures haven't
                # actually changed, which also shrinks the edit-commit race
                # window between this fragment rerun and the next one).
                _letter_disc_signature = tuple((l.discipline, l.total_hours, l.rate_per_hour, l.note) for l in letter_rebuilt)
                if st.session_state.get("_letter_disc_fee_cache_sig") != _letter_disc_signature:
                    st.session_state._letter_disc_fee_cache_sig = _letter_disc_signature
                    st.session_state._letter_disc_fee_cache_xlsx = resourcing.discipline_fee_lines_to_excel(
                        letter_rebuilt, theme_name=st.session_state.proposal_theme)
                    st.session_state._letter_disc_fee_cache_pie = graphics_engine.generate_fee_distribution_pie(
                        [(l.discipline, l.fee_amount) for l in letter_rebuilt],
                        "Fee distribution by discipline (hours x rate)",
                    )
                letter_hours_xlsx = st.session_state._letter_disc_fee_cache_xlsx
                letter_hours_pie_png = st.session_state._letter_disc_fee_cache_pie
                if letter_hours_xlsx:
                    st.download_button(
                        "Export to Excel", data=letter_hours_xlsx, key="letter_download_hours_fee_xlsx",
                        file_name="discipline_fee_build_up.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        help="Includes a Total row and the average rate across the project (total fee / total hours).",
                     type="primary")
                else:
                    st.caption("Excel export needs the 'openpyxl' package -- run `pip install openpyxl` and reload.")

                if letter_hours_pie_png:
                    st.image(letter_hours_pie_png, use_container_width=True)

            _render_letter_discipline_fee_table()

            st.divider()
            st.markdown("#### Delivery program")
            pcol1, pcol2 = st.columns([2, 1])
            with pcol1:
                st.number_input("Number of weeks", min_value=1, max_value=52, step=1, key="program_num_weeks")
            with pcol2:
                st.write("")
                if st.button("Generate default program", type="primary"):
                    st.session_state.program_schedule = program_schedule.build_default_program(
                        scope_items, st.session_state.program_num_weeks,
                    )
                    st.session_state.program_week_labels = [f"Wk {i + 1}" for i in range(st.session_state.program_num_weeks)]

            if st.session_state.program_schedule:
                labels = st.session_state.program_week_labels
                program_rows = [
                    {"Scope item": title, **{lbl: bool(v) for lbl, v in zip(labels, active)}}
                    for title, active in st.session_state.program_schedule.items()
                ]
                column_config = {"Scope item": st.column_config.TextColumn("Scope item", disabled=True)}
                for lbl in labels:
                    column_config[lbl] = st.column_config.CheckboxColumn(lbl)
                edited_program = st.data_editor(
                    program_rows, key="program_editor", use_container_width=True, hide_index=True,
                    column_config=column_config,
                )
                st.session_state.program_schedule = {
                    r["Scope item"]: [bool(r[lbl]) for lbl in labels] for r in edited_program
                }
            else:
                st.info("Click 'Generate default program' for an editable starting grid, sized by how many tasks each scope item lists -- adjust the weeks freely afterwards.")

        st.divider()
        @st.fragment
        def _render_letter_pct_fee_table():
            # Wrapped in its own fragment (this used to rerun the entire ~3800-line
            # script on every keystroke, with no caching at all on the Excel/chart
            # regen below -- the worst case of the edit-commit race across all the
            # fee tables). See _render_large_discipline_fee_table() for the general
            # rationale.
            with st.expander("Discipline fee split (%) -- this is what's exported", expanded=False):
                st.caption(
                    "This Fee % table is what actually goes into the exported pack's Fees section "
                    "(the old scope-item fee table above no longer is). Its discipline list always "
                    "matches the discipline fee build-up table above -- add or remove disciplines "
                    "up there, not here."
                )
                st.warning(fee_estimation_engine.INDICATIVE_NOTE)

                letter_buildup_discs = [l.discipline for l in st.session_state.discipline_fee_lines]
                letter_buildup_total = sum(l.fee_amount for l in st.session_state.discipline_fee_lines)

                # Prepopulate the total from the discipline fee build-up the first time
                # this is used (0.0 = "not yet set") -- after that it's an independent
                # figure the user can edit freely, even if the build-up total changes
                # later, rather than staying permanently locked to it.
                if not st.session_state.letter_fee_total_override and letter_buildup_total:
                    st.session_state.letter_fee_total_override = letter_buildup_total

                st.number_input(
                    "Total project fee ($, excl. GST) -- used to convert Fee % into a $ figure below",
                    min_value=0.0, step=1000.0, key="letter_fee_total_override",
                    help="Starts prepopulated from the discipline fee build-up total above, then "
                         "stays independently editable -- change it here to use a different total "
                         "for this % split's $ column, Excel export, and chart only. Doesn't change "
                         "the build-up table itself.",
                )
                letter_fee_total = st.session_state.letter_fee_total_override

                def _letter_reconcile_estimates(estimates):
                    by_disc = {resourcing.canonical_discipline(e.discipline): e for e in (estimates or [])}
                    reconciled = []
                    for disc in letter_buildup_discs:
                        key = resourcing.canonical_discipline(disc)
                        existing = by_disc.get(key)
                        if existing is not None:
                            reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                                discipline=disc, fee_percentage=existing.fee_percentage,
                                source=existing.source, confidence=existing.confidence,
                            ))
                        else:
                            reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                                discipline=disc, fee_percentage=0.0, source="", confidence="",
                            ))
                    return reconciled

                bcol1, bcol2, bcol3 = st.columns(3)
                with bcol1:
                    if st.button("Reset % from discipline fee build-up", key="letter_reset_from_buildup_btn", type="primary"):
                        if letter_buildup_total > 0:
                            st.session_state.fee_estimates = [
                                fee_estimation_engine.DisciplineFeeEstimate(
                                    discipline=l.discipline,
                                    fee_percentage=round(l.fee_amount / letter_buildup_total * 100, 1),
                                    source="From discipline fee build-up",
                                    confidence="User-set",
                                )
                                for l in st.session_state.discipline_fee_lines
                            ]
                        else:
                            st.warning("Enter hours and rates in the discipline fee build-up table above first.")
                with bcol2:
                    if st.button("Estimate from bundled benchmarks", key="letter_benchmark_btn", type="primary"):
                        fee_cap = st.session_state.analysis.fee_cap if st.session_state.analysis else None
                        estimates = fee_estimation_engine.estimate_fee_split(st.session_state.project_type, fee_cap)
                        st.session_state.fee_estimates = _letter_reconcile_estimates(estimates)
                with bcol3:
                    refresh_ready = bool(st.session_state.ai_config.get("api_key"))
                    if st.button("Refresh via AI knowledge (not a live web fetch)", disabled=not refresh_ready, key="letter_refresh_btn", type="primary"):
                        fee_cap = st.session_state.analysis.fee_cap if st.session_state.analysis else None
                        with st.spinner("Asking the AI provider for its knowledge of published benchmarks..."):
                            estimates = fee_estimation_engine.refresh_estimate_from_web(
                                st.session_state.project_type, letter_buildup_discs, fee_cap, st.session_state.ai_config,
                            )
                        st.session_state.fee_estimates = _letter_reconcile_estimates(estimates)

                st.session_state.fee_estimates = _letter_reconcile_estimates(st.session_state.fee_estimates)

                letter_fee_pct_rows = [
                    {
                        "discipline": e.discipline,
                        "fee_percentage": e.fee_percentage,
                        "indicative_amount": (f"${letter_fee_total * e.fee_percentage / 100:,.0f}"
                                               if letter_fee_total else "-"),
                        "confidence": e.confidence,
                        "source": e.source,
                    }
                    for e in st.session_state.fee_estimates
                ]
                letter_edited_pct = st.data_editor(
                    letter_fee_pct_rows, key="letter_fee_pct_editor", use_container_width=True, hide_index=True,
                    column_config={
                        "discipline": st.column_config.TextColumn("Discipline", disabled=True),
                        "fee_percentage": st.column_config.NumberColumn("Fee %", min_value=0.0, max_value=100.0, step=0.5, format="%.1f%%"),
                        "indicative_amount": st.column_config.TextColumn(
                            "Indicative $", disabled=True,
                            help="Fee % x the total project fee entered above -- recalculated automatically.",
                        ),
                        "confidence": st.column_config.TextColumn("Confidence"),
                        "source": st.column_config.TextColumn("Source"),
                    },
                )

                # Deferred apply -- same pattern as the discipline fee build-up
                # table's checkbox (see the comment there for the full rationale).
                # The three buttons above are unaffected -- they're deliberate,
                # single-click actions, not rapid per-keystroke edits, so they
                # still take effect immediately.
                letter_pct_raw_sig = tuple(
                    (r.get("discipline"), r.get("fee_percentage"), r.get("confidence"), r.get("source"))
                    for r in letter_edited_pct
                )
                letter_pct_first_load = st.session_state.get("_letter_pct_fee_last_applied_editor_sig") is None
                letter_pct_pending = letter_pct_raw_sig != st.session_state.get("_letter_pct_fee_last_applied_editor_sig")
                letter_pct_tick_val = st.session_state.get("_letter_pct_fee_apply_tick", False)
                letter_pct_tick_seen = st.session_state.get("_letter_pct_fee_apply_tick_seen", False)
                if letter_pct_pending and letter_pct_tick_val and letter_pct_tick_seen:
                    st.session_state["_letter_pct_fee_apply_tick"] = False
                letter_pct_apply_now = st.checkbox(
                    "Done entering data -- refresh totals & chart",
                    key="_letter_pct_fee_apply_tick",
                )
                st.session_state["_letter_pct_fee_apply_tick_seen"] = letter_pct_apply_now

                if letter_pct_first_load or (letter_pct_apply_now and letter_pct_pending):
                    st.session_state.fee_estimates = [
                        fee_estimation_engine.DisciplineFeeEstimate(
                            discipline=r["discipline"], fee_percentage=float(r["fee_percentage"] or 0),
                            confidence=r["confidence"] or "", source=r["source"] or "",
                        )
                        for r in letter_edited_pct
                    ]
                    st.session_state._letter_pct_fee_last_applied_editor_sig = letter_pct_raw_sig
                else:
                    st.caption(
                        "Totals, the chart, and the Excel export below are from the last time "
                        "you ticked the box above -- tick it again to bring them up to date."
                        if letter_pct_pending else
                        "Totals, the chart, and the Excel export below reflect the ticked data above."
                    )

                letter_pct_total = sum(e.fee_percentage for e in st.session_state.fee_estimates)
                st.caption(f"Total: {letter_pct_total:.1f}% (doesn't need to sum to exactly 100%).")

                _letter_pct_indicative_amounts = {
                    e.discipline: (letter_fee_total * e.fee_percentage / 100 if letter_fee_total else None)
                    for e in st.session_state.fee_estimates
                }
                letter_pct_xlsx = fee_estimation_engine.fee_estimates_to_excel(
                    st.session_state.fee_estimates,
                    indicative_amounts=_letter_pct_indicative_amounts,
                    theme_name=st.session_state.proposal_theme,
                )
                if letter_pct_xlsx:
                    st.download_button(
                        "Export to Excel", data=letter_pct_xlsx, key="letter_download_pct_fee_xlsx",
                        file_name="indicative_fee_split.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     type="primary")
                else:
                    st.caption("Excel export needs the 'openpyxl' package -- run `pip install openpyxl` and reload.")

                # Chart the $ split once a total is available (matches the $ column and
                # Excel export); otherwise chart the raw percentages.
                if letter_fee_total > 0:
                    letter_pie_items = [(e.discipline, _letter_pct_indicative_amounts.get(e.discipline) or 0) for e in st.session_state.fee_estimates]
                    letter_pie_fmt = lambda v: f"${v:,.0f}"
                    letter_pie_legend_value = "raw"
                else:
                    letter_pie_items = [(e.discipline, e.fee_percentage) for e in st.session_state.fee_estimates]
                    letter_pie_fmt = lambda v: f"{v:.0f}%"
                    letter_pie_legend_value = "share"
                letter_pie_png = graphics_engine.generate_fee_distribution_pie(
                    letter_pie_items, "Discipline fee split", value_fmt=letter_pie_fmt,
                    legend_value=letter_pie_legend_value,
                )
                if letter_pie_png:
                    st.image(letter_pie_png, use_container_width=True)

        _render_letter_pct_fee_table()
    else:
        @st.fragment
        def _render_large_discipline_fee_table():
            # Wrapped in a fragment so editing a cell only reruns this table
            # (fast, in place) instead of the whole ~3700-line script -- without
            # this, each keystroke-commit reruns everything (every other tab's
            # code, every chart) which is slow enough that fast typing across
            # cells can land before the previous rerun finishes and get
            # silently dropped when the widget remounts. Downstream sections
            # (the "Indicative fee split" below) read st.session_state
            # .discipline_fee_lines directly rather than a local variable here,
            # since this fragment can rerun on its own without the rest of the
            # script -- they'll pick up the latest values on their own next full
            # rerun (e.g. switching tabs).
            st.markdown("#### First-pass discipline fee build-up")
            st.caption(
                "Your own first-pass fee per discipline, built from hours x rate. The table is "
                "seeded from the disciplines the brief calls for, plus Project Management (always "
                "included). Enter total hours and an hourly rate per discipline -- the Total column "
                "is calculated automatically, not typed in directly. Add or remove rows as needed -- "
                "these are your figures, not an AI estimate."
            )
            brief_disc = st.session_state.analysis.disciplines_involved if st.session_state.analysis else []
            if st.session_state.get("dismissed_fee_disciplines") is None:
                st.session_state.dismissed_fee_disciplines = []
            dismissed_fee = {d.lower() for d in st.session_state.dismissed_fee_disciplines}

            if not st.session_state.discipline_fee_lines:
                st.session_state.discipline_fee_lines = resourcing.seed_discipline_fee_lines(brief_disc)
                st.session_state._discipline_fee_editor_version += 1
            else:
                # Add any newly-required disciplines (e.g. after a Tender Analysis re-run
                # picks up more of them) without wiping existing entries -- but never
                # re-add one the user explicitly removed from this table.
                existing_fee_discs = {resourcing.canonical_discipline(l.discipline) for l in st.session_state.discipline_fee_lines}
                for disc in resourcing.required_disciplines(brief_disc):
                    if disc not in existing_fee_discs and disc.lower() not in dismissed_fee:
                        st.session_state.discipline_fee_lines.append(resourcing.DisciplineFeeLine(discipline=disc))
                        # Force the data_editor below to re-seed from the underlying data
                        # model -- it otherwise ignores its `data` argument once its
                        # widget state already exists under a given key. See the
                        # state-defaults comment for _discipline_fee_editor_version.
                        st.session_state._discipline_fee_editor_version += 1

            disc_fee_rows = [
                {
                    "discipline": l.discipline,
                    "total_hours": l.total_hours,
                    "rate_per_hour": l.rate_per_hour,
                    "total": l.fee_amount,
                    "note": l.note,
                }
                for l in st.session_state.discipline_fee_lines
            ]
            before_discs = {r["discipline"].strip() for r in disc_fee_rows if r["discipline"].strip()}

            edited_disc_fees = st.data_editor(
                disc_fee_rows, key=f"discipline_fee_editor_v{st.session_state._discipline_fee_editor_version}",
                use_container_width=True,
                hide_index=True, num_rows="dynamic",
                column_config={
                    "discipline": st.column_config.TextColumn("Discipline", required=True),
                    "total_hours": st.column_config.NumberColumn("Total hours", min_value=0.0, step=1.0, format="%.1f"),
                    "rate_per_hour": st.column_config.NumberColumn("Rate per hour ($)", min_value=0.0, step=5.0, format="$%.0f"),
                    "total": st.column_config.NumberColumn("Total ($, excl. GST)", format="$%.0f", disabled=True,
                                                            help="Calculated automatically -- total hours x rate per hour."),
                    "note": st.column_config.TextColumn("Note"),
                },
            )
            st.caption(
                "To delete a row: tick the checkbox on its left, then either press "
                "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
                "above the table."
            )
            # Deferred apply: rebuilding the model (dedup/dismiss logic) and
            # regenerating the Excel export + pie chart on literally every
            # keystroke-commit was a big contributor to the intermittent
            # value-loss race in this grid -- every rerun while the user was
            # actively typing did real work server-side, widening the window
            # in which a second, fast edit could race the round trip and get
            # silently dropped. Now, reruns while editing do nothing but hold
            # the editor's own state (cheap); the heavier rebuild only runs
            # once, on a deliberate, separate action -- ticking this box --
            # well after typing has settled. Any further edit auto-unticks
            # it, so stale numbers can't linger unnoticed.
            _disc_raw_sig = tuple(
                (str(r.get("discipline") or ""), r.get("total_hours"), r.get("rate_per_hour"), str(r.get("note") or ""))
                for r in edited_disc_fees
            )
            _disc_first_load = st.session_state.get("_disc_fee_last_applied_editor_sig") is None
            _disc_pending = _disc_raw_sig != st.session_state.get("_disc_fee_last_applied_editor_sig")
            # Distinguish "the user just ticked the box this rerun" (must NOT
            # be reset -- that's the click we want to act on) from "the box
            # was already ticked from a previous apply, and a fresh edit
            # since then has made it stale" (SHOULD be reset). Both look
            # identical as (pending=True, tick=True) at the top of a rerun,
            # so _disc_fee_apply_tick_seen tracks whether the tick was
            # already True as of the end of the *previous* rerun -- only
            # then is it safe to call it stale.
            _disc_tick_val = st.session_state.get("_disc_fee_apply_tick", False)
            _disc_tick_seen = st.session_state.get("_disc_fee_apply_tick_seen", False)
            if _disc_pending and _disc_tick_val and _disc_tick_seen:
                st.session_state["_disc_fee_apply_tick"] = False
            disc_apply_now = st.checkbox(
                "Done entering data -- refresh totals & chart",
                key="_disc_fee_apply_tick",
            )
            st.session_state["_disc_fee_apply_tick_seen"] = disc_apply_now

            if _disc_first_load or (disc_apply_now and _disc_pending):
                # Rebuild from the editor, dropping blank-discipline rows, then guarantee
                # Project Management is present even if the user deleted it.
                rebuilt = [
                    resourcing.DisciplineFeeLine(
                        discipline=str(r.get("discipline") or "").strip(),
                        total_hours=float(r.get("total_hours") or 0),
                        rate_per_hour=float(r.get("rate_per_hour") or 0),
                        note=str(r.get("note") or ""),
                    )
                    for r in edited_disc_fees
                    if str(r.get("discipline") or "").strip()
                ]

                # A discipline present before this edit but missing after it was removed
                # via the editor's own delete-row control -- remember that so the
                # brief-sync merge above doesn't just re-add it on the next rerun.
                after_discs = {l.discipline for l in rebuilt}
                removed_now = before_discs - after_discs
                if removed_now:
                    newly_dismissed = {resourcing.canonical_discipline(d) for d in removed_now if resourcing.canonical_discipline(d)}
                    st.session_state.dismissed_fee_disciplines = list(dict.fromkeys(
                        list(st.session_state.dismissed_fee_disciplines) + list(newly_dismissed)
                    ))

                present = [l.discipline for l in rebuilt]
                missing_always = set(resourcing.ensure_project_management_present(present)) - set(present)
                for missing in missing_always:
                    rebuilt.append(resourcing.DisciplineFeeLine(discipline=missing,
                                                                note="Always included -- re-added automatically"))
                if missing_always:
                    # The user deleted Project Management via the editor's row-delete
                    # control -- it's being silently re-added to the data model, but the
                    # editor widget itself won't show it again until its key changes.
                    st.session_state._discipline_fee_editor_version += 1
                st.session_state.discipline_fee_lines = rebuilt
                st.session_state._disc_fee_last_applied_editor_sig = _disc_raw_sig
            else:
                st.caption(
                    "Totals, the chart, and the Excel export below are from the last time "
                    "you ticked the box above -- tick it again to bring them up to date."
                    if _disc_pending else
                    "Totals, the chart, and the Excel export below reflect the ticked data above."
                )

            # Always display from the applied model (session_state), not a
            # freshly-rebuilt local var -- until the box above is (re)ticked,
            # this intentionally still shows the last-applied figures even
            # though the editor itself may have newer, unapplied edits in it.
            rebuilt = st.session_state.discipline_fee_lines

            disc_total = sum(l.fee_amount for l in rebuilt)
            total_hours_all = sum(l.total_hours for l in rebuilt)
            # The blended rate across the whole project (total fee / total hours) --
            # the key sanity-check figure for whether the priced hours/rates make
            # sense in aggregate, not just discipline by discipline.
            avg_rate = (disc_total / total_hours_all) if total_hours_all else None
            mcol1, mcol2 = st.columns(2)
            with mcol1:
                st.markdown(f"**Discipline fee total: ${disc_total:,.0f}**")
            with mcol2:
                st.markdown(f"**Average rate across project: {f'${avg_rate:,.0f}/hr' if avg_rate else '-- (enter hours to calculate)'}**")
            if not any(resourcing.canonical_discipline(l.discipline) == resourcing.ALWAYS_INCLUDED_DISCIPLINE
                       or l.discipline.strip().lower() == resourcing.ALWAYS_INCLUDED_DISCIPLINE.lower()
                       for l in rebuilt):
                st.info("Project Management is always part of the fee build-up and has been re-added.")

            # The Excel export and pie chart are regenerated from `rebuilt` --
            # both are real work (openpyxl workbook + matplotlib render), and
            # without caching that ran again on literally every keystroke
            # commit, even ones that don't touch these disciplines at all.
            # That's wasted time on its own, but it also matters for
            # correctness: it's extra wall-clock inside this fragment's rerun,
            # which widens the window in which a second, fast edit (typing
            # into the next row before this rerun settles) can race the
            # server round-trip and have its own value overwritten by a
            # stale re-render. Skipping the regen when the underlying figures
            # haven't changed since the last render shrinks that window.
            # Keyed by a plain tuple signature (not an object identity) so it
            # survives across reruns via session_state.
            _disc_signature = tuple((l.discipline, l.total_hours, l.rate_per_hour, l.note) for l in rebuilt)
            if st.session_state.get("_disc_fee_cache_sig") != _disc_signature:
                st.session_state._disc_fee_cache_sig = _disc_signature
                st.session_state._disc_fee_cache_xlsx = resourcing.discipline_fee_lines_to_excel(
                    rebuilt, theme_name=st.session_state.proposal_theme)
                st.session_state._disc_fee_cache_pie = graphics_engine.generate_fee_distribution_pie(
                    [(l.discipline, l.fee_amount) for l in rebuilt],
                    "Fee distribution by discipline (hours x rate)",
                )
            hours_xlsx = st.session_state._disc_fee_cache_xlsx
            hours_pie_png = st.session_state._disc_fee_cache_pie
            if hours_xlsx:
                st.download_button(
                    "Export to Excel", data=hours_xlsx, key="download_hours_fee_xlsx",
                    file_name="discipline_fee_build_up.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    help="Includes a Total row and the average rate across the project (total fee / total hours).",
                 type="primary")
            else:
                st.caption("Excel export needs the 'openpyxl' package -- run `pip install openpyxl` and reload.")

            if hours_pie_png:
                st.image(hours_pie_png, use_container_width=True)
            else:
                st.caption("Enter hours and a rate for at least one discipline above to see the fee distribution chart.")

        _render_large_discipline_fee_table()

        st.divider()
        @st.fragment
        def _render_large_scope_fee_table():
            # Same fragment-wrap rationale as the discipline table above -- see
            # _render_large_discipline_fee_table().
            st.markdown("#### Scope item / deliverable fee build-up")
            _large_scope_items = st.session_state.analysis.scope_items if st.session_state.analysis else []
            if not _large_scope_items:
                st.info("Run Tender Analysis to extract scope items and deliverables first.")
            else:
                st.caption(fee_estimation_engine.SCOPE_FEE_SEED_NOTE)
                st.caption(
                    "Prepopulated with the scope items/deliverables extracted from the brief, "
                    "one row each, so there's a real starting list to price rather than a blank "
                    "table -- edit, rename, delete, or add rows freely; nothing here is exported "
                    "automatically (the discipline build-up above is what feeds the pack)."
                )
                if not st.session_state.scope_item_fees:
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                        fee_estimation_engine.seed_scope_item_fees(_large_scope_items, None)
                    )
                    st.session_state._large_scope_fee_editor_version += 1
                else:
                    _existing_titles = {f.item_title.strip().lower() for f in st.session_state.scope_item_fees}
                    for _item in _large_scope_items:
                        if _item.title.strip().lower() not in _existing_titles:
                            st.session_state.scope_item_fees.append(
                                fee_estimation_engine.ScopeItemFee(item_title=_item.title, fee_amount=0.0,
                                                                   notes="Enter fee -- no estimate seeded")
                            )
                            # Force the data_editor below to re-seed from the underlying
                            # data model -- it otherwise ignores its `data` argument once
                            # its widget state already exists under a given key. See the
                            # state-defaults comment for _large_scope_fee_editor_version.
                            st.session_state._large_scope_fee_editor_version += 1
                    # Project Management is a fixed line item, additional to whatever
                    # deliverables Tender Analysis extracts -- re-add it if missing.
                    if not any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                               for f in st.session_state.scope_item_fees):
                        st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                            st.session_state.scope_item_fees
                        )
                        st.session_state._large_scope_fee_editor_version += 1

                _large_fee_rows = [
                    {"item_title": f.item_title, "fee_amount": f.fee_amount, "notes": f.notes}
                    for f in st.session_state.scope_item_fees
                ]
                _large_edited_fees = st.data_editor(
                    _large_fee_rows,
                    key=f"large_scope_fee_editor_v{st.session_state._large_scope_fee_editor_version}",
                    use_container_width=True, hide_index=True,
                    num_rows="dynamic",
                    column_config={
                        "item_title": st.column_config.TextColumn("Scope item / deliverable", required=True),
                        "fee_amount": st.column_config.NumberColumn("Fee ($, excl. GST)", min_value=0.0, step=50.0, format="$%.0f"),
                        "notes": st.column_config.TextColumn("Notes"),
                    },
                )
                st.caption(
                    "To delete a row: tick the checkbox on its left, then either press "
                    "Delete/Backspace on your keyboard or click the 🗑 icon that appears "
                    "above the table."
                )
                # Deferred apply -- same pattern as the discipline fee build-up
                # table's checkbox (see the comment there for the full
                # rationale).
                _large_scope_raw_sig = tuple(
                    (str(r.get("item_title") or ""), r.get("fee_amount"), str(r.get("notes") or ""))
                    for r in _large_edited_fees
                )
                _large_scope_first_load = st.session_state.get("_large_scope_fee_last_applied_editor_sig") is None
                _large_scope_pending = _large_scope_raw_sig != st.session_state.get("_large_scope_fee_last_applied_editor_sig")
                _large_scope_tick_val = st.session_state.get("_large_scope_fee_apply_tick", False)
                _large_scope_tick_seen = st.session_state.get("_large_scope_fee_apply_tick_seen", False)
                if _large_scope_pending and _large_scope_tick_val and _large_scope_tick_seen:
                    st.session_state["_large_scope_fee_apply_tick"] = False
                large_scope_apply_now = st.checkbox(
                    "Done entering data -- refresh total",
                    key="_large_scope_fee_apply_tick",
                )
                st.session_state["_large_scope_fee_apply_tick_seen"] = large_scope_apply_now

                if _large_scope_first_load or (large_scope_apply_now and _large_scope_pending):
                    _large_rebuilt_scope_fees = [
                        fee_estimation_engine.ScopeItemFee(
                            item_title=str(r.get("item_title") or "").strip(),
                            fee_amount=float(r.get("fee_amount") or 0), notes=str(r.get("notes") or ""),
                        )
                        for r in _large_edited_fees
                        if str(r.get("item_title") or "").strip()
                    ]
                    # Project Management is a fixed line item -- if the user deleted it via
                    # the editor's own row-delete control, silently re-add it.
                    _large_had_pm = any(f.item_title.strip().lower() == fee_estimation_engine.ALWAYS_INCLUDED_ITEM.lower()
                                        for f in _large_rebuilt_scope_fees)
                    st.session_state.scope_item_fees = fee_estimation_engine.ensure_project_management_present(
                        _large_rebuilt_scope_fees
                    )
                    if not _large_had_pm:
                        st.session_state._large_scope_fee_editor_version += 1
                        st.info("Project Management is a fixed line item and has been re-added.")
                    st.session_state._large_scope_fee_last_applied_editor_sig = _large_scope_raw_sig
                else:
                    st.caption(
                        "The total below is from the last time you ticked the box above -- "
                        "tick it again to bring it up to date."
                        if _large_scope_pending else
                        "The total below reflects the ticked data above."
                    )

                _large_scope_fee_total = sum(f.fee_amount for f in st.session_state.scope_item_fees)
                st.markdown(f"**Total: ${_large_scope_fee_total:,.0f}**")

        _render_large_scope_fee_table()

        st.divider()
        st.markdown("#### Delivery program")
        st.caption(
            "A starting delivery schedule across your scope items. Unlike the Small Scope "
            "pack, this isn't embedded in the DOCX -- download it as an editable PowerPoint "
            "table from the Export Pack tab instead, to paste into a program/methodology slide."
        )
        pcol1, pcol2 = st.columns([2, 1])
        with pcol1:
            st.number_input("Number of weeks", min_value=1, max_value=52, step=1, key="program_num_weeks")
        with pcol2:
            st.write("")
            if st.button("Generate default program", type="primary"):
                st.session_state.program_schedule = program_schedule.build_default_program(
                    st.session_state.analysis.scope_items if st.session_state.analysis else [],
                    st.session_state.program_num_weeks,
                )
                st.session_state.program_week_labels = [f"Wk {i + 1}" for i in range(st.session_state.program_num_weeks)]

        if st.session_state.program_schedule:
            labels = st.session_state.program_week_labels
            program_rows = [
                {"Scope item": title, **{lbl: bool(v) for lbl, v in zip(labels, active)}}
                for title, active in st.session_state.program_schedule.items()
            ]
            program_column_config = {"Scope item": st.column_config.TextColumn("Scope item", disabled=True)}
            for lbl in labels:
                program_column_config[lbl] = st.column_config.CheckboxColumn(lbl)
            edited_program = st.data_editor(
                program_rows, key="program_editor", use_container_width=True, hide_index=True,
                column_config=program_column_config,
            )
            st.session_state.program_schedule = {
                r["Scope item"]: [bool(r[lbl]) for lbl in labels] for r in edited_program
            }
        else:
            st.info("Click 'Generate default program' for an editable starting grid, sized by how many tasks each scope item lists -- adjust the weeks freely afterwards.")

        st.divider()
        @st.fragment
        def _render_large_pct_fee_table():
            # Wrapped in its own fragment -- this used to rerun the entire
            # ~3900-line script on every keystroke, with no caching at all on
            # the Excel/chart regen below. See _render_large_discipline_fee_table()
            # for the general rationale.
            st.markdown("#### Indicative fee split by discipline")
            st.caption(
                "Its discipline list always matches the discipline fee build-up table above -- add "
                "or remove disciplines up there, not here. Fee % is directly editable below; reset "
                "it from the build-up's own $ split, or seed it from the benchmark/AI buttons "
                "(remapped onto the build-up's discipline list either way)."
            )
            st.warning(fee_estimation_engine.INDICATIVE_NOTE)

            # Read from session_state rather than the discipline-table block's own
            # `rebuilt` local (that block is a separate, self-contained
            # @st.fragment, so its locals aren't in scope here) -- equivalent,
            # since that fragment always writes its result to
            # st.session_state.discipline_fee_lines before returning.
            buildup_discs = [l.discipline for l in st.session_state.discipline_fee_lines]
            buildup_total = sum(l.fee_amount for l in st.session_state.discipline_fee_lines)

            # Prepopulate the total from the discipline fee build-up the first time
            # this is used (0.0 = "not yet set") -- after that it's an independent
            # figure the user can edit freely, even if the build-up total changes
            # later, rather than staying permanently locked to it. Same pattern as
            # the Small Scope pack's letter_fee_total_override, below.
            if not st.session_state.fee_estimate_manual_total and buildup_total:
                st.session_state.fee_estimate_manual_total = buildup_total

            st.number_input(
                "Total project fee ($, excl. GST) -- optional",
                min_value=0.0, step=1000.0, key="fee_estimate_manual_total",
                help="Starts prepopulated from the discipline fee build-up total above, then stays "
                     "independently editable -- change it here to use a different total for this "
                     "split's $ column, Excel export, and chart only. Doesn't change the build-up "
                     "table itself.",
            )
            manual_total = st.session_state.fee_estimate_manual_total

            def _reconcile_estimates(estimates):
                by_disc = {resourcing.canonical_discipline(e.discipline): e for e in (estimates or [])}
                reconciled = []
                for disc in buildup_discs:
                    key = resourcing.canonical_discipline(disc)
                    existing = by_disc.get(key)
                    if existing is not None:
                        reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                            discipline=disc, fee_percentage=existing.fee_percentage,
                            source=existing.source, confidence=existing.confidence,
                        ))
                    else:
                        reconciled.append(fee_estimation_engine.DisciplineFeeEstimate(
                            discipline=disc, fee_percentage=0.0, source="", confidence="",
                        ))
                return reconciled

            bcol1, bcol2, bcol3 = st.columns(3)
            with bcol1:
                if st.button("Reset % from discipline fee build-up", key="reset_from_buildup_btn", type="primary"):
                    if buildup_total > 0:
                        st.session_state.fee_estimates = [
                            fee_estimation_engine.DisciplineFeeEstimate(
                                discipline=l.discipline,
                                fee_percentage=round(l.fee_amount / buildup_total * 100, 1),
                                source="From discipline fee build-up",
                                confidence="User-set",
                            )
                            for l in st.session_state.discipline_fee_lines
                        ]
                    else:
                        st.warning("Enter hours and rates in the discipline fee build-up table above first.")
            with bcol2:
                if st.button("Estimate from bundled benchmarks", key="benchmark_btn", type="primary"):
                    fee_cap = (str(manual_total) if manual_total > 0
                               else (st.session_state.analysis.fee_cap if st.session_state.analysis else None))
                    estimates = fee_estimation_engine.estimate_fee_split(st.session_state.project_type, fee_cap)
                    st.session_state.fee_estimates = _reconcile_estimates(estimates)
            with bcol3:
                refresh_ready = bool(st.session_state.ai_config.get("api_key"))
                if st.button("Refresh via AI knowledge (not a live web fetch)", disabled=not refresh_ready, key="refresh_btn", type="primary"):
                    fee_cap = (str(manual_total) if manual_total > 0
                               else (st.session_state.analysis.fee_cap if st.session_state.analysis else None))
                    with st.spinner("Asking the AI provider for its knowledge of published benchmarks..."):
                        estimates = fee_estimation_engine.refresh_estimate_from_web(
                            st.session_state.project_type, buildup_discs, fee_cap, st.session_state.ai_config,
                        )
                    st.session_state.fee_estimates = _reconcile_estimates(estimates)

            st.session_state.fee_estimates = _reconcile_estimates(st.session_state.fee_estimates)

            def _indicative_amount(pct):
                if manual_total > 0:
                    return manual_total * pct / 100
                if buildup_total > 0:
                    return buildup_total * pct / 100
                return None

            fee_pct_rows = [
                {
                    "discipline": e.discipline,
                    "fee_percentage": e.fee_percentage,
                    "indicative_amount": (f"${_indicative_amount(e.fee_percentage):,.0f}"
                                           if _indicative_amount(e.fee_percentage) else "-"),
                    "confidence": e.confidence,
                    "source": e.source,
                }
                for e in st.session_state.fee_estimates
            ]
            edited_pct = st.data_editor(
                fee_pct_rows, key="fee_pct_editor", use_container_width=True, hide_index=True,
                column_config={
                    "discipline": st.column_config.TextColumn("Discipline", disabled=True),
                    "fee_percentage": st.column_config.NumberColumn("Fee %", min_value=0.0, max_value=100.0, step=0.5, format="%.1f%%"),
                    "indicative_amount": st.column_config.TextColumn(
                        "Indicative $", disabled=True,
                        help="Fee % x the manual total above (if entered), else x the discipline fee build-up total.",
                    ),
                    "confidence": st.column_config.TextColumn("Confidence"),
                    "source": st.column_config.TextColumn("Source"),
                },
            )

            # Deferred apply -- same pattern as the discipline fee build-up
            # table's checkbox (see the comment there for the full rationale).
            # The three buttons above are unaffected -- they're deliberate,
            # single-click actions, not rapid per-keystroke edits, so they
            # still take effect immediately.
            pct_raw_sig = tuple(
                (r.get("discipline"), r.get("fee_percentage"), r.get("confidence"), r.get("source"))
                for r in edited_pct
            )
            pct_first_load = st.session_state.get("_pct_fee_last_applied_editor_sig") is None
            pct_pending = pct_raw_sig != st.session_state.get("_pct_fee_last_applied_editor_sig")
            pct_tick_val = st.session_state.get("_pct_fee_apply_tick", False)
            pct_tick_seen = st.session_state.get("_pct_fee_apply_tick_seen", False)
            if pct_pending and pct_tick_val and pct_tick_seen:
                st.session_state["_pct_fee_apply_tick"] = False
            pct_apply_now = st.checkbox(
                "Done entering data -- refresh totals & chart",
                key="_pct_fee_apply_tick",
            )
            st.session_state["_pct_fee_apply_tick_seen"] = pct_apply_now

            if pct_first_load or (pct_apply_now and pct_pending):
                st.session_state.fee_estimates = [
                    fee_estimation_engine.DisciplineFeeEstimate(
                        discipline=r["discipline"], fee_percentage=float(r["fee_percentage"] or 0),
                        confidence=r["confidence"] or "", source=r["source"] or "",
                    )
                    for r in edited_pct
                ]
                st.session_state._pct_fee_last_applied_editor_sig = pct_raw_sig
            else:
                st.caption(
                    "Totals, the chart, and the Excel export below are from the last time "
                    "you ticked the box above -- tick it again to bring them up to date."
                    if pct_pending else
                    "Totals, the chart, and the Excel export below reflect the ticked data above."
                )

            pct_total = sum(e.fee_percentage for e in st.session_state.fee_estimates)
            st.caption(f"Total: {pct_total:.1f}% (doesn't need to sum to exactly 100%).")

            _fee_pct_indicative_amounts = {e.discipline: _indicative_amount(e.fee_percentage) for e in st.session_state.fee_estimates}
            pct_xlsx = fee_estimation_engine.fee_estimates_to_excel(
                st.session_state.fee_estimates,
                indicative_amounts=_fee_pct_indicative_amounts,
                theme_name=st.session_state.proposal_theme,
            )
            if pct_xlsx:
                st.download_button(
                    "Export to Excel", data=pct_xlsx, key="download_pct_fee_xlsx",
                    file_name="indicative_fee_split.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                 type="primary")
            else:
                st.caption("Excel export needs the 'openpyxl' package -- run `pip install openpyxl` and reload.")

            # Chart the $ split once a total (manual or build-up) is available (matches
            # the other pie's units); otherwise chart the raw percentages, since that's
            # the only figure available with no total to anchor to.
            if any(_fee_pct_indicative_amounts.values()):
                pct_pie_items = [(e.discipline, _fee_pct_indicative_amounts.get(e.discipline) or 0) for e in st.session_state.fee_estimates]
                pct_pie_fmt = lambda v: f"${v:,.0f}"
                pct_pie_legend_value = "raw"
            else:
                pct_pie_items = [(e.discipline, e.fee_percentage) for e in st.session_state.fee_estimates]
                pct_pie_fmt = lambda v: f"{v:.0f}%"
                # "share" (not "raw"): if disciplines beyond the top 6 get folded into
                # "Other", the chart's total shrinks below 100 -- showing each slice's
                # recomputed share keeps the legend number matching what's actually
                # drawn, instead of the un-renormalised percentage.
                pct_pie_legend_value = "share"
            pct_pie_png = graphics_engine.generate_fee_distribution_pie(
                pct_pie_items, "Indicative fee split by discipline", value_fmt=pct_pie_fmt,
                legend_value=pct_pie_legend_value,
            )
            if pct_pie_png:
                st.image(pct_pie_png, use_container_width=True)

        _render_large_pct_fee_table()


# ---------------------------------------------------------------------------
# Tab 10: Export Pack
# ---------------------------------------------------------------------------

with tabs[9]:
    st.subheader("Export Pack")

    if _is_letter():
        st.caption("Generates the first-pass Small Scope Proposal Response Pack. Review the checklist page inside before this goes anywhere near a real submission.")
        ready = st.session_state.sections is not None
        if not ready:
            st.info("Generate the Proposal Structure first.")

        if _structure_format_stale():
            st.warning(
                "The Proposal format (Project Setup) was changed after these sections were generated -- "
                "go to Structure and click **Generate Proposal Structure** again first, or the "
                "exported pack will be missing the Introduction/Methodology drafts even if you "
                "already ran drafting."
            )

        if st.button("Generate Small Scope Pack DOCX", type="primary", disabled=not ready):
            with st.spinner("Assembling document..."):
                cover_image = st.session_state.project_photo_bytes[0] if st.session_state.project_photo_bytes else None
                sender = {
                    "name": st.session_state.letter_sender_name,
                    "title": st.session_state.letter_sender_title,
                    "phone": st.session_state.letter_sender_phone,
                    "email": st.session_state.letter_sender_email,
                }
                understanding_draft = (st.session_state.drafts or {}).get("Project Understanding")
                understanding_text = understanding_draft.draft_text if understanding_draft else ""
                methodology_draft = (st.session_state.drafts or {}).get("Methodology and Deliverables")
                methodology_text = methodology_draft.draft_text if methodology_draft else ""
                buffer = export_docx.build_letter_docx(
                    project_info=_project_info(),
                    sender=sender,
                    analysis=st.session_state.analysis,
                    understanding_text=understanding_text,
                    methodology_text=methodology_text,
                    resource_plan=st.session_state.resource_plan,
                    personnel_photos=st.session_state.personnel_photos,
                    program_schedule=st.session_state.program_schedule,
                    program_week_labels=st.session_state.program_week_labels,
                    terms_of_engagement_text=st.session_state.terms_of_engagement_text,
                    executive_summary=st.session_state.executive_summary,
                    cover_image_bytes=cover_image,
                    cover_theme_image_bytes=st.session_state.cover_hero_png,
                    fee_estimates=st.session_state.fee_estimates,
                    discipline_fee_lines=st.session_state.discipline_fee_lines,
                    differentiator_text=st.session_state.project_differentiator,
                    sales_pitch_text=st.session_state.project_sales_pitch,
                )
                st.session_state.docx_buffer = buffer

                # Same companion internal document the Large Scope pack generates
                # alongside its own DOCX (see export_docx.build_tender_summary_docx) --
                # a guide to the brief's main requirements (scope/objectives/mandatory
                # requirements/deliverables/risks), plus whatever compliance matrix and
                # gap analysis the user chose to run in Proposal Structure (tab 4), kept
                # OUT of the proposal itself. Small Scope packs don't generate an
                # evaluation weighting chart, so that section is simply omitted.
                st.session_state.tender_summary_buffer = export_docx.build_tender_summary_docx(
                    project_info=_project_info(),
                    analysis=st.session_state.analysis,
                    weighting_chart_png=st.session_state.weighting_chart_png,
                    compliance_items=st.session_state.compliance_items or [],
                    gap_items=st.session_state.gap_items or [],
                    sections=st.session_state.sections,
                    drafts=st.session_state.drafts or {},
                    body_font=st.session_state.body_font,
                )
            st.success("Document generated.")
    else:
        st.caption("Generates the first-pass DOCX response pack. Review the checklist inside the document before this goes anywhere near a real submission.")

        ready = st.session_state.sections is not None and st.session_state.guidance_notes is not None
        if not ready:
            st.info("Generate the Proposal Structure first. Drafts, graphics, and fee estimate are optional but recommended before exporting.")

        if _structure_format_stale():
            st.warning(
                "The Proposal format (Project Setup) was changed after these sections were generated -- "
                "go to Structure and click **Generate Proposal Structure** again first, or the "
                "exported pack may not match what you drafted."
            )

        if st.button("Generate DOCX", type="primary", disabled=not ready):
            with st.spinner("Assembling document..."):
                cover_image = st.session_state.project_photo_bytes[0] if st.session_state.project_photo_bytes else None

                # Same override the Fee Estimate tab's "Indicative fee split by discipline"
                # section applies to its own on-screen table/Excel/chart: a manually-entered
                # total project fee takes priority, else the discipline fee build-up's own $
                # total, else nothing -- without this, the proposal's fee table could show "-"
                # for every discipline even though the app's own Fee Estimate tab was showing
                # real dollar figures for the same split.
                _manual_fee_total = st.session_state.get("fee_estimate_manual_total") or 0
                _buildup_fee_total = sum(l.fee_amount for l in (st.session_state.discipline_fee_lines or []))
                _fee_indicative_amounts = {
                    e.discipline: (
                        _manual_fee_total * e.fee_percentage / 100 if _manual_fee_total > 0
                        else (_buildup_fee_total * e.fee_percentage / 100 if _buildup_fee_total else None)
                    )
                    for e in (st.session_state.fee_estimates or [])
                }

                buffer = export_docx.build_docx(
                    project_info=_project_info(),
                    analysis=st.session_state.analysis,
                    weighted_criteria=st.session_state.weighted_criteria or [],
                    allocations=st.session_state.allocations or [],
                    sections=st.session_state.sections,
                    guidance_notes=st.session_state.guidance_notes,
                    drafts=st.session_state.drafts or {},
                    compliance_items=st.session_state.compliance_items or [],
                    gap_items=st.session_state.gap_items or [],
                    graphics=st.session_state.graphics or [],
                    fee_estimates=st.session_state.fee_estimates,
                    weighting_chart_png=st.session_state.weighting_chart_png,
                    cover_image_bytes=cover_image,
                    cover_theme_image_bytes=st.session_state.cover_hero_png,
                    divider_images=st.session_state.divider_images,
                    resource_plan=st.session_state.resource_plan,
                    org_chart_png=st.session_state.org_chart_png,
                    body_font=st.session_state.body_font,
                    personnel_photos=st.session_state.personnel_photos,
                    reference_projects=st.session_state.reference_projects,
                    reference_project_photos=st.session_state.reference_project_photos,
                    discipline_fee_lines=st.session_state.discipline_fee_lines,
                    executive_summary=st.session_state.executive_summary,
                    fee_estimate_indicative_amounts=_fee_indicative_amounts,
                    team_intro=st.session_state.team_intro,
                    experience_intro=st.session_state.experience_intro,
                    differentiator_text=st.session_state.project_differentiator,
                    sales_pitch_text=st.session_state.project_sales_pitch,
                )
                st.session_state.docx_buffer = buffer

                # Companion internal document -- everything that's about how the
                # brief was read and how this pack was assembled (tender summary,
                # compliance matrix, gap analysis, review checklist, user-input
                # list), kept OUT of the proposal itself so that document is only
                # the proposal. Generated alongside it, same click.
                st.session_state.tender_summary_buffer = export_docx.build_tender_summary_docx(
                    project_info=_project_info(),
                    analysis=st.session_state.analysis,
                    weighting_chart_png=st.session_state.weighting_chart_png,
                    compliance_items=st.session_state.compliance_items or [],
                    gap_items=st.session_state.gap_items or [],
                    sections=st.session_state.sections,
                    drafts=st.session_state.drafts or {},
                    body_font=st.session_state.body_font,
                )
            st.success("Document generated.")

    if st.session_state.docx_buffer:
        filename = (st.session_state.tender_name or "tender_response_pack").replace(" ", "_")
        suffix = "small_scope_pack" if _is_letter() else "large_scope_pack"
        # Small Scope: DOCX + Tender Summary. Large Scope: DOCX + Org Chart + Methodology
        # Table + Program, all PPTX, + Tender Summary.
        dcols = st.columns(2 if _is_letter() else 5)
        with dcols[0]:
            st.download_button(
                "Download DOCX", data=st.session_state.docx_buffer,
                file_name=f"{filename}_{suffix}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
            )
        # The formal pack's Key Personnel section leaves an explicit placeholder for the
        # org chart (see export_docx._build_personnel_block) rather than embedding the
        # auto-generated preview -- the finished chart is built in PowerPoint and pasted
        # in by hand. Build that PowerPoint fresh from this project's actual resourcing
        # plan (see org_chart_pptx.populate_org_chart) right next to the DOCX download,
        # so it's never a separate hunt. Every discipline in resource_plan gets its own
        # column, showing that discipline's Lead name (or a red "TBC" if nobody's
        # assigned yet) -- support roles, the client's own PM, subconsultant firms have
        # no equivalent in the app's data and simply aren't shown, same no-invention rule
        # as everywhere else in this tool. The Small Scope pack doesn't have a Key
        # Personnel/org chart section, so skip it there.
        if not _is_letter():
            with dcols[1]:
                try:
                    chart_bytes = org_chart_pptx.populate_org_chart(
                        st.session_state.resource_plan or [],
                        client_name=st.session_state.client_name,
                        project_name=st.session_state.project_name,
                    )
                    st.download_button(
                        "Download Org Chart (PPTX)",
                        data=chart_bytes,
                        file_name="Org_Chart.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     type="primary")
                    st.caption(
                        "Built from this project's assigned Lead names -- unassigned roles show as red "
                        "\"TBC\". Fill in any remaining names, then paste the finished chart into the DOCX placeholder."
                    )
                except Exception:
                    # Never let a chart-generation bug block the DOCX download that
                    # actually matters -- just skip the org chart download this time.
                    st.caption("Couldn't build the org chart this time -- the DOCX download above is unaffected.")

        # Same placeholder-in-DOCX / finish-in-PowerPoint pattern as the org chart
        # above (see export_docx._build_methodology_table). Four generic stage
        # columns (Project Initiation, then three progressively-developed design
        # stages), themed to match this proposal's chosen colours (see
        # methodology_pptx.populate_methodology). Column 1 is standard
        # boilerplate; column 2's Key tasks are built straight from this
        # project's real scope items (title + tasks), never invented. Columns
        # 3-4 cover stages the brief doesn't describe, so they stay explicit red
        # "[CONFIRM ...]" placeholders, same no-invention rule as everywhere
        # else in this tool. The legend's client-name hold-point label is
        # populated from Project Setup, showing a red placeholder if not yet
        # entered.
        if not _is_letter():
            with dcols[2]:
                try:
                    methodology_bytes = methodology_pptx.populate_methodology(
                        st.session_state.analysis,
                        client_name=st.session_state.client_name,
                        project_name=st.session_state.project_name,
                        theme_name=st.session_state.proposal_theme,
                    )
                    st.download_button(
                        "Download Methodology Table (PPTX)",
                        data=methodology_bytes,
                        file_name="Methodology_Table.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     type="primary")
                    st.caption(
                        "Column 2's Key tasks are built from this project's real scope items; columns 3-4 "
                        "are red placeholders for stages the brief doesn't describe. Fill in the remaining "
                        "content, then paste the finished table into the DOCX placeholder."
                    )
                except Exception:
                    # Never let a chart-generation bug block the DOCX download that
                    # actually matters -- just skip the methodology table download this time.
                    st.caption("Couldn't build the methodology table this time -- the DOCX download above is unaffected.")

        # Same PPTX-companion pattern as the org chart / methodology table above -- the
        # Large Scope pack's DOCX has no Program section of its own (unlike the Small
        # Scope pack, which embeds one inline), so the delivery program built in the Fee
        # Estimate tab is exported here instead, as an editable Gantt-style table (see
        # program_pptx.populate_program) to paste into a program/methodology slide.
        if not _is_letter():
            with dcols[3]:
                try:
                    program_bytes = program_pptx.populate_program(
                        st.session_state.program_schedule or {},
                        st.session_state.program_week_labels or [],
                        client_name=st.session_state.client_name,
                        project_name=st.session_state.project_name,
                        theme_name=st.session_state.proposal_theme,
                    )
                    st.download_button(
                        "Download Program (PPTX)",
                        data=program_bytes,
                        file_name="Delivery_Program.pptx",
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     type="primary")
                    st.caption(
                        "Built from the delivery program entered in the Fee Estimate tab -- shows a red "
                        "placeholder if no program has been generated there yet."
                    )
                except Exception:
                    # Never let a chart-generation bug block the DOCX download that
                    # actually matters -- just skip the program download this time.
                    st.caption("Couldn't build the program this time -- the DOCX download above is unaffected.")

        # The Tender Summary is a separate document (see export_docx.build_tender_summary_docx),
        # generated in the same click as the Proposal DOCX above -- everything about how the
        # brief was read and how this pack was assembled (a guide to the brief's main
        # requirements, plus the compliance matrix, gap analysis, review checklist, and
        # user-input list, where generated) lives here instead of inside the proposal itself.
        # Available for both pack sizes -- the Small Scope pack just won't have an evaluation
        # weighting chart or (unless run manually in tab 4) a compliance matrix/gap analysis.
        with dcols[1 if _is_letter() else 4]:
            if st.session_state.tender_summary_buffer:
                st.download_button(
                    "Download Tender Summary (DOCX)",
                    data=st.session_state.tender_summary_buffer,
                    file_name=f"{filename}_tender_summary.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                 type="primary")
                st.caption(
                    "Companion internal document -- guidance on the brief's main requirements, plus "
                    "the compliance matrix, gap analysis, review checklist, and user input list where "
                    "generated. Not part of the proposal itself."
                )
            else:
                st.caption("Tender Summary document will be generated alongside the DOCX above.")

        st.divider()
        st.markdown("#### Proposal Library")
        st.caption(
            "Archive this generated proposal into the Proposal Library "
            f"(library/{st.session_state.project_type or '<project type>'}/) for reuse later -- "
            "as a 'Previous proposals' reference in Upload Docs, or to browse and "
            "download from the 'Proposal Library' button in the top banner. Nothing is archived automatically; click below "
            "whenever you're happy with this version. Only the proposal DOCX itself is archived, "
            "not the Tender Summary or the PowerPoint companions above."
        )
        if st.button("Archive to Library", key="archive_to_library_btn", type="primary"):
            try:
                _archived = proposal_library.archive_proposal(
                    _lib_user_id(),
                    st.session_state.docx_buffer.getvalue(),
                    project_type=st.session_state.project_type,
                    pack_type="small_scope" if _is_letter() else "large_scope",
                    project_name=st.session_state.project_name,
                    client_name=st.session_state.client_name,
                    tender_name=st.session_state.tender_name,
                )
                st.success(f"Archived to the library under '{_archived['project_type']}' as {_archived['filename']}.")
            except Exception as exc:
                st.error(f"Couldn't archive to the library: {exc}")


# ---------------------------------------------------------------------------
# Auto-save -- runs once per script execution, after every tab above has had
# a chance to mutate session_state, so it captures this run's latest state.
# ---------------------------------------------------------------------------

_maybe_autosave()
