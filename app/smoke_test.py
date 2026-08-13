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

    if failures:
        print("SMOKE TEST FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("SMOKE TEST PASSED: both pack formats render all 10 tabs with no exceptions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
