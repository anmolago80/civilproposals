"""
cloud_project_store.py

Database-backed equivalent of local_project_store.py, for hosted SaaS use
(see IS_SAAS_MODE in app.py). local_project_store.py writes to a folder on
the *server's* local disk -- fine for the original single-user desktop app,
but wrong for a multi-tenant deployment on two counts: every logged-in
user's browser session would share the same folder (a real cross-account
data leak, not just a rough edge), and Railway's container disk is wiped on
every redeploy anyway, so nothing saved there survives a deploy regardless.

This module keeps the same "one entry per project, current state only"
shape, just scoped to a user_id and stored as a row in the database instead
of a file. It reuses project_store.save_project()/load_project() for the
actual serialisation format (a .tenderproj.zip's worth of bytes, with AI
credentials deliberately excluded -- see that module's docstring) -- this
module is only responsible for *where* those bytes live.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from modules import db, project_store


def _slugify(name: str) -> str:
    name = (name or "").strip()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return slug or "untitled_project"


def project_identifier(project_name: str, tender_name: str) -> str:
    """Same preference order as local_project_store.project_identifier():
    the descriptive project name over the often-generic tender/EOI name."""
    project_name = (project_name or "").strip()
    tender_name = (tender_name or "").strip()
    return project_name or tender_name or ""


def list_cloud_projects(user_id: str) -> list[dict]:
    """[{"id", "slug", "display_name", "modified"}] for every project this
    user has saved, newest first. Empty list if they've never saved one."""
    with db.get_session() as s:
        rows = (
            s.query(db.SavedProject)
            .filter(db.SavedProject.user_id == user_id)
            .order_by(db.SavedProject.updated_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "slug": r.slug,
                "display_name": r.name or r.slug.replace("_", " "),
                "modified": r.updated_at,
            }
            for r in rows
        ]


def save_cloud(user_id: str, project_name: str, blob: bytes) -> str:
    """Upserts the given (already-serialized, see project_store.save_project())
    bytes against (user_id, slug) -- reusing the same project name
    overwrites the existing row rather than creating a new one, same as the
    local version. Returns the slug saved under.

    Used to serialize `state` itself via project_store.save_project()
    internally -- the caller (app.py's _maybe_autosave()) now does that
    once up front instead, so it can hash the result and skip this
    function's DB write entirely when nothing's actually changed since the
    last autosave. That write is the expensive part at scale (a network
    round trip writing a multi-MB blob to Postgres, potentially every
    AUTOSAVE_INTERVAL_SECONDS for every active user), so avoiding a
    redundant one matters more here than in the local-disk equivalent."""
    slug = _slugify(project_name)
    now = datetime.now(timezone.utc)
    with db.get_session() as s:
        existing = (
            s.query(db.SavedProject)
            .filter(db.SavedProject.user_id == user_id, db.SavedProject.slug == slug)
            .first()
        )
        if existing:
            existing.name = project_name
            existing.project_bytes = blob
            existing.updated_at = now
        else:
            s.add(db.SavedProject(
                user_id=user_id, name=project_name, slug=slug, project_bytes=blob,
            ))
        s.commit()
    return slug


def load_cloud(user_id: str, entry_id: str) -> dict:
    with db.get_session() as s:
        row = s.query(db.SavedProject).filter(
            db.SavedProject.id == entry_id, db.SavedProject.user_id == user_id,
        ).first()
        if not row:
            raise project_store.ProjectLoadError("That saved project could not be found.")
        return project_store.load_project(row.project_bytes)


def delete_cloud(user_id: str, entry_id: str) -> None:
    with db.get_session() as s:
        row = s.query(db.SavedProject).filter(
            db.SavedProject.id == entry_id, db.SavedProject.user_id == user_id,
        ).first()
        if row:
            s.delete(row)
            s.commit()
