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


# --------------------------------------------------------------------------
# CP-TASK 3b -- per-call evidence, purposes, cost breakdown
# --------------------------------------------------------------------------

class _FakeAnthropic:
    """Stands in for the `anthropic` package: records each request and returns
    whatever the test queued, with the usage shape the real SDK returns."""
    calls: list[dict] = []
    replies: list[tuple] = []     # (text, output_tokens, thinking_tokens, stop_reason)

    class _Block:
        def __init__(self, text):
            self.type, self.text = "text", text

    class _Details:
        def __init__(self, thinking):
            self.thinking_tokens = thinking

    class _Usage:
        def __init__(self, inp, out, thinking):
            self.input_tokens, self.output_tokens = inp, out
            self.output_tokens_details = _FakeAnthropic._Details(thinking) if thinking is not None else None

    class _Response:
        def __init__(self, text, inp, out, thinking, stop):
            self.content = [_FakeAnthropic._Block(text)]
            self.usage = _FakeAnthropic._Usage(inp, out, thinking)
            self.stop_reason = stop

    class _Messages:
        def create(self, model, max_tokens, system, messages, **kw):
            _FakeAnthropic.calls.append({"model": model, "max_tokens": max_tokens, "prompt": messages[0]["content"],
                                         "thinking": kw.get("thinking", "ABSENT")})
            if _FakeAnthropic.replies:
                nxt = _FakeAnthropic.replies.pop(0)
                if isinstance(nxt, Exception):
                    raise nxt
                text, out, thinking, stop = nxt
            else:
                text, out, thinking, stop = ("ok", 50, None, "end_turn")
            return _FakeAnthropic._Response(text, 1000, out, thinking, stop)

    def __init__(self, api_key=None):
        self.messages = _FakeAnthropic._Messages()


def _with_fake_anthropic(fn):
    import types
    saved = sys.modules.get("anthropic")
    mod = types.ModuleType("anthropic"); mod.Anthropic = _FakeAnthropic
    sys.modules["anthropic"] = mod
    _FakeAnthropic.calls, _FakeAnthropic.replies = [], []
    try:
        return fn()
    finally:
        if saved is not None:
            sys.modules["anthropic"] = saved
        else:
            del sys.modules["anthropic"]
        ai_interface.set_usage_context()


_CFG = {"provider": "Anthropic Claude", "api_key": "k", "model": "claude-sonnet-5"}


def _rows_for(user_id: str):
    with db.get_session() as s:
        return s.query(db.AiCallLog).filter(db.AiCallLog.user_id == user_id).order_by(
            db.AiCallLog.created_at, db.AiCallLog.id).all()


def test_requested_max_tokens_and_evidence_stored_per_attempt(failures: list[str]) -> None:
    user = _new_user()
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="k|t|c|h", project_name="P", purpose="tender_analysis")
            # 1) a plain call: its own cap, thinking tokens and stop reason are stored.
            _FakeAnthropic.replies = [("notes", 1190, 900, "end_turn")]
            ai_interface.call_ai("p", "sys", _CFG, max_tokens=1200, purpose="tender_analysis", step="map")
            # 2) an EMPTY reply -> _call_with_resilience re-asks with double the cap: a NEW row.
            _FakeAnthropic.replies = [("", 1200, 1200, "max_tokens"), ("notes", 800, 100, "end_turn")]
            ai_interface.call_ai("p", "sys", _CFG, max_tokens=1200, purpose="tender_analysis", step="map")
            # 3) call_ai_json starts at the 16,000 ceiling; a genuine parse failure gets ONE
            #    corrective retry (same cap) -- a NEW row.
            _FakeAnthropic.replies = [("not json at all", 700, 0, "end_turn"), ('{"a": 1}', 900, 0, "end_turn")]
            out = ai_interface.call_ai_json("p", "sys", _CFG, max_tokens=4000, purpose="tender_analysis", step="reduce")
            return out
        out = _with_fake_anthropic(run)
        rows = _rows_for(user.id)
        got = [(r.step, r.attempt, r.max_tokens, r.output_tokens, r.thinking_tokens, r.stop_reason) for r in rows]
        want = [
            ("map", None, 1200, 1190, 900, "end_turn"),
            ("map", None, 1200, 1200, 1200, "max_tokens"),
            ("map", "empty_retry", 2400, 800, 100, "end_turn"),
            ("reduce", None, 16000, 700, 0, "end_turn"),
            ("reduce", "json_retry", 16000, 900, 0, "end_turn"),
        ]
        if got != want:
            failures.append(f"test_max_tokens: rows {got} != {want}")
        if out != {"a": 1}:
            failures.append("test_max_tokens: json result lost")
        if [c["max_tokens"] for c in _FakeAnthropic.calls] != [1200, 1200, 2400, 16000, 16000]:
            failures.append("test_max_tokens: the logged cap is not what was actually requested")
    finally:
        _cleanup(user.id)


