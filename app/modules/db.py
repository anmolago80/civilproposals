"""
db.py

Database layer for the CivilProposals SaaS build. Replaces the local-disk
assumptions in project_store.py / local_project_store.py / proposal_library.py
with a real multi-tenant Postgres database (Railway provisions one
automatically when you add a Postgres service to the project).

Falls back to a local SQLite file (civilproposals_local.db, next to this
file) when DATABASE_URL isn't set, so the app still runs during local
development without a Postgres instance running. Railway sets DATABASE_URL
automatically once you attach its Postgres plugin -- no code change needed
to go from local SQLite to production Postgres, just that one env var.

Every function here is user-scoped (takes a user_id) on purpose: this module
is imported once per Streamlit worker process, which can be serving many
different users' requests over its lifetime, so nothing here may hold
per-user state in a module-level variable. Session-scoped state (the
logged-in user) belongs in st.session_state, in app.py / auth.py, not here.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime, Boolean, LargeBinary,
    ForeignKey, Text, select, func, case, UniqueConstraint, inspect, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Computed independently here rather than imported from 00_init.py's
# IS_SAAS_MODE -- db.py is imported directly by test scripts and other
# modules without app.py/00_init.py ever running, so it can't depend on
# that module's import-time state. Same env var, same default, same
# normalisation as 00_init.py's IS_SAAS_MODE, deliberately duplicated.
_SAAS_MODE_ON = os.environ.get("SAAS_MODE", "true").strip().lower() != "false"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    if _SAAS_MODE_ON:
        # Part 3 (BRIEF_ISOLATION_AND_PRIVACY.md): the SQLite fallback
        # below means a hosted deploy that starts without DATABASE_URL set
        # comes up against an empty, throwaway local database -- nobody's
        # account exists in it, and the first person to register an
        # ADMIN_ACCOUNTS email becomes an admin of a database nobody else
        # can see. Refuse to start instead of doing that silently.
        sys.exit(
            "FATAL: DATABASE_URL is not set. SAAS_MODE is on, and without a "
            "real database a hosted deploy would start against an empty "
            "local SQLite file instead of the shared production database. "
            "Set DATABASE_URL (e.g. attach Railway's Postgres plugin) and "
            "redeploy."
        )
    # Local dev fallback -- a file next to this module, gitignored. This is
    # what the fallback exists for; do not remove it.
    _local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "civilproposals_local.db")
    DATABASE_URL = f"sqlite:///{_local_path}"

# Railway (and most managed Postgres providers) hand out a "postgres://" URL.
# Name the driver explicitly: SQLAlchemy 2.1+ defaults a bare "postgresql://"
# to psycopg (v3), but this app ships psycopg2-binary. URLs that already name
# a driver ("+psycopg", "+asyncpg", ...) and sqlite URLs are left unchanged.
for _prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(_prefix):
        DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len(_prefix):]
        break

_engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

Base = declarative_base()


def _uid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    name = Column(String, default="")
    firm_name = Column(String, default="")
    created_at = Column(DateTime, default=_now)

    # Stripe / billing
    stripe_customer_id = Column(String, default="")
    stripe_subscription_id = Column(String, default="")
    # One of: "trial", "active", "past_due", "canceled"
    subscription_status = Column(String, default="trial")
    subscription_updated_at = Column(DateTime, default=_now)

    # The Monthly plan's advertised "4 bids included" cap (see
    # auth.SUBSCRIPTION_MONTHLY_BID_LIMIT) -- how many of THIS Stripe billing
    # period's 4 bids have been used, and the period-end timestamp Stripe
    # reported the last time we checked. billing.refresh_subscription_status
    # compares the live Stripe current_period_end against
    # subscription_period_end on every call (e.g. every login); a change
    # means a new billing cycle started, which resets
    # subscription_bids_used back to 0 -- no webhook needed, since a login
    # is frequent enough for a monthly cap to mean something. Both stay at
    # their defaults (unused) for anyone who's never subscribed.
    subscription_bids_used = Column(Integer, default=0)
    subscription_period_end = Column(DateTime, nullable=True)

    # Usage-based free trial: N free full proposals (Tender Analysis runs),
    # then payment is required. See auth.get_access_status(). Matches the
    # "1 free bid on sign up" pricing shown on the landing page -- was 3
    # under the old flat $200/month plan.
    trial_proposals_used = Column(Integer, default=0)
    trial_proposals_limit = Column(Integer, default=1)

    # Pay-as-you-go: one credit per $50 one-time Stripe Checkout (mode=
    # "payment", see billing.create_bid_checkout_session), consumed by
    # auth.record_proposal_usage() AFTER the free trial runs out, same
    # "existence of a row = already counted" idempotency as trial usage --
    # never touched at all while subscription_status == "active", since an
    # active subscription is unlimited on its own.
    bid_credits = Column(Integer, default=0)

    is_admin = Column(Boolean, default=False)

    # Set the moment the user ticks "I have read and accept these terms" --
    # on signup for new accounts, or on the one-time acceptance gate
    # require_login() shows any returning account that doesn't have this set
    # yet (existing accounts created before this column existed). NULL means
    # "hasn't accepted" -- see auth.require_login() and auth.TERMS_TEXT.
    accepted_terms_at = Column(DateTime, nullable=True)

    # Part A0 of the EN/ES dual-language brief -- the account's remembered
    # UI language, one of modules/i18n.LANGUAGES' keys ("en"/"es"). Adopted
    # into st.session_state the first time modules/i18n.current_language()
    # sees this user each session; NULL means "never explicitly chosen yet"
    # (falls back to the browser's Accept-Language header, then English --
    # see modules/i18n.py). Deliberately NOT used to pick the language a
    # generated proposal/tender-summary/org-chart comes out in -- that's
    # the separate, per-PROJECT `output_language` field in session_state
    # (see modules/pages/10_state_helpers.py's PLAIN_KEYS / Part A3).
    preferred_language = Column(String, nullable=True)

    # One free trial per person (see auth.create_user / claim_trial and the
    # TrialClaim ledger below).
    #
    # email_normalized: email_identity.normalize_email(email) -- lowercase,
    # "+tag" stripped on every domain, dots removed for gmail/googlemail. UNIQUE,
    # so "a.b+x@gmail.com" cannot be opened beside "ab@gmail.com". NULL only for
    # a legacy account whose normalised form collided with an older account
    # (several NULLs are allowed by a unique index).
    email_normalized = Column(String, unique=True, nullable=True, index=True)

    # NULL = the address has not been confirmed yet: the account can sign in
    # but cannot spend the trial (auth.is_email_verified). Every account that
    # existed when this column was added is stamped verified by the migration.
    email_verified_at = Column(DateTime, nullable=True)
    # Pending 6-digit confirmation code: HMAC of the code (never the code),
    # when it expires, how many wrong guesses it has had, when it was sent
    # (resend cooldown).
    verify_code_hash = Column(String, nullable=True)
    verify_code_expires_at = Column(DateTime, nullable=True)
    verify_code_attempts = Column(Integer, default=0)
    verify_code_sent_at = Column(DateTime, nullable=True)

    # "" = this account may claim / holds the free trial. Otherwise why it
    # gets none: "email" (that mailbox already had a trial), "device" (this
    # browser already claimed one), "domain" (company-domain switch).
    trial_denied_reason = Column(String, default="")

    library_entries = relationship("LibraryEntry", back_populates="user", cascade="all, delete-orphan")
    reference_library_entries = relationship(
        "ReferenceLibraryEntry", back_populates="user", cascade="all, delete-orphan",
    )
    proposal_usage = relationship("ProposalUsage", back_populates="user", cascade="all, delete-orphan")
    saved_projects = relationship("SavedProject", back_populates="user", cascade="all, delete-orphan")


class ProposalUsage(Base):
    """One row per distinct proposal (project) a user has run Tender Analysis
    on. Existence of a row for (user_id, project_key) is what "already
    counted toward the trial" means -- re-running analysis on the same
    project doesn't consume another trial credit.

    The unique constraint below is what actually makes that safe under
    concurrency. auth.record_proposal_usage() checks "does a row already
    exist?" and, if not, inserts one and spends a credit -- but a Streamlit
    double-rerun (a double-click, or a rerun triggered mid-click by
    something else on the page) can run that whole function twice before
    either commit lands, so both calls see "no row yet" and both insert,
    burning two credits for one bid. The unique index this constraint
    creates (see _run_light_migrations()'s CREATE UNIQUE INDEX for the
    existing-database retrofit -- create_all() alone only applies this to
    a brand new table) makes the second INSERT fail at the database level
    instead of silently succeeding; record_proposal_usage() catches that
    IntegrityError and treats it as "already recorded," the same outcome
    the check-first-then-insert path was supposed to guarantee on its own."""
    __tablename__ = "proposal_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "project_key", name="uq_proposal_usage_user_project_key"),
    )

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_key = Column(String, nullable=False)
    project_name = Column(String, default="")
    created_at = Column(DateTime, default=_now)

    # Part B of the one-pass-free-tier brief: WHICH funding tier actually
    # paid for this project's first Tender Analysis run -- one of "trial",
    # "subscription", "credit" (mirrors the three branches in
    # auth.record_proposal_usage(), and stays "" for older rows recorded
    # before this column existed, or for UNLIMITED_ACCOUNTS runs, which
    # don't spend from any tier at all). This is what "has this project
    # actually been PAID for, in money, not just trial-recorded" means --
    # see auth.project_funded_by() and its docstring for exactly how the
    # free-tier artifact/download gating (Part B) and the pass allowance
    # (Part B2) use it. Deliberately a separate column from the mere
    # existence of this row (which already means "already counted toward
    # SOME tier's usage", see the class docstring above) -- existence alone
    # can't distinguish a trial-funded project (free-tier rules apply) from
    # a subscription/credit-funded one (paid rules apply).
    funded_by = Column(String, default="")

    user = relationship("User", back_populates="proposal_usage")


class TrialClaim(Base):
    """The free-trial ledger: one row per mailbox that has ever been granted a
    trial, keyed by the NORMALISED email (see email_identity.normalize_email).

    Rows are never deleted -- deliberately not cascaded from users and never
    touched by any account-deletion path -- so deleting an account and signing
    up again with the same mailbox (or an alias of it) finds its old row and
    gets no second trial.

    user_id is a plain string, not a foreign key, for the same reason: it must
    survive the user row being removed.

    device_hash is the day-rotated SHA-256 of IP + user-agent at claim time.
    It is a SIGNAL for the admin view only (offices share IPs, so it can never
    block anyone) and only matches claims made the same UTC day."""
    __tablename__ = "trial_claims"

    id = Column(String, primary_key=True, default=_uid)
    email_normalized = Column(String, nullable=False, unique=True, index=True)
    email_domain = Column(String, default="", index=True)
    user_id = Column(String, nullable=False, index=True)
    claimed_at = Column(DateTime, default=_now)
    device_hash = Column(String, default="", index=True)


class ArtifactEvent(Base):
    """Part B of the one-pass-free-tier brief: records that a specific free-
    tier artifact has already been DOWNLOADED once for a given (user,
    project). Only ever written for artifacts on the free list
    (see modules/pages/80_export.py's _FREE_TIER_ARTIFACTS --
    "proposal_docx", "tender_summary_docx", "org_chart_pptx") on a project
    whose ProposalUsage.funded_by == "trial" -- a paid project never writes
    rows here at all, because paid projects get unlimited re-downloads (see
    auth.project_funded_by() / Part B2's "unlimited downloads of current
    docs"). Existence of a row is what "this free download has already been
    used" means; the unique constraint gives the same double-click-safe
    idempotency as ProposalUsage (see that class's docstring for why the
    check-then-insert pattern alone isn't enough under concurrency)."""
    __tablename__ = "artifact_events"
    __table_args__ = (
        UniqueConstraint("user_id", "project_key", "artifact_type",
                          name="uq_artifact_events_user_project_artifact"),
    )

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_key = Column(String, nullable=False)
    artifact_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)


class ProjectPasses(Base):
    """Part B2 (owner-confirmed, supersedes Part B's flat "one generation
    pass" wherever the two conflict): tracks the generation-pass allowance
    for ONE paid project -- a "pass" is spent by a full generation cycle
    (the initial Tender Analysis run, or a later regeneration after a
    tracked input actually changed -- see
    modules/pages/10_state_helpers.py's _export_input_signature()/
    _analysis_input_signature()-style staleness check, NOT by re-downloading
    already-generated, unchanged documents).

    One row per (user_id, project_key), created the moment a project is
    first funded by a real $50 bid (see auth.record_proposal_usage()) --
    never for trial-funded projects, which are governed by the plain
    trial_proposals_used/limit counters instead (a trial is, by definition,
    exactly one pass, on one project, ever). passes_purchased starts at 5
    (a single bid's allowance) and increases by 5 with each top-up
    (billing.create_bid_checkout_session() reused for the same purpose --
    see billing.py's Part B2 handling in handle_checkout_redirect()).
    passes_used increments by auth.consume_project_pass() each time a pass
    is actually spent; never decremented. "Passes remaining" is always
    `passes_purchased - passes_used`, computed on read rather than stored,
    so there's exactly one place that number can drift out of sync with
    reality."""
    __tablename__ = "project_passes"
    __table_args__ = (
        UniqueConstraint("user_id", "project_key", name="uq_project_passes_user_project_key"),
    )

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_key = Column(String, nullable=False)
    passes_purchased = Column(Integer, default=5)
    passes_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now)


