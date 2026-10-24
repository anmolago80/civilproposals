"""
project_progress.py

"How far did this account get?" -- derived, read-only, from a saved project
(db.SavedProject.project_bytes, the .tenderproj.zip modules/project_store.py
writes). Nothing here records anything new; it only reads project.json, never
the images in the zip.

Streamlit-free and database-free on purpose (db.py's admin view imports it).

STEPS is the order the owner asked for, which is NOT the tab order in the app
(there Team comes after Draft). "Furthest" is the highest step in this list
with evidence -- it does not require the earlier ones, because someone can
legitimately fill in Fees before drafting.

Each test mirrors the sidebar stepper's own "done" rule in
modules/pages/20_chrome.py, including its traps: resource_plan and
fee_estimates are auto-populated with EMPTY placeholder rows as soon as a
brief is analysed, so Team needs a real assigned name and Fees a non-zero
figure -- mere non-emptiness would put every analysed account at Fees.

Export cannot be read from a saved project at all (the built DOCX lives only
in the browser session), so the caller passes in whether a download was
recorded for it (db.ArtifactEvent -- written only for FREE-tier projects; a
paid project's unlimited re-downloads leave no row, so for those Export is
never reported and the step shown is the last one the project data proves).
"""

from __future__ import annotations

import io
import json
import zipfile

STEPS = ("setup", "upload", "analysis", "team", "fees", "draft", "export")


def _nonblank(value) -> bool:
    return bool((value or "").strip()) if isinstance(value, str) else bool(value)


def _any_positive(items, field: str) -> bool:
    for item in items or []:
        try:
            if isinstance(item, dict) and float(item.get(field) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def project_name_of(payload: dict) -> str:
    """The same identity the app uses (project name, else tender name)."""
    return (payload.get("project_name") or "").strip() or (payload.get("tender_name") or "").strip()


def reached_steps(payload: dict) -> set[str]:
    """Which of STEPS ("export" excluded -- see module docstring) the saved
    project's own data proves were reached."""
    reached: set[str] = set()
    if project_name_of(payload) or _nonblank(payload.get("client_name")):
        reached.add("setup")
    if payload.get("tender_extracted"):
        reached.add("upload")
    if payload.get("analysis"):
        reached.add("analysis")
    if any(
        isinstance(a, dict) and (a.get("person_name") or "").strip()
        for a in (payload.get("resource_plan") or [])
    ):
        reached.add("team")
    if (
        _any_positive(payload.get("fee_estimates"), "fee_percentage")
        or _any_positive(payload.get("discipline_fee_lines"), "fee_amount")
        or _any_positive(payload.get("scope_item_fees"), "fee_amount")
    ):
        reached.add("fees")
    if payload.get("drafts"):
        reached.add("draft")
    return reached


def read_payload(project_bytes: bytes) -> dict | None:
    """project.json from a saved-project zip, or None if it can't be read
    (corrupt / not a project file) -- the admin view shows that as unreadable
    rather than failing the whole table."""
    try:
        with zipfile.ZipFile(io.BytesIO(project_bytes)) as zf:
            payload = json.loads(zf.read("project.json"))
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


def furthest_step(payload: dict, export_recorded: bool = False) -> str:
    """The furthest of STEPS reached, or "" if none is."""
    reached = reached_steps(payload)
    if export_recorded:
        reached.add("export")
    for step in reversed(STEPS):
        if step in reached:
            return step
    return ""
