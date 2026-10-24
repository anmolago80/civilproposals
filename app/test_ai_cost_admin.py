"""
test_ai_cost_admin.py -- regression tests for CP-TASK 3 (25 Oct 2026):
AI cost accuracy, tender size in the admin tables, and upload_log.

Same house style as test_trial_abuse.py: plain `def test_X(failures)`
functions, no pytest, main() prints PASS/FAIL. Run from this directory:

    python test_ai_cost_admin.py
"""

from __future__ import annotations

import hashlib
import os
import sys
import uuid

os.environ.setdefault("SAAS_MODE", "true")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-for-ai-cost")
os.environ["DATABASE_URL"] = "sqlite:////tmp/ai_cost_admin_test.db"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-not-real"
os.environ.pop("REDIS_URL", None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("/tmp/ai_cost_admin_test.db"):
    os.remove("/tmp/ai_cost_admin_test.db")

from modules import ai_interface, auth, db, email_utils, limits, tender_analyser  # noqa: E402

db.init_db()

# The real figures from the brief: York Region, 23 Oct UTC.
YORK_IN, YORK_OUT = 206_431, 146_745
ANTHROPIC_BILL_23_OCT = 1.88


def _new_user():
    email_utils.is_configured = lambda: False          # no emails from tests
    email = f"_t_{uuid.uuid4().hex[:10]}@example.invalid"
    user = auth.create_user(email, "testpassword123", "T", "F", device_claimed=False)
    auth.accept_terms(user)
    return user


def _cleanup(user_id: str) -> None:
    try:
        with db.get_session() as s:
            for model in (db.SavedProject, db.UploadLog, db.AiCallLog, db.ArtifactEvent, db.ProposalUsage, db.Job):
                s.query(model).filter(model.user_id == user_id).delete()
            s.query(db.TrialClaim).filter(db.TrialClaim.user_id == user_id).delete()
            s.query(db.User).filter(db.User.id == user_id).delete()
            s.commit()
    except Exception:
        pass


def _brief(chars: int) -> str:
    """A brief of exactly `chars` characters made of paragraphs, so the
    paragraph-aware splitter behaves as it does on a real document."""
    para = ("The consultant shall provide services including design, review and reporting. " * 8).strip()
    out = ""
    while len(out) < chars:
        out += para + "\n\n"
    return out[:chars]


def _project_zip(**state) -> bytes:
    from modules import project_store
    return project_store.save_project(state)


def _save_row(user_id: str, name: str, blob: bytes) -> None:
    with db.get_session() as s:
        s.add(db.SavedProject(id=uuid.uuid4().hex, user_id=user_id, name=name,
                              slug=name.replace(" ", "_") + uuid.uuid4().hex[:4], project_bytes=blob))
        s.commit()


def _key_for(text: str, name: str = "York Region", tender: str = "T1", client: str = "Client") -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return f"{name}|{tender}|{client}|{h}"


# --------------------------------------------------------------------------
# Part A -- prices
# --------------------------------------------------------------------------

def test_sonnet5_price_matches_anthropic_bill(failures: list[str]) -> None:
    if ai_interface.MODEL_PRICES_PER_MTOK["claude-sonnet-5"] != (2.00, 10.00):
        failures.append(f"sonnet-5 price is {ai_interface.MODEL_PRICES_PER_MTOK['claude-sonnet-5']}, expected (2.00, 10.00)")
    cost = ai_interface.estimate_cost_usd("claude-sonnet-5", YORK_IN, YORK_OUT)
    if cost is None or round(cost, 2) != ANTHROPIC_BILL_23_OCT:
        failures.append(f"York tokens priced at {cost}, Anthropic billed {ANTHROPIC_BILL_23_OCT}")
    if abs(cost - 1.880312) > 1e-6:
        failures.append(f"York cost {cost} != 206,431 x $2 + 146,745 x $10 per M = 1.880312")


def test_other_model_prices(failures: list[str]) -> None:
    est = ai_interface.estimate_cost_usd
    checks = [
        ("claude-sonnet-5-5", 1_000_000, 1_000_000, 12.00),
        ("claude-sonnet-4-5", 1_000_000, 1_000_000, 18.00),
        ("claude-haiku-4-5", 1_000_000, 1_000_000, 6.00),
        ("claude-opus-4-6", 1_000_000, 1_000_000, 30.00),       # was (15, 75) = 90
        ("claude-opus-5-5", 1_000_000, 1_000_000, 24.00),
        ("claude-fable-5-1", 1_000_000, 1_000_000, 60.00),
        ("claude-haiku-5-5", 100_000, 1_000_000, 0.51),          # at the threshold: base rate
        ("claude-haiku-5-5", 100_001, 1_000_000, 2.5500005),   # over 100k prompt: long-prompt rate
        ("claude-sonnet-5-20261001", 1_000_000, 0, 2.00),        # dated snapshot id
        ("  Claude-Sonnet-5 ", 1_000_000, 0, 2.00),
        ("gpt-4o", 1_000_000, 1_000_000, 12.50),
    ]
    for model, i, o, want in checks:
        got = est(model, i, o)
        if got is None or abs(got - want) > 1e-4:
            failures.append(f"{model} {i}/{o}: priced {got}, expected {want}")
    if est("some-future-model", 1000, 1000) is not None:
        failures.append("an unknown model must stay unpriced (None), never guessed")
    if est("claude-sonnet-5", None, None) is not None:
        failures.append("no token counts must stay unpriced")


def test_trial_ceiling_trips_at_real_five_dollars(failures: list[str]) -> None:
    """The ceiling sums stored estimates: ~US$3.33 of REAL spend used to trip
    it (x1.5); now it takes the real US$5.00."""
    user = _new_user()
    try:
        access = {"unlimited": False, "subscribed": False, "past_due": False, "bid_credits": 0}
        # Real spend of $3.40 = York-sized Sonnet 5 usage, logged the way the app logs it.
        for _ in range(2):
            i, o = 190_000, 130_000                       # ~$1.68 each
            db.log_ai_call(user.id, "k", "n", "tender_analysis", "Anthropic Claude", "claude-sonnet-5",
                           i, o, ai_interface.estimate_cost_usd("claude-sonnet-5", i, o))
        spent = db.account_ai_cost(user.id)
        if not (3.3 < spent < 3.5):
            failures.append(f"test_ceiling: expected ~$3.36 logged, got {spent}")
        if limits.ai_spend_block_reason(user.id, access, spent) is not None:
            failures.append("test_ceiling: a trial account was blocked at ~$3.36 of real spend")
        db.log_ai_call(user.id, "k", "n", "tender_analysis", "Anthropic Claude", "claude-sonnet-5",
                       400_000, 150_000, ai_interface.estimate_cost_usd("claude-sonnet-5", 400_000, 150_000))
        if limits.ai_spend_block_reason(user.id, access, db.account_ai_cost(user.id)) is None:
            failures.append("test_ceiling: the ceiling no longer trips at all")
    finally:
        _cleanup(user.id)


def test_history_is_repriced_by_migration(failures: list[str]) -> None:
    """Stored estimates were written at the old price; the migration recomputes
    them from the stored tokens, only for the corrected models, idempotently."""
    user = _new_user()
    try:
        with db.get_session() as s:
            s.add(db.AiCallLog(user_id=user.id, model="claude-sonnet-5", input_tokens=YORK_IN,
                               output_tokens=YORK_OUT, estimated_cost_usd=2.820468))
            s.add(db.AiCallLog(user_id=user.id, model="claude-sonnet-4-5", input_tokens=1000,
                               output_tokens=1000, estimated_cost_usd=0.018))
            s.add(db.AiCallLog(user_id=user.id, model="claude-sonnet-5", input_tokens=None,
                               output_tokens=None, estimated_cost_usd=None))
            s.add(db.AiCallLog(user_id=user.id, model="mystery-model", input_tokens=5, output_tokens=5,
                               estimated_cost_usd=None))
            s.commit()
        db._run_light_migrations()
        db._run_light_migrations()                         # idempotent
        with db.get_session() as s:
            rows = {(r.model, r.input_tokens): r.estimated_cost_usd
                    for r in s.query(db.AiCallLog).filter(db.AiCallLog.user_id == user.id).all()}
        if abs(rows[("claude-sonnet-5", YORK_IN)] - 1.880312) > 1e-6:
            failures.append(f"test_reprice: York row is {rows[('claude-sonnet-5', YORK_IN)]}, expected 1.880312")
        if rows[("claude-sonnet-4-5", 1000)] != 0.018:
            failures.append("test_reprice: a correctly priced model's row was touched")
        if rows[("claude-sonnet-5", None)] is not None or rows[("mystery-model", 5)] is not None:
            failures.append("test_reprice: rows with no tokens / unknown models must stay NULL")
        if abs(db.account_ai_cost(user.id) - (1.880312 + 0.018 + 0.02 * 2)) > 1e-6:
            failures.append("test_reprice: account total wrong after repricing")
    finally:
        _cleanup(user.id)


# --------------------------------------------------------------------------
# Part B -- size columns, upload_log
# --------------------------------------------------------------------------

def test_chunk_count_uses_analysers_own_split(failures: list[str]) -> None:
    for chars in (500, 12_000, 12_001, 30_000, 125_000):
        text = _brief(chars)
        want = len(tender_analyser.split_text_into_chunks(
            tender_analyser.clean_extracted_text(text), chunk_size=12000, overlap=300))
        got = len(tender_analyser.clean_and_chunk_tender_text(text)[1])
        if got != want:
            failures.append(f"test_chunks: {chars} chars -> {got}, expected {want}")
    if len(tender_analyser.clean_and_chunk_tender_text(_brief(125_000))[1]) < 10:
        failures.append("test_chunks: a 125k-character brief should be ~10+ chunks")
    # analyse_tender must be driven by the same helper (no drifting copy).
    import inspect
    if "clean_and_chunk_tender_text" not in inspect.getsource(tender_analyser.analyse_tender):
        failures.append("test_chunks: analyse_tender() no longer uses clean_and_chunk_tender_text()")


def test_log_upload_records_size_and_dedupes(failures: list[str]) -> None:
    user = _new_user()
    try:
        key = _key_for("brief text")
        n = db.log_upload(user.id, key, [("brief.pdf", 3 * 1024 * 1024, 120), ("addendum.docx", 1024 * 1024, 4)])
        if n != 2:
            failures.append(f"test_log_upload: wrote {n} rows, expected 2")
        again = db.log_upload(user.id, key, [("brief.pdf", 3 * 1024 * 1024, 120)])
        if again != 0:
            failures.append("test_log_upload: the same file re-uploaded was recorded twice")
        if db.log_upload(user.id, key, [("brief.pdf", 3 * 1024 * 1024 + 1, 120)]) != 1:
            failures.append("test_log_upload: a different-size file of the same name must be recorded")
        with db.get_session() as s:
            rows = {(r.filename, r.size_bytes, r.page_count) for r in
                    s.query(db.UploadLog).filter(db.UploadLog.user_id == user.id).all()}
        if ("brief.pdf", 3 * 1024 * 1024, 120) not in rows or ("addendum.docx", 1024 * 1024, 4) not in rows:
            failures.append(f"test_log_upload: wrong rows stored: {rows}")
        if db.log_upload("", key, [("x.pdf", 1, 1)]) != 0 or db.log_upload(user.id, key, []) != 0:
            failures.append("test_log_upload: empty user / empty list must write nothing")
        # The table has no column that could hold file contents.
        cols = {c.name for c in db.UploadLog.__table__.columns}
        if cols != {"id", "user_id", "project_key", "filename", "size_bytes", "page_count", "uploaded_at"}:
            failures.append(f"test_log_upload: unexpected upload_log columns {sorted(cols)}")
    finally:
        _cleanup(user.id)


def test_upload_tab_logs_uploads(failures: list[str]) -> None:
    """The Upload tab calls db.log_upload with each file's name, size and
    extracted pages, for brief files AND zips (AppTest cannot drive a
    file_uploader, so this checks the wiring in the page source)."""
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "modules", "pages", "30_setup_upload_analysis.py")).read()
    for needle in ("db.log_upload(current_user.id, _current_project_key(), _upload_log_rows)",
                   "_upload_log_rows = [", "_upload_log_rows.append((_zf.name",
                   'getattr(_uf, "size", None)'):
        if needle not in src:
            failures.append(f"test_upload_tab: page no longer contains {needle!r}")
    if src.index("db.log_upload(") < src.index("st.session_state.tender_extracted = extracted"):
        failures.append("test_upload_tab: upload is logged before the brief was accepted")