class ProcessedCheckoutSession(Base):
    """Idempotency guard for billing.handle_checkout_redirect(). Stripe's
    success redirect (?checkout=success&session_id=...) is a plain GET URL
    that survives in browser history, bookmarks, and a plain page refresh --
    without this table, every re-visit of that URL would re-apply whatever
    the session paid for (another +1 bid_credit, or re-activating a
    subscription that may have since changed). One row per Stripe Checkout
    Session id we've ever actually applied; handle_checkout_redirect() checks
    for an existing row before crediting anything, and writes one in the
    same transaction as the credit itself, so a second call with the same
    session_id is a safe no-op rather than a second free bid."""
    __tablename__ = "processed_checkout_sessions"

    session_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    processed_at = Column(DateTime, default=_now)


class LibraryEntry(Base):
    """DB-backed replacement for the local library/<project_type>/ folder in
    modules/proposal_library.py -- one row per archived proposal pack,
    scoped to the user (and, by project_type/tags, filterable/searchable)
    who archived it, with the DOCX itself stored as bytes."""
    __tablename__ = "library_entries"

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    project_name = Column(String, default="")
    client_name = Column(String, default="")
    tender_name = Column(String, default="")
    project_type = Column(String, default="Unspecified")
    pack_type = Column(String, default="formal")  # "formal" | "letter"
    tags = Column(String, default="")  # comma-separated free tags, user-entered
    filename = Column(String, default="")
    archived_at = Column(DateTime, default=_now)
    docx_bytes = Column(LargeBinary, nullable=False)

    user = relationship("User", back_populates="library_entries")


