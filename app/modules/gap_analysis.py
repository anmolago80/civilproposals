"""
gap_analysis.py

Rule-based (no AI call) risk view over the analysed tender and compliance
matrix: missing mandatory requirements, missing forms, missing CVs/project
references, unclear weightings, missing page limits, commercial exclusions,
and anything the extraction pass itself flagged as ambiguous.

This module never invents information. If something is missing, it says
so and tells the user what to do about it -- it doesn't guess a plausible
answer to make the gap look smaller than it is.
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.tender_analyser import TenderAnalysis
from modules.weighting_engine import WeightedCriterion
from modules.compliance_matrix import ComplianceItem

RISK_LEVELS = ["High", "Medium", "Low"]

_PERSONNEL_EXPERIENCE_KEYWORDS = [
    "personnel", "key team", "cv", "experience", "capability", "track record", "team member",
]


class GapItem(BaseModel):
    risk_level: str
    issue: str
    impact: str
    recommended_action: str
    mapped_section: str | None = None


def analyse_gaps(
    analysis: TenderAnalysis,
    compliance_items: list[ComplianceItem],
    weighted_criteria: list[WeightedCriterion],
    company_materials: dict[str, bool] | None = None,
) -> list[GapItem]:
    company_materials = company_materials or {}
    gaps: list[GapItem] = []

    # 1. Missing mandatory requirements / evaluation criteria (from the compliance matrix).
    for item in compliance_items:
        if item.status == "Missing" and item.requirement_type in ("Mandatory", "Evaluation Criterion"):
            gaps.append(GapItem(
                risk_level="High" if item.priority == "High" else "Medium",
                issue=item.description,
                impact="Assessors may score this as unaddressed or non-compliant.",
                recommended_action=item.user_action_required or "Resolve before drafting continues.",
                mapped_section=item.mapped_section,
            ))

    # 2. Missing/incomplete returnable schedules and forms.
    for f in analysis.required_forms:
        gaps.append(GapItem(
            risk_level="High",
            issue=f"Returnable schedule/form required by the brief: {f}",
            impact="Missing or incomplete returnable schedules can make a submission non-conforming outright, independent of content quality.",
            recommended_action="Locate, complete, and attach this form before lodgement.",
        ))

    # 3. Unclear / defaulted weightings.
    for c in weighted_criteria:
        if c.weighting_source == "default_standard" and not c.is_mandatory_gate:
            gaps.append(GapItem(
                risk_level="Medium",
                issue=f"No weighting was stated in the brief for '{c.mapped_section}' -- the default standard template value ({c.applied_weighting:.0f}%) was applied.",
                impact="Proposal structure and page allocation may not reflect the client's actual priorities.",
                recommended_action="Raise a clarification question with the client before the enquiry deadline if the weighting materially changes your approach, or confirm the assumption in your covering material.",
                mapped_section=c.mapped_section,
            ))

    # 4. No page limit information anywhere in the brief.
    no_section_limits = not analysis.section_page_limits and not any(
        c.page_limit for c in weighted_criteria
    )
    if analysis.total_page_limit is None and no_section_limits:
        gaps.append(GapItem(
            risk_level="Medium",
            issue="No page limits (total or per-section) were stated anywhere in the brief.",
            impact="The default page allocation template was applied, which may not match client expectations or may be more/less generous than a well-judged response needs.",
            recommended_action="Confirm whether page limits exist via an addendum or clarification question, and adjust the page allocation manually if needed.",
        ))

    # 5. Personnel/experience-heavy weighting with no supporting material uploaded.
    personnel_experience_weight = sum(
        c.applied_weighting for c in weighted_criteria
        if any(kw in (c.mapped_section + " " + c.criterion_description).lower() for kw in _PERSONNEL_EXPERIENCE_KEYWORDS)
    )
    has_supporting_material = any(company_materials.get(k) for k in (
        "has_cv_library", "has_project_references", "has_previous_proposals",
    ))
    if personnel_experience_weight >= 30 and not has_supporting_material:
        gaps.append(GapItem(
            risk_level="High",
            issue=(
                f"Personnel/experience-related criteria carry roughly {personnel_experience_weight:.0f}% "
                f"combined weighting in this tender, but no CV library, project references, or past "
                f"proposals have been uploaded."
            ),
            impact="This is very likely the single biggest scoring risk for this pursuit -- see the Burnett River example of what happens when this content is missing at submission time.",
            recommended_action="Prioritise sourcing CVs and 2-4 directly relevant project references before drafting begins.",
        ))

    # 6. Stated fee cap -- flagged as a commercial exclusion risk.
    if analysis.fee_cap:
        gaps.append(GapItem(
            risk_level="Medium",
            issue=f"The brief states a fee cap/budget ceiling: {analysis.fee_cap}.",
            impact="A priced offer above this ceiling may be excluded or heavily down-scored regardless of technical quality.",
            recommended_action="Confirm the final priced schedule against this ceiling before submission.",
            mapped_section="Commercial / Value for Money",
        ))

    # 7. Anything the extraction pass itself couldn't confidently resolve.
    for warning in analysis.analysis_warnings:
        gaps.append(GapItem(
            risk_level="Medium",
            issue=f"Automated extraction flagged this as ambiguous: {warning}",
            impact="Automated analysis may be incomplete or incorrect on this point.",
            recommended_action="Manually verify this against the original brief text.",
        ))

    # Sort High -> Medium -> Low for a useful default reading order.
    order = {"High": 0, "Medium": 1, "Low": 2}
    gaps.sort(key=lambda g: order.get(g.risk_level, 3))
    return gaps