def test_output_over_requested_cap_is_flagged(failures: list[str]) -> None:
    """max_tokens is a hard cap, so output above it is an anomaly worth shouting about:
    a stderr warning at log time and a YES in the breakdown."""
    import io, contextlib
    user = _new_user()
    key = "over|t|c|h"
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key=key, project_name="Over")
            _FakeAnthropic.replies = [("notes", 5000, None, "end_turn")]
            ai_interface.call_ai("p", "sys", _CFG, max_tokens=1200, purpose="tender_analysis", step="map")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            _with_fake_anthropic(run)
        if "output_tokens 5000 > requested max_tokens 1200" not in buf.getvalue():
            failures.append("test_over_cap: no warning logged")
        bd = db.project_cost_breakdown(key, user.id)
        if not bd["calls"] or not bd["calls"][0]["over_cap"]:
            failures.append("test_over_cap: breakdown did not flag the call")
    finally:
        _cleanup(user.id)


def test_every_ai_call_site_sets_a_purpose(failures: list[str]) -> None:
    import ast
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
    sites = 0
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".py") or fn == "ai_interface.py":
                continue
            path = os.path.join(dirpath, fn)
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
                    if name in ("call_ai", "call_ai_json"):
                        sites += 1
                        if "purpose" not in {k.arg for k in node.keywords}:
                            failures.append(f"test_purposes: {os.path.relpath(path, root)}:{node.lineno} {name}() has no purpose=")
    if sites < 15:
        failures.append(f"test_purposes: only {sites} call sites found -- the scan is broken")
    # An unlabelled call is still never blank: it takes its calling module's name.
    user = _new_user()
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="u|t|c|h", project_name="U")
            ai_interface.call_ai("p", "sys", _CFG, max_tokens=100)
        _with_fake_anthropic(run)
        purposes = [r.purpose for r in _rows_for(user.id)]
        if not purposes or not all(purposes):
            failures.append(f"test_purposes: an unlabelled call logged a blank purpose: {purposes}")
    finally:
        _cleanup(user.id)


def test_inline_features_log_their_purpose(failures: list[str]) -> None:
    """Real feature functions, run against the stub: discipline re-scan and the
    tender analysis steps land with the right purpose/step -- including when the
    surrounding job context carries no purpose at all (the inline path)."""
    user = _new_user()
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="in|t|c|h", project_name="In")  # no purpose
            _FakeAnthropic.replies = [('{"disciplines": ["Structural"]}', 40, None, "end_turn")]
            tender_analyser.detect_disciplines_from_text("A bridge over a creek. " * 20, config=_CFG)
            text = _brief(40_000)
            n_chunks = len(tender_analyser.clean_and_chunk_tender_text(text)[1])
            _FakeAnthropic.replies = [("note (p.1)", 300, None, "end_turn")] * n_chunks + [
                ('{"project_scope": "x"}', 500, None, "end_turn")]
            tender_analyser.analyse_tender(text, None, _CFG)
            return n_chunks
        n_chunks = _with_fake_anthropic(run)
        rows = _rows_for(user.id)
        got = [(r.purpose, r.step or "") for r in rows]
        want = [("discipline_detection", "")] + [("tender_analysis", "map")] * n_chunks + [("tender_analysis", "reduce")]
        if got != want:
            failures.append(f"test_inline_purposes: {got[:4]}... != {want[:4]}...")
        if any(not r.purpose for r in rows):
            failures.append("test_inline_purposes: a blank purpose was logged")
        reduce_row = rows[-1]
        if reduce_row.max_tokens != 16000:
            failures.append(f"test_inline_purposes: reduce requested {reduce_row.max_tokens}, expected 16000")
        if {r.max_tokens for r in rows if r.step == "map"} != {tender_analyser.MAP_MAX_TOKENS}:
            failures.append("test_inline_purposes: map calls are not requested at MAP_MAX_TOKENS")
    finally:
        _cleanup(user.id)