class FeeSnapshot(Base):
    """One row per project whose fee build-up has been exported or archived:
    the per-discipline hours/rate/amount split, as priced, kept so the firm's
    OWN history can seed the next bid of the same type.

    Why this exists: the fee sheet opened at zeros and the only "benchmark"
    on offer was a bundled rule-of-thumb table of industry averages. A firm
    that has priced eleven bridge duplications has far better data about its
    own splits than any published average, and it was throwing it away.

    UNIQUE on (user_id, project_key) deliberately. This is written both when
    a pack is archived and when one is generated, and a user who regenerates
    a pack five times has still only bid once -- without the constraint,
    "median of 5 bids" would be one bid counted five times, which is worse
    than having no history at all because it looks like corroboration.
    """
    __tablename__ = "fee_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "project_key", name="uq_fee_snapshot_user_project_key"),
    )

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_key = Column(String, nullable=False)

    project_name = Column(String, default="")
    project_type = Column(String, default="Unspecified", index=True)
    total_amount = Column(Float, default=0.0)
    # [{discipline, hours, rate, amount, pct_of_total}] -- JSON rather than a
    # child table because it is only ever read back whole, per project.
    lines_json = Column(Text, default="[]")
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class ReferenceLibraryEntry(Base):
    """A firm 'reference project' (case study / past-experience writeup) the
    user has uploaded directly to the Project Reference Library -- separate
    from LibraryEntry (which holds full proposals archived from Export
    Pack). Organised by project_type (discipline) the same way LibraryEntry
    is, so both libraries share the same filtering pattern. See
    modules/reference_library.py."""
    __tablename__ = "reference_library_entries"

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String, default="")
    project_type = Column(String, default="Unspecified")
    tags = Column(String, default="")  # comma-separated free tags, user-entered
    filename = Column(String, default="")
    uploaded_at = Column(DateTime, default=_now)
    file_bytes = Column(LargeBinary, nullable=False)

    user = relationship("User", back_populates="reference_library_entries")


class SavedProject(Base):
    """DB-backed replacement for local_project_store.py's local-disk
    autosave/"Recent projects" -- one row per in-progress project per user,
    reusing the same slug (derived from the project name) overwrites it, same
    "current state only, not version history" behaviour as the local version.
    project_bytes is exactly what project_store.save_project() produces (a
    .tenderproj.zip's bytes): every session_state field except AI
    credentials, so this is safe to store per-user rather than per-server-disk.
    See modules/cloud_project_store.py, which app.py actually calls."""
    __tablename__ = "saved_projects"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_saved_project_user_slug"),)

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String, nullable=False)   # display name, e.g. "Jindabyne Barrier"
    slug = Column(String, nullable=False, index=True)
    project_bytes = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    user = relationship("User", back_populates="saved_projects")


class Job(Base):
    """A thin, permanent index of who owns which background job (see
    modules/job_queue.py) -- NOT where the job's actual input or output
    lives. Those stay in Redis, under RQ's own TTL, because the two jobs
    this app currently queues (Tender Analysis, Draft Generation) both take
    the user's own pasted AI provider API key as an input (BYOK -- see
    ai_config in app.py, never stored in this database anywhere else
    either), so this table must not become a second, longer-lived place
    that key ends up written to. What this table IS for: letting the
    Streamlit process that enqueued a job (which may not be the same
    worker-thread invocation that polls it later, if the user's browser
    reconnects) look up "is this job id actually mine?" before it's ever
    allowed to ask Redis for that job's status or result -- an RQ job id is
    just an opaque string that could end up in a log line, not a secret, so
    ownership has to be re-checked server-side on every poll.

    id is the RQ job's own id (see job_queue.enqueue) -- no separate uuid
    layer on top of it."""
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_type = Column(String, nullable=False)  # "tender_analysis" | "draft_generation"
    status = Column(String, default="queued")  # queued | started | finished | failed
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    error_message = Column(Text, default="")
    # In-flight guard for the metered Tender Analysis run: which project this
    # job belongs to (lower-cased, same form as ProposalUsage.project_key), and
    # whether the run RESERVED a ProposalUsage row before it was queued (so a
    # failed job knows it must refund it -- a repeat run on a paid project
    # spent a pass instead, which is never refunded). See find_inflight_job().
    project_key = Column(String, nullable=True, index=True)
    reserved = Column(Boolean, default=False)


