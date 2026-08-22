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
from modules.export_i18n import PLACEHOLDER_PREFIXES
from modules.proposal_structure import ProposalSection
from modules.tender_analyser import TenderAnalysis

# Cap on simultaneous in-flight AI calls in generate_all_drafts() below --
# high enough to turn a slow sequential wait into a short parallel one, low
# enough that a large (12+ section) pack doesn't fire that many requests at
# the AI provider at once and risk a rate limit.
MAX_CONCURRENT_DRAFTS = 5

# Roughly how many words of body text fit on one page of the exported pack
# at its font/margins/leading. Used to turn a page allocation into a word
# target the model can actually aim at -- "3 pages" means nothing to a
# language model, "about 1350 words" means quite a lot.
WORDS_PER_PAGE = 450

# Output budget. This used to be a flat 2000 tokens for every section, which
# capped even a 6-page allocation at roughly two pages of prose: the prompt
# asked for six pages and the budget made six pages impossible. Scaled from
# the allocation now, with a floor so a 1-page section still has room to be
# written properly and a ceiling so a mis-parsed 40-page allocation can't
# order an enormous, expensive generation.
MIN_DRAFT_TOKENS = 2000
MAX_DRAFT_TOKENS = 12000
TOKENS_PER_WORD = 1.7   # generous: JSON escaping and the heading/inputs fields ride along

# Beyond this far from its page budget, the export's guidance note says so.
# Deliberately wide -- a draft is a first pass and nobody should be chasing
# a word count -- but a section at a third of its allocation is a real
# finding an evaluator will notice as thin.
LENGTH_TOLERANCE = 0.40


def target_words(section) -> int:
    """The word target for one section, from its page allocation.

    A brief that states its own formatting rules (10pt, single spacing, etc.)
    changes how much text a page holds, so where those were extracted they
    nudge the target rather than being ignored entirely."""
    pages = max(1, int(getattr(section, "allocated_pages", 1) or 1))
    words = pages * WORDS_PER_PAGE
    requirements = (getattr(section, "format_requirements", "") or "").lower()
    # A tight font/spacing rule fits materially more on a page; a large one
    # fits less. Only the unambiguous cases are acted on.
    if any(hint in requirements for hint in ("9pt", "9 pt", "10pt", "10 pt", "single spac")):
        words = int(words * 1.15)
    if any(hint in requirements for hint in ("12pt", "12 pt", "14pt", "double spac", "1.5 spac")):
        words = int(words * 0.8)
    return max(150, words)


def draft_token_budget(section) -> int:
    budget = int(target_words(section) * TOKENS_PER_WORD)
    return max(MIN_DRAFT_TOKENS, min(budget, MAX_DRAFT_TOKENS))


def length_verdict(section, draft) -> str:
    """"", "under" or "over" -- how a finished draft sits against its page
    budget. Used at export time to flag a section that will read as thin (or
    won't fit) before anyone has to notice it by eye."""
    text = (getattr(draft, "draft_text", "") or "").strip()
    if not text:
        return ""
    words = len(text.split())
    target = target_words(section)
    if words < target * (1 - LENGTH_TOLERANCE):
        return "under"
    if words > target * (1 + LENGTH_TOLERANCE):
        return "over"
    return ""

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

PROJECT: {project_name}
CLIENT: {client_name}
BIDDER (the firm writing this response -- "we"): {bidder_name}

SECTION: {title}{criterion_code}
PAGE LIMIT: {page_limit} pages -- aim for roughly {target_words} words of body text. This is a \
target, not a rule: never pad with generic filler to reach it, and never invent content to \
fill space. Coming in short with honest placeholders is correct; coming in short because you \
stopped early is not.
EVALUATION WEIGHTING: {weighting}
FORMATTING RULES THE BRIEF IMPOSES: {format_requirements}

BRIEF REQUIREMENTS FOR THIS SECTION:
{brief_requirements}

RECOMMENDED CONTENT TO COVER:
{recommended_content}

TENDER CONTEXT (project scope, for grounding -- do not restate verbatim, use it to inform \
relevance):
{project_scope}

SCOPE OF WORK THE BRIEF DEFINES (the actual work packages and their tasks -- reference the real \
ones where this section calls for it):
{scope_items}

DELIVERABLES THE BRIEF REQUIRES (name the real ones; never invent an extra deliverable):
{deliverables}

WHAT THE CLIENT SAYS IT WANTS TO ACHIEVE:
{client_objectives}

RISKS THE BRIEF ITSELF RAISES (address the real ones where relevant; do not invent new risks):
{risks}

MANDATORY REQUIREMENTS (must not be contradicted anywhere in this draft):
{mandatory_requirements}

COMPLIANCE ITEMS MAPPED TO THIS SECTION (each with its current status -- this section is where \
they get answered):
{compliance_items}

