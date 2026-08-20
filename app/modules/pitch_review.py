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

Also offers an optional second step (generate_pitch_questions): a small,
button-triggered set of targeted follow-up questions aimed at whatever is
still vague or unsupported in the user's current text -- Kahneman-style
sharpening only works when there's a real specific to anchor on, so this is
how the tool asks for one instead of guessing. The user's own answers are
then treated exactly like the rest of their hand-written text: real input
that review_pitch() is allowed to fold into the rewrite, never invented.
"""

from __future__ import annotations

import re

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
and worded, ready to paste straight into the proposal. This rewrite renders in the document as a \
short highlighted pull-quote box, not a paragraph, so it MUST be a maximum of THREE sentences \
total -- shorter is better if the claim lands in one or two.

Write the rewrite for fast, System-1 reading, using the attention-grabbing techniques from \
Kahneman's "Thinking, Fast and Slow" -- applied to presentation, never to the underlying facts:
- Lead with the single most concrete, specific claim already in the user's text (a number, a \
named outcome, a stated track record). Concrete claims are processed faster and judged more \
credible than vague ones -- if the user gave you a specific detail, put it first, not buried.
- Prefer short, plain, low-effort sentences over long or jargon-heavy ones. Cognitive ease reads \
as more trustworthy; a sentence a reader has to work to parse loses them.
- Cut hedging language ("we believe", "we aim to", "we strive to", "we try to") -- confident, \
unqualified statements are judged as more credible. State the claim, don't qualify it.
- If the user's own text already implies a real stake or consequence for the client (a risk \
avoided, a deadline that matters, a cost overrun prevented), keep that concrete framing rather \
than flattening it into generic reassurance -- loss-framed, concrete stakes are more memorable \
and more persuasive than abstract benefit statements.
These are rewriting techniques applied to the SAME underlying claims the user already wrote -- \
never add a number, project, credential, or fact that isn't already present in their text.

Either input may be followed by a "FOLLOW-UP ANSWERS" block -- these are the user's own answers to \
targeted questions asked earlier about that same text (see generate_pitch_questions). Treat these \
answers exactly like the rest of the user's hand-written text: genuine input you're allowed to pull \
into the rewrite (ideally the concrete detail that now leads it), never a licence to add anything \
beyond what the user actually wrote across the original text and these answers combined.

If an input was not supplied (empty), leave both its comment and its rewrite as empty strings -- \
do not invent content to review or rewrite."""

PROMPT_TEMPLATE = """Review the differentiator and sales pitch below for this tender.

PROJECT: {project_name}
CLIENT: {client_name}
PROJECT SCOPE (from the brief, if extracted yet):
{project_scope}

CLIENT OBJECTIVES (from the brief, if extracted yet):
{client_objectives}

EVALUATION CRITERIA AND THEIR WEIGHTINGS (what this bid is actually scored on -- the whole \
point of re-angling a pitch is to aim it at the heaviest-weighted criteria, so use these; \
they do NOT license any new claim about the firm):
{evaluation_criteria}

DIFFERENTIATOR (the user's own draft -- what sets this firm apart for this bid):
{differentiator}
{differentiator_followup}
SALES PITCH (the user's own draft -- the pitch for why this firm should win):
{sales_pitch}
{sales_pitch_followup}
Return a JSON object:
{{
  "differentiator_comment": string,
  "differentiator_refined": string,
  "sales_pitch_comment": string,
  "sales_pitch_refined": string
}}"""

QUESTIONS_SYSTEM_MESSAGE = """You are helping a proposal writer sharpen their own hand-drafted \
"differentiator" and "sales pitch" text for an engineering/infrastructure tender proposal, by asking \
a small number of targeted follow-up questions. The rewrite that follows this step uses presentation \
techniques from Kahneman's "Thinking, Fast and Slow" (a concrete number or named outcome leading the \
statement, short plain sentences, no hedging, real stakes kept concrete) -- but those techniques only \
work when there's a genuine specific to anchor on. Your job here is to spot exactly what's still vague \
or unsupported in the user's own text and ask for it directly, not to comment on style.

For EACH of the two inputs supplied (differentiator, sales pitch), write UP TO FOUR short, specific \
follow-up questions -- fewer is fine, and if the text is already concrete and specific throughout, \
return an empty list rather than padding with filler questions. A good question asks for one of: the \
specific number or metric behind a claim already made, the name of the project or client a claim is \
based on, the concrete result or outcome that followed, or the real cost/delay/risk to the client if \
they choose someone else. Never ask a generic question ("tell us more") and never ask about anything \
that isn't already implied by what the user wrote.

If an input was not supplied (empty), return an empty list of questions for it."""

QUESTIONS_PROMPT_TEMPLATE = """Suggest follow-up questions for the differentiator and sales pitch below.

PROJECT: {project_name}
CLIENT: {client_name}
PROJECT SCOPE (from the brief, if extracted yet):
{project_scope}

CLIENT OBJECTIVES (from the brief, if extracted yet):
{client_objectives}

EVALUATION CRITERIA AND THEIR WEIGHTINGS (what this bid is actually scored on -- the whole \
point of re-angling a pitch is to aim it at the heaviest-weighted criteria, so use these; \
they do NOT license any new claim about the firm):
{evaluation_criteria}

DIFFERENTIATOR (the user's own draft -- what sets this firm apart for this bid):
{differentiator}

SALES PITCH (the user's own draft -- the pitch for why this firm should win):
{sales_pitch}

Return a JSON object:
{{
  "differentiator_questions": [string, ...],
  "sales_pitch_questions": [string, ...]
}}"""