class AiCallLog(Base):
    """One row per individual AI provider call made anywhere in the app (web
    process or worker process) -- provider, model, token counts, and an
    estimated cost in USD, attributed to the user/project that triggered it
    via ai_interface.set_usage_context(). Written best-effort by
    ai_interface._record_usage(): a logging failure must never fail (or slow
    down) the AI call itself, so everything about this table is optional
    from the caller's point of view.

    estimated_cost_usd is NULL (not 0) when the model's pricing isn't in
    ai_interface.MODEL_PRICES_PER_MTOK -- an unknown cost and a free call
    are different facts, and the admin rollup below reports "N calls with
    unpriced models" rather than silently under-counting."""
    __tablename__ = "ai_call_log"

    id = Column(String, primary_key=True, default=_uid)
    # Nullable on purpose: desktop/BYOK mode has no logged-in user, and a
    # worker-side call that somehow arrives without context should still be
    # counted in the global total rather than dropped.
    user_id = Column(String, index=True, nullable=True)
    project_key = Column(String, index=True, default="")
    project_name = Column(String, default="")
    purpose = Column(String, default="")  # e.g. "tender_analysis", "draft_generation"
    provider = Column(String, default="")
    model = Column(String, default="")
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_now)


class BlogPost(Base):
    """One row per marketing-blog article (see modules/blog.py and the Blog
    tab in the admin panel). This table is the SOURCE OF TRUTH for post
    content; the public pages readers actually hit are rendered HTML pushed
    into Cloudflare Workers KV at publish time, so the live blog keeps
    serving even when this database (or the whole Railway service) is down.
    Re-publishing simply re-renders from these rows.

    Deliberately NOT user-scoped, unlike every other model in this file:
    there is exactly one company blog, and only admin accounts
    (auth.is_admin_user) can reach the editor at all. author_id records who
    wrote a post for display/attribution -- it is not an ownership or
    access-control boundary.

    status is "draft" | "scheduled" | "published" | "unpublished":
      draft        never public; visible only in the editor
      scheduled    publishes itself once published_at passes
      published    live in KV, in the sitemap, in the homepage strip
      unpublished  pulled from the live site but kept here, so an
                   accidental publish is reversible without losing the text
    """
    __tablename__ = "blog_posts"

    id = Column(String, primary_key=True, default=_uid)

    # The URL: /blog/<slug>/. Unique and effectively permanent once
    # published -- changing it orphans any inbound link or search result
    # pointing at the old one, so blog.py warns before allowing an edit to
    # a slug that has already been live.
    slug = Column(String, nullable=False, unique=True, index=True)

    title = Column(String, nullable=False, default="")
    excerpt = Column(Text, default="")        # card text + fallback meta description
    body_md = Column(Text, default="")        # the post itself, markdown
    hero_image_key = Column(String, default="")  # -> BlogImage.key, card + OG image

    category = Column(String, default="")     # one of blog.CATEGORIES
    tags = Column(String, default="")         # comma-separated, free-form

    status = Column(String, default="draft", index=True)
    published_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # Optional SEO overrides -- used when the headline that reads well on
    # the page isn't the phrase the post should rank for. Both fall back to
    # title/excerpt when blank.
    seo_title = Column(String, default="")
    seo_description = Column(Text, default="")

    author_id = Column(String, nullable=True)
    author_name = Column(String, default="")

    # Set the first time this post is successfully pushed to KV. Lets the
    # editor show "published, but with unsaved changes since" by comparing
    # against updated_at.
    last_published_at = Column(DateTime, nullable=True)


class BlogImage(Base):
    """An image uploaded through the blog editor -- hero shots and in-body
    figures. Stored as bytes here (same pattern as LibraryEntry.docx_bytes)
    and mirrored into KV at publish time, served to readers from
    /blog/media/<key>.

    Kept in the database rather than committed to landing/assets/ so that
    adding an image to a post needs no git commit and no site redeploy --
    publishing is the only step."""
    __tablename__ = "blog_images"

    id = Column(String, primary_key=True, default=_uid)
    # Filename-safe, unique, and used verbatim in the public URL.
    key = Column(String, nullable=False, unique=True, index=True)
    filename = Column(String, default="")
    content_type = Column(String, default="image/jpeg")
    alt_text = Column(String, default="")
    image_bytes = Column(LargeBinary, nullable=False)
    uploaded_at = Column(DateTime, default=_now)


class FirmProfile(Base):
    """The bidding firm's own standing facts -- one row per account.

    Everything here is the same on every bid this firm ever writes: legal
    name, ABN, registered address, logo, insurances, certifications, the
    signatory block, offices, rate card, standing terms. Before this table
    existed the app had no way to know any of it, which is where roughly ten
    recurring red placeholders in every exported pack came from: the "ABN
    [XX XXX XXX XXX] | [REGISTERED ADDRESS]" footer on every Small Scope
    page, the [COMPANY LOGO] box on page 1, the schedule filler's permanent
    inability to answer an insurance or ABN label, the compliance matrix's
    standing "Missing -- must come from the user" against insurance
    requirements. None of that was missing information; it was information
    nobody had been asked for.

    Scoped by user_id, like every other model in this file except BlogPost.
    In local mode (SAAS_MODE=false) there is no logged-in user, so the row
    is keyed by LOCAL_USER_ID -- the same single-user fallback the rest of
    the local path uses.

    List/table fields are JSON-encoded text rather than separate tables:
    they are small, always read as a whole, and never queried across
    accounts, so a join buys nothing and costs a migration.
    """
    __tablename__ = "firm_profiles"

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True, index=True)

    # Identity
    company_name = Column(String, default="")       # legal entity name
    abn = Column(String, default="")
    acn = Column(String, default="")
    registered_address = Column(Text, default="")
    logo_bytes = Column(LargeBinary, nullable=True)
    logo_filename = Column(String, default="")

    # Standing signatory / contact block, seeded into each new project
    signatory_name = Column(String, default="")
    signatory_title = Column(String, default="")
    signatory_phone = Column(String, default="")
    signatory_email = Column(String, default="")

    # JSON text columns -- see the class note above.
    insurances_json = Column(Text, default="")      # [{type, insurer, policy_no, cover, expiry}]
    certifications_json = Column(Text, default="")  # ["ISO 9001:2015", ...]
    rate_card_json = Column(Text, default="")       # {discipline: rate_per_hour}

    offices_text = Column(Text, default="")         # offices + local presence
    community_text = Column(Text, default="")       # community/reinvestment programs
    leadership_text = Column(Text, default="")      # standing leadership names/roles
    terms_of_engagement_text = Column(Text, default="")
    qa_statement = Column(Text, default="")         # e.g. the WVR/QA commitment

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


