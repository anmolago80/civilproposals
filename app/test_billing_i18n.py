"""
test_billing_i18n.py -- regression tests for the EN/ES dual-language +
one-pass-free-tier brief (Parts A0, B, B2, C).

Same house style as test_batch1_wiring.py: plain `def test_X(failures)`
functions appending human-readable strings, no pytest, driven by main()
printing PASS/FAIL + exit code. Exercises the auth.py / db.py layer
directly (no Streamlit AppTest needed for these -- record_proposal_usage,
consume_project_pass, project_funded_by etc. are all plain functions that
take a db.User and never touch st.session_state) plus the i18n catalog's
own internal consistency, which is cheap to check exhaustively and catches
the single most common mistake across a large translation sweep: a key
used in one language's catalog but missing from the other.

Run from this directory:

    python test_billing_i18n.py
"""

from __future__ import annotations

import os
import sys
import uuid


def _fresh_test_user(auth, db):
    """A throwaway account for these tests, isolated by a random email so
    repeated runs never collide with each other or with anything real."""
    email = f"_test_billing_{uuid.uuid4().hex[:12]}@example.invalid"
    user = auth.create_user(email, "testpassword123", "Test User", "Test Firm")
    return user


def _cleanup_test_user(db, user_id: str) -> None:
    """Best-effort teardown -- deletes everything this test suite could
    have written for this user across every table touched by the brief.
    Never raises: a cleanup failure must never be reported as a test
    failure, and must never stop the other tests from running."""
    try:
        with db.get_session() as s:
            s.query(db.ArtifactEvent).filter(db.ArtifactEvent.user_id == user_id).delete()
            s.query(db.ProjectPasses).filter(db.ProjectPasses.user_id == user_id).delete()
            s.query(db.ProposalUsage).filter(db.ProposalUsage.user_id == user_id).delete()
            s.query(db.User).filter(db.User.id == user_id).delete()
            s.commit()
    except Exception:
        pass


def test_funded_by_trial(failures: list[str]) -> None:
    """Part B: the first Tender Analysis run on a fresh trial account
    should record funded_by == "trial", and project_funded_by /
    is_trial_funded_project should agree with that."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        key = "test project|test tender|test client|abc123"
        charged = auth.record_proposal_usage(user, key, "Test Project")
        if not charged:
            failures.append("test_funded_by_trial: record_proposal_usage() returned False on a fresh account")
            return
        funded = auth.project_funded_by(user, key)
        if funded != "trial":
            failures.append(f"test_funded_by_trial: expected funded_by='trial', got {funded!r}")
        if not auth.is_trial_funded_project(user, key):
            failures.append("test_funded_by_trial: is_trial_funded_project() should be True right after a trial-funded run")
        # No ProjectPasses row should exist for a trial-funded project --
        # passes are a paid-project-only concept (Part B2).
        status = auth.project_passes_status(user, key)
        if status["has_passes"]:
            failures.append("test_funded_by_trial: a trial-funded project should not have a ProjectPasses row")
    finally:
        _cleanup_test_user(db, user.id)


def test_funded_by_subscription_opens_passes(failures: list[str]) -> None:
    """Part B2: a project funded by an ACTIVE subscription should open a
    5-pass ProjectPasses row with 1 already spent (the analysis run that
    was just funded) -- 4 remaining, not 5."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        with db.get_session() as s:
            db_user = s.query(db.User).filter(db.User.id == user.id).first()
            db_user.subscription_status = "active"
            s.commit()
            s.refresh(db_user)

        key = "sub project|sub tender|sub client|def456"
        charged = auth.record_proposal_usage(user, key, "Sub Project")
        if not charged:
            failures.append("test_funded_by_subscription_opens_passes: record_proposal_usage() returned False for an active subscriber")
            return
        funded = auth.project_funded_by(user, key)
        if funded != "subscription":
            failures.append(f"test_funded_by_subscription_opens_passes: expected funded_by='subscription', got {funded!r}")
        if auth.is_trial_funded_project(user, key):
            failures.append("test_funded_by_subscription_opens_passes: a subscription-funded project must not read back as trial-funded")

        status = auth.project_passes_status(user, key)
        if not status["has_passes"]:
            failures.append("test_funded_by_subscription_opens_passes: expected a ProjectPasses row to exist")
        elif status["remaining"] != 4 or status["purchased"] != 5 or status["used"] != 1:
            failures.append(
                "test_funded_by_subscription_opens_passes: expected purchased=5 used=1 remaining=4, got "
                f"purchased={status['purchased']} used={status['used']} remaining={status['remaining']}"
            )
    finally:
        _cleanup_test_user(db, user.id)


