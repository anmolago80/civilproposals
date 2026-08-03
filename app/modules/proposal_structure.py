"""
proposal_structure.py

Assembles the final proposal section list. Three modes, picked by
proposal_format / TenderAnalysis.uses_named_selection_criteria:

- Named selection criteria (e.g. SC1: Technical Skill of Key Team Members,
  SC2: Delivering the Service): the proposal mirrors those exact labels and
  order. This matters -- assessors mark against the named criteria, and
  renaming them into a generic skeleton risks a compliance failure at
  EOI/shortlisting stage.

- No named criteria: falls back to the conventional full-proposal skeleton,
  always starting with Executive Summary, Relevant Experience, Key
  Personnel, and Methodology, followed by any other criteria-driven
  sections ordered by weighting.

- Small Scope pack (proposal_format="letter"): a short response pack for a
  small brief or an email-based fee request rather than a formal RFT/EOI --
  no evaluation weighting or page limits exist to mirror, so the structure
  is a fixed, content-agnostic anatomy (Introduction, Scope of Work,
  Methodology and Deliverables, Project Team, Fees, Program, Assumptions and
  Clarifications, Terms of Engagement) built from whatever the brief
  actually says, exactly like the other two modes never invent content for
  a project type. It's the same proposal-building pipeline underneath --
  just a smaller, leaner output shape.

Either way, each section is enriched with seed content/graphic suggestions
that guidance_generator.py and graphics_engine.py build on.
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.tender_analyser import TenderAnalysis
from modules.weighting_engine import WeightedCriterion
from modules.page_allocation import PageAllocation, DEFAULT_PAGE_TEMPLATE


class ProposalSection(BaseModel):
    section_number: int
    title: str
    is_fixed: bool
    criterion_code: str | None = None
    source_criterion: str = ""
    weighting: float = 0.0
    weighting_source: str = ""
    page_limit_source: str = ""
    allocated_pages: int = 2
    format_requirements: str | None = None
    brief_requirements: list[str] = []
    recommended_content: list[str] = []
    recommended_graphics: list[str] = []
    display_order: int


FIXED_SECTIONS = ["Executive Summary", "Relevant Experience", "Key Personnel", "Methodology"]

# Fixed anatomy for the Small Scope pack format -- same idea as FIXED_SECTIONS above, just a
# different (smaller) shape suited to a short response pack rather than a formal (Large Scope)
# response. Section titles here are internal keys used to match drafts/guidance notes across the
# app -- export_docx.build_letter_docx() renders "Project Understanding" under the heading
# "1. Introduction" in the actual document; the key itself doesn't change.
LETTER_SECTIONS = [
    "Project Understanding", "Scope of Work", "Methodology and Deliverables", "Project Team",
    "Fees", "Program", "Assumptions and Clarifications", "Terms of Engagement",
]
_LETTER_DEFAULT_PAGES = {
    "Project Understanding": 1, "Scope of Work": 2, "Methodology and Deliverables": 1,
    "Project Team": 1, "Fees": 1, "Program": 1, "Assumptions and Clarifications": 1,
    "Terms of Engagement": 1,
}

# Seed content ideas, matched by keyword against the section title. Used as a
# starting point for guidance_generator.py's red notes and draft_generator.py's
# first-pass drafts -- not final copy.
CONTENT_SUGGESTIONS: dict[str, list[str]] = {
    "executive summary": [
        "State your understanding of what the client actually needs (not just a scope restatement)",
        "Lead with your strongest, most relevant win themes and differentiators",
        "A clear commitment statement on program, budget, and quality",
    ],
    "project understanding": [
        "State your understanding of what the client actually needs, in your own words -- not a copy of the brief",
        "Reference the specific site(s)/assets/context the brief describes",
        "Show you understand why the client wants this work done, not just what it is",
    ],
    "relevant experience": [
        "2-4 directly comparable past projects with client, value, and outcome",
        "Explicit link from each project back to this tender's specific risks/requirements",
        "Client testimonial or reference contact if available",
    ],
    "key personnel": [
        "Named individuals with role, RPEQ/registration status, years of experience",
        "A short 'on this project, [name] will...' statement per person",
        "Availability commitment for the duration of the engagement",
    ],
    # Checked before the generic "methodology" entry below (first substring match
    # wins) -- specific to the Small Scope pack's "Methodology and Deliverables"
    # section, which wants shorter, catchier copy than a formal pack's methodology
    # section, plus an explicit deliverables list.
    "methodology and deliverables": [
        "The delivery approach for this brief, broken into short, catchy subheaded stages -- "
        "written to be skimmed in under a minute, not a dense technical narrative",
        "The specific priorities/issues this brief raises that matter most to the client, and "
        "how the approach addresses them directly",
        "The key deliverables the client will actually receive, drawn from what the brief asks for",
    ],
    "methodology": [
        "Project understanding and key issues specific to this site/brief",
        "Delivery approach and program/staging logic",
        "Risk controls and quality assurance process",
    ],
    "risk": [
        "Approach to identifying and managing project-specific risks",
        "Reference to the client's own risk framework/tools if the brief names one",
    ],
    "safety": ["Safety management approach and relevant systems/certifications"],
    "quality": ["Quality management plan and review/sign-off process"],
    "sustainability": ["Environmental management approach", "Relevant sustainability credentials"],
    "innovation": ["Specific innovations proposed for this project, not generic claims"],
    "commercial": ["Fee summary and value-for-money narrative", "Confirmation of commercial terms"],
    "value for money": ["Fee summary and value-for-money narrative"],
    "local": ["Local content / local benefit commitments if the brief asks for them"],
    "delivering the service": ["Approach methodology addressing the brief's stated needs and outcomes"],
    "technical skill": ["Key team member relevant experience", "Company experience on similar work", "Team availability for the project duration"],
}

GRAPHIC_SUGGESTIONS: dict[str, list[str]] = {
    "executive summary": ["Cover page hero image"],
    "relevant experience": ["Project experience matrix"],
    "key personnel": ["Organisation chart"],
    "methodology": ["Methodology process diagram", "Programme timeline", "Key risk diagram"],
    "risk": ["Risk management diagram"],
    "commercial": ["Fee summary table"],
    "technical skill": ["Organisation chart"],
    "delivering the service": ["Methodology process diagram", "Programme timeline"],
}


def build_proposal_structure(
    analysis: TenderAnalysis,
    weighted_criteria: list[WeightedCriterion],
    allocations: list[PageAllocation],
    proposal_format: str = "formal",
) -> list[ProposalSection]:
    """
    proposal_format: "formal" (default -- the existing named-criteria / fixed-skeleton
    branching below, driven by weighting and page allocation) or "letter" (a short
    fee-proposal letter -- weighted_criteria/allocations are ignored since letter briefs
    don't carry evaluation weighting or page limits to mirror).
    """
    if proposal_format == "letter":
        sections = _build_letter_proposal_sections(analysis)
    else:
        alloc_by_section = {a.section_name: a for a in allocations}
        if analysis.uses_named_selection_criteria:
            sections = _build_named_criteria_sections(weighted_criteria, alloc_by_section)
        else:
            sections = _build_fixed_skeleton_sections(weighted_criteria, alloc_by_section)

    for i, s in enumerate(sections, start=1):
        s.section_number = i
        s.display_order = i
    return sections


def _build_letter_proposal_sections(analysis: TenderAnalysis) -> list[ProposalSection]:
    sections = []
    for title in LETTER_SECTIONS:
        sections.append(ProposalSection(
            section_number=0,
            title=title,
            is_fixed=True,
            source_criterion="",
            weighting=0.0,
            weighting_source="not_applicable",
            page_limit_source="not_applicable",
            allocated_pages=_LETTER_DEFAULT_PAGES.get(title, 1),
            format_requirements=None,
            brief_requirements=[],
            recommended_content=_suggestions_for(title, CONTENT_SUGGESTIONS),
            recommended_graphics=[],
            display_order=0,
        ))
    return sections


def _build_named_criteria_sections(
    weighted_criteria: list[WeightedCriterion], alloc_by_section: dict
) -> list[ProposalSection]:
    scored = [c for c in weighted_criteria if not c.is_mandatory_gate]
    # Prefer natural criterion-code order (SC1, SC2, ...) when available; fall back to weighting.
    if all(c.criterion_code for c in scored):
        scored.sort(key=lambda c: _natural_code_key(c.criterion_code))
    else:
        scored.sort(key=lambda c: c.priority_rank)

    sections = []
    for c in scored:
        alloc = alloc_by_section.get(c.mapped_section)
        title = f"{c.criterion_code}: {c.criterion_name}" if c.criterion_code else c.criterion_name
        sections.append(ProposalSection(
            section_number=0,
            title=title,
            is_fixed=False,
            criterion_code=c.criterion_code,
            source_criterion=c.criterion_description,
            weighting=c.applied_weighting,
            weighting_source=c.weighting_source,
            page_limit_source=alloc.page_limit_source if alloc else "default_template",
            allocated_pages=alloc.allocated_pages if alloc else 2,
            format_requirements=c.format_requirements,
            brief_requirements=[c.criterion_description] if c.criterion_description else [],
            recommended_content=_suggestions_for(title, CONTENT_SUGGESTIONS),
            recommended_graphics=_suggestions_for(title, GRAPHIC_SUGGESTIONS),
            display_order=0,
        ))
    return sections


def _build_fixed_skeleton_sections(
    weighted_criteria: list[WeightedCriterion], alloc_by_section: dict
) -> list[ProposalSection]:
    by_mapped_section = {c.mapped_section: c for c in weighted_criteria if not c.is_mandatory_gate}
    sections = []
    consumed_sections = set()

    # Two-pass matching so a criterion can only ever be claimed by one fixed section:
    # strict (substring) matches are decided first across ALL fixed titles, then the
    # weaker keyword-overlap fallback only fills in titles still unmatched. Without this,
    # processing order could let a loose match (e.g. "experience" appearing inside a Key
    # Personnel criterion's description) grab a criterion before the correct strict match
    # for Key Personnel itself gets a turn, double-counting one criterion into two sections.
    fixed_title_matches: dict[str, object] = {}
    for fixed_title in FIXED_SECTIONS:
        available = {k: v for k, v in by_mapped_section.items() if k not in consumed_sections}
        match = _find_by_keyword_strict(fixed_title, available)
        if match:
            fixed_title_matches[fixed_title] = match
            consumed_sections.add(match.mapped_section)
    for fixed_title in FIXED_SECTIONS:
        if fixed_title in fixed_title_matches:
            continue
        available = {k: v for k, v in by_mapped_section.items() if k not in consumed_sections}
        match = _find_by_keyword_loose(fixed_title, available)
        if match:
            fixed_title_matches[fixed_title] = match
            consumed_sections.add(match.mapped_section)

    for fixed_title in FIXED_SECTIONS:
        match = fixed_title_matches.get(fixed_title)
        alloc = alloc_by_section.get(match.mapped_section) if match else alloc_by_section.get(fixed_title)
        # A conventional fixed section (e.g. Executive Summary) often has no evaluation
        # criterion mapped to it at all, so page_allocation.py never produced a
        # PageAllocation for it. Fall back to the same default page template rather than
        # the model's generic 2pp default, so Executive Summary still gets 1pp etc.
        fallback_pages = DEFAULT_PAGE_TEMPLATE.get(fixed_title, 2)
        sections.append(ProposalSection(
            section_number=0,
            title=fixed_title,
            is_fixed=True,
            source_criterion=match.criterion_description if match else "",
            weighting=match.applied_weighting if match else 0.0,
            weighting_source=match.weighting_source if match else "default_standard",
            page_limit_source=alloc.page_limit_source if alloc else "default_template",
            allocated_pages=alloc.allocated_pages if alloc else fallback_pages,
            format_requirements=match.format_requirements if match else None,
            brief_requirements=[match.criterion_description] if match and match.criterion_description else [],
            recommended_content=_suggestions_for(fixed_title, CONTENT_SUGGESTIONS),
            recommended_graphics=_suggestions_for(fixed_title, GRAPHIC_SUGGESTIONS),
            display_order=0,
        ))

    remaining = [c for c in weighted_criteria
                 if not c.is_mandatory_gate and c.mapped_section not in consumed_sections]
    remaining.sort(key=lambda c: c.priority_rank)

    for c in remaining:
        alloc = alloc_by_section.get(c.mapped_section)
        sections.append(ProposalSection(
            section_number=0,
            title=c.mapped_section,
            is_fixed=False,
            criterion_code=c.criterion_code,
            source_criterion=c.criterion_description,
            weighting=c.applied_weighting,
            weighting_source=c.weighting_source,
            page_limit_source=alloc.page_limit_source if alloc else "default_template",
            allocated_pages=alloc.allocated_pages if alloc else 2,
            format_requirements=c.format_requirements,
            brief_requirements=[c.criterion_description] if c.criterion_description else [],
            recommended_content=_suggestions_for(c.mapped_section, CONTENT_SUGGESTIONS),
            recommended_graphics=_suggestions_for(c.mapped_section, GRAPHIC_SUGGESTIONS),
            display_order=0,
        ))
    return sections


def apply_manual_overrides(
    sections: list[ProposalSection],
    renamed: dict[str, str] | None = None,
    excluded_titles: set[str] | None = None,
    reordered_titles: list[str] | None = None,
) -> list[ProposalSection]:
    """Rename, exclude, or reorder sections per user edits in the Proposal Structure tab."""
    renamed = renamed or {}
    excluded_titles = excluded_titles or set()

    kept = [s for s in sections if s.title not in excluded_titles]
    for s in kept:
        if s.title in renamed:
            s.title = renamed[s.title]

    if reordered_titles:
        order_index = {t: i for i, t in enumerate(reordered_titles)}
        kept.sort(key=lambda s: order_index.get(s.title, 999))

    for i, s in enumerate(kept, start=1):
        s.section_number = i
        s.display_order = i
    return kept


def _suggestions_for(title: str, table: dict[str, list[str]]) -> list[str]:
    lowered = title.lower()
    for keyword, suggestions in table.items():
        if keyword in lowered:
            return list(suggestions)
    return []


def _find_by_keyword_strict(fixed_title: str, by_mapped_section: dict[str, WeightedCriterion]):
    """Substring match on the mapped-section name only -- high confidence."""
    lowered_fixed = fixed_title.lower()
    for mapped_section, criterion in by_mapped_section.items():
        if lowered_fixed in mapped_section.lower() or mapped_section.lower() in lowered_fixed:
            return criterion
    return None


def _find_by_keyword_loose(fixed_title: str, by_mapped_section: dict[str, WeightedCriterion]):
    """Keyword overlap against the criterion's description too -- lower confidence,
    only used as a fallback for fixed titles that got no strict match at all."""
    lowered_fixed = fixed_title.lower()
    for mapped_section, criterion in by_mapped_section.items():
        combined = (mapped_section + " " + criterion.criterion_description).lower()
        if lowered_fixed == "key personnel" and any(k in combined for k in ["personnel", "capability", "cv", "team"]):
            return criterion
        if lowered_fixed == "relevant experience" and any(k in combined for k in ["experience", "track record"]):
            return criterion
        if lowered_fixed == "methodology" and any(k in combined for k in ["methodology", "approach", "delivery"]):
            return criterion
    return None


def _natural_code_key(code: str | None) -> tuple:
    """Sort 'SC1', 'SC2', 'SC10' in natural order rather than lexical order."""
    if not code:
        return (999,)
    import re
    match = re.search(r"\d+", code)
    return (int(match.group()) if match else 999,)
