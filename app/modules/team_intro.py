"""
team_intro.py

Drafts a short, sales-forward team-introduction block for the very start of
the Key Personnel section -- before the org chart and the individual pen
pics. Unlike those (deterministic, built straight from the resourcing plan),
this is a narrative "why this team" pitch: a catchy heading, 2-3 short
paragraphs, and a closing pull-quote line, grounded in the SAME real,
already-entered personnel data (their real value-to-project write-ups and
relevant past projects) plus the brief's real scope/objectives.

Same no-invention discipline as the rest of the app: every named project or
claim must come from the resourcing plan's own value_to_project /
relevant_projects fields or the brief's project_scope / client_objectives --
never invented. Personnel excluded via the "Include in proposal" tick must
not be named here either -- the caller passes only already-filtered team
member data (draft_generator.format_team_context-style filtering, done by
the caller via resourcing.personnel_profiles_deduped + include_in_proposal).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai_json

SYSTEM_MESSAGE = """You are drafting a short, sales-forward "why this team" introduction for \
the very start of the Key Personnel section of an engineering/infrastructure tender proposal \
-- a FIRST-PASS, not submission-ready, block for a human proposal writer to review and finish. \
Its job is to sell the nominated team to the evaluator before they read the individual CV-style \
profiles that follow: a catchy, specific headline and a few short paragraphs that connect this \
team's REAL past project experience directly to what THIS brief actually needs, so an evaluator \
comes away thinking "this team has already done exactly this kind of work."

You must not invent: names, roles, projects, qualifications, or claims not present in the \
NOMINATED TEAM data you're given below. Only reference a named past project if it appears in \
that data's "relevant projects" or "on this project, X will" text for that specific person -- \
never a project you haven't been told about, and never attribute one person's project to \
another. If the supplied team data is thin, keep the copy shorter and more general rather than \
padding it with invented specifics. Ground the pitch in the brief's real scope and objectives \
(the specific structures/site conditions/challenges named there), not a generic "we are well \
placed to deliver" claim that could apply to any project."""

PROMPT_TEMPLATE = """Draft the team-introduction block for the start of the Key Personnel \
section.

PROJECT: {project_name}
CLIENT: {client_name}
PROJECT SCOPE (from the brief):
{project_scope}

CLIENT OBJECTIVES (from the brief, if stated):
{client_objectives}

NOMINATED TEAM (the ACTUAL people staffed to this bid, with their real project experience -- \
only reference a named project if it's listed here for that specific person; never invent one \
or mix up whose project is whose):
{team_context}

Write:
1. A short, catchy, specific headline naming or alluding to the real project (not a generic \
"Our Expert Team" label) -- think "The Right Team for [Project]'s [specific real challenge]".
2. Two to three short paragraphs (2-4 sentences each) connecting named team members' REAL past \
projects (bold them with **double asterisks**) to this brief's real, specific technical \
challenges -- pick whichever real experience is most directly relevant, don't force in every \
person if their experience doesn't add something specific.
3. One closing sentence as a bold, italic pull-quote-style statement that sums up why this team \
is the right fit -- specific to this project, not generic.

Return a JSON object:
{{
  "heading": string,
  "paragraphs": [string, ...],
  "pullquote": string
}}"""


class TeamIntro(BaseModel):
    heading: str = ""
    paragraphs: list[str] = Field(default_factory=list)
    pullquote: str = ""


def _format_team_context(people: list[dict]) -> str:
    """people: the same list personnel_profiles_deduped() returns, already
    filtered by the caller to only include_in_proposal=True entries with a
    real name. Formats each person's real value-to-project write-up and
    relevant projects so the drafting prompt can quote them, never invent."""
    lines = []
    for entry in people:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        roles = ", ".join(entry.get("roles") or [])
        lines.append(f"- {name} ({roles})")
        value = (entry.get("value_to_project") or "").strip()
        if value:
            lines.append(f"  On this project, {name} will: {value}")
        for proj in entry.get("relevant_projects") or []:
            proj = (proj or "").strip()
            if proj:
                lines.append(f"  Relevant project: {proj}")
    return "\n".join(lines)


def draft_team_intro(
    people: list[dict],
    analysis,
    project_info: dict | None = None,
    config: dict | None = None,
) -> TeamIntro:
    """people: resourcing.personnel_profiles_deduped(resource_plan), already
    filtered by the caller to entries with include_in_proposal=True and a
    real name -- see resourcing.excluded_personnel_names for the same filter
    used elsewhere (draft_generator.format_team_context, the CV material
    handed to drafting, the personnel x experience matrix)."""
    project_info = project_info or {}
    team_context = _format_team_context(people)

    prompt = PROMPT_TEMPLATE.format(
        project_name=project_info.get("project_name") or "(not supplied)",
        client_name=project_info.get("client_name") or "(not supplied)",
        project_scope=(getattr(analysis, "project_scope", "") or "").strip() or "(not extracted)",
        client_objectives="\n".join(f"- {o}" for o in (getattr(analysis, "client_objectives", None) or [])) or "- (none extracted)",
        team_context=team_context or "(no included personnel with real project experience yet)",
    )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=1800)

    return TeamIntro(
        heading=(data.get("heading") or "").strip(),
        paragraphs=[p.strip() for p in (data.get("paragraphs") or []) if (p or "").strip()],
        pullquote=(data.get("pullquote") or "").strip(),
    )
