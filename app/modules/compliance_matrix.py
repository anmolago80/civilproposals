"""
compliance_matrix.py

Builds a requirement-by-requirement compliance matrix from the analysed
tender: every mandatory requirement, evaluation/selection criterion,
deliverable, required form/returnable schedule, formatting rule, and
submission-process item gets its own row, mapped to a proposal section
where possible, with a status that reflects what's actually been supplied
-- never assumed.

Status is driven by what the user has actually uploaded (company_materials),
not by guesswork: content that depends on personnel/references/certs the
user hasn't supplied is marked Missing, not silently assumed covered.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from modules.tender_analyser import TenderAnalysis
from modules.proposal_structure import ProposalSection

REQUIREMENT_TYPES = [
    "Mandatory", "Evaluation Criterion", "Deliverable", "Form or Schedule",
    "Commercial", "Technical", "Formatting", "Submission",
]
STATUS_OPTIONS = ["Covered", "Partially Covered", "Missing", "User Input Required"]

# Keywords that mean a requirement genuinely depends on company-supplied material
# (never invent these -- see draft_generator.py / gap_analysis.py for the same rule).
_PERSONNEL_KEYWORDS = ["personnel", "cv", "staff", "team member", "resume", "qualification", "rpeq", "registration"]
_REFERENCE_KEYWORDS = ["reference", "past project", "similar project", "case stud", "track record"]
_COMMERCIAL_KEYWORDS = ["insurance", "certificat", "accreditation", "licence", "license", "financial"]


class ComplianceItem(BaseModel):
    requirement_id: str
    description: str
    requirement_type: str
    source_location: str | None = None
    mapped_section: str | None = None
    priority: str  # High | Medium | Low
    status: str
    user_action_required: str | None = None


def build_compliance_matrix(
    analysis: TenderAnalysis,
    sections: list[ProposalSection],
    company_materials: dict[str, bool] | None = None,
) -> list[ComplianceItem]:
    company_materials = company_materials or {}
    items: list[ComplianceItem] = []
    section_titles = [s.title for s in sections]

    for i, req in enumerate(analysis.mandatory_requirements, start=1):
        text, page = _split_page_reference(req)
        mapped = _best_section_match(text, section_titles)
        status, action = _status_for_text(text, mapped, company_materials)
        items.append(ComplianceItem(
            requirement_id=f"M-{i:02d}", description=text, requirement_type="Mandatory",
            source_location=page,
            mapped_section=mapped, priority="High", status=status, user_action_required=action,
        ))

    # Implicit scope compliance. The brief's own scope of work is a compliance
    # obligation in its own right, even when it isn't written up as a numbered
    # "mandatory requirement": an offer that doesn't cover the stated scope is
    # non-conforming and won't be considered. So every discrete scope item the
    # brief describes is added here as a High-priority Mandatory item, unless it
    # already duplicates something the explicit mandatory-requirements list
    # captured above. These are marked so the user can see they're inferred from
    # scope rather than quoted verbatim from a "mandatory" clause.
    existing_desc = {it.description.strip().lower() for it in items}
    for i, scope in enumerate(getattr(analysis, "scope_items", []) or [], start=1):
        title = (getattr(scope, "title", "") or "").strip()
        if not title:
            continue
        desc = f"Deliver the scope item: {title} (key scope requirement -- mandatory to conform to the brief)"
        if title.lower() in existing_desc or desc.lower() in existing_desc:
            continue
        mapped = _best_section_match(title, section_titles)
        status, action = _status_for_text(title, mapped, company_materials)
        items.append(ComplianceItem(
            requirement_id=f"SCOPE-{i:02d}", description=desc,
            requirement_type="Mandatory", source_location="Implicit from scope of work",
            mapped_section=mapped, priority="High", status=status,
            user_action_required=action or "Confirm the proposal fully addresses this scope item -- required to be conforming.",
        ))

    for i, c in enumerate(analysis.evaluation_criteria, start=1):
        label = f"{c.criterion_code}: {c.name}" if c.criterion_code else c.name
        req_type = "Mandatory" if c.is_mandatory_gate else "Evaluation Criterion"
        priority = "High" if (c.is_mandatory_gate or (c.detected_weighting or 0) >= 25) else (
            "Medium" if (c.detected_weighting or 0) >= 10 else "Low"
        )
        mapped = _best_section_match(label, section_titles) or label
        status, action = _status_for_text(c.description or label, mapped, company_materials)
        items.append(ComplianceItem(
            requirement_id=f"EC-{i:02d}", description=f"{label} -- {c.description}".strip(" -"),
            requirement_type=req_type, mapped_section=mapped, priority=priority,
            status=status, user_action_required=action,
        ))

    for i, d in enumerate(analysis.deliverables, start=1):
        mapped = _best_section_match(d, section_titles)
        items.append(ComplianceItem(
            requirement_id=f"DEL-{i:02d}", description=d, requirement_type="Deliverable",
            mapped_section=mapped, priority="Medium",
            status="User Input Required", user_action_required="Confirm delivery approach and timing for this deliverable.",
        ))

    for i, f in enumerate(analysis.required_forms, start=1):
        items.append(ComplianceItem(
            requirement_id=f"FORM-{i:02d}", description=f, requirement_type="Form or Schedule",
            mapped_section=None, priority="High", status="User Input Required",
            user_action_required="Complete and attach this returnable schedule/form -- missing forms risk a non-conforming submission.",
        ))

    for i, note in enumerate(analysis.submission_format_notes, start=1):
        items.append(ComplianceItem(
            requirement_id=f"FMT-{i:02d}", description=note, requirement_type="Formatting",
            mapped_section=None, priority="Medium", status="User Input Required",
            user_action_required="Confirm the final document complies with this formatting rule before export.",
        ))

    if analysis.fee_cap:
        items.append(ComplianceItem(
            requirement_id="COM-01", description=f"Stated fee cap/budget ceiling: {analysis.fee_cap}",
            requirement_type="Commercial", mapped_section=None, priority="High",
            status="User Input Required", user_action_required="Ensure the priced schedule does not exceed this stated ceiling.",
        ))

    if analysis.submission_date:
        items.append(ComplianceItem(
            requirement_id="SUB-01", description=f"Submission closes: {analysis.submission_date}",
            requirement_type="Submission", mapped_section=None, priority="High",
            status="User Input Required", user_action_required="Confirm internal sign-off and lodgement plan allows for this deadline.",
        ))

    return items


_PAGE_REFERENCE_RE = re.compile(r"\s*\((?:p\.?|page)\s*(\d{1,4})\)\s*$", re.IGNORECASE)


def _split_page_reference(text: str) -> tuple[str, str | None]:
    """Peels a trailing "(p.12)" off an extracted requirement.

    The analysis chunk notes now carry the page each note came from (see
    tender_analyser's map prompt), which is what finally lets
    source_location point at somewhere in the client's own document. It has
    been an always-empty column since the matrix was written -- a compliance
    matrix that can't tell you where a requirement came from makes the bid
    team re-find every one of them by hand."""
    text = (text or "").strip()
    match = _PAGE_REFERENCE_RE.search(text)
    if not match:
        return text, None
    return text[:match.start()].strip(), f"Brief, p.{match.group(1)}"


def _status_for_text(text: str, mapped_section: str | None, company_materials: dict[str, bool]) -> tuple[str, str | None]:
    lowered = text.lower()

    if any(kw in lowered for kw in _PERSONNEL_KEYWORDS):
        if company_materials.get("has_cv_library"):
            return "Partially Covered", "CV library was uploaded -- select and insert the relevant CVs for this requirement."
        return "Missing", "No CV library was uploaded. Upload CVs or add named personnel detail before this can be addressed."

    if any(kw in lowered for kw in _REFERENCE_KEYWORDS):
        if company_materials.get("has_project_references") or company_materials.get("has_previous_proposals"):
            return "Partially Covered", "Project references/past proposals were uploaded -- select the most relevant ones for this requirement."
        return "Missing", "No project references or past proposals were uploaded. This cannot be addressed without user input."

    if any(kw in lowered for kw in _COMMERCIAL_KEYWORDS):
        # The firm profile holds real insurances and certifications, so this
        # requirement is genuinely covered rather than "must come from the
        # user" -- which is what it said permanently, before there was
        # anywhere in the app to put an insurance policy.
        has_insurance = company_materials.get("firm_profile_has_insurances")
        has_certs = company_materials.get("firm_profile_has_certifications")
        if has_insurance or has_certs:
            held = " and ".join(
                part for part in (
                    "insurances" if has_insurance else "",
                    "certifications" if has_certs else "",
                ) if part
            )
            return "Covered", (
                f"Your firm profile holds {held} -- check they meet this requirement's stated "
                f"limits and dates, then reference them here."
            )
        if company_materials.get("has_company_profile"):
            return "Partially Covered", "Check the company profile for current certification/insurance detail and insert it here."
        return "Missing", (
            "Nothing on file. Add your insurances and certifications to the Firm profile "
            "(sidebar) and they will fill this and your returnable schedules automatically."
        )

    if mapped_section:
        return "Partially Covered", f"A proposal section ('{mapped_section}') exists for this -- first-pass draft content will need review and project-specific detail."

    return "Missing", "No proposal section currently maps to this requirement -- add one manually or fold it into an existing section."


def _best_section_match(text: str, section_titles: list[str]) -> str | None:
    lowered = text.lower()
    best, best_score = None, 0
    for title in section_titles:
        title_words = set(w for w in title.lower().replace(":", " ").split() if len(w) > 3)
        score = sum(1 for w in title_words if w in lowered)
        if score > best_score:
            best, best_score = title, score
    return best