USER-STATED WIN THEMES (the bid team's own words on why this firm should win -- REPHRASE ONLY, \
never extend into a claim they did not make):
{win_themes}

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
    project_info: dict | None = None,
    compliance_items: list | None = None,
    win_themes: str = "",
    structured_material: str = "",
    output_language: str = "en",
) -> SectionDraft:
    """`structured_material`: user-reviewed structured content that should
    REPLACE the raw uploaded blob for this section -- the edited reference
    projects for a Relevant Experience section, the personnel profiles for a
    Key Personnel one. Without it those sections drafted from truncated raw
    upload text while the cards beside them showed the user's corrected
    version, so the two disagreed in the same document.

    `output_language`: language for the drafted prose ("draft_heading",
    "draft_text", "required_user_inputs") -- "en" (default) or "es".
    Independent of the app's own UI language; see modules/i18n.py's module
    docstring. Never changes what's drafted, only what language it's written in."""
    company_material_text = company_material_text or {}
    project_info = project_info or {}
    material_block = structured_material.strip() or _format_company_material(company_material_text)

    prompt = DRAFT_PROMPT_TEMPLATE.format(
        project_name=project_info.get("project_name") or "(not supplied)",
        client_name=project_info.get("client_name") or "(not supplied)",
        bidder_name=project_info.get("bidder_name") or "(not supplied)",
        title=section.title,
        criterion_code=f"  (evaluation criterion {section.criterion_code})" if getattr(section, "criterion_code", None) else "",
        page_limit=section.allocated_pages,
        target_words=target_words(section),
        weighting=f"{section.weighting:.0f}%" if section.weighting else "not separately weighted",
        format_requirements=(getattr(section, "format_requirements", "") or "").strip() or "(none stated)",
        brief_requirements="\n".join(f"- {r}" for r in section.brief_requirements) or "- (none extracted -- use general judgement based on the section title)",
        recommended_content="\n".join(f"- {c}" for c in section.recommended_content) or "- (none)",
        project_scope=analysis.project_scope or "(not extracted)",
        scope_items=_format_scope_items(analysis),
        deliverables=_bullets(getattr(analysis, "deliverables", None)),
        client_objectives=_bullets(getattr(analysis, "client_objectives", None)),
        risks=_bullets(getattr(analysis, "risks", None)),
        mandatory_requirements=_bullets(getattr(analysis, "mandatory_requirements", None)),
        compliance_items=_format_compliance(compliance_items, section.title),
        win_themes=(win_themes or "").strip() or "(none written)",
        team_context=(team_context or "").strip() or "(no team assigned yet -- use bracketed placeholders for any named roles)",
        company_material=material_block,
    )
    if output_language == "es":
        # Audit Round 2, Part 4: the model used to be told to translate
        # bracketed placeholder markers freely (e.g. "[EL USUARIO DEBE
        # INSERTAR...]"), which the export sweep's fixed marker list never
        # matched -- Spanish packs under-reported what still needed a human.
        # It must now use ONLY the canonical Spanish prefixes so
        # collect_placeholders() (export_docx.py) reliably finds them.
        _es = PLACEHOLDER_PREFIXES["es"]
        prompt += (
            "\n\nWrite \"draft_heading\", \"draft_text\", and the entries of "
            "\"required_user_inputs\" in Spanish (Español) -- the full drafted prose, not just a "
            "summary. Keep the JSON field names above exactly as given, in English. Translate only "
            "the language, not the substance: do not invent, omit, or alter any fact, name, figure, "
            "deliverable, or placeholder because of this instruction. Any bracketed placeholder you "
            "write for missing information MUST use exactly one of these Spanish markers -- never a "
            f"free translation of your own: {_es['insert']} ...] for something to insert, "
            f"{_es['confirm']} ...] for something to confirm, {_es['tbc']}: ...] for something to be "
            f"completed, {_es['no']} ...] for something not supplied. For example, write "
            f"{_es['insert']}: DETALLE ESPECÍFICO DEL PROYECTO] -- not a paraphrase of it -- so a "
            "reviewer scanning the Spanish draft, and the app's own automated sweep for placeholders, "
            "both reliably find every gap."
        )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config,
                        max_tokens=draft_token_budget(section))

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
    project_info: dict | None = None,
    compliance_items: list | None = None,
    win_themes: str = "",
    structured_material: dict[str, str] | None = None,
    output_language: str = "en",
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
    order, not each section's position in the original list.

    `output_language`: passed through to each generate_draft_section() call --
    "en" (default) or "es". See that function's docstring."""
    drafts: dict[str, SectionDraft] = {}
    total = len(sections)
    completed = 0

    with ThreadPoolExecutor(max_workers=max(1, min(MAX_CONCURRENT_DRAFTS, total))) as pool:
        future_to_section = {
            pool.submit(
                generate_draft_section, section, analysis, company_material_text, config,
                team_context=team_context,
                project_info=project_info,
                compliance_items=compliance_items,
                win_themes=win_themes,
                structured_material=(structured_material or {}).get(section.title, ""),
                output_language=output_language,
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


def _bullets(values, empty: str = "(none extracted)") -> str:
    values = [str(v).strip() for v in (values or []) if str(v or "").strip()]
    return "\n".join(f"- {v}" for v in values) or f"- {empty}"


def _format_scope_items(analysis) -> str:
    lines = []
    for item in (getattr(analysis, "scope_items", None) or []):
        title = (getattr(item, "title", "") or "").strip()
        if not title:
            continue
        tasks = [str(t).strip() for t in (getattr(item, "tasks", None) or []) if str(t or "").strip()]
        lines.append(f"- {title}" + (f": {'; '.join(tasks)}" if tasks else ""))
    return "\n".join(lines) or "- (none extracted)"


def _format_compliance(compliance_items: list | None, section_title: str) -> str:
    """The compliance rows this section is responsible for answering.

    The matrix already works out which section each requirement maps to, and
    the drafter never saw any of it -- so a section could be drafted without
    knowing it was the one place a mandatory requirement had to be
    addressed."""
    rows = []
    for item in (compliance_items or []):
        if (getattr(item, "mapped_section", "") or "") != section_title:
            continue
        description = (getattr(item, "description", "") or "").strip()
        if not description:
            continue
        status = (getattr(item, "status", "") or "").strip()
        rows.append(f"- {description}" + (f"  [status: {status}]" if status else ""))
    return "\n".join(rows) or "- (none mapped to this section)"


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