def test_admin_size_columns_from_saved_project(failures: list[str]) -> None:
    from modules.document_processor import ExtractedDocument
    big, small = _brief(125_000), _brief(4_000)
    a, b, c = _new_user(), _new_user(), _new_user()
    try:
        # a: a real save_project() fixture + recorded uploads (3 MB + 1 MB), project later RENAMED.
        doc = ExtractedDocument(filename="brief.pdf", text=big, page_count=312)
        _save_row(a.id, "York Region Water Model Update",
                  _project_zip(project_name="Renamed since upload", tender_extracted=doc))
        db.log_upload(a.id, _key_for(big, name="Old name"), [("brief.pdf", 3 * 1024 * 1024, 300),
                                                              ("addendum.pdf", 1024 * 1024, 12)])
        # b: a saved project with NO upload_log rows (an older project).
        _save_row(b.id, "Older", _project_zip(project_name="Older", tender_extracted=ExtractedDocument(
            filename="o.pdf", text=small, page_count=2)))
        # c: no saved project.
        rows = {r["email"]: r for r in db.admin_stats()["recent_activity"]}
        ra, rb, rc = rows[a.email], rows[b.email], rows[c.email]
        want_chunks = len(tender_analyser.clean_and_chunk_tender_text(big)[1])
        if (ra["tender_pages"], ra["tender_chars"], ra["chunks"]) != (312, 125_000, want_chunks):
            failures.append(f"test_admin_size[a]: {(ra['tender_pages'], ra['tender_chars'], ra['chunks'])} "
                            f"!= {(312, 125_000, want_chunks)}")
        if ra["uploaded_mb"] is None or abs(ra["uploaded_mb"] - 4.0) > 1e-9:
            failures.append(f"test_admin_size[a]: uploaded MB {ra['uploaded_mb']}, expected 4.0 "
                            "(matched on the brief hash, so the rename must not matter)")
        if (rb["tender_pages"], rb["tender_chars"]) != (2, 4_000) or rb["chunks"] != 1:
            failures.append(f"test_admin_size[b]: {(rb['tender_pages'], rb['tender_chars'], rb['chunks'])}")
        if rb["uploaded_mb"] is not None:
            failures.append("test_admin_size[b]: an older upload must read 'not recorded' (None), not 0")
        if (rc["tender_pages"], rc["tender_chars"], rc["chunks"], rc["uploaded_mb"]) != (None,) * 4:
            failures.append("test_admin_size[c]: an account with no saved project should have no size data")
    finally:
        for u in (a, b, c):
            _cleanup(u.id)


