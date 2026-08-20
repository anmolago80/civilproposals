"""
test_batch1_wiring.py -- regression tests for the Batch 1 wiring fixes.

Each test here pins one behaviour that used to be silently wrong: data the
app already collected but never got into the exported document. They are
deliberately plain assertions over the module functions rather than UI
tests, because the bugs were all in the wiring, not the widgets.

Run from this directory:

    python test_batch1_wiring.py
"""

from __future__ import annotations

import os
import sys


class _State(dict):
    """Stands in for st.session_state: .get() plus attribute-free access is
    all the modules under test use."""


def test_schedule_filler_reads_real_quals(failures: list[str]) -> None:
    """1(a): qualifications/years came from a session key nothing ever wrote,
    so a fully-filled Team & Resourcing tab still produced an empty
    Qualifications column in the client's personnel schedule."""
    from modules import resourcing, returnable_schedules

    state = _State(
        resource_plan=[
            resourcing.ResourceAssignment(
                slot="Project Director",
                slot_kind="management",
                person_name="Jane Smith",
                qualification="BEng (Civil) (Hons), UQ, 2003",
                rpeq_status="RPEQ 12345",
                years_experience="18 years",
            ),
            resourcing.ResourceAssignment(
                slot="Structural",
                slot_kind="discipline",
                person_name="Raj Patel",
                qualification="MEng (Structural)",
                # no RPEQ entered -- must not produce a trailing comma
                years_experience="9 years",
            ),
        ],
        team_members=[],
    )
    data = returnable_schedules.build_fill_data(state)
    people = {p["name"]: p for p in data["personnel"]}

    if "Jane Smith" not in people or "Raj Patel" not in people:
        failures.append("[1a] the resourcing plan's people didn't reach the fill data")
        return
    if people["Jane Smith"]["quals"] != "BEng (Civil) (Hons), UQ, 2003, RPEQ 12345":
        failures.append(f"[1a] qualification+RPEQ not joined: {people['Jane Smith']['quals']!r}")
    if people["Jane Smith"]["years"] != "18 years":
        failures.append(f"[1a] years_experience not carried: {people['Jane Smith']['years']!r}")
    if people["Raj Patel"]["quals"] != "MEng (Structural)":
        failures.append(f"[1a] blank RPEQ left punctuation behind: {people['Raj Patel']['quals']!r}")
    if people["Jane Smith"]["role"] != "Project Director":
        failures.append("[1a] role no longer resolves from slot/custom_title")


def test_blank_person_still_placeholders(failures: list[str]) -> None:
    """The no-invention rule: a person with nothing entered must come through
    with empty strings so the filler placeholders those cells, not with
    anything guessed."""
    from modules import resourcing, returnable_schedules

    state = _State(
        resource_plan=[
            resourcing.ResourceAssignment(
                slot="Geotechnical", slot_kind="discipline", person_name="Sam Lee",
            )
        ],
        team_members=[],
    )
    person = returnable_schedules.build_fill_data(state)["personnel"][0]
    if person["quals"] or person["years"]:
        failures.append(f"[1a] blank credentials were not left blank: {person!r}")


def test_sender_address_is_wired_and_saved(failures: list[str]) -> None:
    """1(b): the schedule filler read letter_sender_address, but no widget
    ever set it and it wasn't in the saved-project key list, so the address
    labels on client forms could never be filled by anyone."""
    from modules import project_store, returnable_schedules

    if "letter_sender_address" not in project_store.PLAIN_KEYS:
        failures.append("[1b] letter_sender_address is not saved with the project")

    state = _State(
        letter_sender_address="Level 3, 100 Example St, Brisbane QLD 4000",
        resource_plan=[], team_members=[],
    )
    data = returnable_schedules.build_fill_data(state)
    if data.get("contact_address") != "Level 3, 100 Example St, Brisbane QLD 4000":
        failures.append(f"[1b] contact_address not built: {data.get('contact_address')!r}")

    # Round-trip it through a real save/load so a registration that exists but
    # doesn't survive the zip still fails here.
    saved = project_store.save_project(_State(letter_sender_address="12 Test Rd"))
    if project_store.load_project(saved).get("letter_sender_address") != "12 Test Rd":
        failures.append("[1b] letter_sender_address did not survive save/load")

    # And it must actually match an address label on a form.
    field_key, value = returnable_schedules.match_label("Registered Office:", data)
    if field_key != "contact_address" or not value:
        failures.append(f"[1b] a 'Registered Office' label didn't resolve: {field_key!r} {value!r}")


def test_program_start_date(failures: list[str]) -> None:
    """1(f): week headers can carry real calendar dates, and the date has to
    survive save/load (a date is not JSON-safe, so it needs its own handling
    rather than a PLAIN_KEYS entry)."""
    import datetime

    from modules import program_schedule, project_store

    plain = program_schedule.week_labels(3, None)
    if plain != ["Wk 1", "Wk 2", "Wk 3"]:
        failures.append(f"[1f] unchanged behaviour without a start date broke: {plain}")

    dated = program_schedule.week_labels(3, datetime.date(2026, 10, 6))
    if dated != ["Wk 1 - 6 Oct", "Wk 2 - 13 Oct", "Wk 3 - 20 Oct"]:
        failures.append(f"[1f] dated week labels are wrong: {dated}")

    if "program_start_date" not in project_store.DATE_KEYS:
        failures.append("[1f] program_start_date is not saved with the project")
    saved = project_store.save_project(_State(program_start_date=datetime.date(2026, 10, 6)))
    if project_store.load_project(saved).get("program_start_date") != datetime.date(2026, 10, 6):
        failures.append("[1f] the start date did not survive save/load")
    # Unset must round-trip as None, not as today's date or a crash.
    if project_store.load_project(project_store.save_project(_State())).get("program_start_date") is not None:
        failures.append("[1f] an unset start date did not round-trip as None")