def log_ai_call(user_id: str | None, project_key: str, project_name: str, purpose: str,
                provider: str, model: str, input_tokens: int | None,
                output_tokens: int | None, estimated_cost_usd: float | None) -> None:
    """Best-effort insert -- see AiCallLog. Callers must wrap in try/except
    (ai_interface._record_usage does); this function itself doesn't swallow
    errors so tests can still see them."""
    with get_session() as s:
        s.add(AiCallLog(
            user_id=user_id or None,
            project_key=(project_key or "")[:512],
            project_name=(project_name or "")[:512],
            purpose=(purpose or "")[:64],
            provider=(provider or "")[:64],
            model=(model or "")[:128],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
        ))
        s.commit()


def ai_cost_summary(limit_projects: int = 25) -> dict:
    """Admin rollup for app.py's admin-only AI cost panel. Returns
    {"total_cost_usd", "total_calls", "unpriced_calls", "per_project":
    [{"project_name", "project_key", "user_id", "calls", "cost_usd",
    "input_tokens", "output_tokens"}, ...]} across ALL users (the caller is
    responsible for gating this behind is_admin)."""
    with get_session() as s:
        total_cost = s.query(func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0)).scalar() or 0.0
        total_calls = s.query(func.count(AiCallLog.id)).scalar() or 0
        unpriced = s.query(func.count(AiCallLog.id)).filter(AiCallLog.estimated_cost_usd.is_(None)).scalar() or 0
        rows = (
            s.query(
                AiCallLog.project_key,
                func.max(AiCallLog.project_name),
                func.max(AiCallLog.user_id),
                func.count(AiCallLog.id),
                func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0),
                func.coalesce(func.sum(AiCallLog.input_tokens), 0),
                func.coalesce(func.sum(AiCallLog.output_tokens), 0),
            )
            .group_by(AiCallLog.project_key)
            .order_by(func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0).desc())
            .limit(limit_projects)
            .all()
        )
    return {
        "total_cost_usd": float(total_cost),
        "total_calls": int(total_calls),
        "unpriced_calls": int(unpriced),
        "per_project": [
            {
                "project_key": r[0] or "(no project)",
                "project_name": r[1] or "(no project)",
                "user_id": r[2] or "",
                "calls": int(r[3]),
                "cost_usd": float(r[4]),
                "input_tokens": int(r[5]),
                "output_tokens": int(r[6]),
            }
            for r in rows
        ],
    }


# A queued/started Job row older than this is treated as dead rather than
# "still running" -- comfortably above job_queue.JOB_TIMEOUT_SECONDS (15 min)
# plus the web side's own wait ceiling, so a worker that died can never leave
# a project's Run button disabled forever.
INFLIGHT_JOB_MAX_AGE_MINUTES = 30


def find_inflight_job(user_id: str, project_key: str, job_type: str = "tender_analysis") -> dict | None:
    """The queued/running background job for (user, project), if any -- the
    in-flight guard behind the Tender Analysis Run button. It is read from the
    database, not from session state, so it holds across a browser refresh and
    across tabs. Returns {"id", "status", "reserved", "created_at"} or None."""
    project_key = (project_key or "").strip().lower()
    if not user_id or not project_key:
        return None
    cutoff = (_now() - timedelta(minutes=INFLIGHT_JOB_MAX_AGE_MINUTES)).replace(tzinfo=None)
    with get_session() as s:
        row = (
            s.query(Job)
            .filter(
                Job.user_id == user_id,
                Job.project_key == project_key,
                Job.job_type == job_type,
                Job.status.in_(("queued", "started")),
                Job.created_at >= cutoff,
            )
            .order_by(Job.created_at.desc())
            .first()
        )
        if row is None:
            return None
        return {"id": row.id, "status": row.status, "reserved": bool(row.reserved), "created_at": row.created_at}