def test_cost_by_project_size_columns(failures: list[str]) -> None:
    from modules.document_processor import ExtractedDocument
    text = _brief(60_000)
    old_text = _brief(20_000) + "older"
    user = _new_user()
    try:
        _save_row(user.id, "Latest", _project_zip(
            project_name="Latest", tender_extracted=ExtractedDocument(filename="l.pdf", text=text, page_count=80)))
        latest_key, other_key = _key_for(text, name="Latest"), _key_for(old_text, name="Earlier one")
        for key, name in ((latest_key, "Latest"), (other_key, "Earlier one")):
            db.log_ai_call(user.id, key, name, "tender_analysis", "Anthropic Claude", "claude-sonnet-5",
                           10_000, 2_000, ai_interface.estimate_cost_usd("claude-sonnet-5", 10_000, 2_000))
        db.log_upload(user.id, other_key, [("earlier.pdf", 2 * 1024 * 1024, 30)])
        rows = {p["project_name"]: p for p in db.ai_cost_summary()["per_project"]}
        lat, old = rows["Latest"], rows["Earlier one"]
        want = len(tender_analyser.clean_and_chunk_tender_text(text)[1])
        if (lat["tender_pages"], lat["tender_chars"], lat["chunks"]) != (80, 60_000, want):
            failures.append(f"test_cost_table[latest]: {lat}")
        if lat["uploaded_mb"] is not None:
            failures.append("test_cost_table[latest]: no uploads recorded -> must be None ('not recorded')")
        # Not the account's latest project: only ONE saved project per account is loaded,
        # so pages/chars/chunks are unknown -- but its recorded upload size still shows.
        if (old["tender_pages"], old["tender_chars"], old["chunks"]) != (None, None, None):
            failures.append(f"test_cost_table[earlier]: loaded a non-latest project: {old}")
        if old["uploaded_mb"] is None or abs(old["uploaded_mb"] - 2.0) > 1e-9:
            failures.append(f"test_cost_table[earlier]: uploaded MB {old['uploaded_mb']}, expected 2.0")
    finally:
        _cleanup(user.id)


