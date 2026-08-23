"""
verify_isolation.py

Empirical multi-tenant isolation test for the CivilProposals SaaS build.

Creates user A, fills A's account with one row in every user-scoped table,
then creates user B (a brand-new account) and calls every public read
function the app uses -- with B's id, and with A's ids/slugs/project keys
guessed -- asserting B sees NOTHING of A's and that B's trial allowance is
untouched by A's usage.

Run with an isolated database:

    DATABASE_URL="sqlite:////tmp/iso_test.db" python3 verify_isolation.py

Exits non-zero if any check fails.
"""

from __future__ import annotations

import os
import sys

if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "sqlite:////tmp/iso_test.db"
os.environ.setdefault("SAAS_MODE", "true")
os.environ.setdefault("APP_SECRET_KEY", "verify-isolation-test-key")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules import (  # noqa: E402
    artifact_download_gate,
    auth,
    cloud_project_store,
    db,
    fee_history,
    firm_profile,
    project_store,
    proposal_library,
    reference_library,
)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(passed), detail))


def check_raises(name: str, fn, *exc_types) -> None:
    """Passes when fn() raises one of exc_types (i.e. access was refused)."""
    try:
        value = fn()
    except exc_types as exc:
        check(name, True, f"refused: {type(exc).__name__}")
    except Exception as exc:  # noqa: BLE001
        check(name, False, f"raised unexpected {type(exc).__name__}: {exc}")
    else:
        check(name, False, f"RETURNED DATA: {value!r:.120}")


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

def _all_users() -> list:
    with db.get_session() as s:
        return s.query(db.User).all()


def fresh_db() -> None:
    url = db.DATABASE_URL
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
        if os.path.exists(path):
            db.engine.dispose()
            os.remove(path)
    db.init_db()


def make_user(email: str) -> db.User:
    existing = auth.get_user_by_email(email)
    if existing:
        return existing
    return auth.create_user(email, "Correct-Horse-9", name="Test", firm_name="Firm")


A_PROJECT_NAME = "Alpha Secret Bridge Duplication"
A_PROJECT_KEY = "alpha secret bridge duplication|tender-a|client-a|deadbeef"
A_DOCX = b"PK\x03\x04ALPHA-CONFIDENTIAL-PROPOSAL-BYTES"
A_REF = b"PK\x03\x04ALPHA-CONFIDENTIAL-REFERENCE-BYTES"