def test_breakdown_from_fixture_rows(failures: list[str]) -> None:
    from datetime import datetime, timedelta, timezone
    user = _new_user()
    key = "York Region Water Model Update|T|C|abcdef0123456789"
    t0 = datetime(2026, 10, 23, 14, 53, tzinfo=timezone.utc)
    try:
        with db.get_session() as s:
            for run in range(2):
                base = t0 + timedelta(minutes=6 * run)
                s.add(db.Job(id=f"bd{run}-{user.id}", user_id=user.id, job_type="tender_analysis", status="finished",
                             project_key=key.lower(), created_at=base))
                for i in range(14):    # legacy rows: no step / attempt / max_tokens
                    s.add(db.AiCallLog(user_id=user.id, project_key=key, project_name="York", purpose="tender_analysis",
                                       model="claude-sonnet-5", input_tokens=4000, output_tokens=1000,
                                       estimated_cost_usd=0.0165, created_at=base + timedelta(seconds=20 * i)))
                s.add(db.AiCallLog(user_id=user.id, project_key=key, project_name="York", purpose="tender_analysis",
                                   model="claude-sonnet-5", input_tokens=46_000, output_tokens=4_000,
                                   estimated_cost_usd=0.2, created_at=base + timedelta(seconds=320)))
            # a labelled, post-analysis call
            s.add(db.AiCallLog(user_id=user.id, project_key=key, project_name="York", purpose="team_bios", step="",
                               model="claude-sonnet-5", input_tokens=5000, output_tokens=2000, max_tokens=3000,
                               stop_reason="end_turn", created_at=t0 + timedelta(minutes=30)))
            s.commit()
        bd = db.project_cost_breakdown(key, user.id)
        if bd["totals"]["calls"] != 31:
            failures.append(f"test_breakdown: {bd['totals']['calls']} calls, expected 31")
        want_in = 2 * (14 * 4000 + 46_000) + 5000
        want_out = 2 * (14 * 1000 + 4000) + 2000
        if (bd["totals"]["input_tokens"], bd["totals"]["output_tokens"]) != (want_in, want_out):
            failures.append(f"test_breakdown: totals {bd['totals']}")
        want_cost = want_in * 2 / 1e6 + want_out * 10 / 1e6     # recomputed at (2, 10), not the stored $0.0165s
        if abs(bd["totals"]["cost_usd"] - want_cost) > 1e-6:
            failures.append(f"test_breakdown: cost {bd['totals']['cost_usd']} != {want_cost}")
        purposes = {p["purpose"]: p for p in bd["by_purpose"]}
        if purposes["tender_analysis"]["calls"] != 30 or purposes["team_bios"]["calls"] != 1:
            failures.append(f"test_breakdown: by purpose {purposes}")
        if len(bd["runs"]) != 2:
            failures.append(f"test_breakdown: {len(bd['runs'])} runs, expected 2 (one per queued job)")
        else:
            kinds = {k["kind"]: k for k in bd["runs"][0]["kinds"]}
            if kinds.get("map (inferred)", {}).get("calls") != 14 or kinds.get("reduce (inferred)", {}).get("calls") != 1:
                failures.append(f"test_breakdown: legacy map/reduce inference wrong: {kinds}")
            run_cost = 14 * (4000 * 2 + 1000 * 10) / 1e6 + (46_000 * 2 + 4000 * 10) / 1e6
            if abs(bd["runs"][0]["cost_usd"] - run_cost) > 1e-6:
                failures.append(f"test_breakdown: run cost {bd['runs'][0]['cost_usd']} != {run_cost}")
        if not any(c["purpose"] == "team_bios" and c["run"] is None for c in bd["calls"]):
            failures.append("test_breakdown: a post-analysis call must sit outside every run")
        if [c["time"] for c in bd["calls"]] != sorted(c["time"] for c in bd["calls"]):
            failures.append("test_breakdown: calls not in time order")
    finally:
        _cleanup(user.id)


