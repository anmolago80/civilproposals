"""
test_exports.py -- builds a full sample project and generates every export.

This is the open-check harness for output changes: it constructs one
realistic project (analysis, structure, drafts, resourcing plan, fees,
program, references) and runs it through all six exports the app produces:

    Proposal (Large Scope) DOCX      Org Chart PPTX
    Tender Summary DOCX              Methodology Table PPTX
    Proposal (Small Scope) DOCX      Delivery Program PPTX

Then it asserts the things a human would otherwise have to open six files
to check. Every assertion here corresponds to a specific behaviour that was
wrong before, so a regression shows up as a named failure rather than as a
document someone has to notice is subtly worse.

    python test_exports.py               # assert only
    python test_exports.py --out DIR     # also write the files out for review

The sample project is deliberately hand-written rather than AI-generated:
these tests must be deterministic and must never need an API key.
"""

from __future__ import annotations

import io
import os
import sys


# ---------------------------------------------------------------------------
# The sample project
# ---------------------------------------------------------------------------

def build_sample_project() -> dict:
    """One realistic in-progress project, as a plain dict of the session-state
    values the exporters read."""
    from modules import (
        draft_generator, fee_estimation_engine, page_allocation, proposal_structure,
        reference_projects, resourcing, tender_analyser, weighting_engine,
    )

    analysis = tender_analyser.TenderAnalysis(
        project_scope=(
            "Detailed design of the replacement Example Creek bridge and 400 m of "
            "approach road, including geotechnical investigation and stormwater upgrades."
        ),
        client_objectives=[
            "Restore flood immunity to a 1% AEP event",
            "Minimise disruption to the adjoining residential street",
        ],
        submission_date="14 July 2026",
        mandatory_requirements=[
            "Professional Indemnity insurance of not less than $10,000,000",
            "RPEQ certification for all structural design",
        ],
        deliverables=[
            "Concept design report",
            "Detailed design drawings (IFC)",
            "Design certification and RPEQ sign-off",
        ],
        scope_items=[
            tender_analyser.ScopeItem(
                title="Project inception and site investigation",
                tasks=["Inception meeting", "Site inspection", "Geotechnical investigation"],
            ),
            tender_analyser.ScopeItem(
                title="Concept design",
                tasks=["Options assessment", "Concept drawings", "Cost estimate"],
            ),
            tender_analyser.ScopeItem(
                title="Detailed design",
                tasks=["Structural design", "Drainage design", "IFC drawing set"],
            ),
        ],
        risks=["Wet-season access to the creek bed", "Unknown service locations"],
        assumptions=["Survey is provided by the Principal"],
        fee_cap="$450,000 ex GST",
        disciplines_involved=["Structural", "Geotechnical", "Hydraulics & Hydrology"],
    )

    # The real Large Scope skeleton, built through the same entry point the
    # Proposal Structure tab uses, so the exported document has the shape a
    # user's would. Weighted criteria are supplied (rather than left empty)
    # because a bare skeleton is only the four fixed sections -- no Commercial
    # or Relationship Management section, and so no coverage of the parts of
    # the exporter that render them.
    weighted_criteria = [
        weighting_engine.WeightedCriterion(
            criterion_name="Methodology and program", criterion_code="SC1",
            applied_weighting=35.0, weighting_source="tender_provided",
            mapped_section="Methodology / Approach", priority_rank=1,
        ),
        weighting_engine.WeightedCriterion(
            criterion_name="Relevant experience", criterion_code="SC2",
            applied_weighting=25.0, weighting_source="tender_provided",
            mapped_section="Relevant Experience", priority_rank=2,
        ),
        weighting_engine.WeightedCriterion(
            criterion_name="Key personnel", criterion_code="SC3",
            applied_weighting=20.0, weighting_source="tender_provided",
            mapped_section="Key Personnel / Capability", priority_rank=3,
        ),
        weighting_engine.WeightedCriterion(
            criterion_name="Commercial and value for money", criterion_code="SC4",
            applied_weighting=20.0, weighting_source="tender_provided",
            mapped_section="Commercial", priority_rank=4,
        ),
    ]
    allocations = [
        page_allocation.PageAllocation(
            section_name=c.mapped_section, weighting=c.applied_weighting,
            page_limit_source="weighted_total_limit", allocated_pages=3,
            reason="Weighted share of the total page limit.",
        )
        for c in weighted_criteria
    ]
    sections = proposal_structure.build_proposal_structure(
        analysis, weighted_criteria=weighted_criteria, allocations=allocations,
        proposal_format="formal",
    )

    resource_plan = [
        resourcing.ResourceAssignment(
            slot="Project Director", slot_kind="management", person_name="Jane Smith",
            qualification="BEng (Civil) (Hons), UQ, 2003", rpeq_status="RPEQ 12345",
            years_experience="18 years",
            value_to_project="lead the design and hold RPEQ certification for the structure.",
            relevant_projects=["Example River bridge replacement, 2024"],
        ),
        resourcing.ResourceAssignment(
            slot="Structural", slot_kind="discipline", person_name="Mat Williams",
            qualification="MEng (Structural)", rpeq_status="RPEQ 22334",
            years_experience="12 years",
        ),
        # A support member with NO custom title -- must render a red placeholder,
        # never a silent "Team member".
        resourcing.ResourceAssignment(
            slot="Structural", slot_kind="discipline", person_name="Ryan Swagemakers",
            is_lead=False, years_experience="4 years",
        ),
        resourcing.ResourceAssignment(
            slot="Geotechnical", slot_kind="discipline", person_name="Sam Lee",
            qualification="BSc (Geology)", years_experience="9 years",
        ),
        # Deliberately unassigned -- exports must show this as TBC, not hide it.
        resourcing.ResourceAssignment(slot="Hydraulics & Hydrology", slot_kind="discipline"),
    ]

    discipline_fee_lines = [
        resourcing.DisciplineFeeLine(discipline="Structural", total_hours=800, rate_per_hour=210),
        resourcing.DisciplineFeeLine(discipline="Geotechnical", total_hours=260, rate_per_hour=195),
        # A priced-at-nothing row: must never export as a literal $0.
        resourcing.DisciplineFeeLine(discipline="Hydraulics & Hydrology", total_hours=0, rate_per_hour=0),
    ]

    fee_estimates = [
        fee_estimation_engine.DisciplineFeeEstimate(
            discipline="Structural", fee_percentage=58.3, confidence="Medium", source="Benchmark",
        ),
        fee_estimation_engine.DisciplineFeeEstimate(
            discipline="Geotechnical", fee_percentage=25.4, confidence="Medium", source="Benchmark",
        ),
        fee_estimation_engine.DisciplineFeeEstimate(
            discipline="Hydraulics & Hydrology", fee_percentage=16.3, confidence="Low", source="Benchmark",
        ),
    ]

    week_labels = [f"Wk {i}" for i in range(1, 13)]
    program_schedule = {
        "Project inception and site investigation": [i < 3 for i in range(12)],
        "Concept design": [2 <= i < 6 for i in range(12)],
        # Week 12 is deliberately idle: the derived cash flow must show a
        # gap there rather than smearing fee across a week with no work.
        "Detailed design": [5 <= i < 11 for i in range(12)],
    }

    drafts = {
        "Project Understanding": draft_generator.SectionDraft(
            section_title="Project Understanding",
            draft_heading="Understanding the brief",
            draft_text=(
                "**Our understanding**\n\nThe Principal requires the replacement of the "
                "Example Creek bridge together with 400 m of approach road.\n\n"
                "The controlling constraint is flood immunity to a 1% AEP event."
            ),
            required_user_inputs=[],
            recommended_graphic_placeholders=[],
        ),
        "Methodology and Deliverables": draft_generator.SectionDraft(
            section_title="Methodology and Deliverables",
            draft_heading="How we will deliver",
            draft_text=(
                "**Staged delivery**\n\nThe work is delivered in three stages: inception "
                "and investigation, concept design, and detailed design."
            ),
            required_user_inputs=[],
            recommended_graphic_placeholders=[],
        ),
    }

    refs = [
        reference_projects.ReferenceProject(
            title="Example River bridge replacement",
            client="Example Shire Council",
            description="Replacement of a 3-span bridge on a flood-affected rural road.",
            relevance_text="Same structure type and the same 1% AEP immunity requirement.",
        ),
    ]

    return {
        "project_info": {
            "project_name": "Example Creek Bridge Replacement",
            "client_name": "Example Shire Council",
            "tender_name": "RFT 2026-014",
            "bidder_name": "Test Engineering Pty Ltd",
            "submission_date_input": "14 July 2026",
            "proposal_theme": "Forest Green",
            "project_type": "Bridge",
        },
        "analysis": analysis,
        "sections": sections,
        "drafts": drafts,
        "resource_plan": resource_plan,
        "discipline_fee_lines": discipline_fee_lines,
        "fee_estimates": fee_estimates,
        "program_schedule": program_schedule,
        "program_week_labels": week_labels,
        "reference_projects": refs,
        "sender": {
            "name": "Jane Smith", "title": "Project Director",
            "phone": "07 3000 0000", "email": "jane@example.com",
        },
        "terms_of_engagement_text": "AS 4122-2010 General Conditions of Contract.",
    }


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def generate_all(project: dict) -> dict:
    """Runs every exporter. Returns {filename: bytes}."""
    from modules import (
        export_docx, methodology_pptx, org_chart, org_chart_pptx, program_pptx,
    )

    info = project["project_info"]
    org_png = org_chart.render_org_chart(
        project["resource_plan"], theme_name=info["proposal_theme"],
        project_title=info["project_name"],
    )

    out: dict[str, bytes] = {}

    out["Proposal_LargeScope.docx"] = export_docx.build_docx(
        project_info=info,
        analysis=project["analysis"],
        weighted_criteria=[],
        allocations=[],
        sections=project["sections"],
        guidance_notes={},
        drafts=project["drafts"],
        compliance_items=[],
        gap_items=[],
        graphics=[],
        fee_estimates=project["fee_estimates"],
        resource_plan=project["resource_plan"],
        org_chart_png=org_png,
        reference_projects=project["reference_projects"],
        discipline_fee_lines=project["discipline_fee_lines"],
        program_schedule=project["program_schedule"],
        program_week_labels=project["program_week_labels"],
    ).getvalue()

    out["Tender_Summary.docx"] = export_docx.build_tender_summary_docx(
        project_info=info,
        analysis=project["analysis"],
        weighting_chart_png=None,
        compliance_items=[],
        gap_items=[],
        sections=project["sections"],
        drafts=project["drafts"],
    ).getvalue()

    out["Proposal_SmallScope.docx"] = export_docx.build_letter_docx(
        project_info=info,
        sender=project["sender"],
        analysis=project["analysis"],
        understanding_text=project["drafts"]["Project Understanding"].draft_text,
        methodology_text=project["drafts"]["Methodology and Deliverables"].draft_text,
        resource_plan=project["resource_plan"],
        personnel_photos={},
        program_schedule=project["program_schedule"],
        program_week_labels=project["program_week_labels"],
        terms_of_engagement_text=project["terms_of_engagement_text"],
        fee_estimates=project["fee_estimates"],
        discipline_fee_lines=project["discipline_fee_lines"],
    ).getvalue()

    out["Org_Chart.pptx"] = org_chart_pptx.populate_org_chart(
        project["resource_plan"],
        client_name=info["client_name"],
        project_name=info["project_name"],
    )
    out["Methodology_Table.pptx"] = methodology_pptx.populate_methodology(
        project["analysis"],
        client_name=info["client_name"],
        project_name=info["project_name"],
        theme_name=info["proposal_theme"],
    )
    out["Delivery_Program.pptx"] = program_pptx.populate_program(
        project["program_schedule"], project["program_week_labels"],
        client_name=info["client_name"],
        project_name=info["project_name"],
        theme_name=info["proposal_theme"],
    )
    if org_png:
        out["_org_chart_preview.png"] = org_png
    return out


