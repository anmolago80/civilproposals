"""
pitch_review.py

AI review of the user's own hand-written "differentiator" and "sales pitch"
text for a tender proposal (Draft Responses tab, ahead of the AI-drafted
content further down). Unlike the other drafting modules in this app, the
underlying claims here are NOT sourced from uploaded documents or structured
data -- the user writes both in their own words. This module's job is
editorial, not inventive: comment on what's there, and re-angle/tighten it
into a submission-ready version -- never add a claim, credential, project, or
fact that isn't already present in the user's own text. It's allowed to tie
the re-angling to the brief's real, stated scope and objectives (from the
tender analysis, if one has been run yet), since that's genuine brief content,
not an invented fact about the firm.
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.ai_interface import call_ai_json

SYSTEM_MESSAGE = """You are reviewing a proposal writer's own hand-drafted "differentiator" and \
"sales pitch" text for an engineering/infrastructure tender proposal, before it goes into the \
document. Both pieces of text are written by the user in their own words -- your job is \
editorial, not inventive: sharpen what's genuinely there, tighten the language, and re-angle it \
to speak directly to THIS brief's real, stated scope and objectives (given below, where \
available) -- never add a claim, credential, project, experience, or fact that isn't already \
present in the user's own text. If a piece of text is vague or generic, say so plainly in your \
comment rather than papering over it with invented specifics.

For EACH of the two inputs supplied (differentiator, sales pitch), return:
1. A short, direct comment (2-4 sentences) on the text as written -- is it specific enough, does \
it speak to this brief's real drivers, is anything vague or generic, what's the one change that \
would sharpen it most. Direct and useful, like an experienced bid manager marking it up, not \
generic praise.
2. A tightened, submission-ready rewrite -- same underlying claims the user wrote, better angled \
and worded, ready to paste straight into the proposal.

If an input was not supplied (empty), leave both its comment and its rewrite as empty strings -- \
do not invent content to review or rewrite."""

PROMPT_TEMPLATE = """Review the differentiator and sales pitch below for this tender.

PROJECT: {project_name}
CLIENT: {client_name}
PROJECT SCOPE (from the brief, if extracted yet):
{project_scope}

CLIENT OBJECTIVES (from the brief, if extracted yet):
{client_objectives}

DIFFERENTIATOR (the user's own draft -- what sets this firm apart for this bid):
{differentiator}

SALES PITCH (the user's own draft -- the pitch for why this firm should win):
{sales_pitch}

Return a JSON object:
{{
  "differentiator_comment": string,
  "differentiator_refined": string,
  "sales_pitch_comment": string,
  "sales_pitch_refined": string
}}"""


class PitchReview(BaseModel):
    differentiator_comment: str = ""
    differentiator_refined: str = ""
    sales_pitch_comment: str = ""
    sales_pitch_refined: str = ""


def review_pitch(
    differentiator: str,
    sales_pitch: str,
    analysis=None,
    project_info: dict | None = None,
    config: dict | None = None,
) -> PitchReview:
    """differentiator/sales_pitch: the user's own raw text from the Draft
    Responses tab. analysis (tender_analyser.TenderAnalysis) is optional --
    the tool doesn't require Tender Analysis (tab 3) to have been run first,
    it just grounds the re-angling in real brief content when it's there."""
    project_info = project_info or {}
    project_scope = (getattr(analysis, "project_scope", "") or "").strip() if analysis else ""
    client_objectives = (getattr(analysis, "client_objectives", None) or []) if analysis else []

    prompt = PROMPT_TEMPLATE.format(
        project_name=project_info.get("project_name") or "(not supplied)",
        client_name=project_info.get("client_name") or "(not supplied)",
        project_scope=project_scope or "(not extracted yet)",
        client_objectives="\n".join(f"- {o}" for o in client_objectives) or "(not extracted yet)",
        differentiator=(differentiator or "").strip() or "(not supplied)",
        sales_pitch=(sales_pitch or "").strip() or "(not supplied)",
    )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=1500)

    return PitchReview(
        differentiator_comment=(data.get("differentiator_comment") or "").strip(),
        differentiator_refined=(data.get("differentiator_refined") or "").strip(),
        sales_pitch_comment=(data.get("sales_pitch_comment") or "").strip(),
        sales_pitch_refined=(data.get("sales_pitch_refined") or "").strip(),
    )
