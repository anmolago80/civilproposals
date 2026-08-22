"""
experience_intro.py

Drafts a short, sales-forward intro paragraph for the start of "Relevant
project experience" -- before the individual project cards. Same idea as
team_intro.py but for the firm's track record rather than its people: pick
whichever real reference projects make the strongest case for THIS brief and
say so directly, instead of the generic "selected past projects most
relevant to this brief's scope" placeholder note.

Same no-invention discipline as the rest of the app: every named project and
claim must come from the reference_projects entries themselves (their real
title/client/description/relevance_text, already drafted in Upload
Documents) or the brief's project_scope -- never invented, and never a
project not present in the supplied list.
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.ai_interface import call_ai_json

SYSTEM_MESSAGE = """You are drafting a short, sales-forward intro paragraph for the start of \
the "Relevant project experience" section of an engineering/infrastructure tender proposal -- \
a FIRST-PASS, not submission-ready, paragraph for a human proposal writer to review and \
finish. Its job is to make the case, in a few sentences, for why the reference projects that \
follow prove this firm can deliver THIS brief -- not a bland "selected past projects most \
relevant to this brief's scope" placeholder, but a specific, confident statement naming the \
strongest 2-4 comparable projects and exactly why they're comparable (same client, same \
structure type, same technical challenge, same delivery model -- whatever is genuinely true).

You must not invent: project names, clients, or claims not present in the REFERENCE PROJECTS \
data you're given below. Only reference a project that's actually in that list, and only claim \
something about it that's actually stated in its description or relevance text there. Pick the \
strongest, most relevant projects rather than trying to summarise every one supplied -- a \
focused pitch citing 2-4 projects beats a diluted one trying to mention all of them. If fewer \
than 2 projects have enough real detail to support a specific claim, keep the paragraph shorter \
and more general rather than padding it with invented specifics."""

PROMPT_TEMPLATE = """Draft the intro paragraph for the start of "Relevant project experience".

PROJECT: {project_name}
CLIENT: {client_name}
PROJECT SCOPE (from the brief):
{project_scope}

DISCIPLINES THIS BRIEF REQUIRES: {disciplines}

WHAT THE CLIENT SAYS IT WANTS TO ACHIEVE (lead with the reference projects that speak to \
these, where the projects' own text supports it):
{client_objectives}

REFERENCE PROJECTS (the firm's real project reference library for this bid -- only reference \
projects listed here, only claim what's stated in their own description/relevance text):
{projects_context}

Write ONE short paragraph (3-5 sentences) that names the strongest 2-4 comparable projects \
(bold them with **double asterisks**) and states plainly why they prove this firm can deliver \
this brief. This paragraph will be a direct replacement for a generic placeholder note, so it \
needs to read as a real, specific, confident sales statement -- not a summary of the brief, and \
not restating the cards that follow it in full detail.

Return a JSON object:
{{
  "paragraph": string
}}"""


class ExperienceIntro(BaseModel):
    paragraph: str = ""


def _format_projects_context(reference_projects: list) -> str:
    lines = []
    for p in reference_projects or []:
        title = (getattr(p, "title", "") or "").strip()
        if not title:
            continue
        client = (getattr(p, "client", "") or "").strip()
        lines.append(f"- {title}" + (f" ({client})" if client else ""))
        description = (getattr(p, "description", "") or "").strip()
        if description:
            lines.append(f"  Description: {description}")
        relevance = (getattr(p, "relevance_text", "") or "").strip()
        if relevance:
            lines.append(f"  Relevance: {relevance}")
    return "\n".join(lines)


def draft_experience_intro(
    reference_projects: list,
    analysis,
    project_info: dict | None = None,
    config: dict | None = None,
    output_language: str = "en",
) -> ExperienceIntro:
    """reference_projects: list[reference_projects.ReferenceProject], the same
    list already drafted in Upload Documents (tab 2) and rendered as project
    cards -- this just adds a short sales paragraph ahead of those cards.

    `output_language`: language for the drafted "paragraph" -- "en" (default)
    or "es". Independent of the app's own UI language; see modules/i18n.py's
    module docstring."""
    project_info = project_info or {}
    projects_context = _format_projects_context(reference_projects)

    prompt = PROMPT_TEMPLATE.format(
        project_name=project_info.get("project_name") or "(not supplied)",
        client_name=project_info.get("client_name") or "(not supplied)",
        project_scope=(getattr(analysis, "project_scope", "") or "").strip() or "(not extracted)",
        disciplines=", ".join(getattr(analysis, "disciplines_involved", None) or []) or "(none extracted)",
        client_objectives="\n".join(f"- {o}" for o in (getattr(analysis, "client_objectives", None) or []))
                           or "- (none extracted)",
        projects_context=projects_context or "(no reference projects entered yet)",
    )
    if output_language == "es":
        prompt += (
            "\n\nWrite \"paragraph\" in Spanish (Español). Keep the JSON field name above exactly "
            "as given, in English. Translate only the language, not the substance -- do not "
            "invent, omit, or alter any project, name, or claim because of this instruction."
        )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=800)

    return ExperienceIntro(paragraph=(data.get("paragraph") or "").strip())
