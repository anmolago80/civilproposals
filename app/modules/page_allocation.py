"""
page_allocation.py

Allocates pages to proposal sections following a strict priority order:

  1. Section-specific page limit stated in the brief -- used exactly as given.
  2. No section-specific limit, but a total page limit is stated -- allocate
     a weighted share of the total, reserving 1 page for an Executive
     Summary-equivalent section by convention (unless the brief says
     otherwise, which priority 1 would already have caught).
  3. No page limit information anywhere -- apply the default page
     allocation template.

Each priority tier can apply to different sections of the *same* proposal
at once -- e.g. a brief might give Methodology an explicit 6-page cap while
saying nothing about Risk, which then falls back to a weighted share of
whatever's left of a stated total.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from modules.tender_analyser import TenderAnalysis
from modules.weighting_engine import WeightedCriterion


class PageAllocation(BaseModel):
    section_name: str
    weighting: float
    page_limit_source: str  # "tender_section_limit" | "weighted_total_limit" | "default_template"
    allocated_pages: int
    page_limit_raw: str | None = None
    format_requirements: str | None = None
    reason: str


# Last-resort fallback only -- used when there's no page limit information at all.
DEFAULT_PAGE_TEMPLATE = {
    "Executive Summary": 1,
    "Relevant Experience": 4,
    "Key Personnel": 3,
    "Methodology": 6,
    "Risk, Safety, Quality": 2,
    "Sustainability / Innovation": 2,
    "Commercial / Value for Money": 2,
}

_KEYWORD_MAP = {
    "Executive Summary": ["executive summary"],
    "Relevant Experience": ["experience", "past performance", "track record"],
    "Key Personnel": ["personnel", "key staff", "team", "capability", "cv"],
    "Methodology": ["methodology", "approach", "delivery"],
    "Risk, Safety, Quality": ["risk", "safety", "quality"],
    "Sustainability / Innovation": ["sustainability", "innovation", "environment"],
    "Commercial / Value for Money": ["price", "cost", "commercial", "value for money", "fee"],
}


def allocate_pages(
    weighted_criteria: list[WeightedCriterion], analysis: TenderAnalysis
) -> list[PageAllocation]:
    non_gates = [c for c in weighted_criteria if not c.is_mandatory_gate]
    allocations: list[PageAllocation] = []
    remaining: list[WeightedCriterion] = []

    # --- Priority 1: explicit section-specific limits ---
    for c in non_gates:
        limit_text = c.page_limit or analysis.section_page_limits.get(c.mapped_section)
        if limit_text:
            pages = _parse_page_count(limit_text) or _default_pages_for(c.mapped_section)
            allocations.append(PageAllocation(
                section_name=c.mapped_section,
                weighting=c.applied_weighting,
                page_limit_source="tender_section_limit",
                allocated_pages=pages,
                page_limit_raw=limit_text,
                format_requirements=c.format_requirements,
                reason=f'Brief states an explicit page limit for this section: "{limit_text}".',
            ))
        else:
            remaining.append(c)

    if not remaining:
        return _sort(allocations)

    # --- Priority 2: weighted share of a stated total ---
    if analysis.total_page_limit:
        consumed = sum(a.allocated_pages for a in allocations)
        budget = max(0, analysis.total_page_limit - consumed)

        exec_item = next((c for c in remaining if "executive summary" in c.mapped_section.lower()), None)
        if exec_item and budget > 0:
            allocations.append(PageAllocation(
                section_name=exec_item.mapped_section,
                weighting=exec_item.applied_weighting,
                page_limit_source="weighted_total_limit",
                allocated_pages=1,
                format_requirements=exec_item.format_requirements,
                reason=(
                    "Executive Summary is reserved at 1 page by standard convention; the "
                    "remaining pages are split across other sections by weighting."
                ),
            ))
            budget -= 1
            remaining = [c for c in remaining if c is not exec_item]

        total_weight = sum(c.applied_weighting for c in remaining) or 1.0
        for c in remaining:
            share = budget * (c.applied_weighting / total_weight) if budget > 0 else 0
            pages = max(1, round(share)) if budget > 0 else _default_pages_for(c.mapped_section)
            allocations.append(PageAllocation(
                section_name=c.mapped_section,
                weighting=c.applied_weighting,
                page_limit_source="weighted_total_limit",
                allocated_pages=pages,
                format_requirements=c.format_requirements,
                reason=(
                    f"No section-specific limit stated; allocated a "
                    f"{c.applied_weighting:.0f}%-weighted share of the "
                    f"{analysis.total_page_limit}-page total limit."
                ),
            ))
        return _sort(allocations)

    # --- Priority 3: default template ---
    for c in remaining:
        pages = _default_pages_for(c.mapped_section)
        allocations.append(PageAllocation(
            section_name=c.mapped_section,
            weighting=c.applied_weighting,
            page_limit_source="default_template",
            allocated_pages=pages,
            format_requirements=c.format_requirements,
            reason=(
                "No section-specific or total page limit stated anywhere in the brief; "
                "applied the default page allocation template -- confirm this is reasonable "
                "for the size of this pursuit."
            ),
        ))
    return _sort(allocations)


def apply_manual_page_override(
    allocations: list[PageAllocation], overrides: dict[str, int]
) -> list[PageAllocation]:
    """Apply user-entered page count overrides, keyed by section_name."""
    updated = []
    for a in allocations:
        if a.section_name in overrides:
            a = a.model_copy(update={
                "allocated_pages": overrides[a.section_name],
                "page_limit_source": "manual_override",
                "reason": "Manually overridden by the user in the Page Allocation tab.",
            })
        updated.append(a)
    return updated


def _sort(allocations: list[PageAllocation]) -> list[PageAllocation]:
    # Executive Summary (or equivalent) first, then weighting descending.
    def sort_key(a: PageAllocation):
        is_exec = "executive summary" in a.section_name.lower()
        return (0 if is_exec else 1, -a.weighting)
    return sorted(allocations, key=sort_key)


_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _parse_page_count(text: str) -> int | None:
    """Pull a page count out of free text like 'Two (2) A4 single sided pages' or 'max 4 pages'."""
    if not text:
        return None
    digit_match = re.search(r"\d+", text)
    if digit_match:
        return int(digit_match.group())
    lowered = text.lower()
    for word, value in _NUMBER_WORDS.items():
        if word in lowered:
            return value
    return None


def _default_pages_for(section_name: str) -> int:
    lowered = section_name.lower()
    for template_section, keywords in _KEYWORD_MAP.items():
        if any(kw in lowered for kw in keywords):
            return DEFAULT_PAGE_TEMPLATE[template_section]
    return 2  # reasonable generic default for an unmatched section