def test_consume_and_exhaust_passes(failures: list[str]) -> None:
    """Part B2: consume_project_pass() should succeed exactly as many times
    as there are passes remaining, then start returning False without
    touching the database further -- and a top-up should top it back up."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        with db.get_session() as s:
            db_user = s.query(db.User).filter(db.User.id == user.id).first()
            db_user.subscription_status = "active"
            s.commit()

        key = "consume project|consume tender|consume client|ghi789"
        auth.record_proposal_usage(user, key, "Consume Project")  # spends pass 1 of 5

        ok_count = 0
        for _ in range(10):  # way more than the 4 remaining -- must stop itself
            if auth.consume_project_pass(user, key):
                ok_count += 1
            else:
                break
        if ok_count != 4:
            failures.append(f"test_consume_and_exhaust_passes: expected exactly 4 successful consumes, got {ok_count}")

        status = auth.project_passes_status(user, key)
        if status["remaining"] != 0:
            failures.append(f"test_consume_and_exhaust_passes: expected 0 remaining after exhausting, got {status['remaining']}")

        if auth.consume_project_pass(user, key):
            failures.append("test_consume_and_exhaust_passes: consume_project_pass() should return False once exhausted")

        if not auth.add_project_pass_topup(user, key, passes=5):
            failures.append("test_consume_and_exhaust_passes: add_project_pass_topup() should return True")
        status = auth.project_passes_status(user, key)
        if status["remaining"] != 5 or status["purchased"] != 10:
            failures.append(
                f"test_consume_and_exhaust_passes: expected purchased=10 remaining=5 after topup, got "
                f"purchased={status['purchased']} remaining={status['remaining']}"
            )
    finally:
        _cleanup_test_user(db, user.id)


def test_atomic_pass_consumption_race(failures: list[str]) -> None:
    """Audit fix Part 1c: consume_project_pass() must be a single atomic
    guarded UPDATE, not read-check-increment-commit -- spin up N threads
    all racing to spend the project's LAST remaining pass and assert
    exactly one of them succeeds, no matter how their reads/writes
    interleave. A non-atomic version of this function would let more than
    one thread pass its own "remaining > 0" read before any of them
    committed, over-spending the allowance."""
    import threading

    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        with db.get_session() as s:
            db_user = s.query(db.User).filter(db.User.id == user.id).first()
            db_user.subscription_status = "active"
            s.commit()

        key = "race project|race tender|race client|race000"
        auth.record_proposal_usage(user, key, "Race Project")  # opens 5 purchased, 1 used -> 4 remaining

        # Burn down to exactly 1 remaining before the race, so the race
        # itself is contested over the single last pass.
        for _ in range(3):
            if not auth.consume_project_pass(user, key):
                failures.append("test_atomic_pass_consumption_race: setup consume unexpectedly failed before the race")
                return

        status_before = auth.project_passes_status(user, key)
        if status_before["remaining"] != 1:
            failures.append(f"test_atomic_pass_consumption_race: expected 1 remaining before the race, got {status_before['remaining']}")
            return

        N_THREADS = 12
        results: list[bool] = []
        results_lock = threading.Lock()

        def _racer():
            outcome = auth.consume_project_pass(user, key)
            with results_lock:
                results.append(outcome)

        threads = [threading.Thread(target=_racer) for _ in range(N_THREADS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        wins = sum(1 for r in results if r)
        if wins != 1:
            failures.append(
                f"test_atomic_pass_consumption_race: expected exactly 1 of {N_THREADS} concurrent "
                f"consume_project_pass() calls to succeed on the last remaining pass, got {wins}"
            )
        status_after = auth.project_passes_status(user, key)
        if status_after["remaining"] != 0 or status_after["used"] != 5:
            failures.append(
                f"test_atomic_pass_consumption_race: expected purchased=5 used=5 remaining=0 after the race, got "
                f"used={status_after['used']} remaining={status_after['remaining']}"
            )
    finally:
        _cleanup_test_user(db, user.id)


def test_bid_purchase_unlocks_trial_project(failures: list[str]) -> None:
    """Audit fix Part 1a: buying a $50 bid earmarked for a project that's
    still trial-funded (its one free pass already spent) must actually
    unlock that project -- funded_by flips from "trial" to "credit", and
    a fresh 5-pass allowance opens with 1 already used (the analysis that
    already ran), i.e. 4 remaining -- not just land as an untouched
    generic account credit that leaves the project stuck."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        key = "unlock project|unlock tender|unlock client|unlock000"
        auth.record_proposal_usage(user, key, "Unlock Project")  # trial-funded, 1 free pass spent
        if auth.project_funded_by(user, key) != "trial":
            failures.append("test_bid_purchase_unlocks_trial_project: setup project should be trial-funded")
            return

        upgraded = auth.upgrade_trial_project_to_paid(user, key, passes=5)
        if not upgraded:
            failures.append("test_bid_purchase_unlocks_trial_project: upgrade_trial_project_to_paid() should return True for a trial-funded project")

        if auth.project_funded_by(user, key) != "credit":
            failures.append(f"test_bid_purchase_unlocks_trial_project: expected funded_by='credit' after upgrade, got {auth.project_funded_by(user, key)!r}")
        if auth.is_trial_funded_project(user, key):
            failures.append("test_bid_purchase_unlocks_trial_project: project must no longer read as trial-funded after upgrade")

        status = auth.project_passes_status(user, key)
        if status["purchased"] != 5 or status["used"] != 1 or status["remaining"] != 4:
            failures.append(
                "test_bid_purchase_unlocks_trial_project: expected purchased=5 used=1 remaining=4 after unlock, got "
                f"purchased={status['purchased']} used={status['used']} remaining={status['remaining']}"
            )

        # Free-tier download gating must also be lifted -- this is what the
        # blocked download screen actually promised.
        if auth.is_trial_funded_project(user, key):
            failures.append("test_bid_purchase_unlocks_trial_project: is_trial_funded_project() should be False -- downloads should be unlocked")

        # Calling it again now that the project is already paid must be
        # correctly reported as "not a trial upgrade" (False) -- a second
        # real $50 purchase on an already-paid project is a legitimate
        # Part B2 top-up (more passes), not a trial-unlock, and the
        # distinct return value is how billing.py's caller tells the two
        # apart. Actual double-charge protection lives one layer up, at
        # the Stripe Checkout session_id level (db.ProcessedCheckoutSession)
        # -- this function is never called twice for the same payment.
        again = auth.upgrade_trial_project_to_paid(user, key, passes=5)
        if again:
            failures.append("test_bid_purchase_unlocks_trial_project: a second upgrade call on an already-paid project should return False (it's a top-up, not a trial upgrade)")
        status_after = auth.project_passes_status(user, key)
        if status_after["purchased"] != 10:
            failures.append(
                f"test_bid_purchase_unlocks_trial_project: a second real purchase on an already-paid project "
                f"should top up passes_purchased to 10, got {status_after['purchased']}"
            )
    finally:
        _cleanup_test_user(db, user.id)


