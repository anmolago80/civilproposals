"""
draft_generator.py

Generates first-pass draft content for each proposal section, using the
tender requirements plus whatever company material the user uploaded
(company profile, previous proposals, project references, CV library,
boilerplate content).

Hard rule, enforced in the prompt and worth repeating here: this must never
invent project experience, staff names, certifications, accreditations,
insurances, commercial terms, or safety performance. Where the necessary
information hasn't been supplied, the draft uses an explicit placeholder
instead of a plausible-sounding guess.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel

from modules.ai_interface import call_ai_json
from modules.proposal_structure import ProposalSection
from modules.tender_analyser import TenderAnalysis

# Cap on simultaneous in-flight AI calls in generate_all_drafts() below --
# high enough to turn a slow sequential wait into a short parallel one, low
# enough that a large (12+ section) pack doesn't fire that many requests at
# the AI provider at once and risk a rate limit.
MAX_CONCURRENT_DRAFTS = 5

PLACEHOLDER_EXAMPLES = [
    "[USER TO INSERT PROJECT-SPECIFIC DETAIL]",
    "[INSERT RELEVANT PROJECT REFERENCE]",
    "[INSERT KEY PERSONNEL DETAILS]",
    "[CONFIRM COMMERCIAL REQUIREMENTS]",
    "[INSERT CERTIFICATION / ACCREDITATION DETAIL]",
]

SYSTEM_MESSAGE = """You are drafting a FIRST-PASS, NOT submission-ready section of an \
engineering/infrastructure tender proposal, for a human proposal writer to review, correct, \
and finish. You must not invent: project experience, staff names, certifications, \
accreditations, insurances, safety performance, or commercial/pricing terms. Where the \
supplied company material actually contains something specific and relevant, use it. Where \
it doesn't, insert an explicit bracketed placeholder like [USER TO INSERT PROJECT-SPECIFIC \
DETAIL], [INSERT RELEVANT PROJECT REFERENCE], [INSERT KEY PERSONNEL DETAILS], or [CONFIRM \
COMMERCIAL REQUIREMENTS] rather than writing something generic that sounds plausible but \
isn't grounded in anything supplied. It is much better to leave an obvious gap than to write \
a confident-sounding sentence that isn't true. Keep the tone professional and specific to \
the brief, not generic boilerplate, wherever real information is available.

WRITE LIKE A SENIOR ENGINEER EXPLAINING THE APPROACH TO A CLIENT, NOT LIKE GENERATED TEXT. This \
is the single biggest quality bar for this draft, so take it seriously:
- Write in continuous, connected prose. A paragraph should read as one idea flowing into the \
next, with real transitions ("this matters because...", "given that, we..."), not a stack of \
disconnected topic-sentences that each restate what they're about to say.
- Do NOT default to bullet lists. Use a bulleted list only for something that is genuinely a \
list (e.g. a sequence of discrete deliverables or standards) -- never as a substitute for \
explaining an approach, which should be prose.
- Vary sentence length and structure. Avoid starting consecutive sentences or paragraphs the \
same way, and avoid overused AI-sounding connective tissue ("Furthermore", "Moreover", "In \
addition", "It is important to note that", "This ensures that") -- say the plain version \
instead of dressing up a simple sentence.
- Never open a paragraph by restating the section heading or repeating the brief's own wording \
back at it. Start with substance.
- Use SHORT, BOLD SUBHEADINGS to break a longer section into scannable stages or themes -- \
write a subheading as its own short line wrapped in double asterisks, e.g. **Site \
investigation and staging**, followed by a blank line and then the prose paragraph(s) under \
it. Use as many subheadings as suit the section's real structure (a short section may need \
none; a multi-stage methodology usually wants one per stage) -- never force one if the content \
doesn't naturally break that way. You may also bold a short phrase inline for emphasis \
(**geotechnical risk**) the same way, sparingly.
- The result should read like something a person who knows this project well sat down and \
wrote in one sitting -- confident, specific, and easy to skim -- not like a checklist being \
narrated."""

DRAFT_PROMPT_TEMPLATE = """Draft first-pass content for this proposal section.

SECTION: {title}
PAGE LIMIT: {page_limit} pages
EVALUATION WEIGHTING: {weighting}
BRIEF REQUIREMENTS FOR THIS SECTION:
{brief_requirements}

RECOMMENDED CONTENT TO COVER:
{recommended_content}

TENDER CONTEXT (project scope, for grounding -- do not restate verbatim, use it to inform \
relevance):
{project_scope}

NOMINATED TEAM (the ACTUAL people staffed to this bid -- when this section refers to who will \
do the work, use THESE names and roles exactly; never invent a different name or make one up. \
If a role here is unfilled, use a bracketed placeholder, not an invented name):
{team_context}