def test_breakdown_expander_renders(failures: list[str]) -> None:
    from streamlit.testing.v1 import AppTest
    admin_email = f"_adm_{uuid.uuid4().hex[:8]}@example.invalid"
    auth.ADMIN_ACCOUNTS.add(admin_email)
    email_utils.is_configured = lambda: False
    admin = auth.create_user(admin_email, "testpassword123", device_claimed=False)
    auth.accept_terms(admin)
    other = _new_user()
    key = "Culvert Job|T|C|0123456789abcdef"
    try:
        with db.get_session() as s:
            s.add(db.AiCallLog(user_id=other.id, project_key=key, project_name="Culvert Job", purpose="tender_analysis",
                               step="map", model="claude-sonnet-5", input_tokens=4000, output_tokens=1100,
                               max_tokens=1200, thinking_tokens=800, stop_reason="end_turn", estimated_cost_usd=0.02))
            s.add(db.AiCallLog(user_id=other.id, project_key=key, project_name="Culvert Job", purpose="tender_analysis",
                               step="reduce", attempt="json_retry", model="claude-sonnet-5", input_tokens=15000,
                               output_tokens=9000, max_tokens=8000, estimated_cost_usd=0.1))
            s.add(db.AiCallLog(user_id=other.id, project_key=key, project_name="Culvert Job", purpose="team_bios",
                               model="claude-sonnet-5", input_tokens=3000, output_tokens=900, max_tokens=3000))
            s.commit()
        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["_auth_user_id"] = admin.id
        at.session_state["_state_owner_id"] = admin.id
        at.run()
        [b for b in at.sidebar.button if "Admin" in (b.label or "")][0].click().run()
        if at.exception:
            failures.append(f"test_expander: exception {[e.value for e in at.exception]}")
            return
        boxes = [sb for sb in at.selectbox if sb.key == "_admin_breakdown_pick"]
        if not boxes:
            failures.append("test_expander: project picker not found under Cost by project")
            return
        # Nothing is computed until a project is chosen.
        if any("max_tokens requested" in set(df.value.columns) for df in at.dataframe):
            failures.append("test_expander: breakdown tables shown before a project was picked")
        choice = [o for o in boxes[0].options if o.startswith("Culvert Job")][0]
        # AppTest re-runs the whole script (closing the dialog) on any widget change, so the
        # pick is pre-seeded and the dialog re-opened -- the same render path a real pick takes.
        at.session_state["_admin_breakdown_pick"] = choice
        [b for b in at.sidebar.button if "Admin" in (b.label or "")][0].click().run()
        if at.exception:
            failures.append(f"test_expander: exception after picking {[e.value for e in at.exception]}")
            return
        frames = [df.value for df in at.dataframe]
        calls_df = [f for f in frames if "max_tokens requested" in set(f.columns)]
        if not calls_df:
            failures.append("test_expander: call-by-call table did not render")
            return
        calls_df = calls_df[0]
        if len(calls_df) != 3:
            failures.append(f"test_expander: {len(calls_df)} call rows, expected 3")
        need = {"Time (UTC)", "Purpose", "Step", "Model", "Tokens in", "Tokens out", "Cost (USD)",
                "max_tokens requested", "Thinking tokens", "Stop reason", "Output over cap"}
        if not need <= set(calls_df.columns):
            failures.append(f"test_expander: columns missing: {sorted(need - set(calls_df.columns))}")
        by_kind = {r["Step"]: r for _, r in calls_df.iterrows()}
        if by_kind["reduce (json_retry)"]["Output over cap"] != "YES" or by_kind["map"]["max_tokens requested"] != "1,200":
            failures.append(f"test_expander: row contents wrong: {by_kind}")
        if not any("Purpose" in f.columns and "Calls" in f.columns and "Step" not in f.columns for f in frames):
            failures.append("test_expander: per-purpose totals table missing")
        if not any("Run" in f.columns and "Calls" in f.columns and "Started (UTC)" in f.columns for f in frames):
            failures.append("test_expander: per-run table missing")
        if not any("Totals: 3 calls" in m.value for m in at.markdown):
            failures.append("test_expander: totals line missing")
    finally:
        auth.ADMIN_ACCOUNTS.discard(admin_email)
        _cleanup(admin.id); _cleanup(other.id)


def test_new_columns_migrate_onto_an_old_table(failures: list[str]) -> None:
    from sqlalchemy import text
    with db.engine.begin() as conn:
        for col in ("max_tokens", "thinking_tokens", "stop_reason", "step", "attempt"):
            conn.execute(text(f"ALTER TABLE ai_call_log DROP COLUMN {col}"))
    db._run_light_migrations()
    db._run_light_migrations()
    from sqlalchemy import inspect as sa_inspect
    cols = {c["name"] for c in sa_inspect(db.engine).get_columns("ai_call_log")}
    for col in ("max_tokens", "thinking_tokens", "stop_reason", "step", "attempt"):
        if col not in cols:
            failures.append(f"test_migrate_cols: {col} was not added")


# --------------------------------------------------------------------------
# CP-TASK 4 -- no paying for failed attempts, truncated notes, dedupe
# --------------------------------------------------------------------------