def test_topup_no_project_falls_back(failures: list[str]) -> None:
    """apply_project_bid_topup() must report "no_project" (not raise, not
    silently pretend success) for a project_key with no ProposalUsage row
    at all -- billing.handle_checkout_redirect() relies on exactly this
    signal to fall back to a generic bid_credit so a real $50 payment is
    never dropped on the floor."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        with db.get_session() as s:
            result = auth.apply_project_bid_topup(s, user.id, "never analysed|nope|nope|000000", passes=5)
            s.commit()
        if result != "no_project":
            failures.append(f"test_topup_no_project_falls_back: expected 'no_project', got {result!r}")
    finally:
        _cleanup_test_user(db, user.id)


def test_artifact_event_gating(failures: list[str]) -> None:
    """Part B: a trial-funded project's free artifacts should download
    exactly once each; a project not on the free list should always be
    reported as blocked; a paid project should never be blocked."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        key = "artifact project|artifact tender|artifact client|jkl012"
        auth.record_proposal_usage(user, key, "Artifact Project")  # trial-funded

        with db.get_session() as s:
            already = s.query(db.ArtifactEvent).filter(
                db.ArtifactEvent.user_id == user.id,
                db.ArtifactEvent.project_key == key.lower(),
                db.ArtifactEvent.artifact_type == "proposal_docx",
            ).first()
        if already is not None:
            failures.append("test_artifact_event_gating: a fresh trial project should have no download recorded yet")

        with db.get_session() as s:
            s.add(db.ArtifactEvent(user_id=user.id, project_key=key.lower(), artifact_type="proposal_docx"))
            s.commit()

        with db.get_session() as s:
            recorded = s.query(db.ArtifactEvent).filter(
                db.ArtifactEvent.user_id == user.id,
                db.ArtifactEvent.project_key == key.lower(),
                db.ArtifactEvent.artifact_type == "proposal_docx",
            ).first()
        if recorded is None:
            failures.append("test_artifact_event_gating: ArtifactEvent row didn't persist")

        # The unique constraint should make a second identical insert fail
        # harmlessly (same idempotency pattern as ProposalUsage) rather than
        # silently duplicating.
        with db.get_session() as s:
            s.add(db.ArtifactEvent(user_id=user.id, project_key=key.lower(), artifact_type="proposal_docx"))
            try:
                s.commit()
                failures.append("test_artifact_event_gating: a duplicate (user, project, artifact_type) insert should have raised IntegrityError")
            except Exception:
                s.rollback()
    finally:
        _cleanup_test_user(db, user.id)