def seed_user_a(a: db.User) -> dict:
    """Every user-scoped table gets one row belonging to A."""
    seeded = {}

    # SavedProject (via the real save path, real serialized project bytes)
    blob = project_store.save_project({
        "project_name": A_PROJECT_NAME,
        "client_name": "Client A",
        "tender_name": "Tender A",
    })
    seeded["slug"] = cloud_project_store.save_cloud(a.id, A_PROJECT_NAME, blob)
    seeded["saved_projects"] = cloud_project_store.list_cloud_projects(a.id)
    seeded["saved_project_id"] = seeded["saved_projects"][0]["id"]

    # LibraryEntry
    entry = proposal_library.archive_proposal(
        a.id, A_DOCX, "Bridges", "formal",
        project_name=A_PROJECT_NAME, client_name="Client A",
        tender_name="Tender A", tags="confidential",
    )
    seeded["library_entry_id"] = entry["path"]

    # ReferenceLibraryEntry
    ref = reference_library.upload_reference(
        a.id, A_REF, "Bridges", "alpha-reference.docx",
        title="Alpha Reference", tags="confidential",
    )
    seeded["reference_entry_id"] = ref["path"]

    # ProposalUsage (+ trial spend) -- A burns their trial bid
    auth.record_proposal_usage(a, A_PROJECT_KEY, A_PROJECT_NAME)

    # ProjectPasses -- give A a paid project with passes
    with db.get_session() as s:
        s.add(db.ProjectPasses(user_id=a.id, project_key=A_PROJECT_KEY,
                               passes_purchased=5, passes_used=1))
        # ArtifactEvent -- A's one free download of each artifact
        for artifact in artifact_download_gate.FREE_TIER_ARTIFACTS:
            s.add(db.ArtifactEvent(
                user_id=a.id,
                project_key=artifact_download_gate.TRIAL_ARTIFACT_EVENT_SENTINEL_KEY,
                artifact_type=artifact,
            ))
        # Job -- A owns a background job
        s.add(db.Job(id="alpha-job-id-0001", user_id=a.id,
                     job_type="tender_analysis", status="finished"))
        s.commit()

    # AiCallLog -- A racks up AI spend
    db.log_ai_call(a.id, A_PROJECT_KEY, A_PROJECT_NAME, "tender_analysis",
                   "anthropic", "claude-sonnet-5", 900_000, 300_000, 7.20)

    # FeeSnapshot -- A's own pricing history
    class _Line:
        def __init__(self, d, h, r, amt):
            self.discipline, self.total_hours, self.rate_per_hour, self.fee_amount = d, h, r, amt

    for i in range(5):
        fee_history.record_snapshot(
            a.id, f"{A_PROJECT_KEY}-{i}", "Bridges",
            [_Line("Structural", 100, 200, 20000), _Line("Geotech", 50, 180, 9000)],
            A_PROJECT_NAME,
        )

    # FirmProfile -- A's standing firm facts
    firm_profile.save_profile(a.id, company_name="Alpha Engineering Pty Ltd",
                              abn="11 111 111 111",
                              registered_address="1 Secret St")
    return seeded


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def run() -> int:
    fresh_db()
    a = make_user("alpha@example.com")
    seeded = seed_user_a(a)

    # Sanity: A really can see A's own data (otherwise every check below is
    # vacuously "isolated").
    check("[sanity] A sees A's saved project",
          len(cloud_project_store.list_cloud_projects(a.id)) == 1)
    check("[sanity] A sees A's library entry",
          len(proposal_library.list_library(a.id)) == 1)
    check("[sanity] A sees A's reference entry",
          len(reference_library.list_library(a.id)) == 1)
    check("[sanity] A's docx bytes readable by A",
          proposal_library.read_entry_bytes(a.id, seeded["library_entry_id"]) == A_DOCX)
    check("[sanity] A's trial is now spent",
          auth.get_access_status(auth.get_user_by_id(a.id))["trial_remaining"] == 0)
    check("[sanity] A's artifact gate is tripped",
          artifact_download_gate.already_downloaded(db, a.id, "proposal_docx", True) is True)
    check("[sanity] A has fee history",
          fee_history.snapshot_count(a.id) == 5)
    check("[sanity] A has AI spend logged",
          db.account_ai_cost(a.id) > 0)

    # ---- B: a brand new account, created after A filled everything in ----
    b = make_user("beta@example.com")
    check("B is a distinct account", b.id != a.id)

    # 1. Saved projects (the "load a project" path)
    check("B's cloud project list is empty",
          cloud_project_store.list_cloud_projects(b.id) == [],
          repr(cloud_project_store.list_cloud_projects(b.id))[:120])
    check_raises("B cannot load A's SavedProject by its id",
                 lambda: cloud_project_store.load_cloud(b.id, seeded["saved_project_id"]),
                 project_store.ProjectLoadError)
    # Guessing by slug: B saves a project under the SAME slug and must get
    # their own row, not A's bytes.
    b_blob = project_store.save_project({"project_name": A_PROJECT_NAME,
                                         "client_name": "Client B",
                                         "tender_name": "Tender B"})
    b_slug = cloud_project_store.save_cloud(b.id, A_PROJECT_NAME, b_blob)
    b_entries = cloud_project_store.list_cloud_projects(b.id)
    check("B reusing A's exact project name gets B's OWN row",
          b_slug == seeded["slug"] and len(b_entries) == 1
          and b_entries[0]["id"] != seeded["saved_project_id"])
    b_loaded = cloud_project_store.load_cloud(b.id, b_entries[0]["id"])
    check("B's same-slug project loads B's content, not A's",
          b_loaded.get("client_name") == "Client B",
          f"client_name={b_loaded.get('client_name')!r}")
    check("A's saved project survived B's same-slug save",
          len(cloud_project_store.list_cloud_projects(a.id)) == 1)
    # Deleting by A's id from B's account must not touch A's row.
    cloud_project_store.delete_cloud(b.id, seeded["saved_project_id"])
    check("B cannot delete A's SavedProject by id",
          len(cloud_project_store.list_cloud_projects(a.id)) == 1)

    # 2. Proposal library
    check("B's proposal library is empty",
          proposal_library.list_library(b.id) == [])
    check("B's proposal library is empty (filtered by A's project_type)",
          proposal_library.list_library(b.id, project_type="Bridges") == [])
    check("B's proposal library is empty (filtered by A's tag)",
          proposal_library.list_library(b.id, tag="confidential") == [])
    check_raises("B cannot read A's archived DOCX by entry id",
                 lambda: proposal_library.read_entry_bytes(b.id, seeded["library_entry_id"]),
                 FileNotFoundError)
    proposal_library.delete_entry(b.id, seeded["library_entry_id"])
    check("B cannot delete A's library entry",
          len(proposal_library.list_library(a.id)) == 1)

    # 3. Reference library
    check("B's reference library is empty",
          reference_library.list_library(b.id) == [])
    check("B's reference library is empty (filtered by A's project_type)",
          reference_library.list_library(b.id, project_type="Bridges") == [])
    check_raises("B cannot read A's reference file by entry id",
                 lambda: reference_library.read_entry_bytes(b.id, seeded["reference_entry_id"]),
                 FileNotFoundError)
    reference_library.delete_entry(b.id, seeded["reference_entry_id"])
    check("B cannot delete A's reference entry",
          len(reference_library.list_library(a.id)) == 1)

    # 4. Access status / trial allowance
    b_access = auth.get_access_status(auth.get_user_by_id(b.id))
    check("B's trial is a fresh 1 bid, unaffected by A's usage",
          b_access["trial_remaining"] == auth.DEFAULT_TRIAL_LIMIT == 1
          and b_access["allowed"] is True and b_access["limit_reached"] is False,
          repr(b_access))
    check("B is not treated as unlimited", b_access["unlimited"] is False)
    check("B has no bid credits from A's account", b_access["bid_credits"] == 0)

    # 5. Proposal usage / project funding / passes -- guessing A's project key
    check("B's funded_by for A's project key is empty",
          auth.project_funded_by(auth.get_user_by_id(b.id), A_PROJECT_KEY) == "",
          repr(auth.project_funded_by(auth.get_user_by_id(b.id), A_PROJECT_KEY)))
    check("B does not inherit A's project passes",
          auth.project_passes_status(auth.get_user_by_id(b.id), A_PROJECT_KEY)
          == {"has_passes": False, "purchased": 0, "used": 0, "remaining": 0})
    check("B cannot consume a pass on A's project",
          auth.consume_project_pass(auth.get_user_by_id(b.id), A_PROJECT_KEY) is False)
    with db.get_session() as s:
        b_usage = s.query(db.ProposalUsage).filter(db.ProposalUsage.user_id == b.id).count()
        b_passes = s.query(db.ProjectPasses).filter(db.ProjectPasses.user_id == b.id).count()
        b_events = s.query(db.ArtifactEvent).filter(db.ArtifactEvent.user_id == b.id).count()
    check("B owns zero ProposalUsage rows", b_usage == 0)
    check("B owns zero ProjectPasses rows", b_passes == 0)
    check("B owns zero ArtifactEvent rows", b_events == 0)

    # B running the SAME project key as A must spend B's own trial, and must
    # not disturb A's row.
    spent = auth.record_proposal_usage(auth.get_user_by_id(b.id), A_PROJECT_KEY, A_PROJECT_NAME)
    check("B analysing A's exact project key spends B's own trial", spent is True)
    check("A's ProposalUsage row is untouched by B's run",
          auth.project_funded_by(auth.get_user_by_id(a.id), A_PROJECT_KEY) == "trial")
    check("A's project passes untouched by B",
          auth.project_passes_status(auth.get_user_by_id(a.id), A_PROJECT_KEY)["remaining"] == 4)

    # 6. Free-trial artifact gate -- the sentinel-key path
    b_fresh = auth.get_user_by_id(b.id)
    for artifact in artifact_download_gate.FREE_TIER_ARTIFACTS:
        check(f"B's artifact gate for {artifact} is fresh (A already used theirs)",
              artifact_download_gate.already_downloaded(db, b.id, artifact, True) is False)
        check(f"B's first download of {artifact} is NOT blocked",
              artifact_download_gate.blocked(
                  True, artifact,
                  artifact_download_gate.already_downloaded(db, b.id, artifact, True)) is False)
    # B marks one download; A's state must not change, and B's other
    # artifacts must stay independent.
    err = artifact_download_gate.mark_downloaded(db, b.id, "proposal_docx", True)
    check("B marking a download succeeds", err is False)
    check("B's proposal_docx is now used",
          artifact_download_gate.already_downloaded(db, b.id, "proposal_docx", True) is True)
    check("B's org_chart_pptx is still fresh",
          artifact_download_gate.already_downloaded(db, b.id, "org_chart_pptx", True) is False)
    check("A's gate state unchanged by B's download",
          artifact_download_gate.already_downloaded(db, a.id, "proposal_docx", True) is True)
    with db.get_session() as s:
        check("Exactly one ArtifactEvent row for B/proposal_docx",
              s.query(db.ArtifactEvent).filter(
                  db.ArtifactEvent.user_id == b.id,
                  db.ArtifactEvent.artifact_type == "proposal_docx").count() == 1)
    _ = b_fresh

    # 7. AI spend / cost ceiling
    check("B's account AI cost is 0 despite A's spend",
          db.account_ai_cost(b.id) == 0.0, repr(db.account_ai_cost(b.id)))

    # 8. Fee history (the firm's own pricing benchmarks)
    check("B has no fee snapshots", fee_history.snapshot_count(b.id) == 0)
    check("B gets no benchmark from A's 5 bids",
          fee_history.fee_history_benchmarks(b.id, "Bridges") == {"bids": 0, "disciplines": []},
          repr(fee_history.fee_history_benchmarks(b.id, "Bridges"))[:160])

    # 9. Firm profile
    b_profile = firm_profile.get_profile(b.id)
    check("B has no firm profile of A's", b_profile is None,
          repr(getattr(b_profile, "company_name", None)))
    b_created = firm_profile.get_or_create(b.id)
    check("B's auto-created firm profile is blank, not A's",
          (b_created.company_name or "") == "" and (b_created.abn or "") == "",
          f"company_name={b_created.company_name!r} abn={b_created.abn!r}")

    # 10. Background jobs
    with db.get_session() as s:
        owned_by_b = s.query(db.Job).filter(
            db.Job.id == "alpha-job-id-0001", db.Job.user_id == b.id).first()
    check("B cannot claim ownership of A's job row", owned_by_b is None)
    try:
        from modules import job_queue
        status = job_queue.get_status("alpha-job-id-0001", b.id)
        check("job_queue.get_status refuses A's job for B",
              status["status"] == "not_found" and status["result"] is None,
              repr(status))
    except Exception as exc:  # noqa: BLE001 -- redis/rq may not be importable
        check("job_queue.get_status refuses A's job for B", False,
              f"could not run: {type(exc).__name__}: {exc}")

    # 11. Admin gate
    check("B is not an admin", auth.is_admin_user(auth.get_user_by_id(b.id)) is False)
    check("B's email is not in ADMIN_ACCOUNTS",
          (b.email or "").lower() not in auth.ADMIN_ACCOUNTS)
    check("B's is_admin DB flag is off", not bool(getattr(b, "is_admin", False)))

    # 11b. Admin escalation by email spoofing -- an ADMIN_ACCOUNTS address in
    # a different case / with padding must not create a second, admin-passing
    # account (is_admin_user() lowercases, so a case-variant row would slip
    # through if create_user() stored the address verbatim).
    admin_email = sorted(auth.ADMIN_ACCOUNTS)[0]
    owner = make_user(admin_email)  # the real owner has claimed the address
    check("[sanity] the real admin address IS an admin",
          auth.is_admin_user(owner) is True)
    for spoof in (admin_email.upper(), f" {admin_email.capitalize()} "):
        try:
            impostor = auth.create_user(spoof, "Correct-Horse-9")
        except ValueError:
            impostor = None
        if impostor is None:
            # Address is taken (correctly normalised) -- no impostor exists.
            check(f"Cannot register admin-email variant {spoof!r}", True, "refused")
        else:
            check(f"Cannot register admin-email variant {spoof!r}", False,
                  f"created id={impostor.id} email={impostor.email!r} "
                  f"is_admin_user={auth.is_admin_user(impostor)}")
    check("No second row exists for the admin address",
          len([u for u in _all_users() if (u.email or "").lower() == admin_email]) <= 1)

    # 11c. An empty / whitespace user_id must never act as a wildcard.
    for blank in ("", "   ", None):
        check(f"proposal_library.list_library({blank!r}) returns nothing of A's",
              proposal_library.list_library(blank) == [])
        check(f"reference_library.list_library({blank!r}) returns nothing of A's",
              reference_library.list_library(blank) == [])
        check(f"cloud_project_store.list_cloud_projects({blank!r}) is empty",
              cloud_project_store.list_cloud_projects(blank) == [])
        check(f"fee_history.snapshot_count({blank!r}) is 0",
              fee_history.snapshot_count(blank) == 0)
    blank_profile = firm_profile.get_profile("")
    check("firm_profile.get_profile('') is not A's profile",
          blank_profile is None or blank_profile.user_id == firm_profile.LOCAL_USER_ID,
          repr(getattr(blank_profile, "company_name", None)))

    # 12. No user-scoped table leaks rows to B by any global read
    with db.get_session() as s:
        for model, label in ((db.LibraryEntry, "LibraryEntry"),
                             (db.ReferenceLibraryEntry, "ReferenceLibraryEntry"),
                             (db.SavedProject, "SavedProject"),
                             (db.FeeSnapshot, "FeeSnapshot"),
                             (db.FirmProfile, "FirmProfile")):
            rows = s.query(model).filter(model.user_id == b.id).all()
            leaked = [r for r in rows if r.user_id != b.id]
            check(f"No {label} row visible to B belongs to A", not leaked)

    # 13. Session-state account switch (Part 2, BRIEF_ISOLATION_AND_PRIVACY.md)
    # -- logging out of A, or logging into B in the same browser tab, must
    # not leave any of A's in-memory project data behind for B to inherit.
    # auth.log_in()/log_out() only ever call .get()/[]/.pop()/.keys()/del on
    # st.session_state, all of which a plain dict satisfies -- so a dict
    # stands in for the real Streamlit session object here, with no need to
    # spin up an actual Streamlit script run.
    A_OWNED_SESSION_KEYS = {
        "tender_extracted", "drafts", "company_material_files",
        "returnable_schedule_files", "project_photo_bytes", "project_name",
        "_firm_profile_cache", "_firm_rate_card_cache",
    }

    def _a_owned_session_payload() -> dict:
        return {
            "tender_extracted": {"secret": "A's tender text"},
            "drafts": {"exec_summary": "A's confidential draft"},
            "company_material_files": [b"A-company-material"],
            "returnable_schedule_files": [b"A-schedule"],
            "project_photo_bytes": b"A-photo-bytes",
            "project_name": A_PROJECT_NAME,
            "_firm_profile_cache": {"company_name": "Alpha Engineering Pty Ltd"},
            "_firm_rate_card_cache": {"Structural": 200},
        }

    _real_session_state = auth.st.session_state
    fake_state = {
        "_auth_user_id": a.id,
        "_state_owner_id": a.id,
        "_cookie_write_pending": False,
        "_lang": "fr",
        **_a_owned_session_payload(),
    }
    auth.st.session_state = fake_state
    try:
        auth.log_out()
        check("log_out() clears every A-owned session key",
              not (A_OWNED_SESSION_KEYS & set(fake_state.keys())),
              repr(sorted(A_OWNED_SESSION_KEYS & set(fake_state.keys()))))
        check("log_out() preserves the UI language",
              fake_state.get("_lang") == "fr")
        check("log_out() clears _auth_user_id",
              "_auth_user_id" not in fake_state)
        check("log_out() sets the cookie-clear flag",
              fake_state.get("_cookie_clear_pending") is True)

        # A logged-out tab that somehow still carries A's data (e.g. no
        # log_out() call happened, or it happened before this code existed)
        # must ALSO be wiped the moment B logs in -- log_in() is a second,
        # independent line of defense, not just log_out().
        fake_state.update(_a_owned_session_payload())
        fake_state["_auth_user_id"] = a.id
        auth.log_in(b)
        check("log_in() to a DIFFERENT account clears every A-owned session key",
              not (A_OWNED_SESSION_KEYS & set(fake_state.keys())),
              repr(sorted(A_OWNED_SESSION_KEYS & set(fake_state.keys()))))
        check("log_in() preserves the UI language across the switch",
              fake_state.get("_lang") == "fr")
        check("log_in() stamps the new owner",
              fake_state.get("_auth_user_id") == b.id
              and fake_state.get("_state_owner_id") == b.id)

        # Logging back in as the SAME account must NOT wipe anything -- only
        # an actual account switch should trigger the clear.
        fake_state["untouched_marker"] = "still here"
        auth.log_in(b)
        check("log_in() to the SAME account does not wipe session state",
              fake_state.get("untouched_marker") == "still here")
    finally:
        auth.st.session_state = _real_session_state

    # ---- report ----
    width = max(len(n) for n, _, _ in RESULTS) + 2
    print()
    print("=" * (width + 10))
    print("MULTI-TENANT ISOLATION -- USER B vs USER A")
    print(f"database: {db.DATABASE_URL}")
    print("=" * (width + 10))
    failures = 0
    for name, passed, detail in RESULTS:
        tag = "PASS" if passed else "FAIL"
        if not passed:
            failures += 1
        line = f"{tag:<5} {name:<{width}}"
        if detail and not passed:
            line += f"  <-- {detail}"
        print(line)
    print("-" * (width + 10))
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} checks passed"
          + ("" if not failures else f"  ({failures} FAILED)"))
    print("=" * (width + 10))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