# ---------------------------------------------------------------------------
# Reading the outputs back
# ---------------------------------------------------------------------------

def docx_text(blob: bytes) -> str:
    """All body + table text of a DOCX, as one string."""
    from docx import Document
    doc = Document(io.BytesIO(blob))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            parts.extend(c.text for c in row.cells)
    return "\n".join(parts)


def docx_image_count(blob: bytes) -> int:
    from docx import Document
    doc = Document(io.BytesIO(blob))
    return sum(1 for part in doc.part.package.parts if part.content_type.startswith("image/"))


def pptx_text(blob: bytes) -> str:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(blob))
    parts = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    parts.extend(c.text for c in row.cells)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def check(files: dict, failures: list[str]) -> None:
    large = docx_text(files["Proposal_LargeScope.docx"])

    # 1(c): the generated org chart must actually be in the pack, and the
    # "replace me with the finished chart" note must survive alongside it.
    if docx_image_count(files["Proposal_LargeScope.docx"]) < 3:
        failures.append("[1c] the Large Scope pack lost an image -- org chart not embedded")
    if "FIRST-PASS CHART ABOVE" not in large:
        failures.append("[1c] the org chart's replace-me note is missing")
    if "Project organisation chart" not in large:
        failures.append("[1c] the org chart heading disappeared")

    # 1(d): the cash-flow profile is derived when the fee build-up and the
    # program both exist, instead of telling the user to combine them by hand.
    if "[INSERT PROJECT CASH FLOW PROFILE" in large:
        failures.append("[1d] cash flow is still a placeholder despite a priced fee and a program")
    if "Indicative only, derived from your fee build-up and program" not in large:
        failures.append("[1d] the derived cash flow's honesty note is missing")

    from modules import export_docx
    project = build_sample_project()
    rows = export_docx.cash_flow_rows(
        project["discipline_fee_lines"], project["program_schedule"], project["program_week_labels"],
    )
    expected_total = sum(l.fee_amount for l in project["discipline_fee_lines"])
    if not rows:
        failures.append("[1d] cash_flow_rows returned nothing for a fully-specified project")
    else:
        if abs(rows[-1][2] - expected_total) > 0.01:
            failures.append(f"[1d] cash flow doesn't sum to the fee total: {rows[-1][2]} vs {expected_total}")
        # Week 12 has no scope item active in the fixture -- it must carry $0
        # rather than have money smeared into it.
        if abs(rows[-1][1]) > 0.01:
            failures.append("[1d] a week with no programmed work was given fee")

    # ...and it must NOT invent a profile when either input is missing.
    if export_docx.cash_flow_rows(project["discipline_fee_lines"], {}, []):
        failures.append("[1d] a cash flow was derived with no program")
    if export_docx.cash_flow_rows([], project["program_schedule"], project["program_week_labels"]):
        failures.append("[1d] a cash flow was derived with no priced fee")


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    out_dir = None
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]
        os.makedirs(out_dir, exist_ok=True)

    project = build_sample_project()
    files = generate_all(project)

    if out_dir:
        for name, blob in files.items():
            with open(os.path.join(out_dir, name), "wb") as fh:
                fh.write(blob)
        print(f"Wrote {len(files)} files to {out_dir}")

    failures: list[str] = []
    check(files, failures)

    if failures:
        print("EXPORT TESTS FAILED:")
        for failure in failures:
            print("  -", failure)
        return 1
    print(f"EXPORT TESTS PASSED ({len(files)} artefacts generated and checked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