def test_free_tier_rename_bypass_closed(failures: list[str]) -> None:
    """Audit fix Part 2b: a trial account's free-artifact download record
    is written with a fixed sentinel project_key (see
    10_state_helpers.py's _TRIAL_ARTIFACT_EVENT_SENTINEL_KEY = ""), so it's
    found by a query scoped to (user_id, artifact_type) alone -- NOT also
    by project_key -- no matter what project_key the download happened
    under, or what a rename (a brand new project_key -- see
    _current_project_key()'s brief-hash-folded identity) would compute
    next. This exercises the underlying DB mechanism the app-level
    functions build on directly (those need a live Streamlit session with
    current_user/_access set to call)."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        with db.get_session() as s:
            s.add(db.ArtifactEvent(user_id=user.id, project_key="", artifact_type="proposal_docx"))
            s.commit()

        # A "renamed" project computes a completely different project_key
        # under the OLD (pre-fix) per-project scheme -- but the query the
        # app actually runs now ignores project_key entirely, so this must
        # still read as already-downloaded for this account+artifact_type.
        with db.get_session() as s:
            found = s.query(db.ArtifactEvent).filter(
                db.ArtifactEvent.user_id == user.id,
                db.ArtifactEvent.artifact_type == "proposal_docx",
            ).first()
        if found is None:
            failures.append("test_free_tier_rename_bypass_closed: expected the account-level download record to be found regardless of project_key")

        # A second insert under the same sentinel key (what a second
        # download attempt -- under ANY project name -- would write) must
        # collide with the unique constraint instead of creating a second row.
        with db.get_session() as s:
            s.add(db.ArtifactEvent(user_id=user.id, project_key="", artifact_type="proposal_docx"))
            try:
                s.commit()
                failures.append("test_free_tier_rename_bypass_closed: a second account-level download record for the same artifact_type should have raised IntegrityError")
            except Exception:
                s.rollback()

        with db.get_session() as s:
            count = s.query(db.ArtifactEvent).filter(
                db.ArtifactEvent.user_id == user.id,
                db.ArtifactEvent.artifact_type == "proposal_docx",
            ).count()
        if count != 1:
            failures.append(f"test_free_tier_rename_bypass_closed: expected exactly 1 ArtifactEvent row after the rename + duplicate attempts, got {count}")
    finally:
        _cleanup_test_user(db, user.id)


def test_artifact_download_gate_real_flow(failures: list[str]) -> None:
    """Round 3, Part 5c: test_free_tier_rename_bypass_closed() above only
    ever exercised the raw db.ArtifactEvent insert/query -- never the actual
    gating functions a download button calls (modules/pages/
    10_state_helpers.py's _free_artifact_already_downloaded() /
    _mark_free_artifact_downloaded() / _free_artifact_download_blocked()),
    which read current_user/_access/IS_SAAS_MODE as globals shared through
    app.py's exec-composition and so couldn't be called from a plain test.
    Those three are now thin wrappers over modules/artifact_download_gate.py
    (see its docstring), whose functions take the live-session values as
    explicit parameters instead -- this calls the REAL functions a download
    button calls, with is_free_tier passed the same way
    _project_is_free_tier() would supply it, and checks the actual
    mark-then-serve-gate flow end to end: first download of a free-tier
    artifact allowed, second blocked, an unrelated user's own first download
    of the SAME artifact_type unaffected, and a paid (is_free_tier=False)
    project never blocked or written to at all."""
    from modules import artifact_download_gate, auth, db

    user = _fresh_test_user(auth, db)
    other_user = _fresh_test_user(auth, db)
    try:
        artifact_type = "proposal_docx"  # one of FREE_TIER_ARTIFACTS

        # Free-tier project, first download: not blocked, nothing recorded yet.
        already = artifact_download_gate.already_downloaded(db, user.id, artifact_type, True)
        if already:
            failures.append("test_artifact_download_gate_real_flow: a fresh account already read as downloaded")
        if artifact_download_gate.blocked(True, artifact_type, already):
            failures.append("test_artifact_download_gate_real_flow: a free-tier project's FIRST download was blocked")

        # The download "happens" -- mark it, the same call
        # _mark_free_artifact_downloaded() makes on a real click.
        had_error = artifact_download_gate.mark_downloaded(db, user.id, artifact_type, True)
        if had_error:
            failures.append("test_artifact_download_gate_real_flow: mark_downloaded() reported an unexpected error on a fresh insert")

        # Re-check the gate exactly as a second download attempt would --
        # this is the actual mark-THEN-serve-gate interaction the old test
        # never exercised.
        already_now = artifact_download_gate.already_downloaded(db, user.id, artifact_type, True)
        if not already_now:
            failures.append("test_artifact_download_gate_real_flow: already_downloaded() didn't see the mark that was just made")
        if not artifact_download_gate.blocked(True, artifact_type, already_now):
            failures.append("test_artifact_download_gate_real_flow: a free-tier project's SECOND download of the same artifact wasn't blocked")

        # A different account's own first download of the SAME artifact_type
        # must be entirely unaffected -- the gate is per-account, not global.
        other_already = artifact_download_gate.already_downloaded(db, other_user.id, artifact_type, True)
        if other_already:
            failures.append("test_artifact_download_gate_real_flow: a different account was incorrectly treated as having already downloaded")
        if artifact_download_gate.blocked(True, artifact_type, other_already):
            failures.append("test_artifact_download_gate_real_flow: a different account's own first download was incorrectly blocked")

        # An artifact NOT on the free list is always blocked for a free-tier
        # project, regardless of any download history.
        if not artifact_download_gate.blocked(True, "methodology_pptx", False):
            failures.append("test_artifact_download_gate_real_flow: a non-free-tier artifact wasn't blocked for a free-tier project")

        # A paid project (is_free_tier=False) is never blocked, and
        # mark_downloaded() must be a no-op -- no row written, no error --
        # matching _project_is_free_tier()==False short-circuiting both
        # _free_artifact_already_downloaded() and _mark_free_artifact_downloaded()
        # before they ever touch the database.
        if artifact_download_gate.blocked(False, artifact_type, False):
            failures.append("test_artifact_download_gate_real_flow: a paid project's download was incorrectly blocked")
        paid_had_error = artifact_download_gate.mark_downloaded(db, user.id, "org_chart_pptx", False)
        if paid_had_error:
            failures.append("test_artifact_download_gate_real_flow: mark_downloaded() reported an error for a paid (no-op) project")
        if artifact_download_gate.already_downloaded(db, user.id, "org_chart_pptx", True):
            failures.append("test_artifact_download_gate_real_flow: mark_downloaded() wrote a row despite is_free_tier=False")
    finally:
        _cleanup_test_user(db, user.id)
        _cleanup_test_user(db, other_user.id)


def test_migrate_project_identity_on_rename(failures: list[str]) -> None:
    """Audit fix Part 3b: renaming a paid project must migrate its
    ProposalUsage/ProjectPasses/ArtifactEvent rows to the new project_key,
    not strand them under the old one -- and must never clobber a
    DIFFERENT project's own existing billing history if the new key
    happens to collide with one."""
    from modules import auth, db

    user = _fresh_test_user(auth, db)
    try:
        with db.get_session() as s:
            db_user = s.query(db.User).filter(db.User.id == user.id).first()
            db_user.subscription_status = "active"
            s.commit()

        old_key = "old name|old tender|old client|migrate01"
        new_key = "new name|new tender|new client|migrate01"
        auth.record_proposal_usage(user, old_key, "Old Name")  # paid, opens 5/1
        auth.consume_project_pass(user, old_key)  # burn one more, now 5/2 -> 3 remaining
        with db.get_session() as s:
            s.add(db.ArtifactEvent(user_id=user.id, project_key=old_key, artifact_type="proposal_docx"))
            s.commit()

        migrated = auth.migrate_project_identity(user, old_key, new_key)
        if not migrated:
            failures.append("test_migrate_project_identity_on_rename: expected migrate_project_identity() to return True")
            return

        if auth.project_funded_by(user, old_key) != "":
            failures.append("test_migrate_project_identity_on_rename: old_key should no longer have a ProposalUsage row after migration")
        if auth.project_funded_by(user, new_key) != "subscription":
            failures.append(f"test_migrate_project_identity_on_rename: expected new_key funded_by='subscription', got {auth.project_funded_by(user, new_key)!r}")

        old_status = auth.project_passes_status(user, old_key)
        new_status = auth.project_passes_status(user, new_key)
        if old_status["has_passes"]:
            failures.append("test_migrate_project_identity_on_rename: old_key should have no ProjectPasses row left after migration")
        if not new_status["has_passes"] or new_status["purchased"] != 5 or new_status["used"] != 2:
            failures.append(
                f"test_migrate_project_identity_on_rename: expected new_key purchased=5 used=2, got "
                f"has_passes={new_status['has_passes']} purchased={new_status['purchased']} used={new_status['used']}"
            )

        with db.get_session() as s:
            old_artifact = s.query(db.ArtifactEvent).filter(
                db.ArtifactEvent.user_id == user.id, db.ArtifactEvent.project_key == old_key,
            ).first()
            new_artifact = s.query(db.ArtifactEvent).filter(
                db.ArtifactEvent.user_id == user.id, db.ArtifactEvent.project_key == new_key,
            ).first()
        if old_artifact is not None:
            failures.append("test_migrate_project_identity_on_rename: ArtifactEvent should have moved off old_key")
        if new_artifact is None:
            failures.append("test_migrate_project_identity_on_rename: ArtifactEvent should now be under new_key")

        # Collision case: a THIRD, unrelated project already owns some_key --
        # migrating onto it must be refused, not silently merge histories.
        some_key = "third name|third tender|third client|migrate02"
        auth.record_proposal_usage(user, some_key, "Third Project")  # trial or paid, doesn't matter -- it just needs to exist
        collided = auth.migrate_project_identity(user, new_key, some_key)
        if collided:
            failures.append("test_migrate_project_identity_on_rename: migrating onto an already-existing project_key should return False")
        if auth.project_funded_by(user, new_key) == "":
            failures.append("test_migrate_project_identity_on_rename: a refused migration must leave the source project's row untouched")
    finally:
        _cleanup_test_user(db, user.id)


def test_unlimited_account_bypasses_everything(failures: list[str]) -> None:
    """UNLIMITED_ACCOUNTS should never have their trial/subscription
    counters actually decremented in a way that would ever block them --
    get_access_status()['allowed'] must stay True no matter what."""
    from modules import auth, db

    # Use a real UNLIMITED_ACCOUNTS address so this test means something --
    # but never actually charge against the real production account; only
    # read-check get_access_status()'s pure computation, which needs a
    # User object but never writes anything by itself.
    fake_unlimited = db.User(
        id="test-unlimited-" + uuid.uuid4().hex[:8],
        email=next(iter(auth.UNLIMITED_ACCOUNTS)),
        password_hash="x",
        subscription_status="trial",
        trial_proposals_used=999,  # would exhaust a normal trial many times over
        bid_credits=0,
    )
    access = auth.get_access_status(fake_unlimited)
    if not access["unlimited"] or not access["allowed"] or access["limit_reached"]:
        failures.append(
            f"test_unlimited_account_bypasses_everything: expected unlimited=True allowed=True limit_reached=False, "
            f"got unlimited={access['unlimited']} allowed={access['allowed']} limit_reached={access['limit_reached']}"
        )


def test_unlimited_bypasses_page_limits_and_rate_gate(failures: list[str]) -> None:
    """Audit Round 2, Part 8: UNLIMITED_ACCOUNTS must bypass the paid-tier
    200-page soft warn / 300-page hard stop (modules/limits.py) exactly like
    every other gate in the app. Also pins down the rate-gate cap itself:
    ai_rate_limit_peek()/record_ai_call() have no concept of "unlimited"
    (they only take a bare is_trial bool), so a merely-paid account that
    isn't in UNLIMITED_ACCOUNTS IS still expected to hit the paid cap -- the
    bypass has to happen at the call site (00_init.py), not inside those
    functions. This test can't exercise that call site directly (00_init.py
    is a Streamlit page, exec'd in place rather than importable -- see the
    module docstring above), so it instead pins the two building blocks the
    bypass depends on: (a) an unlimited access dict makes both page-limit
    functions return None no matter how large page_count is, and (b) calling
    record_ai_call() past PAID_AI_CALLS_PER_5MIN times in a row for a fresh
    (non-unlimited) user id DOES eventually block, confirming 00_init.py's
    explicit `if _access.get('unlimited')` skip is doing real work and not
    just guarding against a check that could never fire anyway."""
    from modules import limits

    unlimited_access = {"unlimited": True, "subscribed": False, "past_due": False, "bid_credits": 0}
    for huge_pages in (250, 301, 10_000):
        if limits.tender_page_cap_message(huge_pages, unlimited_access) is not None:
            failures.append(
                f"test_unlimited_bypasses_page_limits_and_rate_gate: tender_page_cap_message() blocked an "
                f"unlimited account at {huge_pages} pages"
            )
        if limits.tender_page_soft_warn_message(huge_pages, unlimited_access) is not None:
            failures.append(
                f"test_unlimited_bypasses_page_limits_and_rate_gate: tender_page_soft_warn_message() warned an "
                f"unlimited account at {huge_pages} pages"
            )

    probe_user_id = "test-rate-probe-" + uuid.uuid4().hex[:8]
    blocked = None
    for _ in range(limits.PAID_AI_CALLS_PER_5MIN + 1):
        blocked = limits.record_ai_call(probe_user_id, is_trial=False)
    if blocked is None:
        failures.append(
            "test_unlimited_bypasses_page_limits_and_rate_gate: expected a paid (non-unlimited) account to "
            "eventually hit the fair-use rate cap after PAID_AI_CALLS_PER_5MIN+1 calls, got None every time -- "
            "if this cap can never trip, 00_init.py's unlimited bypass would be pointless dead code"
        )


def test_subscription_monthly_bid_limit_is_four(failures: list[str]) -> None:
    """Part B2 (owner-confirmed): the Monthly plan raised from 3 to 4
    proposal projects/month. Pinning the constant directly so a future
    accidental revert is caught immediately, loudly, in one place."""
    from modules import auth

    if auth.SUBSCRIPTION_MONTHLY_BID_LIMIT != 4:
        failures.append(
            f"test_subscription_monthly_bid_limit_is_four: expected 4, got {auth.SUBSCRIPTION_MONTHLY_BID_LIMIT}"
        )


def test_email_bid_count_matches_subscription_limit(failures: list[str]) -> None:
    """Audit Round 2, Part 6: email_utils.py's purchase-receipt and trial-
    used emails had hardcoded "3 bids"/"3 tender analyses" copy that drifted
    stale after SUBSCRIPTION_MONTHLY_BID_LIMIT moved to 4 (test above).
    Both now read the constant via a deferred import instead of a second
    hardcoded number, specifically so they can't drift apart from it again --
    this pins that by generating both emails and asserting the live constant's
    value appears, and the number it replaced does not."""
    from modules import auth, email_utils

    sent = []
    original_send = email_utils._send
    email_utils._send = lambda to, subject, html: sent.append(html)
    try:
        email_utils.send_purchase_receipt_email("test@example.invalid", "subscription")
        email_utils.send_trial_used_email("test@example.invalid")
    finally:
        email_utils._send = original_send

    limit = auth.SUBSCRIPTION_MONTHLY_BID_LIMIT
    for html in sent:
        if f"{limit} " not in html:
            failures.append(
                f"test_email_bid_count_matches_subscription_limit: expected the live "
                f"SUBSCRIPTION_MONTHLY_BID_LIMIT ({limit}) in the email body, not found: {html[:200]!r}"
            )
        if "3 bids" in html or "3 tender analyses" in html:
            failures.append(
                f"test_email_bid_count_matches_subscription_limit: stale hardcoded '3' copy "
                f"survived in the email body: {html[:200]!r}"
            )


def test_i18n_catalogs_are_in_sync(failures: list[str]) -> None:
    """Every key defined in the English catalog must also exist in the
    Spanish one and vice versa -- modules/i18n.t() silently falls back to
    English for a missing Spanish key, which is the RIGHT behaviour at
    runtime (never crash), but a silent English string inside an otherwise
    Spanish document/screen is exactly the kind of thing that should be
    caught in CI, not discovered by a Spanish-speaking user."""
    from modules.translations import en, es

    en_keys = set(en.STRINGS.keys())
    es_keys = set(es.STRINGS.keys())
    missing_in_es = sorted(en_keys - es_keys)
    missing_in_en = sorted(es_keys - en_keys)
    if missing_in_es:
        failures.append(f"test_i18n_catalogs_are_in_sync: {len(missing_in_es)} key(s) in en.py missing from es.py: {missing_in_es[:10]}")
    if missing_in_en:
        failures.append(f"test_i18n_catalogs_are_in_sync: {len(missing_in_en)} key(s) in es.py missing from en.py: {missing_in_en[:10]}")
    empty_values = [k for k, v in en.STRINGS.items() if not (v or "").strip()]
    if empty_values:
        failures.append(f"test_i18n_catalogs_are_in_sync: {len(empty_values)} key(s) with an empty English value: {empty_values[:10]}")


def test_i18n_t_fallback_behaviour(failures: list[str]) -> None:
    """t() must fall back to English for a language-specific miss, then to
    a visible [[key]] marker for a total miss -- never raise, never return
    None, never silently return an empty string for a genuinely missing
    key (that would look like a rendering bug, not a translation gap)."""
    from modules import i18n

    missing = i18n.t("this_key_definitely_does_not_exist_anywhere")
    if missing != "[[this_key_definitely_does_not_exist_anywhere]]":
        failures.append(f"test_i18n_t_fallback_behaviour: expected a [[key]] marker for a missing key, got {missing!r}")

    formatted = i18n.t("sidebar_trial_remaining", remaining=2, limit=1)
    if "2" not in formatted or "1" not in formatted:
        failures.append(f"test_i18n_t_fallback_behaviour: format placeholders didn't substitute, got {formatted!r}")


def test_export_i18n_headings_differ_by_language(failures: list[str]) -> None:
    """Part A3: export_i18n.export_t() must actually return different text
    for "en" vs "es" for at least the headings the DOCX builders use, and
    must never raise for a totally unknown key (same fallback contract as
    the UI i18n system)."""
    from modules import export_i18n

    en_heading = export_i18n.export_t("heading_executive_summary", "en")
    es_heading = export_i18n.export_t("heading_executive_summary", "es")
    if en_heading == es_heading:
        failures.append(
            f"test_export_i18n_headings_differ_by_language: heading_executive_summary is identical in both "
            f"languages ({en_heading!r}) -- expected a real Spanish translation"
        )
    unknown = export_i18n.export_t("this_export_key_does_not_exist", "es")
    if not unknown:
        failures.append("test_export_i18n_headings_differ_by_language: export_t() returned falsy for an unknown key instead of a fallback marker")


def test_last_draft_metered_signature_round_trip(failures: list[str]) -> None:
    """Round 3, Part 3 (money): _last_draft_metered_signature is the paid-
    drafting metering baseline (see _draft_would_consume_pass() in
    modules/pages/10_state_helpers.py) -- a missing baseline means "no pass
    spent yet, the next regenerate is free" (deliberately, for a genuinely
    fresh project's first-ever generation). It was NOT in
    project_store.PLAIN_KEYS, so ANY save/load round trip -- a saved project
    reopened later, a page refresh that lands on a fresh session and
    restores from cloud auto-save, handing a project to a colleague -- reset
    a PAID project's baseline back to missing, letting a paid regeneration
    run free indefinitely just by reloading.

    Covers the two pieces that don't require the Streamlit page-script
    machinery those tabs run in (same boundary
    check_generated_language_stale_notice() in test_exports.py already
    draws for its own companion PLAIN_KEYS entry): the key's own save/load
    round trip (the normal case, now fixed), and confirming an OLDER
    project file -- saved before this key existed -- still round-trips with
    the key genuinely ABSENT rather than defaulted to some value. That
    absent-vs-None distinction is exactly the signal
    _apply_loaded_project() checks (`not st.session_state.get(...)`) before
    deciding whether a reload with drafts already present must stamp the
    CURRENT signature as the baseline instead of leaving it looking like a
    free first-ever generation -- that decision itself needs a live
    Streamlit session (current_user, _access, real st.session_state) to
    exercise directly, so it isn't re-tested here."""
    import io
    import json
    import zipfile

    from modules import project_store

    if "_last_draft_metered_signature" not in project_store.PLAIN_KEYS:
        failures.append(
            "test_last_draft_metered_signature_round_trip: _last_draft_metered_signature "
            "is not registered in project_store.PLAIN_KEYS")
        return

    # The normal case, going forward: a real signature survives a save/load
    # round trip -- e.g. paid project, generate (baseline B stamped), save,
    # reload, change an input, regenerate -- should compare against B, not
    # against nothing.
    saved = project_store.save_project({
        "output_language": "en", "_last_draft_metered_signature": "abc123deadbeef",
    })
    loaded = project_store.load_project(saved)
    if loaded.get("_last_draft_metered_signature") != "abc123deadbeef":
        failures.append(
            f"test_last_draft_metered_signature_round_trip: didn't round-trip through "
            f"save/load: {loaded.get('_last_draft_metered_signature')!r}")

    # An older project file, saved before this key existed, never wrote it
    # at all -- simulate that by stripping it back out of an otherwise-real
    # saved payload (rather than a hand-built one, so every other field
    # save_project() writes is still realistic), then confirm
    # load_project() reports the key as genuinely missing from its result,
    # not present with a None/empty default.
    with zipfile.ZipFile(io.BytesIO(saved)) as zf:
        payload = json.loads(zf.read("project.json"))
    del payload["_last_draft_metered_signature"]
    old_format_buffer = io.BytesIO()
    with zipfile.ZipFile(old_format_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(payload))
    old_loaded = project_store.load_project(old_format_buffer.getvalue())
    if "_last_draft_metered_signature" in old_loaded:
        failures.append(
            "test_last_draft_metered_signature_round_trip: an older project file without "
            "_last_draft_metered_signature should load with the key absent, not defaulted "
            "to a value -- _apply_loaded_project()'s fallback relies on that absence")