_THINKING_OFF_PURPOSES = {
    "tender_analysis", "discipline_detection", "cv_name_extraction", "team_bios", "resourcing",
    "reference_projects", "methodology", "risk_register", "fee_benchmark", "team_intro", "experience_intro",
}
_THINKING_ON_PURPOSES = {"draft_generation", "pitch_review", "pitch_review_questions", "executive_summary"}
_CACHED_PURPOSES = {"discipline_detection", "cv_name_extraction", "team_bios", "resourcing",
                    "reference_projects", "methodology", "risk_register"}


def _ai_call_sites():
    """[(relpath, lineno, purpose, {keyword names -> ast node})] for every call_ai / call_ai_json."""
    import ast
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
    out = []
    for dirpath, _d, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".py") or fn == "ai_interface.py":
                continue
            path = os.path.join(dirpath, fn)
            for node in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
                if isinstance(node, ast.Call):
                    f = node.func
                    name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
                    if name in ("call_ai", "call_ai_json"):
                        kws = {k.arg: k.value for k in node.keywords}
                        purpose = kws["purpose"].value if "purpose" in kws and isinstance(kws["purpose"], ast.Constant) else None
                        out.append((os.path.relpath(path, root), node.lineno, purpose, kws))
    return out


def test_thinking_is_off_exactly_where_listed(failures: list[str]) -> None:
    import ast
    sites = _ai_call_sites()
    seen_off, seen_on = set(), set()
    for rel, line, purpose, kws in sites:
        off = "thinking" in kws and isinstance(kws["thinking"], ast.Constant) and kws["thinking"].value == "off"
        if purpose in _THINKING_OFF_PURPOSES:
            seen_off.add(purpose)
            if not off:
                failures.append(f"test_thinking: {rel}:{line} ({purpose}) must pass thinking='off'")
        elif purpose in _THINKING_ON_PURPOSES:
            seen_on.add(purpose)
            if "thinking" in kws:
                failures.append(f"test_thinking: {rel}:{line} ({purpose}) is a reasoning task -- thinking must stay on")
        else:
            failures.append(f"test_thinking: {rel}:{line} has an unclassified purpose {purpose!r}")
    if seen_off != _THINKING_OFF_PURPOSES or seen_on != _THINKING_ON_PURPOSES:
        failures.append(f"test_thinking: classification incomplete: off={sorted(_THINKING_OFF_PURPOSES - seen_off)} "
                        f"on={sorted(_THINKING_ON_PURPOSES - seen_on)}")


def test_thinking_param_reaches_the_api(failures: list[str]) -> None:
    user = _new_user()
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="th|t|c|h", project_name="Th")
            text = _brief(40_000)
            n = len(tender_analyser.clean_and_chunk_tender_text(text)[1])
            _FakeAnthropic.replies = [("note", 300, None, "end_turn")] * n + [('{"project_scope": "x"}', 500, None, "end_turn")]
            tender_analyser.analyse_tender(text, None, _CFG)
            map_reduce = [c["thinking"] for c in _FakeAnthropic.calls]
            _FakeAnthropic.calls.clear()
            _FakeAnthropic.replies = [('{"a": 1}', 10, None, "end_turn")] * 2
            ai_interface.call_ai_json("p", "s", _CFG, purpose="executive_summary")       # a reasoning task: untouched
            ai_interface.call_ai_json("p", "s", _CFG, purpose="x", thinking="off")
            return map_reduce, [c["thinking"] for c in _FakeAnthropic.calls]
        map_reduce, others = _with_fake_anthropic(run)
        if any(t != {"type": "disabled"} for t in map_reduce) or not map_reduce:
            failures.append(f"test_thinking_api: map/reduce requests carried {set(map(str, map_reduce))}")
        if others != ["ABSENT", {"type": "disabled"}]:
            failures.append(f"test_thinking_api: reasoning call must send no thinking param, got {others}")
        # Per model: what 'off' means.
        want = {"claude-sonnet-5": {"type": "disabled"}, "claude-sonnet-5-20261001": {"type": "disabled"},
                "claude-haiku-5-5": {"type": "disabled"}, "claude-opus-5": {"type": "disabled"},
                "claude-sonnet-5-5": {"type": "between_tools"},
                "claude-opus-5-5": None, "claude-fable-5-1": None, "claude-sonnet-4-5": None, "gpt-4o": None}
        for model, w in want.items():
            if ai_interface.thinking_off_param(model) != w:
                failures.append(f"test_thinking_api: {model} -> {ai_interface.thinking_off_param(model)}, expected {w}")
    finally:
        _cleanup(user.id)


