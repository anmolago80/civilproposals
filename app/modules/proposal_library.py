"""
proposal_library.py

DB-backed, per-user archive of finished proposal packs -- the SaaS
replacement for the original local-disk version of this module (which wrote
DOCX files + JSON sidecars into a library/<project_type>/ folder next to the
code, fine for a single-machine prototype but not for a multi-tenant hosted
app). See modules/db.py's LibraryEntry model for the schema.

Kept as close as possible to the original function names/shapes so app.py's
call sites needed minimal changes -- every function now additionally takes
a user_id as its first argument, since a hosted, multi-tenant library must
never let one firm's archived proposals leak into another firm's library
browser. "path" in the original API (a filesystem path) is now an opaque
library-entry id string; callers don't need to know the difference.
"""

from __future__ import annotations

from modules import db


def archive_proposal(
    user_id: str,
    docx_bytes: bytes,
    project_type: str,
    pack_type: str,
    project_name: str = "",
    client_name: str = "",
    tender_name: str = "",
    tags: str = "",
) -> dict:
    """Stores docx_bytes as a new library entry owned by user_id. Returns a
    dict in the same shape list_library() entries use, plus "path" (an
    opaque id -- pass it to read_entry_bytes() to fetch the bytes back)."""
    folder_name = (project_type or "").strip() or "Unspecified"
    label = (project_name or "").strip() or (tender_name or "").strip() or "Untitled project"
    filename = f"{label}.docx"

    entry = db.LibraryEntry(
        user_id=user_id,
        project_name=project_name or "",
        client_name=client_name or "",
        tender_name=tender_name or "",
        project_type=folder_name,
        pack_type=pack_type,
        tags=tags or "",
        filename=filename,
        docx_bytes=docx_bytes,
    )
    with db.get_session() as s:
        s.add(entry)
        s.commit()
        s.refresh(entry)
        return _entry_to_dict(entry)


def list_library(user_id: str, project_type: str | None = None, pack_type: str | None = None,
                  tag: str | None = None) -> list[dict]:
    """[{project_name, client_name, tender_name, project_type, pack_type,
    archived_at, filename, path, tags}] for this user's archived entries,
    newest first. Optionally filtered by project type, pack type, and/or a
    single tag (substring match against the comma-separated tags field)."""
    with db.get_session() as s:
        q = s.query(db.LibraryEntry).filter(db.LibraryEntry.user_id == user_id)
        if project_type:
            q = q.filter(db.LibraryEntry.project_type == project_type)
        if pack_type:
            q = q.filter(db.LibraryEntry.pack_type == pack_type)
        if tag:
            q = q.filter(db.LibraryEntry.tags.contains(tag))
        q = q.order_by(db.LibraryEntry.archived_at.desc())
        return [_entry_to_dict(e) for e in q.all()]


def read_entry_bytes(user_id: str, entry_id: str) -> bytes:
    """Reads back an archived DOCX's bytes -- scoped to user_id so one
    user can never fetch another user's archived proposal by guessing an
    id."""
    with db.get_session() as s:
        entry = s.query(db.LibraryEntry).filter(
            db.LibraryEntry.id == entry_id, db.LibraryEntry.user_id == user_id,
        ).first()
        if not entry:
            raise FileNotFoundError("Library entry no longer exists.")
        return entry.docx_bytes


def delete_entry(user_id: str, entry_id: str) -> None:
    with db.get_session() as s:
        entry = s.query(db.LibraryEntry).filter(
            db.LibraryEntry.id == entry_id, db.LibraryEntry.user_id == user_id,
        ).first()
        if entry:
            s.delete(entry)
            s.commit()


def _entry_to_dict(entry: db.LibraryEntry) -> dict:
    return {
        "project_name": entry.project_name,
        "client_name": entry.client_name,
        "tender_name": entry.tender_name,
        "project_type": entry.project_type,
        "pack_type": entry.pack_type,
        "tags": entry.tags,
        "archived_at": entry.archived_at.strftime("%Y%m%d_%H%M%S") if entry.archived_at else "",
        "filename": entry.filename,
        "path": entry.id,  # opaque id, kept under the old key name for minimal call-site diff
    }
