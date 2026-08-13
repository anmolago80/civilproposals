"""
app.py

Tender Response Pack Generator -- Streamlit app entry point.

The app used to be one 315KB script in this file. It's now split along its
natural seams into modules/pages/ (state/init, shared helpers, sidebar &
account chrome, then one file per workflow area), executed IN ORDER, IN ONE
SHARED SCRIPT NAMESPACE -- exactly the semantics the single file had, so
user-visible behaviour is unchanged:

    00_init.py                  config, env, SaaS mode, checkout redirect, login gate
    10_state_helpers.py         session-state defaults + every shared helper
    20_chrome.py                sidebar, plan status, account/billing UI, CSS, tab creation
    30_setup_upload_analysis.py tabs 1-3: Project Setup, Upload Docs, Tender Analysis
    40_structure_allocation.py  tabs 4-5: Proposal Structure, Page Allocation
    50_drafting.py              tab 6: Draft Responses
    55_graphics.py              tab 7: Graphics & Design
    60_team.py                  tab 8: Team & Resourcing
    70_commercial_small.py      tab 9: Fees & Program (Small Scope packs)
    71_commercial_large.py      tab 9: Fee Estimate (Large Scope packs)
    80_export.py                tab 10: Export Pack + end-of-run autosave

Why exec-composition rather than a function-per-page refactor: Streamlit
re-runs the whole script top to bottom on every interaction, and this app's
pages share dozens of module-level helpers and values (current_user,
_access, the tabs list, _run_job_or_inline, ...). Converting each page to a
function would change name scoping and evaluation order -- exactly the kind
of change that produces subtle mid-tender regressions -- so the split keeps
the original single-namespace semantics byte-for-byte and leaves a
function-per-page refactor to be done tab-by-tab, with live click-through
testing, later. Segment code objects are cached per (path, mtime) in
modules/pages/_loader.py, so reruns don't pay a recompile cost.

The page files are NOT importable modules -- they're ordered script
segments. Don't import them; edit them in place (each file says at the top
how it runs) and keep _manifest.txt in loading order.
"""

from pathlib import Path

from modules.pages._loader import load_page_code

_PAGES_DIR = Path(__file__).resolve().parent / "modules" / "pages"
_MANIFEST = _PAGES_DIR / "_manifest.txt"

for _page_name in _MANIFEST.read_text(encoding="utf-8").split():
    exec(load_page_code(_PAGES_DIR / _page_name), globals())