def test_thinking_param_rejection_falls_back(failures: list[str]) -> None:
    """If the API refuses the parameter, the step still completes (without it) and
    the model is remembered as not accepting it."""
    class _Bad(Exception):
        status_code = 400
    user = _new_user()
    cfg = {**_CFG, "model": "claude-haiku-5-5"}
    ai_interface._thinking_param_rejected.discard("claude-haiku-5-5")
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="rj|t|c|h", project_name="Rj")
            _FakeAnthropic.replies = [_Bad('thinking.type.disabled is not supported for this model'), ("ok", 10, None, "end_turn"),
                                      ("ok2", 10, None, "end_turn")]
            a = ai_interface.call_ai("p", "s", cfg, max_tokens=100, purpose="x", thinking="off")
            b = ai_interface.call_ai("p", "s", cfg, max_tokens=100, purpose="x", thinking="off")
            return a, b, [c["thinking"] for c in _FakeAnthropic.calls]
        a, b, sent = _with_fake_anthropic(run)
        if (a, b) != ("ok", "ok2"):
            failures.append(f"test_thinking_fallback: results {(a, b)}")
        if sent != [{"type": "disabled"}, "ABSENT", "ABSENT"]:
            failures.append(f"test_thinking_fallback: requests carried {sent} (retry without it, then never again)")
    finally:
        ai_interface._thinking_param_rejected.discard("claude-haiku-5-5")
        _cleanup(user.id)


def test_json_budget_and_single_retry(failures: list[str]) -> None:
    user = _new_user()
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="jb|t|c|h", project_name="Jb")
            out = {}
            # 1) clean first answer: ONE call, at the 16,000 ceiling even though 800 was asked for.
            _FakeAnthropic.replies = [('{"a": 1}', 200, None, "end_turn")]
            ai_interface.call_ai_json("p", "s", _CFG, max_tokens=800, purpose="x")
            out["clean"] = [c["max_tokens"] for c in _FakeAnthropic.calls]
            # 2) genuine parse failure twice: exactly TWO calls (one retry), then a clear error.
            _FakeAnthropic.calls.clear()
            _FakeAnthropic.replies = [("sorry, here you go", 50, None, "end_turn"), ("still prose", 50, None, "end_turn")]
            try:
                ai_interface.call_ai_json("p", "s", _CFG, max_tokens=800, purpose="x")
                out["fail_raised"] = False
            except ai_interface.AIConfigError:
                out["fail_raised"] = True
            out["fail"] = [c["max_tokens"] for c in _FakeAnthropic.calls]
            # 3) parse failure then success: the retry is the second (and last) call.
            _FakeAnthropic.calls.clear()
            _FakeAnthropic.replies = [("prose", 50, None, "end_turn"), ('{"ok": true}', 60, None, "end_turn")]
            out["retry_result"] = ai_interface.call_ai_json("p", "s", _CFG, purpose="x")
            out["retry_calls"] = len(_FakeAnthropic.calls)
            # 4) a reply that STOPPED AT THE CAP is not retried (the same budget would truncate again):
            #    repaired from the truncated JSON, flagged.
            _FakeAnthropic.calls.clear()
            _FakeAnthropic.replies = [('{"a": [1, 2, 3', 16000, None, "max_tokens")]
            repaired = ai_interface.call_ai_json("p", "s", _CFG, purpose="x")
            out["trunc_calls"] = len(_FakeAnthropic.calls)
            out["trunc_repaired"] = ai_interface.was_repaired(repaired)
            return out
        out = _with_fake_anthropic(run)
        if out["clean"] != [16000]:
            failures.append(f"test_json_budget: clean call requested {out['clean']}, expected [16000]")
        if out["fail"] != [16000, 16000] or not out["fail_raised"]:
            failures.append(f"test_json_budget: parse failure made {out['fail']} calls / raised={out['fail_raised']}")
        if out["retry_result"] != {"ok": True} or out["retry_calls"] != 2:
            failures.append(f"test_json_budget: retry path wrong: {out['retry_result']} in {out['retry_calls']} calls")
        if out["trunc_calls"] != 1 or not out["trunc_repaired"]:
            failures.append(f"test_json_budget: a truncated reply was retried ({out['trunc_calls']} calls) or not repaired")
        if ai_interface.JSON_MAX_TOKENS_CEILING != 16000:
            failures.append("test_json_budget: the ceiling is not 16,000")
    finally:
        _cleanup(user.id)