def _recent_activity_rows(s, users: list, signups: list[dict], usage_by_user: dict) -> list[dict]:
    """The owner-only "Recent activity" table (admin panel): one row per
    account in `users` (already the 15 newest), read-only. `signups` is the
    parallel list admin_stats() built (it carries the tier); `usage_by_user`
    is {user_id: (projects_run, non_trial_count)}.

    - ta_runs counts Tender Analysis Job rows that did not fail, so a double
      run on one project shows as 2 runs against 1 project. Accounts whose
      runs predate / bypass the queue (no Job rows) fall back to projects_run.
    - downloads come from ArtifactEvent, which is only written for FREE-tier
      (trial-funded) projects -- a paid project's unlimited re-downloads leave
      no row, so an empty list there does not mean "never downloaded".
    - ip_shared flags a trial claim whose day-rotated IP+user-agent hash
      matches an EARLIER claim by a different account. A flag only: offices
      share IPs, nothing is ever blocked on it."""
    ids = [u.id for u in users]
    if not ids:
        return []
    ta_runs = {
        uid: int(n) for uid, n in
        s.query(Job.user_id, func.count(Job.id))
        .filter(Job.user_id.in_(ids), Job.job_type == "tender_analysis", Job.status != "failed")
        .group_by(Job.user_id).all()
    }
    drafted = {
        r[0] for r in s.query(Job.user_id)
        .filter(Job.user_id.in_(ids), Job.job_type == "draft_generation", Job.status != "failed")
        .distinct().all()
    }
    drafted |= {
        r[0] for r in s.query(AiCallLog.user_id)
        .filter(AiCallLog.user_id.in_(ids), AiCallLog.purpose == "draft_generation")
        .distinct().all()
    }
    downloads: dict[str, list[tuple[str, datetime]]] = {}
    for uid, atype, when in (
        s.query(ArtifactEvent.user_id, ArtifactEvent.artifact_type, func.max(ArtifactEvent.created_at))
        .filter(ArtifactEvent.user_id.in_(ids))
        .group_by(ArtifactEvent.user_id, ArtifactEvent.artifact_type)
        .order_by(func.max(ArtifactEvent.created_at))
        .all()
    ):
        downloads.setdefault(uid, []).append((atype, when))

    claims = {c.user_id: c for c in s.query(TrialClaim).filter(TrialClaim.user_id.in_(ids)).all()}
    hashes = {c.device_hash for c in claims.values() if c.device_hash}
    others = (
        s.query(TrialClaim.device_hash, TrialClaim.user_id, TrialClaim.claimed_at)
        .filter(TrialClaim.device_hash.in_(hashes)).all()
        if hashes else []
    )

    progress = _latest_project_progress(s, ids)

    rows = []
    for u, sign in zip(users, signups):
        claim = claims.get(u.id)
        ip_shared = bool(
            claim and claim.device_hash and any(
                o[0] == claim.device_hash and o[1] != u.id and o[2] is not None
                and claim.claimed_at is not None and o[2] < claim.claimed_at
                for o in others
            )
        )
        projects_run = int(usage_by_user.get(u.id, (0, 0))[0])
        rows.append({
            "email": u.email or "",
            "created": u.created_at,
            "verified": u.email_verified_at is not None,
            "tier": sign["tier"],
            "projects_run": projects_run,
            "ta_runs": max(ta_runs.get(u.id, 0), projects_run),
            "drafted": u.id in drafted,
            "downloads": downloads.get(u.id, []),
            "ip_shared": ip_shared,
            **progress.get(u.id, {"furthest_step": "", "last_active": None, "project_name": "", "unreadable": False}),
        })
    return rows


def _latest_project_progress(s, user_ids: list[str]) -> dict[str, dict]:
    """{user_id: {"furthest_step", "last_active", "project_name", "unreadable"}}
    for each account's LATEST saved project (SavedProject.updated_at), derived
    from the stored project file -- see modules/project_progress.py. Read-only,
    no new tracking. Accounts with no saved project are simply absent.

    The project zips can be several MB, so only the id/timestamp of each
    account's newest project is fetched in bulk and the bytes are loaded one
    project at a time (15 at most) and dropped straight after parsing."""
    from modules import project_progress

    if not user_ids:
        return {}
    newest: dict[str, tuple] = {}
    for pid, uid, name, updated, created in s.query(
        SavedProject.id, SavedProject.user_id, SavedProject.name,
        SavedProject.updated_at, SavedProject.created_at,
    ).filter(SavedProject.user_id.in_(user_ids)).all():
        stamp = updated or created
        if uid not in newest or (stamp is not None and (newest[uid][3] is None or stamp > newest[uid][3])):
            newest[uid] = (pid, name, updated, stamp)

    out: dict[str, dict] = {}
    for uid, (pid, name, updated, stamp) in newest.items():
        blob = s.query(SavedProject.project_bytes).filter(SavedProject.id == pid).scalar()
        payload = project_progress.read_payload(blob) if blob else None
        step, export_recorded = "", False
        if payload is not None:
            ident = project_progress.project_name_of(payload).lower()
            if ident:
                # Export only exists as a recorded free-tier download; match it
                # to this project by the key's leading project-name segment.
                export_recorded = any(
                    (k or "").lower().startswith(ident + "|") or (k or "").lower() == ident
                    for (k,) in s.query(ArtifactEvent.project_key).filter(ArtifactEvent.user_id == uid).all()
                )
            step = project_progress.furthest_step(payload, export_recorded)
        out[uid] = {
            "furthest_step": step,
            "last_active": stamp,
            "project_name": (name or ""),
            "unreadable": payload is None,
        }
        del blob, payload
    return out


def admin_stats() -> dict:
    """Read-only rollup for the admin panel (see app's sidebar "Admin
    stats" button; gated by auth.is_admin_user). Aggregates across ALL
    accounts: user counts, bids run, subscription/pay-as-you-go state, AI
    cost, and the most recent bids. Nothing here mutates anything."""
    from datetime import timedelta
    now = _now()
    month_ago = now - timedelta(days=30)
    with get_session() as s:
        total_users = s.query(func.count(User.id)).scalar() or 0
        new_users_30d = s.query(func.count(User.id)).filter(User.created_at >= month_ago).scalar() or 0
        active_subs = s.query(func.count(User.id)).filter(User.subscription_status == "active").scalar() or 0
        past_due = s.query(func.count(User.id)).filter(User.subscription_status == "past_due").scalar() or 0
        outstanding_credits = s.query(func.coalesce(func.sum(User.bid_credits), 0)).scalar() or 0
        total_bids = s.query(func.count(ProposalUsage.id)).scalar() or 0
        bids_30d = s.query(func.count(ProposalUsage.id)).filter(ProposalUsage.created_at >= month_ago).scalar() or 0
        cost_30d = (
            s.query(func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0))
            .filter(AiCallLog.created_at >= month_ago)
            .scalar() or 0.0
        )
        recent_bids = (
            s.query(ProposalUsage.project_name, ProposalUsage.created_at, User.email)
            .join(User, User.id == ProposalUsage.user_id)
            .order_by(ProposalUsage.created_at.desc())
            .limit(10)
            .all()
        )

        # BRIEF_ADMIN_RECENT_SIGNUPS.md: recent_bids above only ever names
        # an account AFTER its first Tender Analysis run -- a signed-up-
        # but-never-run account is otherwise invisible by name here. This
        # is the 15 newest accounts by creation date, regardless of usage.
        #
        # Local import: auth.py imports db at module level, so importing
        # auth up at this module's top would be a cycle -- this is the
        # only place in db.py that needs UNLIMITED_ACCOUNTS, so it's
        # imported here instead.
        from modules import auth
        _unlimited = {e.strip().lower() for e in auth.UNLIMITED_ACCOUNTS}

        recent_signup_users = (
            s.query(User)
            .order_by(User.created_at.desc())
            .limit(15)
            .all()
        )
        _signup_ids = [u.id for u in recent_signup_users]
        # One grouped query for all 15 users' usage rows -- bids_run AND
        # "has any non-trial row" together via conditional aggregation, so
        # this stays a single query instead of a second one per check (no
        # per-user N+1 either way).
        _usage_by_user: dict[str, tuple[int, int]] = {}
        if _signup_ids:
            for _uid, _cnt, _nontrial_cnt in (
                s.query(
                    ProposalUsage.user_id,
                    func.count(ProposalUsage.id),
                    func.sum(case((ProposalUsage.funded_by != "trial", 1), else_=0)),
                )
                .filter(ProposalUsage.user_id.in_(_signup_ids))
                .group_by(ProposalUsage.user_id)
                .all()
            ):
                _usage_by_user[_uid] = (int(_cnt or 0), int(_nontrial_cnt or 0))

        recent_signups = []
        for u in recent_signup_users:
            _bids_run, _nontrial_count = _usage_by_user.get(u.id, (0, 0))
            _email_norm = (u.email or "").strip().lower()
            if _email_norm in _unlimited:
                tier = "unlimited"
            elif u.subscription_status == "active":
                tier = "subscribed"
            elif u.subscription_status == "past_due":
                tier = "past due"
            elif (u.bid_credits or 0) > 0 or _nontrial_count > 0:
                tier = "paid"
            else:
                tier = "trial"
            recent_signups.append({
                "email": u.email or "",
                "created": u.created_at,
                "tier": tier,
                "bids_run": _bids_run,
            })
        recent_activity = _recent_activity_rows(s, recent_signup_users, recent_signups, _usage_by_user)
    return {
        "total_users": int(total_users),
        "new_users_30d": int(new_users_30d),
        "active_subscriptions": int(active_subs),
        "past_due_subscriptions": int(past_due),
        "outstanding_bid_credits": int(outstanding_credits),
        "total_bids": int(total_bids),
        "bids_30d": int(bids_30d),
        "ai_cost_30d_usd": float(cost_30d),
        "recent_bids": [
            {"project": r[0] or "(unnamed)", "when": r[1], "email": r[2] or ""}
            for r in recent_bids
        ],
        "recent_signups": recent_signups,
        "recent_activity": recent_activity,
    }


