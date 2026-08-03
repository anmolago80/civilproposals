"""
local_project_store.py

Local-disk auto-save on top of project_store.py's save_project()/load_project().
This only makes sense because the app runs locally on the user's own machine
(see run_app.bat) -- a future hosted, multi-tenant version of this tool would
need a real per-user backend, not a shared folder next to the code.

Saves land in PROJECTS_DIR ("projects/" next to app.py) as
"<slugified-project-name>.tenderproj.zip" -- one file per project, reusing the
same slug overwrites it. This is deliberately "current state only", not a
version history; the manual Save/Load Project zip in project_store.py (a
file the user explicitly downloads) already covers point-in-time backups and
handing a project to someone else. This module is purely for "don't lose
today's work if I close the tab" convenience.
"""

from __future__ import annotations

import re
from pathlib import Path

from modules import project_store

PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


def _slugify(name: str) -> str:
    name = (name or "").strip()
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return slug or "untitled_project"


def project_identifier(project_name: str, tender_name: str) -> str:
    """
    What a local auto-save / "Recent projects" entry gets named after. Prefers
    "Project name" over "Tender / EOI name" -- the project name is the
    friendly, descriptive label the user picks (e.g. "Bribie Island Bridge"),
    while the tender/EOI name is often left as a short internal reference or
    placeholder (e.g. just "Tender") that doesn't actually distinguish one
    saved project from another in the "Recent projects" list. Falls back to
    the tender name only if no project name has been entered yet.
    """
    project_name = (project_name or "").strip()
    tender_name = (tender_name or "").strip()
    return project_name or tender_name or ""


def list_local_projects() -> list[dict]:
    """[{"slug", "display_name", "path", "modified"}] for every locally saved
    project, newest first. Empty list if the projects folder doesn't exist yet
    (i.e. nothing has ever been auto-saved)."""
    if not PROJECTS_DIR.exists():
        return []
    entries = []
    for p in sorted(PROJECTS_DIR.glob("*.tenderproj.zip")):
        slug = p.name[: -len(".tenderproj.zip")]
        entries.append({
            "slug": slug,
            "display_name": slug.replace("_", " "),
            "path": str(p),
            "modified": p.stat().st_mtime,
        })
    entries.sort(key=lambda e: e["modified"], reverse=True)
    return entries


def save_local(state, project_name: str) -> str:
    """Writes state to PROJECTS_DIR/<slug>.tenderproj.zip (creating the folder
    on first use) and returns the path written to."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slugify(project_name)
    path = PROJECTS_DIR / f"{slug}.tenderproj.zip"
    path.write_bytes(project_store.save_project(state))
    return str(path)


def load_local(path: str) -> dict:
    with open(path, "rb") as f:
        return project_store.load_project(f.read())


def delete_local(path: str) -> None:
    """Refuses to delete anything outside PROJECTS_DIR -- defence in depth
    against a malformed path ever reaching this function."""
    p = Path(path).resolve()
    if p.exists() and p.parent == PROJECTS_DIR.resolve():
        p.unlink()
