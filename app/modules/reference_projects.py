"""
reference_projects.py

Turns raw, pasted-together project-reference material (the "Project references"
upload in tab 2) into distinct, structured ReferenceProject entries for the
Relevant Experience section of the exported pack -- instead of the old
behaviour of dumping the raw upload text into the AI draft prompt and letting
whatever came back (often close to a verbatim copy-paste) stand as the
section body.

Two things this module does that the old free-text draft didn't:

1. Splits the material into distinct projects (same idea as team_bios.py
   splitting a CV library into distinct people) and REVISES each project's
   write-up for a consistent tone and length, and for RELEVANCE to the
   current tender -- pulling forward the parts of a real past project that
   actually speak to this brief's scope/disciplines, rather than reprinting
   the entire original blurb regardless of fit. Still a no-invention tool:
   the model may only reorganise, tighten, and re-emphasise facts already in
   the source text, never add a client, value, date, or outcome that isn't
   there.

2. Identifies which of the firm's own key personnel (matched against the
   names actually assigned in the resourcing plan / CV library) are named as
   having worked on each reference project -- the data the Section 2 x
   Section 3 cross-reference table (export_docx._build_personnel_project_matrix)
   is built from.

Photos are handled the same way team headshots are (app.py/session_state,
raw bytes keyed by project title) rather than through this module's pydantic
model, since they're binary assets the user uploads and assigns per project.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai_json

SYSTEM_MESSAGE = """You are preparing the "Relevant Experience" section of an engineering/\
infrastructure tender proposal from a firm's own library of past-project write-ups, which may \
describe several distinct projects concatenated together. For EACH project you identify:

- Identify the project's real title and client, exactly as stated in the source material.
- Write a REVISED description: tighten and reorganise the SOURCE material into consistent, \
professional proposal prose -- 3-5 sentences, in the same tone/register as the rest of the \
section. You may cut irrelevant detail and lead with whatever in the source material is most \
relevant to the CURRENT tender's scope and disciplines (given to you below). You must NOT \
invent, add, or infer a client, value, date, scope item, or outcome that is not already stated \
in the source material for that project -- this is a rewrite for clarity, consistency and \
relevance, not new content.
- Write a short "relevance to project" statement (1-3 sentences) explaining why this past \
project is relevant to the CURRENT tender, grounded only in facts already present in the \
source material for that project (e.g. same asset type, same client, same discipline, similar \
constraints) -- never a generic claim.
- List which of the firm's OWN people (not the client's) are named in the source material as \
having worked on that project. Only include a name if the source material for that specific \
project actually names them -- never guess who might have worked on it.

If you cannot confidently tell where one project's material ends and the next begins, or a \
project's source material is too thin to safely revise (e.g. no real detail beyond a title), \
say so in a warning rather than inventing content to fill the gap."""

PROMPT_TEMPLATE = """CURRENT TENDER CONTEXT (use this only to decide what to emphasise from \
each project's real material -- never to add facts to a project that aren't already stated \
for it):
Client for this tender: {client_name}
Project scope: {project_scope}
Disciplines involved: {disciplines}
What the client says it wants to achieve:
{client_objectives}

Relevance to THIS tender is what the "relevance_text" field is for. A past project for the \
SAME client, or with the same objectives, is the strongest possible relevance -- say so when \
the material shows it. Never claim a shared client or objective the material does not state.

Below is the firm's project-reference material, which may contain several distinct past \
projects concatenated together. Identify each distinct project and produce the required fields \
for each.

Return a JSON object:
{{
  "projects": [
    {{
      "title": string,
      "client": string,
      "description": string (the revised, tightened, relevance-led description -- see rules),
      "relevance_text": string,
      "personnel_involved": [string]  (only names the source material actually names for THIS project)
    }}
  ],
  "warnings": [string]
}}

--- PROJECT REFERENCE MATERIAL ---
{material}
--- END MATERIAL ---"""


class ReferenceProject(BaseModel):
    title: str
    client: str = ""
    description: str = ""
    relevance_text: str = ""
    personnel_involved: list[str] = Field(default_factory=list)
    # Stable identity for this project's photo, independent of its title --
    # see ResourceAssignment.photo_id for the same problem and reasoning.
    photo_id: str = ""


def draft_reference_projects(
    raw_text: str,
    project_scope: str = "",
    disciplines: list[str] | None = None,
    config: dict | None = None,
    max_chars: int = 60000,
    client_name: str = "",
    client_objectives: list[str] | None = None,
) -> tuple[list[ReferenceProject], list[str]]:
    """
    Draft candidate ReferenceProject entries from the raw uploaded material.
    Always a DRAFT: app.py must let the user review/edit every field (title,
    client, description, relevance, personnel) before export, same as
    team_bios.draft_team_bios_from_cv().
    """
    material = (raw_text or "").strip()
    if not material:
        return [], ["No project reference material was supplied -- nothing to draft from."]
    if len(material) > max_chars:
        material = material[:max_chars] + "\n\n[...truncated for length...]"

    prompt = PROMPT_TEMPLATE.format(
        client_name=(client_name or "").strip() or "(not supplied)",
        project_scope=project_scope or "(not extracted)",
        disciplines=", ".join(disciplines or []) or "(none extracted)",
        client_objectives="\n".join(f"- {o}" for o in (client_objectives or [])) or "- (none extracted)",
        material=material,
    )
    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=4000)

    raw_projects = data.get("projects", []) if isinstance(data, dict) else []
    projects = [ReferenceProject.model_validate(p) for p in raw_projects]
    warnings = list(data.get("warnings", [])) if isinstance(data, dict) else []
    if not projects:
        warnings.append("No individual reference projects could be confidently identified in the uploaded material.")
    return projects, warnings


def reconcile_personnel(project: ReferenceProject, known_names: list[str]) -> list[str]:
    """
    Case-insensitive match of a project's drafted personnel_involved against the
    real, current key-personnel names (resourcing plan / CV library) -- so a
    name the AI spelled slightly differently, or a stray name that isn't
    actually one of the firm's current key personnel, doesn't silently break
    the cross-reference matrix. Returns the canonical (known_names) spelling
    for every match; unmatched drafted names are dropped from the matrix (the
    user can still see/edit them in the project's own personnel_involved list).
    """
    lower_known = {n.lower(): n for n in known_names or []}
    matched = []
    for name in project.personnel_involved:
        canon = lower_known.get((name or "").strip().lower())
        if canon and canon not in matched:
            matched.append(canon)
    return matched