def project_ai_cost(project_key: str, user_id: str | None = None) -> dict:
    """Cost rollup for ONE project -- used to show a per-bid cost figure.
    Returns {"calls", "cost_usd", "input_tokens", "output_tokens",
    "unpriced_calls"}.

    Part 4a (BRIEF_ISOLATION_AND_PRIVACY.md): project_key alone is not
    unique across accounts -- two accounts whose project name, tender
    name, client name and brief hash all collide produce the same key.
    Nothing leaks today because the only caller (ai_interface.py's
    best-effort cost-logging path, never shown to a customer) always has a
    user_id in its usage context and now always passes it -- but without
    this filter, that collision would blend two accounts' AI spend
    together in the figure. user_id is optional (not every AiCallLog row
    has one -- see the column's own comment) so a caller that genuinely
    wants the project-wide total across all attribution can still get it
    by omitting it."""
    project_key = (project_key or "").strip()
    user_id = (user_id or "").strip() or None
    with get_session() as s:
        row_query = s.query(
            func.count(AiCallLog.id),
            func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0),
            func.coalesce(func.sum(AiCallLog.input_tokens), 0),
            func.coalesce(func.sum(AiCallLog.output_tokens), 0),
        ).filter(AiCallLog.project_key == project_key)
        unpriced_query = s.query(func.count(AiCallLog.id)).filter(
            AiCallLog.project_key == project_key, AiCallLog.estimated_cost_usd.is_(None)
        )
        if user_id is not None:
            row_query = row_query.filter(AiCallLog.user_id == user_id)
            unpriced_query = unpriced_query.filter(AiCallLog.user_id == user_id)
        row = row_query.first()
        unpriced = unpriced_query.scalar() or 0
    return {
        "calls": int(row[0] or 0),
        "cost_usd": float(row[1] or 0.0),
        "input_tokens": int(row[2] or 0),
        "output_tokens": int(row[3] or 0),
        "unpriced_calls": int(unpriced),
    }


# A NULL AiCallLog.estimated_cost_usd means an unpriced model was used, not
# a free one (see the AiCallLog model's own comment) -- account_ai_cost()
# and accounts_ai_cost_summary() below treat it at this conservative flat
# estimate so an unpriced provider can't quietly let a trial account bypass
# limits.TRIAL_AI_SPEND_CEILING_USD.
UNPRICED_CALL_COST_USD = 0.02


def account_ai_cost(user_id: str | None) -> float:
    """Summed estimated AI cost for ONE account, across every project --
    the figure the trial AI-spend ceiling (limits.TRIAL_AI_SPEND_CEILING_USD)
    checks before every AI feature runs. Returns 0.0 for no user_id, no
    calls logged, or any query failure -- degrades to "not over the
    ceiling" rather than risk blocking a legitimate account on a transient
    DB hiccup, same philosophy as the rest of this app's gates."""
    if not user_id:
        return 0.0
    try:
        with get_session() as s:
            total = (
                s.query(func.coalesce(
                    func.sum(func.coalesce(AiCallLog.estimated_cost_usd, UNPRICED_CALL_COST_USD)), 0.0,
                ))
                .filter(AiCallLog.user_id == user_id)
                .scalar()
            )
        return float(total or 0.0)
    except Exception:
        return 0.0


def accounts_ai_cost_summary(min_cost_usd: float = 0.0, limit: int = 50) -> list[dict]:
    """Per-account AI cost rollup across ALL users with at least one logged
    call, highest spend first -- backs the admin stats panel's "trial
    accounts near/over the spend ceiling" and "top accounts by estimated
    spend" figures. Returns [{"user_id", "email", "subscription_status",
    "bid_credits", "cost_usd", "calls"}, ...]. Deliberately returns raw
    account fields rather than a trial/paid verdict: classifying a row
    (auth.get_access_status / limits.is_paid_tier, including the
    auth.UNLIMITED_ACCOUNTS bypass) is the caller's job, to avoid this
    module importing auth (auth already imports db)."""
    with get_session() as s:
        cost_expr = func.coalesce(
            func.sum(func.coalesce(AiCallLog.estimated_cost_usd, UNPRICED_CALL_COST_USD)), 0.0,
        )
        rows = (
            s.query(
                User.id, User.email, User.subscription_status, User.bid_credits,
                cost_expr, func.count(AiCallLog.id),
            )
            .join(AiCallLog, AiCallLog.user_id == User.id)
            .group_by(User.id, User.email, User.subscription_status, User.bid_credits)
            .having(cost_expr >= min_cost_usd)
            .order_by(cost_expr.desc())
            .limit(limit)
            .all()
        )
    return [
        {
            "user_id": r[0],
            "email": r[1] or "",
            "subscription_status": r[2] or "trial",
            "bid_credits": int(r[3] or 0),
            "cost_usd": float(r[4] or 0.0),
            "calls": int(r[5] or 0),
        }
        for r in rows
    ]