def test_graphics_recommendations_are_current(failures: list[str]) -> None:
    """1(g): the graphics list is printed into the exported pack, so a stale
    entry tells the user to hand-build something the app already made."""
    from modules import graphics_engine, proposal_structure, tender_analyser

    sections = proposal_structure.build_proposal_structure(
        tender_analyser.TenderAnalysis(), [], [], "formal",
    )
    recs = {r.graphic_title: r for r in graphics_engine.recommend_graphics(
        sections, project_type="Coastal & Ocean Engineering")}

    for title in ("Organisation chart", "Methodology process diagram", "Programme timeline"):
        rec = recs.get(title)
        if rec is None:
            continue  # this brief's skeleton doesn't recommend it -- fine
        if rec.status != "Generated":
            failures.append(f"[1g] '{title}' is still reported as needing user input")
        if rec.placeholder_text:
            failures.append(f"[1g] '{title}' still carries a red placeholder instruction")

    # Genuinely ungenerated graphics must still be placeholdered.
    risk = recs.get("Key risk diagram")
    if risk is not None and risk.status == "Generated":
        failures.append("[1g] an ungenerated graphic was wrongly marked Generated")

    # The divider hint follows the project type instead of always saying bridge/road.
    divider = next((r for r in recs.values() if "divider" in r.graphic_title.lower()), None)
    if divider is None or "COASTAL" not in divider.placeholder_text:
        failures.append(f"[1g] the divider hint ignores project_type: "
                        f"{getattr(divider, 'placeholder_text', None)!r}")
    if divider is not None and "BRIDGE / ROAD" in divider.placeholder_text:
        failures.append("[1g] the divider hint is still hardcoded to bridge/road")


def _sheet_rows(blob: bytes) -> list[list]:
    import io as _io

    import openpyxl
    ws = openpyxl.load_workbook(_io.BytesIO(blob)).active
    return [list(row) for row in ws.iter_rows(values_only=True)]


def test_excel_fee_exports(failures: list[str]) -> None:
    """1(h): an unpriced discipline exported as a literal $0, which reads as
    an offer to do that work for nothing; the workbook carried nothing
    identifying the project; and the fee-% total cell was left empty."""
    from modules import fee_estimation_engine, resourcing

    info = {"project_name": "Example Creek Bridge", "client_name": "Example Shire Council",
            "tender_name": "RFT 2026-014", "bidder_name": "Test Engineering Pty Ltd"}

    lines = [
        resourcing.DisciplineFeeLine(discipline="Structural", total_hours=800, rate_per_hour=210),
        resourcing.DisciplineFeeLine(discipline="Hydraulics", total_hours=0, rate_per_hour=0),
    ]
    rows = _sheet_rows(resourcing.discipline_fee_lines_to_excel(lines, "Government", info))
    flat = [str(cell) for row in rows for cell in row if cell is not None]

    unpriced = next((r for r in rows if r and r[0] == "Hydraulics"), None)
    if unpriced is None:
        failures.append("[1h] the unpriced discipline row is missing entirely")
    else:
        if any(cell == 0 for cell in unpriced[1:4]):
            failures.append(f"[1h] an unpriced discipline still exports as 0: {unpriced}")
        if unpriced[4] != resourcing.UNPRICED_NOTE:
            failures.append(f"[1h] the unpriced row carries no explanatory note: {unpriced}")
    if not any("NOT been priced" in cell for cell in flat):
        failures.append("[1h] the workbook doesn't explain what a blank fee cell means")
    for expected in ("Example Creek Bridge", "Example Shire Council", "RFT 2026-014"):
        if expected not in flat:
            failures.append(f"[1h] the fee build-up workbook doesn't identify the project ({expected})")
    priced = next((r for r in rows if r and r[0] == "Structural"), None)
    if priced is None or priced[3] != 168000:
        failures.append(f"[1h] a priced discipline no longer exports its total: {priced}")

    estimates = [
        fee_estimation_engine.DisciplineFeeEstimate(
            discipline="Structural", fee_percentage=58.3, confidence="Medium", source="Benchmark"),
        fee_estimation_engine.DisciplineFeeEstimate(
            discipline="Geotechnical", fee_percentage=41.7, confidence="Medium", source="Benchmark"),
    ]
    rows = _sheet_rows(fee_estimation_engine.fee_estimates_to_excel(estimates, project_info=info))
    total_row = next((r for r in rows if r and r[0] == "Total"), None)
    if total_row is None:
        failures.append("[1h] the fee-split workbook has no Total row")
    elif total_row[1] is None:
        failures.append("[1h] the fee-% total cell is still empty")
    elif abs(total_row[1] - 100.0) > 0.05:
        failures.append(f"[1h] the fee-% total is wrong: {total_row[1]}")
    if "Example Creek Bridge" not in [str(c) for r in rows for c in r if c is not None]:
        failures.append("[1h] the fee-split workbook doesn't identify the project")


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    failures: list[str] = []

    test_schedule_filler_reads_real_quals(failures)
    test_blank_person_still_placeholders(failures)
    test_sender_address_is_wired_and_saved(failures)
    test_program_start_date(failures)
    test_graphics_recommendations_are_current(failures)
    test_excel_fee_exports(failures)

    if failures:
        print("BATCH 1 WIRING TESTS FAILED:")
        for failure in failures:
            print("  -", failure)
        return 1
    print("BATCH 1 WIRING TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
