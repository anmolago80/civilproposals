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
    create_engine, Column, String, Integer, DateTime, Boolean, LargeBinary,
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

    # Usage-based free trial: N free full proposals (Tender Analysis runs),
    # then payment is required. See auth.get_access_status(). Matches the
    # "1 free bid on sign up" pricing shown on the landing page -- was 3
    # under the old flat $200/month plan.
    trial_proposals_used = Column(Integer, default=0)
    trial_proposals_limit = Column(Integer, default=1)

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
    project doesn't consume another trial credit."""
    __tablename__ = "proposal_usage"

    id = Column(String, primary_key=True, default=_uid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    project_key = Column(String, nullable=False)
    project_name = Column(String, default="")
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="proposal_usage")


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


def get_session():
    """Short-lived session per Streamlit script run. Callers should use it
    as a context manager: `with db.get_session() as s: ...`."""
    return SessionLocal()