def test_one_saved_project_loaded_per_account(failures: list[str]) -> None:
    """Many saved projects, one account: only the newest is parsed."""
    from modules import project_progress
    from modules.document_processor import ExtractedDocument
    user = _new_user()
    calls: list[int] = []
    orig = project_progress.read_payload
    try:
        for i in range(4):
            _save_row(user.id, f"P{i}", _project_zip(project_name=f"P{i}", tender_extracted=ExtractedDocument(
                filename="x.pdf", text=_brief(1000 + i), page_count=i + 1)))
            import time; time.sleep(0.01)
        project_progress.read_payload = lambda b: (calls.append(1), orig(b))[1]
        with db.get_session() as s:
            out = db._latest_project_progress(s, [user.id])
        if len(calls) != 1:
            failures.append(f"test_one_project: parsed {len(calls)} saved projects for one account, expected 1")
        if out[user.id]["project_name"] != "P3":
            failures.append("test_one_project: not the latest saved project")
    finally:
        project_progress.read_payload = orig
        _cleanup(user.id)


# --------------------------------------------------------------------------
# Tables render (real app, admin dialog)
# --------------------------------------------------------------------------

def test_admin_tables_render(failures: list[str]) -> None:
    from streamlit.testing.v1 import AppTest
    from modules.document_processor import ExtractedDocument
    text = _brief(70_000)
    admin_email = f"_adm_{uuid.uuid4().hex[:8]}@example.invalid"
    auth.ADMIN_ACCOUNTS.add(admin_email)
    email_utils.is_configured = lambda: False
    admin = auth.create_user(admin_email, "testpassword123", device_claimed=False)
    auth.accept_terms(admin)
    other = _new_user()
    try:
        _save_row(other.id, "York Region Water Model Update", _project_zip(
            project_name="York Region Water Model Update",
            tender_extracted=ExtractedDocument(filename="b.pdf", text=text, page_count=140)))
        db.log_upload(other.id, _key_for(text), [("b.pdf", 5 * 1024 * 1024, 140)])
        db.log_ai_call(other.id, _key_for(text), "York Region Water Model Update", "tender_analysis",
                       "Anthropic Claude", "claude-sonnet-5", 20_000, 4_000, 0.08)
        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["_auth_user_id"] = admin.id
        at.session_state["_state_owner_id"] = admin.id
        at.run()
        [b for b in at.sidebar.button if "Admin" in (b.label or "")][0].click().run()
        if at.exception:
            failures.append(f"test_tables_render: exception {[e.value for e in at.exception]}")
            return
        frames = [df.value for df in at.dataframe]
        want_cols = {"Tender pages", "Tender text (chars)", "Chunks", "Uploaded (MB)"}
        with_cols = [f for f in frames if want_cols <= set(f.columns)]
        if len(with_cols) < 2:
            failures.append(f"test_tables_render: expected the size columns in BOTH Recent activity and "
                            f"Cost by project, found them in {len(with_cols)} table(s)")
            return
        activity = [f for f in with_cols if "Furthest step" in f.columns][0]
        cost = [f for f in with_cols if "Est. cost (USD)" in f.columns][0]
        row = activity[activity["Email"] == other.email].iloc[0]
        n_chunks = str(len(tender_analyser.clean_and_chunk_tender_text(text)[1]))
        if (row["Tender pages"], row["Tender text (chars)"], row["Chunks"], row["Uploaded (MB)"]) != \
                ("140", "70,000", n_chunks, "5.00"):
            failures.append(f"test_tables_render: activity row shows "
                            f"{(row['Tender pages'], row['Tender text (chars)'], row['Chunks'], row['Uploaded (MB)'])}")
        crow = cost[cost["Project"] == "York Region Water Model Update"].iloc[0]
        if (crow["Tender pages"], crow["Tender text (chars)"], crow["Uploaded (MB)"]) != ("140", "70,000", "5.00"):
            failures.append("test_tables_render: cost-by-project row wrong")
        # A project with no recorded upload says so in words.
        legacy = [r for r in activity["Uploaded (MB)"] if r == "not recorded"]
        if not legacy:
            failures.append("test_tables_render: nothing reads 'not recorded'")
    finally:
        auth.ADMIN_ACCOUNTS.discard(admin_email)
        _cleanup(admin.id); _cleanup(other.id)


def test_i18n_catalogs_have_new_keys(failures: list[str]) -> None:
    from modules.translations import en, es
    keys = ["chrome_admin_col_tender_pages", "chrome_admin_col_tender_chars", "chrome_admin_col_chunks",
            "chrome_admin_col_uploaded_mb", "chrome_admin_not_recorded", "chrome_admin_size_caption"]
    for k in keys:
        if k not in en.STRINGS or k not in es.STRINGS:
            failures.append(f"test_i18n: {k} missing from EN or ES")
    if set(en.STRINGS) != set(es.STRINGS):
        failures.append(f"test_i18n: catalogs differ: {sorted(set(en.STRINGS) ^ set(es.STRINGS))[:5]}")


def main() -> int:
    failures: list[str] = []
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        before = len(failures)
        try:
            fn(failures)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            failures.append(f"{fn.__name__}: CRASHED: {type(exc).__name__}: {exc}")
        print(("PASS " if len(failures) == before else "FAIL ") + fn.__name__)
    if failures:
        print("\nAI COST / ADMIN TESTS FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nAI COST / ADMIN TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
