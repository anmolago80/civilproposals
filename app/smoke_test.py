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
        # The target-fee prefill sits above the discipline build-up on the same
        # tab. Give one row a rate so the hours-derivation path runs for real
        # rather than short-circuiting on "no rate anywhere".
        for _line in at.session_state["discipline_fee_lines"]:
            _line.rate_per_hour = 200.0
        at.run()
        target = [n for n in at.number_input if n.key == "letter_target_fee"]
        apply_button = [b for b in at.button if b.key == "letter_target_apply"]
        if not target or not apply_button:
            failures.append("[fee prefill] the target-fee control never rendered")
        else:
            target[0].set_value(400000.0).run()
            [b for b in at.button if b.key == "letter_target_apply"][0].click().run()
            for exc in at.exception:
                failures.append(f"[fee prefill] exception: {exc.value}")
            priced = [l for l in at.session_state["discipline_fee_lines"] if l.fee_amount > 0]
            if not priced:
                failures.append("[fee prefill] pre-filling from a target fee priced nothing")
            elif abs(sum(l.fee_amount for l in priced) - 400000.0) > 400000.0 * 0.05:
                failures.append(
                    "[fee prefill] the pre-filled rows don't add up to the target: "
                    f"{sum(l.fee_amount for l in priced):,.0f}")
            # Rows the user has priced must survive a second pre-fill -- and
            # the target has to CHANGE between the two runs for that to prove
            # anything. Re-running with the same target produces identical
            # numbers whether the guard works or not, which is exactly how a
            # first version of this check passed against a deliberately
            # broken guard.
            before = [(l.discipline, l.total_hours) for l in at.session_state["discipline_fee_lines"]]
            [n for n in at.number_input if n.key == "letter_target_fee"][0].set_value(900000.0).run()
            [b for b in at.button if b.key == "letter_target_apply"][0].click().run()
            after = [(l.discipline, l.total_hours) for l in at.session_state["discipline_fee_lines"]]
            if before != after:
                failures.append(
                    "[fee prefill] a second pre-fill at a different target clobbered rows the "
                    "user had priced")

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

        # The org chart style picker and its live preview live on the same
        # tab, and are only reachable once there is a plan to draw.
        from modules import org_chart_render

        style_radios = [r for r in at.radio if r.key == "org_chart_style"]
        if not style_radios:
            failures.append("[org chart] the style picker never rendered")
        elif at.session_state["org_chart_style"] not in org_chart_render.STYLES:
            failures.append(
                f"[org chart] default is not a real style: "
                f"{at.session_state['org_chart_style']!r}")
        else:
            style_radios[0].set_value("bands").run()
            for exc in at.exception:
                failures.append(f"[org chart] exception after picking: {exc.value}")
            if at.session_state["org_chart_style"] != "bands":
                failures.append("[org chart] the chosen style did not round-trip")
            use = [b for b in at.button if "exported pack" in (b.label or "")]
            if not use:
                failures.append("[org chart] no way to put the chart into the pack")
            else:
                use[0].click().run()
                for exc in at.exception:
                    failures.append(f"[org chart] exception after saving: {exc.value}")
                if not at.session_state["org_chart_png"]:
                    failures.append("[org chart] the chart wasn't saved into the pack")
                if at.session_state["org_chart_png_style"] != "bands":
                    failures.append("[org chart] the pack didn't record which style it holds")

        # Project Director and Project Manager must stay non-removable.
        for index, role in ((1, "Project Director"), (2, "Project Manager")):
            if [b for b in at.button if b.key == f"res_del_management_{index}"]:
                failures.append(f"[design manager] {role} became removable")

        # Fix brief Part B: each discipline lead has an optional peer-reviewer
        # field, and it round-trips onto the plan (which the org chart's
        # unconditional Peer Review element then reads).
        peer_inputs = [t for t in at.text_input if (t.key or "").startswith("res_peerrev_discipline_")]
        if not peer_inputs:
            failures.append("[peer reviewer] no peer-reviewer field rendered for any discipline lead")
        else:
            peer_inputs[0].set_value("Jordan Reviewer").run()
            for exc in at.exception:
                failures.append(f"[peer reviewer] exception after setting a reviewer: {exc.value}")
            leads = [a for a in at.session_state["resource_plan"]
                     if a.slot_kind == "discipline" and a.is_lead]
            if not any(a.peer_reviewer == "Jordan Reviewer" for a in leads):
                failures.append("[peer reviewer] the typed reviewer name did not round-trip onto the plan")

        # Fix brief Part A: every org-chart card is exactly name + role, no
        # qualifications text -- checked directly against the shared render
        # model (the same model that feeds the PNG preview, the PPTX export,
        # and the DOCX-embedded PNG) across 3/5/8 disciplines, and the quals
        # data itself must still be collected (just not drawn).
        from modules import org_chart_render as _ocr

        for n_disc in (3, 5, 8):
            names = [f"Discipline Number {k}" for k in range(1, n_disc + 1)]
            plan = resourcing.build_resource_plan(names)
            for idx, a in enumerate(plan):
                if a.slot_kind == "discipline" and a.is_lead:
                    a.person_name = f"Lead Person {idx}"
                    a.qualification = "BEng (Civil), MIEAust CPEng RPEQ 12345"
                    a.peer_reviewer = "Reviewer Person" if idx % 2 == 0 else ""
            model = _ocr.build_model(plan)
            for group in model.disciplines:
                for person in [group.lead] + list(group.supports):
                    if person is None:
                        continue
                    lines = _ocr._person_lines(person)
                    if len(lines) > 2:
                        failures.append(
                            f"[org chart n={n_disc}] {person.name!r} rendered {len(lines)} "
                            "lines, expected at most 2 (name + role)")
                    if any("RPEQ" in text or "MIEAust" in text or "BEng" in text
                           for text, *_ in lines):
                        failures.append(
                            f"[org chart n={n_disc}] qualifications text leaked onto the "
                            f"card for {person.name!r}")
                if group.lead is not None and not group.lead.quals:
                    failures.append(
                        f"[org chart n={n_disc}] {group.lead.name!r} lost its quals data "
                        "-- Part A must stop rendering it, not stop collecting it")

    # Fix brief Part D: the methodology style picker and its live preview
    # live on the Draft Responses tab, next to the Design stages grid, and
    # are only reachable once that grid holds at least one stage.
    if not failures:
        from modules import methodology_render
        from modules.methodology_stages import MethodologyStage
        from modules.tender_analyser import ScopeItem, TenderAnalysis

        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["analysis"] = TenderAnalysis(
            project_scope="Example scope",
            scope_items=[ScopeItem(title="Concept design", tasks=["Sketch options"])],
        )
        at.session_state["methodology_stages"] = [
            MethodologyStage(
                name="Concept design", week_start=1, week_end=3,
                key_tasks=["Sketch options", "Cost plan"],
                engagement_activities=["TBC"], outcome="TBC", deliverables=["TBC"],
            ),
        ]
        at.run()
        for exc in at.exception:
            failures.append(f"[methodology style] exception: {exc.value}")

        style_radios = [r for r in at.radio if r.key == "methodology_style"]
        if not style_radios:
            failures.append("[methodology style] the style picker never rendered")
        elif at.session_state["methodology_style"] not in methodology_render.STYLES:
            failures.append(
                f"[methodology style] default is not a real style: "
                f"{at.session_state['methodology_style']!r}")
        else:
            if not at.image:
                failures.append("[methodology style] no live preview image rendered")
            style_radios[0].set_value("spine").run()
            for exc in at.exception:
                failures.append(f"[methodology style] exception after picking: {exc.value}")
            if at.session_state["methodology_style"] != "spine":
                failures.append("[methodology style] the chosen style did not round-trip")
            if not at.image:
                failures.append("[methodology style] the preview disappeared after picking a style")

        # Every style must render a PPTX for a real 6-stage/8-task grid with
        # no exception -- the actual export the picker drives.
        from modules import methodology_pptx

        fat_stages = [
            MethodologyStage(
                name=f"Stage {i + 1}", week_start=i * 3 + 1, week_end=i * 3 + 3,
                key_tasks=[f"Task {j + 1} for stage {i + 1} covering a fairly long scope description"
                          for j in range(8)],
                engagement_activities=["Client workshop", "Hold point sign-off review"] if i == 1 else ["TBC"],
                outcome="Outcome achieved." if i % 2 == 0 else "TBC",
                deliverables=[f"Deliverable {j + 1}" for j in range(6)],
            )
            for i in range(6)
        ]
        for style in methodology_render.STYLES:
            try:
                blob = methodology_pptx.populate_methodology(
                    at.session_state["analysis"], client_name="Client", project_name="Project",
                    stages=fat_stages, week_labels=[f"Wk {i + 1}" for i in range(20)], style=style)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"[methodology style] {style} raised at 6 stages/8 tasks: {exc}")
                continue
            if not blob:
                failures.append(f"[methodology style] {style} produced no PPTX bytes")

    # Trial upload limits + AI spend backstop (limits.py / db.py) -- unit-
    # style checks against the modules directly rather than through AppTest.
    # IS_SAAS_MODE is read once at import time by 00_init.py, so flipping
    # SAAS_MODE mid-process for a single AppTest pass isn't practical here;
    # these exercise the actual decision logic (limits.py's tier math, the
    # rate limiter's in-memory fallback -- REDIS_URL is popped above, so
    # this genuinely runs the fallback path, not just the Redis path) and
    # db.py's cost aggregation directly, which is where the real behaviour
    # lives regardless of which UI thread calls into it.
    if not failures:
        from modules import limits

        TRIAL_ACCESS = {"unlimited": False, "subscribed": False, "past_due": False, "bid_credits": 0}
        PAID_ACCESS = {"unlimited": False, "subscribed": True, "past_due": False, "bid_credits": 0}
        UNLIMITED_ACCESS = {"unlimited": True, "subscribed": False, "past_due": False, "bid_credits": 0}

        if limits.is_paid_tier(TRIAL_ACCESS):
            failures.append("[limits] a plain trial access dict was classified as paid")
        if not limits.is_paid_tier(PAID_ACCESS) or not limits.is_paid_tier(UNLIMITED_ACCESS):
            failures.append("[limits] subscribed/unlimited access wasn't classified as paid")

        for key, (trial_n, paid_n) in limits.UPLOAD_LIMITS.items():
            if trial_n > paid_n:
                failures.append(f"[limits] {key}: trial limit ({trial_n}) exceeds paid limit ({paid_n})")
        _trial_map = limits.limits_for(None, TRIAL_ACCESS)
        _paid_map = limits.limits_for(None, PAID_ACCESS)
        if _trial_map["cv_library"] != 5 or _paid_map["cv_library"] != 25:
            failures.append(f"[limits] cv_library limits wrong: trial={_trial_map['cv_library']}, paid={_paid_map['cv_library']}")

        class _FakeFile:
            def __init__(self, name):
                self.name = name

        six_cvs = [_FakeFile(f"cv_{i}.pdf") for i in range(6)]
        kept, msg = limits.enforce_count_limit(six_cvs, "cv_library", TRIAL_ACCESS)
        if len(kept) != 5 or not msg:
            failures.append(f"[limits] 6th CV wasn't refused for a trial account: kept={len(kept)}, msg={msg!r}")
        kept_paid, msg_paid = limits.enforce_count_limit(six_cvs, "cv_library", PAID_ACCESS)
        if len(kept_paid) != 6 or msg_paid:
            failures.append("[limits] a paid account's 6 CVs were incorrectly limited")
        kept_unlimited, msg_unlimited = limits.enforce_count_limit(six_cvs, "cv_library", UNLIMITED_ACCESS)
        if len(kept_unlimited) != 6 or msg_unlimited:
            failures.append("[limits] an unlimited account's 6 CVs were incorrectly limited")

        if limits.tender_page_cap_message(100, TRIAL_ACCESS) is not None:
            failures.append("[limits] 100 pages (exactly the trial cap) was incorrectly blocked")
        if limits.tender_page_cap_message(101, TRIAL_ACCESS) is None:
            failures.append("[limits] 101st page didn't block analysis for a trial account")
        # Audit Round 2, Part 8: the paid tier previously had NO ceiling at
        # all here despite the module-level comment claiming one existed --
        # a paid account now soft-warns at 200 pages and hard-blocks at 300
        # (see tender_page_cap_message()/tender_page_soft_warn_message()'s
        # own docstrings). UNLIMITED_ACCOUNTS bypass both, at any page count.
        if limits.tender_page_cap_message(150, PAID_ACCESS) is not None:
            failures.append("[limits] a paid account under the 200-page soft-warn threshold was incorrectly hard-blocked")
        if limits.tender_page_soft_warn_message(150, PAID_ACCESS) is not None:
            failures.append("[limits] a paid account under the 200-page soft-warn threshold was incorrectly soft-warned")
        if limits.tender_page_cap_message(250, PAID_ACCESS) is not None:
            failures.append("[limits] a paid account between 200 and 300 pages was incorrectly hard-blocked")
        if limits.tender_page_soft_warn_message(250, PAID_ACCESS) is None:
            failures.append("[limits] a paid account between 200 and 300 pages wasn't soft-warned")
        if limits.tender_page_cap_message(301, PAID_ACCESS) is None:
            failures.append("[limits] a paid account over the 300-page ceiling wasn't hard-blocked")
        if limits.tender_page_soft_warn_message(301, PAID_ACCESS) is not None:
            failures.append("[limits] a paid account already past the 300-page hard stop was also (redundantly) soft-warned")
        if limits.tender_page_cap_message(500, UNLIMITED_ACCESS) is not None:
            failures.append("[limits] an unlimited account's page count was incorrectly hard-blocked")
        if limits.tender_page_soft_warn_message(500, UNLIMITED_ACCESS) is not None:
            failures.append("[limits] an unlimited account's page count was incorrectly soft-warned")

        # AI-spend ceiling, backed by a real (SQLite fallback) AiCallLog row.
        from modules import db
        _test_user_id = "smoke-test-ai-spend-user"
        with db.get_session() as _s:
            _s.query(db.AiCallLog).filter(db.AiCallLog.user_id == _test_user_id).delete()
            _s.add(db.AiCallLog(
                id=db._uid(), user_id=_test_user_id, project_key="smoke-test-project",
                project_name="Smoke Test Project", purpose="test", provider="anthropic",
                model="test-model", input_tokens=1000, output_tokens=1000,
                estimated_cost_usd=6.00,
            ))
            _s.commit()
        _cost = db.account_ai_cost(_test_user_id)
        if _cost < 6.00:
            failures.append(f"[db] account_ai_cost didn't pick up the inserted row: {_cost}")
        if limits.ai_spend_block_reason(_test_user_id, TRIAL_ACCESS, _cost) is None:
            failures.append("[limits] a trial account $6 over the $5 ceiling wasn't blocked")
        if limits.ai_spend_block_reason(_test_user_id, PAID_ACCESS, _cost) is not None:
            failures.append("[limits] a paid account was blocked by the trial-only spend ceiling")
        if limits.ai_spend_block_reason(None, TRIAL_ACCESS, _cost) is not None:
            failures.append("[limits] a logged-out/no-user_id call was incorrectly blocked")
        with db.get_session() as _s:
            _s.query(db.AiCallLog).filter(db.AiCallLog.user_id == _test_user_id).delete()
            _s.commit()

        # Fair-use rate limit -- exercises the in-memory fallback directly
        # (REDIS_URL is popped for this whole test run).
        _rate_user = "smoke-test-rate-user"
        _blocked_at = None
        for i in range(limits.TRIAL_AI_CALLS_PER_5MIN + 3):
            _msg = limits.record_ai_call(_rate_user, is_trial=True)
            if _msg and _blocked_at is None:
                _blocked_at = i + 1
        if _blocked_at != limits.TRIAL_AI_CALLS_PER_5MIN + 1:
            failures.append(
                f"[limits] trial rate limit tripped at call {_blocked_at}, expected "
                f"{limits.TRIAL_AI_CALLS_PER_5MIN + 1}"
            )
        if limits.record_ai_call(None, is_trial=True) is not None:
            failures.append("[limits] a None user_id was incorrectly rate-limited")

    if failures:
        print("SMOKE TEST FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("SMOKE TEST PASSED: both pack formats render all 10 tabs with no exceptions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
