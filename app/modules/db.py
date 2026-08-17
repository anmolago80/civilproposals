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
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime, Boolean, LargeBinary,
    ForeignKey, Text, select, func, UniqueConstraint, inspect, text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    # Local dev fallback -- a file next to this module, gitignored.
    _local_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "civilproposals_local.db")
    DATABASE_URL = f"sqlite:///{_local_path}"

# Railway (and most managed Postgres providers) hand out a "postgres://" URL;
# SQLAlchemy 2.x / modern psycopg2 wants "postgresql://". Normalise so the
# same env var works without the user having to edit it.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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

    # The Monthly plan's advertised "3 bids included" cap (see
    # auth.SUBSCRIPTION_MONTHLY_BID_LIMIT) -- how many of THIS Stripe billing
    # period's 3 bids have been used, and the period-end timestamp Stripe
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

    user = relationship("User", back_populates="proposal_usage")


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
    }


def project_ai_cost(project_key: str) -> dict:
    """Cost rollup for ONE project -- used to show a per-bid cost figure.
    Returns {"calls", "cost_usd", "input_tokens", "output_tokens",
    "unpriced_calls"}."""
    project_key = (project_key or "").strip()
    with get_session() as s:
        row = (
            s.query(
                func.count(AiCallLog.id),
                func.coalesce(func.sum(AiCallLog.estimated_cost_usd), 0.0),
                func.coalesce(func.sum(AiCallLog.input_tokens), 0),
                func.coalesce(func.sum(AiCallLog.output_tokens), 0),
            )
            .filter(AiCallLog.project_key == project_key)
            .first()
        )
        unpriced = (
            s.query(func.count(AiCallLog.id))
            .filter(AiCallLog.project_key == project_key, AiCallLog.estimated_cost_usd.is_(None))
            .scalar() or 0
        )
    return {
        "calls": int(row[0] or 0),
        "cost_usd": float(row[1] or 0.0),
        "input_tokens": int(row[2] or 0),
        "output_tokens": int(row[3] or 0),
        "unpriced_calls": int(unpriced),
    }


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


def get_session():
    """Short-lived session per Streamlit script run. Callers should use it
    as a context manager: `with db.get_session() as s: ...`."""
    return SessionLocal()
