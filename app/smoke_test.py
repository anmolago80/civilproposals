"""
smoke_test.py -- headless smoke test for the CivilProposals SaaS app.

Runs the full app script (all page segments -- see app.py's docstring) via
streamlit.testing.v1.AppTest in local mode (SAAS_MODE=false, SQLite, no
Redis, no AI key) and fails loudly on any exception, missing tab, or
missing session default. Run from this directory:

    python smoke_test.py

This is the automated half of the Batch-7 verification; the manual half is
CLICKTHROUGH_CHECKLIST.md.
"""

from __future__ import annotations

import logging
import os
import sys


def main() -> int:
    os.environ["SAAS_MODE"] = "false"
    for key in ("DATABASE_URL", "REDIS_URL", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)
    logging.disable(logging.WARNING)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from modules import db
    db.init_db()

    from streamlit.testing.v1 import AppTest

    failures: list[str] = []

    for proposal_format in ("formal", "letter"):
        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["proposal_format"] = proposal_format
        at.run()
        for exc in at.exception:
            failures.append(f"[{proposal_format}] exception: {exc.value}")
        labels = [t.label for t in at.tabs]
        if len(labels) != 10:
            failures.append(f"[{proposal_format}] expected 10 tabs, got {len(labels)}: {labels}")
        for expected in ("Project Setup", "Upload Documents", "Tender Analysis", "Export Pack"):
            if not any(expected in label for label in labels):
                failures.append(f"[{proposal_format}] missing tab: {expected}")
        for state_key in ("project_name", "ai_config", "returnable_schedule_files", "drafts"):
            if state_key not in at.session_state:
                failures.append(f"[{proposal_format}] missing session default: {state_key}")

        if not failures and proposal_format == "formal":
            # One interaction pass: set a project name, rerun everything.
            at.text_input(key="project_name").set_value("Smoke Test Project").run()
            for exc in at.exception:
                failures.append(f"[interaction] exception: {exc.value}")
            if at.session_state["project_name"] != "Smoke Test Project":
                failures.append("[interaction] project_name did not round-trip")

    # The program style picker and its live preview only exist once a program
    # has been built, so the two passes above never reach them -- which is
    # exactly the shape of gap that lets a broken preview ship.
    if not failures:
        from modules import program_render
        from modules.tender_analyser import ScopeItem, TenderAnalysis

        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["proposal_format"] = "letter"
        # The Fees & Program tab only builds its fee/program section once a
        # brief has been analysed, so the picker is unreachable without one.
        at.session_state["analysis"] = TenderAnalysis(
            project_scope="Example scope",
            scope_items=[ScopeItem(title="Concept design", tasks=["Sketch options"]),
                         ScopeItem(title="Detailed design", tasks=["Drawings"])],
        )
        at.session_state["program_num_weeks"] = 6
        at.session_state["program_week_labels"] = [f"Wk {i + 1}" for i in range(6)]
        at.session_state["program_schedule"] = {
            "Concept design": [True, True, True, False, False, False],
            "Detailed design": [False, False, True, True, True, True],
        }
        at.run()
        for exc in at.exception:
            failures.append(f"[program style] exception: {exc.value}")
        style_radios = [r for r in at.radio if r.key == "program_style"]
        if not style_radios:
            failures.append("[program style] the style picker never rendered")
        elif at.session_state["program_style"] not in program_render.STYLES:
            failures.append(
                f"[program style] default is not a real style: "
                f"{at.session_state['program_style']!r}")
        else:
            style_radios[0].set_value("timeline").run()
            for exc in at.exception:
                failures.append(f"[program style] exception after picking: {exc.value}")
            if at.session_state["program_style"] != "timeline":
                failures.append("[program style] the chosen style did not round-trip")

    # The Design Manager ✕ and the "+ Add Design Manager" that replaces it are
    # only reachable once the Team & Resourcing tab has a plan to render.
    if not failures:
        from modules import resourcing
        from modules.tender_analyser import ScopeItem, TenderAnalysis

        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["analysis"] = TenderAnalysis(
            project_scope="Example scope",
            disciplines_involved=["Structural", "Geotechnical"],
            scope_items=[ScopeItem(title="Concept design", tasks=["Sketch options"])],
        )
        at.session_state["resource_plan"] = resourcing.build_resource_plan(
            ["Structural", "Geotechnical"])
        at.run()
        for exc in at.exception:
            failures.append(f"[design manager] exception: {exc.value}")

        def _slots(app):
            return [a.slot for a in app.session_state["resource_plan"]
                    if a.slot_kind == "management"]

        remove = [b for b in at.button if b.key == "res_del_management_3"]
        if "Design Manager" not in _slots(at):
            failures.append("[design manager] the seeded plan has no Design Manager to remove")
        elif not remove:
            failures.append("[design manager] the Design Manager row has no remove control")
        else:
            remove[0].click().run()
            for exc in at.exception:
                failures.append(f"[design manager] exception after removing: {exc.value}")
            if "Design Manager" in _slots(at):
                failures.append("[design manager] ✕ didn't remove the role")
            if at.session_state["removed_management_roles"] != ["Design Manager"]:
                failures.append("[design manager] the removal wasn't recorded")
            # It must survive a plain rerun -- the reconcile pass runs again
            # every time the tab renders, and that is where it used to come back.
            at.run()
            if "Design Manager" in _slots(at):
                failures.append("[design manager] the reconcile pass resurrected the role")
            add = [b for b in at.button if b.key == "_add_mgmt_Design Manager"]
            if not add:
                failures.append("[design manager] no way to add the role back")
            else:
                add[0].click().run()
                for exc in at.exception:
                    failures.append(f"[design manager] exception after re-adding: {exc.value}")
                restored = _slots(at)
                if "Design Manager" not in restored:
                    failures.append("[design manager] the role wasn't restored")
                elif restored != resourcing.MANDATORY_ORG_ROLES:
                    failures.append(
                        f"[design manager] restored out of chain order: {restored}")
                if at.session_state["removed_management_roles"]:
                    failures.append("[design manager] the removal record wasn't cleared")

        # Project Director and Project Manager must stay non-removable.
        for index, role in ((1, "Project Director"), (2, "Project Manager")):
            if [b for b in at.button if b.key == f"res_del_management_{index}"]:
                failures.append(f"[design manager] {role} became removable")

    if failures:
        print("SMOKE TEST FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("SMOKE TEST PASSED: both pack formats render all 10 tabs with no exceptions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
