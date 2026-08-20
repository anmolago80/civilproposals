"""
executive_summary.py

Drafts the Executive Summary -- an unweighted page that goes straight after
the cover/TOC in every formal response pack. It carries no evaluation
weighting of its own, but it's the evaluators' first real impression of the
offeror, so the brief is to make it warm, easy to read, and quietly
persuasive: short, catchily-titled blocks that sell the service on offer,
rather than a dry restatement of the scope.

Same no-invention discipline as the rest of the app: every claim must be
grounded in the actual brief (project_scope, scope_items, disciplines_involved,
client_objectives) and the actual nominated team. Personnel excluded via the
"Include in proposal" tick on the Team & Resourcing tab must not be named here
either -- the caller is expected to pass a team_context string already built
with that filter applied (draft_generator.format_team_context), not the raw
resource plan.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai_json

SYSTEM_MESSAGE = """You are drafting the Executive Summary of an engineering/infrastructure \
tender proposal -- a FIRST-PASS, not submission-ready, page for a human proposal writer to \
review and finish. Unlike the scored selection-criteria sections, this page carries no \
evaluation weighting, so its job is purely to build goodwill: it's the evaluators' first real \
impression of the offeror, read before they get into the weighted sections. Write it warm, \
confident, and easy to read -- like a firm that's genuinely excited about this project talking \
to the client, not a compliance document. Each block needs a short, catchy, benefit-forward \
title (not a bland section label) and a tight, human paragraph underneath it.

You must not invent: project experience, staff names, certifications, accreditations, \
insurances, safety performance, or commercial/pricing terms. Only use a person's name if they \
appear in the NOMINATED TEAM block below -- if a role isn't listed there, refer to the role \
generically ("our design manager") rather than inventing or guessing a name. Ground every \
specific claim (site conditions, structure types, delivery approach, disciplines involved) in \
the actual brief content supplied -- never a generic "typical bridge project" claim that could \
apply to any brief. Where you don't have enough real material to make a specific claim, keep \
that block general and confident rather than inventing a specific-sounding but false detail."""

PROMPT_TEMPLATE = """Draft the Executive Summary for this proposal.

PROJECT: {project_name}
CLIENT: {client_name}
PROJECT SCOPE (from the brief):
{project_scope}

CLIENT OBJECTIVES (from the brief, if stated):
{client_objectives}

KEY SCOPE ITEMS (from the brief):
{scope_items}

DISCIPLINES INVOLVED:
{disciplines}

BIDDER (the firm writing this response): {bidder_name}

FEE AND PROGRAM CONTEXT (where the brief or the bid states them -- reference only what is \
here, never a figure or a duration you were not given):
{commercial_context}

USER-STATED WIN THEMES (the bid team's own words on what sets this firm apart and why it \
should win -- REPHRASE ONLY; never extend these into a claim they did not make):
{win_themes}

NOMINATED TEAM (the ACTUAL people staffed to this bid -- only use these names; for any role \
not listed here, refer to the role generically, never invent a name):
{team_context}

WHAT THE PROPOSAL ITSELF ACTUALLY SAYS -- the headings of the sections that have been drafted, \
in order. The executive summary INTRODUCES this document, so it must not promise anything the \
document does not go on to cover. If a subject is not among these sections, do not claim the \
proposal addresses it:
{drafted_sections}

Write:
1. A short intro (2-3 sentences) that names the project and client, and sets a warm, confident \
tone -- this firm is genuinely well-placed to deliver this project.
2. Between 3 and 5 short blocks (this page has a ONE-PAGE budget -- 5 to 8 blocks plus an intro \
does not fit on one page, so choose the strongest few rather than covering every angle), each \
with a catchy, benefit-forward title (think "Safe hands \
with our technical team", "Designing for holistic resilience", "Committed and available" -- \
specific to THIS project's real scope and team, not generic filler) and a tight paragraph (2-4 \
sentences) underneath. Cover a spread of angles appropriate to what's actually in this brief -- \
things like: the technical team and their fit to this scope, the design/engineering approach to \
the project's specific challenges, constructability and delivery, environmental/planning \
considerations if the brief raises them, local knowledge or presence if relevant, quality and \
reliability of deliverables, and program/cost efficiency. Only include a block if you have real \
material to ground it in -- don't force all these angles if the brief doesn't support them.

Return a JSON object:
{{
  "intro": string,
  "blocks": [
    {{"title": string, "body": string}},
    ...
  ]
}}"""