SUPPLIED COMPANY MATERIAL (use only what's actually here; anything not covered here must be \
a placeholder, not an invention):
{company_material}

Return a JSON object:
{{
  "draft_heading": string,
  "draft_text": string (the actual first-pass draft body -- continuous human-sounding prose, \
paragraphs separated by a blank line, bold **subheadings** on their own line where the section \
has distinct stages/themes, using placeholders as instructed -- see the formatting rules above),
  "required_user_inputs": [string]  (a short list of exactly what a human still needs to supply)
}}"""


class SectionDraft(BaseModel):
    section_title: str
    draft_heading: str
    draft_text: str
    required_user_inputs: list[str]
    recommended_graphic_placeholders: list[str]


def generate_draft_section(
    section: ProposalSection,
    analysis: TenderAnalysis,
    company_material_text: dict[str, str] | None = None,
    config: dict | None = None,
    team_context: str | None = None,
) -> SectionDraft:
    company_material_text = company_material_text or {}
    material_block = _format_company_material(company_material_text)

    prompt = DRAFT_PROMPT_TEMPLATE.format(
        title=section.title,
        page_limit=section.allocated_pages,
        weighting=f"{section.weighting:.0f}%" if section.weighting else "not separately weighted",
        brief_requirements="\n".join(f"- {r}" for r in section.brief_requirements) or "- (none extracted -- use general judgement based on the section title)",
        recommended_content="\n".join(f"- {c}" for c in section.recommended_content) or "- (none)",
        project_scope=analysis.project_scope or "(not extracted)",
        team_context=(team_context or "").strip() or "(no team assigned yet -- use bracketed placeholders for any named roles)",
        company_material=material_block,
    )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=2000)

    return SectionDraft(
        section_title=section.title,
        draft_heading=data.get("draft_heading", section.title),
        draft_text=data.get("draft_text", ""),
        required_user_inputs=data.get("required_user_inputs", []),
        recommended_graphic_placeholders=list(section.recommended_graphics),
    )


def generate_all_drafts(
    sections: list[ProposalSection],
    analysis: TenderAnalysis,
    company_material_text: dict[str, str] | None = None,
    config: dict | None = None,
    progress_callback=None,
    team_context: str | None = None,
) -> dict[str, SectionDraft]:
    """Drafts every section, one AI call each, run concurrently (up to
    MAX_CONCURRENT_DRAFTS at a time) rather than one-at-a-time -- each
    section's draft is fully independent of every other's (none of them
    read another section's drafted output), so there was never a real
    reason to make a 9-section pack wait through 9 sequential AI calls
    back to back. Wall-clock time drops to roughly the slowest single
    section's call instead of the sum of all of them.

    Same all-or-nothing error behaviour as the old sequential version:
    if any section's call raises, this raises too (app.py's call site
    already wraps this in a try/except and expects a clean raise, not a
    partial dict). progress_callback still fires once per completed
    section with a running count, but since sections may finish in any
    order now, the (i, total, title) it receives reflects completion
    order, not each section's position in the original list."""
    drafts: dict[str, SectionDraft] = {}
    total = len(sections)
    completed = 0

    with ThreadPoolExecutor(max_workers=max(1, min(MAX_CONCURRENT_DRAFTS, total))) as pool:
        future_to_section = {
            pool.submit(
                generate_draft_section, section, analysis, company_material_text, config,
                team_context=team_context,
            ): section
            for section in sections
        }
        try:
            for future in as_completed(future_to_section):
                section = future_to_section[future]
                drafts[section.title] = future.result()  # re-raises here if this section's call failed
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, section.title)
        except Exception:
            # Only unstarted futures can actually be cancelled -- anything
            # already mid-request keeps running in its thread, but we stop
            # waiting on it and re-raise immediately, matching the old
            # sequential loop's "first failure aborts the batch" behaviour.
            for f in future_to_section:
                f.cancel()
            raise

    return drafts


def format_team_context(resource_plan: list | None) -> str:
    """Turn the resourcing plan into a compact 'role: name' block for the draft
    prompt, so drafts reference the real nominated people instead of inventing
    names. Only assigned slots that are actually going into the proposal are
    included -- a person unticked via "Include in proposal" (e.g. because their
    CV wasn't provided) must not be named in the drafted prose either, even
    though they're still staffed internally on the resourcing plan."""
    if not resource_plan:
        return ""
    lines = []
    for a in resource_plan:
        if not getattr(a, "include_in_proposal", True):
            continue
        name = (getattr(a, "person_name", "") or "").strip()
        slot = getattr(a, "slot", "")
        if name and slot:
            lines.append(f"- {slot}: {name}")
    return "\n".join(lines)


def _format_company_material(company_material_text: dict[str, str]) -> str:
    labels = {
        "company_profile": "Company profile",
        "previous_proposals": "Previous proposals",
        "project_references": "Project references",
        "cv_library": "CV library",
        "boilerplate_content": "Boilerplate content",
    }
    blocks = []
    for key, label in labels.items():
        text = (company_material_text.get(key) or "").strip()
        if text:
            # Keep each block bounded so the prompt doesn't balloon.
            blocks.append(f"--- {label} ---\n{text[:6000]}")
    if not blocks:
        return "(No company material was uploaded for this project. Use placeholders throughout.)"
    return "\n\n".join(blocks)