def init_db() -> None:
    """Creates all tables if they don't exist yet. Safe to call on every
    app startup -- idempotent. Call this once near the top of app.py."""
    Base.metadata.create_all(engine)
    _run_light_migrations()


def _run_light_migrations() -> None:
    """create_all() above only creates tables that don't exist yet -- it
    does NOT add new columns to a table that's already there (e.g. `users`
    on the live production database), so a new nullable Column on an
    existing model (like User.accepted_terms_at) needs an explicit ALTER
    TABLE the first time this runs against a database created before that
    column existed. Checks column existence first so this is a no-op (and
    safe to run on every startup) once the column is there -- works the
    same way against both the local SQLite fallback and Postgres."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing_columns = {c["name"] for c in inspector.get_columns("users")}
    if "accepted_terms_at" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN accepted_terms_at TIMESTAMP"))
    if "bid_credits" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN bid_credits INTEGER DEFAULT 0"))
    if "subscription_bids_used" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN subscription_bids_used INTEGER DEFAULT 0"))
    if "subscription_period_end" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN subscription_period_end TIMESTAMP"))
    if "preferred_language" not in existing_columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN preferred_language VARCHAR"))

    # One free trial per person: new users columns (see User), then the
    # one-time legacy backfill. Every account that exists when email_verified_at
    # is first added is treated as VERIFIED (created_at) and gets a
    # TrialClaim row, so existing customers are unaffected, and a legacy
    # account that is deleted and re-created cannot pick up a second trial.
    _verified_column_added = "email_verified_at" not in existing_columns
    for _col, _ddl in (
        ("email_normalized", "VARCHAR"),
        ("email_verified_at", "TIMESTAMP"),
        ("verify_code_hash", "VARCHAR"),
        ("verify_code_expires_at", "TIMESTAMP"),
        ("verify_code_attempts", "INTEGER DEFAULT 0"),
        ("verify_code_sent_at", "TIMESTAMP"),
        ("trial_denied_reason", "VARCHAR DEFAULT ''"),
    ):
        if _col not in existing_columns:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {_col} {_ddl}"))
            except Exception:
                # The web and worker services both run init_db() when a deploy
                # starts them together; the other one may have added this
                # column between our check and our ALTER. Anything else wrong
                # with the column surfaces on the very next statement.
                if _col not in {c["name"] for c in inspect(engine).get_columns("users")}:
                    raise

    from modules import email_identity
    with engine.begin() as conn:
        # Oldest account wins a normalised address; a later legacy alias of it
        # keeps NULL (a unique index allows any number of NULLs) rather than
        # failing the whole migration -- it still logs in by its own email.
        _taken = {r[0] for r in conn.execute(text(
            "SELECT email_normalized FROM users WHERE email_normalized IS NOT NULL"
        ))}
        for _uid_, _email in conn.execute(text(
            "SELECT id, email FROM users WHERE email_normalized IS NULL ORDER BY created_at, id"
        )).fetchall():
            _n = email_identity.normalize_email(_email)
            if _n and _n not in _taken:
                conn.execute(text("UPDATE users SET email_normalized = :n WHERE id = :i"),
                             {"n": _n, "i": _uid_})
                _taken.add(_n)
    if _verified_column_added:
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE users SET email_verified_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
                "WHERE email_verified_at IS NULL"
            ))
            for _uid_, _n, _created in conn.execute(text(
                "SELECT id, email_normalized, created_at FROM users WHERE email_normalized IS NOT NULL"
            )).fetchall():
                conn.execute(text(
                    "INSERT INTO trial_claims (id, email_normalized, email_domain, user_id, claimed_at, device_hash) "
                    "SELECT :id, :n, :d, :u, :c, '' WHERE NOT EXISTS "
                    "(SELECT 1 FROM trial_claims WHERE email_normalized = :n)"
                ), {"id": _uid(), "n": _n, "d": email_identity.email_domain(_n), "u": _uid_, "c": _created})
    with engine.begin() as conn:
        # Same name create_all() gives a fresh database's index, so a fresh
        # database doesn't end up with two.
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_normalized ON users (email_normalized)"
        ))

    if "jobs" in inspector.get_table_names():
        _job_columns = {c["name"] for c in inspector.get_columns("jobs")}
        if "project_key" not in _job_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN project_key VARCHAR"))
        if "reserved" not in _job_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN reserved BOOLEAN DEFAULT FALSE"))
        with engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_project_key ON jobs (project_key)"))

    # Retrofit the (user_id, project_key) unique constraint onto
    # proposal_usage -- see ProposalUsage's docstring for why this exists
    # (closing the double-click / double-rerun double-charge race).
    # create_all() only applies a model's UniqueConstraint when it creates
    # the table fresh, so an existing production table needs this done
    # explicitly. A production database that's already hit the race being
    # fixed here may already contain duplicate (user_id, project_key) rows,
    # and CREATE UNIQUE INDEX would simply fail against those -- so any
    # duplicates are cleaned up first (keeping the oldest row of each
    # duplicate set, since that's the one that actually corresponds to the
    # credit that should have been spent; the extra row(s) were the bug).
    # "IF NOT EXISTS" makes both statements safe to run on every startup.
    if "proposal_usage" in inspector.get_table_names():
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM proposal_usage WHERE id NOT IN "
                "(SELECT MIN(id) FROM proposal_usage GROUP BY user_id, project_key)"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_proposal_usage_user_project_key "
                "ON proposal_usage (user_id, project_key)"
            ))
        _pu_columns = {c["name"] for c in inspector.get_columns("proposal_usage")}
        if "funded_by" not in _pu_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE proposal_usage ADD COLUMN funded_by VARCHAR DEFAULT ''"))


def get_session():
    """Short-lived session per Streamlit script run. Callers should use it
    as a context manager: `with db.get_session() as s: ...`."""
    return SessionLocal()