class ExecutiveSummaryBlock(BaseModel):
    title: str
    body: str


class ExecutiveSummary(BaseModel):
    intro: str = ""
    blocks: list[ExecutiveSummaryBlock] = Field(default_factory=list)


# One page, and an exec summary that overruns is the first thing an
# evaluator notices about a proposal's discipline. Enforced after the call
# as well as asked for in the prompt.
MAX_BLOCKS = 5


def draft_executive_summary(
    analysis,
    project_info: dict | None = None,
    team_context: str | None = None,
    config: dict | None = None,
    drafted_section_titles: list[str] | None = None,
    win_themes: str = "",
    program_weeks: int | None = None,
) -> ExecutiveSummary:
    """Draft the Executive Summary. `analysis` is a tender_analyser.TenderAnalysis;
    `team_context` should already be filtered to only personnel actually going
    into the proposal (draft_generator.format_team_context(resource_plan) --
    which itself now respects the "Include in proposal" tick).

    `drafted_section_titles`: the headings of the sections that have actually
    been drafted. The executive summary introduces the document, and without
    knowing what is in it, it could promise an evaluator something the
    methodology never mentions -- so it is generated AFTER the drafts and
    told what they cover."""
    project_info = project_info or {}
    scope_items = getattr(analysis, "scope_items", None) or []
    scope_lines = []
    for item in scope_items:
        title = getattr(item, "title", "") or ""
        tasks = getattr(item, "tasks", None) or []
        if title:
            scope_lines.append(f"- {title}" + (f": {', '.join(tasks[:4])}" if tasks else ""))

    commercial_bits = []
    fee_cap = (getattr(analysis, "fee_cap", "") or "").strip()
    if fee_cap:
        commercial_bits.append(f"- Fee cap stated in the brief: {fee_cap}")
    if program_weeks:
        commercial_bits.append(f"- Delivery program entered for this bid: {program_weeks} weeks")

    prompt = PROMPT_TEMPLATE.format(
        project_name=project_info.get("project_name") or "(not supplied)",
        bidder_name=project_info.get("bidder_name") or "(not supplied)",
        commercial_context="\n".join(commercial_bits) or "- (none stated)",
        win_themes=(win_themes or "").strip() or "(none written)",
        drafted_sections="\n".join(f"- {t}" for t in (drafted_section_titles or []))
                          or "- (no sections drafted yet -- do not claim the proposal covers any "
                             "specific subject)",
        client_name=project_info.get("client_name") or "(not supplied)",
        project_scope=(getattr(analysis, "project_scope", "") or "").strip() or "(not extracted)",
        client_objectives="\n".join(f"- {o}" for o in (getattr(analysis, "client_objectives", None) or [])) or "- (none extracted)",
        scope_items="\n".join(scope_lines) or "- (none extracted)",
        disciplines=", ".join(getattr(analysis, "disciplines_involved", None) or []) or "(none extracted)",
        team_context=(team_context or "").strip() or "(no team assigned yet -- refer to roles generically)",
    )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=2500)

    blocks = [
        ExecutiveSummaryBlock(title=(b.get("title") or "").strip(), body=(b.get("body") or "").strip())
        for b in (data.get("blocks") or [])
        if (b.get("body") or "").strip()
    ]
    # Hard cap: the prompt asks for a page's worth, this guarantees it.
    return ExecutiveSummary(intro=(data.get("intro") or "").strip(), blocks=blocks[:MAX_BLOCKS])