def test_map_cap_and_truncation_warning(failures: list[str]) -> None:
    import io, contextlib
    if tender_analyser.MAP_MAX_TOKENS != 2000:
        failures.append(f"test_map_cap: MAP_MAX_TOKENS is {tender_analyser.MAP_MAX_TOKENS}, expected 2000")
    user = _new_user()
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="mp|t|c|h", project_name="Mp")
            text = _brief(40_000)
            n = len(tender_analyser.clean_and_chunk_tender_text(text)[1])
            replies = [("note", 300, None, "end_turn")] * n
            replies[1] = ("cut off nots", 2000, None, "max_tokens")            # one map call hits the cap
            _FakeAnthropic.replies = replies + [('{"project_scope": "x"}', 500, None, "end_turn")]
            tender_analyser.analyse_tender(text, None, _CFG)
            return n
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            n = _with_fake_anthropic(run)
        warnings = [l for l in buf.getvalue().splitlines() if "stopped at max_tokens=2000" in l]
        if len(warnings) != 1 or "map call 2/" not in warnings[0]:
            failures.append(f"test_map_cap: expected exactly one truncation warning for map call 2, got {warnings}")
        rows = _rows_for(user.id)
        maps = [r for r in rows if r.step == "map"]
        if [r.max_tokens for r in maps] != [2000] * n:
            failures.append("test_map_cap: map calls were not requested at 2,000")
        if [r.stop_reason for r in maps].count("max_tokens") != 1:
            failures.append("test_map_cap: stop_reason not logged for the truncated map call")
    finally:
        _cleanup(user.id)


def test_cached_calls_run_once_per_unchanged_input(failures: list[str]) -> None:
    store: dict = {}
    saved = ai_interface._json_cache_store
    ai_interface._json_cache_store = lambda: store
    user = _new_user()
    try:
        def run():
            ai_interface.set_usage_context(user_id=user.id, project_key="ch|t|c|h", project_name="Ch")
            brief = "A bridge over a creek with a rail crossing. " * 30
            _FakeAnthropic.replies = [('{"disciplines": ["Structural", "Rail"]}', 40, None, "end_turn")] * 3
            first = tender_analyser.detect_disciplines_from_text(brief, config=_CFG)
            second = tender_analyser.detect_disciplines_from_text(brief, config=_CFG)       # same inputs
            n_same = len(_FakeAnthropic.calls)
            third = tender_analyser.detect_disciplines_from_text(brief + " Plus a new addendum.", config=_CFG)
            return first, second, third, n_same, len(_FakeAnthropic.calls)
        first, second, third, n_same, n_after_change = _with_fake_anthropic(run)
        if first != second:
            failures.append("test_cache: the saved result differs from the original")
        if n_same != 1:
            failures.append(f"test_cache: an unchanged re-run made {n_same} AI calls, expected 1")
        if n_after_change != 2:
            failures.append(f"test_cache: a changed input made {n_after_change} calls in total, expected 2")
        if len(store) != 2:
            failures.append(f"test_cache: {len(store)} cached entries, expected 2")
        # Not cached when the caller didn't opt in, and a repaired (truncated) result is never saved.
        store.clear()
        def run2():
            _FakeAnthropic.replies = [('{"a": 1}', 10, None, "end_turn")] * 2 + [('{"a": [1', 16000, None, "max_tokens")] * 2
            ai_interface.call_ai_json("same", "s", _CFG, purpose="draft_generation")
            ai_interface.call_ai_json("same", "s", _CFG, purpose="draft_generation")
            n_plain = len(_FakeAnthropic.calls)
            ai_interface.call_ai_json("trunc", "s", _CFG, purpose="risk_register", cache=True)
            ai_interface.call_ai_json("trunc", "s", _CFG, purpose="risk_register", cache=True)
            return n_plain, len(_FakeAnthropic.calls)
        n_plain, n_total = _with_fake_anthropic(run2)
        if n_plain != 2:
            failures.append("test_cache: a call without cache=True was served from the cache")
        if n_total != 4 or store:
            failures.append(f"test_cache: a repaired/truncated result was cached ({n_total} calls, {len(store)} entries)")
        # Which features opted in.
        import ast
        cached = {p for _r, _l, p, kws in _ai_call_sites() if "cache" in kws and isinstance(kws["cache"], ast.Constant) and kws["cache"].value is True}
        if cached != _CACHED_PURPOSES:
            failures.append(f"test_cache: cached purposes {sorted(cached)} != {sorted(_CACHED_PURPOSES)}")
        # Outside a Streamlit script run (the worker) there is no cache at all.
        ai_interface._json_cache_store = saved
        if ai_interface._json_cache_store() is not None:
            failures.append("test_cache: a cache exists outside a script run -- it would be shared between users")
    finally:
        ai_interface._json_cache_store = saved
        _cleanup(user.id)