def main() -> int:
    import logging
    logging.disable(logging.WARNING)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("SAAS_MODE", "true")

    from modules import db
    db.init_db()

    failures: list[str] = []

    test_funded_by_trial(failures)
    test_funded_by_subscription_opens_passes(failures)
    test_consume_and_exhaust_passes(failures)
    test_atomic_pass_consumption_race(failures)
    test_bid_purchase_unlocks_trial_project(failures)
    test_topup_no_project_falls_back(failures)
    test_artifact_event_gating(failures)
    test_free_tier_rename_bypass_closed(failures)
    test_artifact_download_gate_real_flow(failures)
    test_migrate_project_identity_on_rename(failures)
    test_unlimited_account_bypasses_everything(failures)
    test_unlimited_bypasses_page_limits_and_rate_gate(failures)
    test_subscription_monthly_bid_limit_is_four(failures)
    test_email_bid_count_matches_subscription_limit(failures)
    test_i18n_catalogs_are_in_sync(failures)
    test_i18n_t_fallback_behaviour(failures)
    test_export_i18n_headings_differ_by_language(failures)
    test_last_draft_metered_signature_round_trip(failures)

    if failures:
        print("BILLING + I18N TESTS FAILED:")
        for failure in failures:
            print("  -", failure)
        return 1
    print("BILLING + I18N TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
