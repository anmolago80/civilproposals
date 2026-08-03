"""
guidance_generator.py

Builds the red "DELETE BEFORE SUBMISSION" guidance note for each proposal
section. This is deliberately deterministic (no AI call) -- everything it
needs (page limit, weighting, format rules, brief requirements, recommended
content/graphics) has already been extracted and structured by the earlier
pipeline stages, so assembling the note is just formatting, not judgement.

export_docx.py is responsible for actually rendering this in red/bold text;
this module just produces the structured content and a plain-text version.
"""

from __future__ import annotations

from pydantic import BaseModel

from modules.proposal_structure import ProposalSection

MARKER = "DELETE BEFORE SUBMISSION"


class GuidanceNote(BaseModel):
    section_title: str
    marker: str = MARKER
    page_limit_text: str
    weighting_text: str
    format_requirements_text: str
    brief_requirements: list[str]
    recommended_content: list[str]
    recommended_graphics: list[str]
    user_actions_required: list[str]
    plain_text: str


def generate_guidance_note(section: ProposalSection) -> GuidanceNote:
    page_limit_text = f"{section.allocated_pages} page(s)"
    if section.page_limit_source == "tender_section_limit":
        page_limit_text += " -- stated explicitly in the brief for this section."
    elif section.page_limit_source == "weighted_total_limit":
        page_limit_text += " -- your weighted share of the brief's total page limit."
    elif section.page_limit_source == "manual_override":
        page_limit_text += " -- manually set by the user."
    elif section.page_limit_source == "not_applicable":
        page_limit_text += " -- indicative only; letter proposals don't carry a stated page limit to mirror."
    else:
        page_limit_text += " -- default allocation template; no limit was stated in the brief, confirm this is reasonable."

    if section.weighting > 0:
        weighting_text = f"{section.weighting:.0f}%"
        if section.weighting_source == "tender_provided":
            weighting_text += " (as stated in the brief)"
        elif section.weighting_source == "default_standard":
            weighting_text += " (default standard template -- the brief did not state a weighting; verify)"
        elif section.weighting_source == "manual_override":
            weighting_text += " (manually overridden by the user)"
    else:
        weighting_text = "Not separately weighted / not stated in the brief."

    format_requirements_text = section.format_requirements or "No specific formatting rules stated in the brief -- use firm standard template."

    user_actions = [
        "Replace every placeholder in this section with real, project-specific, verified detail.",
        "Confirm the page limit and any formatting rules above against the current brief and any addenda.",
        "Insert the recommended graphics (or an approved alternative) at the placements noted.",
        "Delete this entire guidance box before the document is finalised for submission.",
    ]
    if section.criterion_code:
        user_actions.insert(0, f"Confirm this section's content directly and visibly addresses {section.criterion_code} as worded in the brief -- assessors mark against the exact criterion.")

    lines = [
        f"[{MARKER}] -- {section.title}",
        f"Page limit: {page_limit_text}",
        f"Evaluation weighting: {weighting_text}",
        f"Formatting requirements: {format_requirements_text}",
    ]
    if section.brief_requirements:
        lines.append("Brief requirements for this section:")
        lines += [f"  - {r}" for r in section.brief_requirements if r]
    if section.recommended_content:
        lines.append("Recommended content to cover:")
        lines += [f"  - {c}" for c in section.recommended_content]
    if section.recommended_graphics:
        lines.append("Recommended graphics:")
        lines += [f"  - {g}" for g in section.recommended_graphics]
    lines.append("User actions required before submission:")
    lines += [f"  - {a}" for a in user_actions]

    return GuidanceNote(
        section_title=section.title,
        page_limit_text=page_limit_text,
        weighting_text=weighting_text,
        format_requirements_text=format_requirements_text,
        brief_requirements=[r for r in section.brief_requirements if r],
        recommended_content=section.recommended_content,
        recommended_graphics=section.recommended_graphics,
        user_actions_required=user_actions,
        plain_text="\n".join(lines),
    )


def generate_all_guidance_notes(sections: list[ProposalSection]) -> dict[str, GuidanceNote]:
    return {s.title: generate_guidance_note(s) for s in sections}