def _cap_sentences(text: str, max_sentences: int = 3) -> str:
    """Safety net behind the prompt's own "max three sentences" instruction --
    the rewrite renders inside the pull-quote box in the document (see
    export_docx._add_pull_quote_box), so this guarantees it always fits even
    if the model runs long. Never adds anything, only trims trailing
    sentences beyond the cap."""
    text = (text or "").strip()
    if not text:
        return text
    parts = re.split(r"(?<=[.!?])\s+", text)
    parts = [p for p in parts if p.strip()]
    return " ".join(parts[:max_sentences]).strip()


def _format_followup(qa_pairs: list[tuple[str, str]] | None) -> str:
    """Renders a list of (question, answer) pairs as the "FOLLOW-UP ANSWERS"
    block PROMPT_TEMPLATE expects, or "" when there are none -- keeps the
    prompt identical to before this feature existed when no questions were
    asked/answered."""
    pairs = [(q, a) for q, a in (qa_pairs or []) if (a or "").strip()]
    if not pairs:
        return ""
    lines = ["FOLLOW-UP ANSWERS (from the user, in response to targeted questions -- genuine "
             "additional detail, safe to incorporate):"]
    for q, a in pairs:
        lines.append(f"Q: {q.strip()}\nA: {a.strip()}")
    return "\n".join(lines) + "\n"


class PitchReview(BaseModel):
    differentiator_comment: str = ""
    differentiator_refined: str = ""
    sales_pitch_comment: str = ""
    sales_pitch_refined: str = ""


class PitchQuestions(BaseModel):
    differentiator_questions: list[str] = []
    sales_pitch_questions: list[str] = []


def review_pitch(
    differentiator: str,
    sales_pitch: str,
    analysis=None,
    project_info: dict | None = None,
    config: dict | None = None,
    differentiator_qa: list[tuple[str, str]] | None = None,
    sales_pitch_qa: list[tuple[str, str]] | None = None,
) -> PitchReview:
    """differentiator/sales_pitch: the user's own raw text from the Draft
    Responses tab. analysis (tender_analyser.TenderAnalysis) is optional --
    the tool doesn't require Tender Analysis (tab 3) to have been run first,
    it just grounds the re-angling in real brief content when it's there.
    differentiator_qa/sales_pitch_qa: optional list of (question, answer)
    pairs from generate_pitch_questions -- the user's own answers to the
    "sharpen further" follow-up questions, folded into the prompt as
    additional genuine input (see _format_followup)."""
    project_info = project_info or {}
    project_scope = (getattr(analysis, "project_scope", "") or "").strip() if analysis else ""
    client_objectives = (getattr(analysis, "client_objectives", None) or []) if analysis else []
    criteria_lines = []
    for criterion in (getattr(analysis, "evaluation_criteria", None) or []) if analysis else []:
        name = (getattr(criterion, "name", "") or "").strip()
        if not name:
            continue
        code = (getattr(criterion, "criterion_code", "") or "").strip()
        weight = getattr(criterion, "detected_weighting", None)
        label = f"{code}: {name}" if code else name
        criteria_lines.append(f"- {label}" + (f" -- {weight:.0f}% of the score" if weight else ""))

    prompt = PROMPT_TEMPLATE.format(
        evaluation_criteria="\n".join(criteria_lines) or "- (none extracted yet)",
        project_name=project_info.get("project_name") or "(not supplied)",
        client_name=project_info.get("client_name") or "(not supplied)",
        project_scope=project_scope or "(not extracted yet)",
        client_objectives="\n".join(f"- {o}" for o in client_objectives) or "(not extracted yet)",
        differentiator=(differentiator or "").strip() or "(not supplied)",
        differentiator_followup=_format_followup(differentiator_qa),
        sales_pitch=(sales_pitch or "").strip() or "(not supplied)",
        sales_pitch_followup=_format_followup(sales_pitch_qa),
    )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=1500)

    return PitchReview(
        differentiator_comment=(data.get("differentiator_comment") or "").strip(),
        differentiator_refined=_cap_sentences(data.get("differentiator_refined") or ""),
        sales_pitch_comment=(data.get("sales_pitch_comment") or "").strip(),
        sales_pitch_refined=_cap_sentences(data.get("sales_pitch_refined") or ""),
    )


def generate_pitch_questions(
    differentiator: str,
    sales_pitch: str,
    analysis=None,
    project_info: dict | None = None,
    config: dict | None = None,
) -> PitchQuestions:
    """Button-triggered only (never on every keystroke) -- generates up to 4
    targeted follow-up questions per field, based on whatever is currently
    typed into Differentiator/Sales pitch. See module docstring."""
    project_info = project_info or {}
    project_scope = (getattr(analysis, "project_scope", "") or "").strip() if analysis else ""
    client_objectives = (getattr(analysis, "client_objectives", None) or []) if analysis else []

    prompt = QUESTIONS_PROMPT_TEMPLATE.format(
        project_name=project_info.get("project_name") or "(not supplied)",
        client_name=project_info.get("client_name") or "(not supplied)",
        project_scope=project_scope or "(not extracted yet)",
        client_objectives="\n".join(f"- {o}" for o in client_objectives) or "(not extracted yet)",
        differentiator=(differentiator or "").strip() or "(not supplied)",
        sales_pitch=(sales_pitch or "").strip() or "(not supplied)",
    )

    data = call_ai_json(prompt, system_message=QUESTIONS_SYSTEM_MESSAGE, config=config, max_tokens=700)

    def _cap_list(items, max_items: int = 4) -> list[str]:
        return [q.strip() for q in (items or []) if isinstance(q, str) and q.strip()][:max_items]

    return PitchQuestions(
        differentiator_questions=_cap_list(data.get("differentiator_questions")),
        sales_pitch_questions=_cap_list(data.get("sales_pitch_questions")),
    )