def test_cache_is_saved_with_the_project(failures: list[str]) -> None:
    from modules import project_store
    if "ai_json_cache" not in project_store.PLAIN_KEYS:
        failures.append("test_cache_saved: ai_json_cache is not saved with the project")
        return
    cache = {"abc": {"purpose": "risk_register", "at": "2026-10-25T00:00:00+00:00", "result": {"entries": [{"a": 1}]}}}
    blob = project_store.save_project({"project_name": "P", "ai_json_cache": cache})
    if project_store.load_project(blob).get("ai_json_cache") != cache:
        failures.append("test_cache_saved: the cache did not survive save -> load")


def test_no_project_breakdown_lists_rows(failures: list[str]) -> None:
    from streamlit.testing.v1 import AppTest
    admin_email = f"_adm_{uuid.uuid4().hex[:8]}@example.invalid"
    auth.ADMIN_ACCOUNTS.add(admin_email)
    email_utils.is_configured = lambda: False
    admin = auth.create_user(admin_email, "testpassword123", device_claimed=False)
    auth.accept_terms(admin)
    u1, u2 = _new_user(), _new_user()
    try:
        with db.get_session() as s:
            s.query(db.AiCallLog).filter(
                (db.AiCallLog.project_key.is_(None)) | (db.AiCallLog.project_key == "")).delete(synchronize_session=False)
            s.commit()
            for i in range(3):      # NULL key, user 1
                s.add(db.AiCallLog(user_id=u1.id, project_key=None, purpose="team_bios", model="claude-sonnet-5",
                                   input_tokens=1000, output_tokens=500, estimated_cost_usd=0.01))
            for i in range(2):      # empty-string key, user 2
                s.add(db.AiCallLog(user_id=u2.id, project_key="", purpose="cv_name_extraction", model="claude-sonnet-5",
                                   input_tokens=2000, output_tokens=100, estimated_cost_usd=0.005))
            s.commit()
        rows = [p for p in db.ai_cost_summary()["per_project"] if p["project_name"] == "(no project)"]
        if len(rows) != 1 or rows[0]["calls"] != 5:
            failures.append(f"test_no_project: expected ONE '(no project)' row of 5 calls, got {[(r['project_key'], r['calls']) for r in rows]}")
        for key in ("(no project)", "", None):
            bd = db.project_cost_breakdown(key, u1.id)             # even when the row carries one user's id
            if bd["totals"]["calls"] != 5:
                failures.append(f"test_no_project: breakdown({key!r}) lists {bd['totals']['calls']} calls, expected 5")
        bd = db.project_cost_breakdown("(no project)", None)
        if {p["purpose"] for p in bd["by_purpose"]} != {"team_bios", "cv_name_extraction"}:
            failures.append("test_no_project: by-purpose totals wrong")
        # And through the admin screen.
        at = AppTest.from_file("app.py", default_timeout=180)
        at.session_state["_auth_user_id"] = admin.id
        at.session_state["_state_owner_id"] = admin.id
        at.run()
        [b for b in at.sidebar.button if "Admin" in (b.label or "")][0].click().run()
        box = [sb for sb in at.selectbox if sb.key == "_admin_breakdown_pick"][0]
        choice = [o for o in box.options if o.startswith("(no project)")]
        if not choice:
            failures.append(f"test_no_project: no '(no project)' option in {box.options}")
            return
        at.session_state["_admin_breakdown_pick"] = choice[0]
        [b for b in at.sidebar.button if "Admin" in (b.label or "")][0].click().run()
        calls_tables = [df.value for df in at.dataframe if "max_tokens requested" in set(df.value.columns)]
        if not calls_tables or len(calls_tables[0]) != 5:
            failures.append(f"test_no_project: the screen listed {len(calls_tables[0]) if calls_tables else 0} rows, expected 5")
        if any("No AI calls are logged" in c.value for c in at.caption):
            failures.append("test_no_project: the screen still says 'No AI calls are logged'")
    finally:
        auth.ADMIN_ACCOUNTS.discard(admin_email)
        for u in (admin, u1, u2):
            _cleanup(u.id)


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
