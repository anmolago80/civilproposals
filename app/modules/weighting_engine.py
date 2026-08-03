"""
weighting_engine.py

Decides how much weight each proposal section carries, following one hard
rule: if the tender brief states its own weightings (whether as a plain
"Evaluation Criteria" table or as named Selection Criteria like SC1/SC2),
those are used exactly as given. A default standard template is only a
last-resort fallback for briefs that genuinely don't state weightings at
all -- real tenders vary far more than one template can capture (see
README), so this should be the exception, not the common path.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.tender_analyser import TenderAnalysis, EvaluationCriterion


class WeightedCriterion(BaseModel):
    criterion_name: str
    criterion_code: str | None = None
    criterion_description: str = ""
    detected_weighting: float | None = None
    applied_weighting: float
    weighting_source: str  # "tender_provided" | "default_standard" | "manual_override"
    priority_rank: int = 0
    mapped_section: str
    page_limit: str | None = None
    format_requirements: str | None = None
    is_mandatory_gate: bool = False
    returnable_schedule_ref: str | None = None


# Last-resort fallback only -- used when the brief states no weightings at all.
DEFAULT_WEIGHTING_TEMPLATE = [
    {"section": "Methodology / Approach", "weighting": 35.0},
    {"section": "Relevant Experience", "weighting": 25.0},
    {"section": "Key Personnel / Capability", "weighting": 20.0},
    {"section": "Risk, Safety, Quality & Sustainability", "weighting": 10.0},
    {"section": "Commercial / Value for Money", "weighting": 10.0},
]


def apply_weighting(analysis: TenderAnalysis) -> list[WeightedCriterion]:
    """
    Build the weighted criteria list for an analysed tender.

    Returns criteria sorted by applied_weighting descending (priority_rank
    1 = highest weighting). Mandatory pass/fail gates (is_mandatory_gate)
    are kept in the list but excluded from percentage-based ranking logic.
    """
    scored = [c for c in analysis.evaluation_criteria if not c.is_mandatory_gate]
    gates = [c for c in analysis.evaluation_criteria if c.is_mandatory_gate]

    any_weighting_stated = any(c.detected_weighting is not None for c in scored)

    if scored and any_weighting_stated:
        weighted = _use_tender_provided_weighting(scored)
    else:
        weighted = _use_default_template(scored)

    # Mandatory gates get a nominal 0% weighting but stay visible and must-pass.
    for gate in gates:
        weighted.append(
            WeightedCriterion(
                criterion_name=gate.name,
                criterion_code=gate.criterion_code,
                criterion_description=gate.description,
                detected_weighting=None,
                applied_weighting=0.0,
                weighting_source="tender_provided",
                mapped_section=gate.name,
                page_limit=gate.page_limit,
                format_requirements=gate.format_requirements,
                is_mandatory_gate=True,
                returnable_schedule_ref=gate.returnable_schedule_ref,
            )
        )

    weighted.sort(key=lambda w: (-w.applied_weighting, w.is_mandatory_gate))
    for rank, item in enumerate(weighted, start=1):
        item.priority_rank = rank
    return weighted


def _use_tender_provided_weighting(scored: list[EvaluationCriterion]) -> list[WeightedCriterion]:
    stated_total = sum(c.detected_weighting or 0 for c in scored)
    missing = [c for c in scored if c.detected_weighting is None]
    remaining = max(0.0, 100.0 - stated_total)
    fallback_share = (remaining / len(missing)) if missing else 0.0

    result = []
    for c in scored:
        applied = c.detected_weighting if c.detected_weighting is not None else fallback_share
        result.append(
            WeightedCriterion(
                criterion_name=c.name,
                criterion_code=c.criterion_code,
                criterion_description=c.description,
                detected_weighting=c.detected_weighting,
                applied_weighting=round(applied, 1),
                weighting_source="tender_provided",
                mapped_section=c.name,
                page_limit=c.page_limit,
                format_requirements=c.format_requirements,
                is_mandatory_gate=False,
                returnable_schedule_ref=c.returnable_schedule_ref,
            )
        )
    return result


def _use_default_template(scored: list[EvaluationCriterion]) -> list[WeightedCriterion]:
    """
    No weighting stated anywhere in the brief. Try to map any criteria the
    brief *did* name (just without a %) onto the default template by keyword;
    anything unmatched, or if no criteria were extracted at all, falls back
    to the template's own section names directly.
    """
    result = []
    matched_template_sections = set()

    for c in scored:
        template_match = _best_template_match(c.name + " " + c.description)
        if template_match and template_match["section"] not in matched_template_sections:
            matched_template_sections.add(template_match["section"])
            applied = template_match["weighting"]
        else:
            applied = 0.0  # unmatched extra criterion -- flagged via 0% for human review
        result.append(
            WeightedCriterion(
                criterion_name=c.name,
                criterion_code=c.criterion_code,
                criterion_description=c.description,
                detected_weighting=None,
                applied_weighting=applied,
                weighting_source="default_standard",
                mapped_section=template_match["section"] if template_match else c.name,
                page_limit=c.page_limit,
                format_requirements=c.format_requirements,
                is_mandatory_gate=False,
                returnable_schedule_ref=c.returnable_schedule_ref,
            )
        )

    # Any default-template sections not matched to an extracted criterion still need to exist.
    for template_item in DEFAULT_WEIGHTING_TEMPLATE:
        if template_item["section"] not in matched_template_sections:
            result.append(
                WeightedCriterion(
                    criterion_name=template_item["section"],
                    criterion_description=(
                        "No matching criterion found in the brief -- applied from the "
                        "default standard weighting template. Verify against the brief."
                    ),
                    detected_weighting=None,
                    applied_weighting=template_item["weighting"],
                    weighting_source="default_standard",
                    mapped_section=template_item["section"],
                )
            )
    return result


def _best_template_match(text: str) -> dict | None:
    text_lower = text.lower()
    keyword_map = {
        "Methodology / Approach": ["methodology", "approach", "technical approach", "delivery"],
        "Relevant Experience": ["experience", "past performance", "track record", "relevant project"],
        "Key Personnel / Capability": ["personnel", "key staff", "team", "capability", "cv", "resource"],
        "Risk, Safety, Quality & Sustainability": ["risk", "safety", "quality", "sustainability", "environment"],
        "Commercial / Value for Money": ["price", "cost", "commercial", "value for money", "fee"],
    }
    for template_item in DEFAULT_WEIGHTING_TEMPLATE:
        for kw in keyword_map[template_item["section"]]:
            if kw in text_lower:
                return template_item
    return None


def apply_manual_override(
    weighted_criteria: list[WeightedCriterion], overrides: dict[str, float]
) -> list[WeightedCriterion]:
    """
    Apply user-entered weighting overrides, keyed by criterion_name.
    Re-ranks the list afterwards. Does not attempt to force the total back
    to 100% -- that's surfaced to the user in the UI as a warning instead,
    since forcing it silently would hide a real user decision.
    """
    updated = []
    for item in weighted_criteria:
        if item.criterion_name in overrides:
            item = item.model_copy(update={
                "applied_weighting": overrides[item.criterion_name],
                "weighting_source": "manual_override",
            })
        updated.append(item)
    updated.sort(key=lambda w: (-w.applied_weighting, w.is_mandatory_gate))
    for rank, item in enumerate(updated, start=1):
        item.priority_rank = rank
    return updated
