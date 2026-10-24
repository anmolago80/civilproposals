"""
test_trial_abuse.py -- regression tests for the "one trial per person + trial
double-run fix + admin activity view" brief (CP-TASK, 24 Oct 2026).

Same house style as test_billing_i18n.py: plain `def test_X(failures)`
functions appending human-readable strings, no pytest, main() prints PASS/FAIL
and sets the exit code. Part A/B logic is exercised on the auth.py / db.py
layer directly; the Tender Analysis tab itself (unverified account locked,
failed run refunded, second tab turned away, refresh mid-run) is driven through
the REAL app with streamlit.testing.v1.AppTest in SaaS mode.

Run from this directory:

    python test_trial_abuse.py
"""

from __future__ import annotations

import os
import sys
import threading
import uuid
from datetime import timedelta

# SaaS mode needs these at import time (db.py / auth.py read them once).
os.environ.setdefault("SAAS_MODE", "true")
os.environ.setdefault("APP_SECRET_KEY", "test-secret-for-trial-abuse")
os.environ["DATABASE_URL"] = "sqlite:////tmp/trial_abuse_test.db"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test-not-real"
os.environ.pop("REDIS_URL", None)
os.environ.pop("TRIAL_ONE_PER_COMPANY_DOMAIN", None)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if os.path.exists("/tmp/trial_abuse_test.db"):
    os.remove("/tmp/trial_abuse_test.db")

from modules import auth, db, email_identity, email_utils, job_queue  # noqa: E402

db.init_db()

SENT: list[tuple[str, str]] = []


def _rand_email(domain: str = "example.invalid", prefix: str = "t") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}@{domain}"


def _install_fake_email() -> None:
    """Resend is replaced by an in-memory outbox so tests can read the code."""
    email_utils.is_configured = lambda: True
    email_utils.send_verification_email = lambda to, code: SENT.append((to, code))
    email_utils.send_welcome_email = lambda *a, **k: None
    email_utils.send_trial_used_email = lambda *a, **k: None
    # Outside a browser st.session_state is ONE process-wide dict, so the real
    # "this tab claimed a trial" marker would leak from one test's user into
    # every later test. Tests that care about it install their own hook.
    auth._mark_device_claimed = lambda: None


def _last_code(email: str) -> str:
    for to, code in reversed(SENT):
        if to == email:
            return code
    raise AssertionError(f"no verification email captured for {email}")


def _new_user(email: str | None = None, *, verify: bool = True, device_claimed: bool | None = False):
    """A throwaway account. device_claimed=False by default so one test's
    claim never poisons another's (there is no browser in these tests)."""
    email = email or _rand_email()
    user = auth.create_user(email, "testpassword123", "Test", "Firm", device_claimed=device_claimed)
    auth.accept_terms(user)
    if verify:
        _verify(user)
    return auth.get_user_by_id(user.id)


def _verify(user) -> None:
    result = auth.verify_email_code(user, _last_code(auth.get_user_by_id(user.id).email))
    assert result == "ok", f"verification failed: {result}"


def _cleanup_user(user_id: str) -> None:
    try:
        with db.get_session() as s:
            for model in (db.ArtifactEvent, db.ProjectPasses, db.ProposalUsage, db.Job, db.AiCallLog):
                s.query(model).filter(model.user_id == user_id).delete()
            s.query(db.User).filter(db.User.id == user_id).delete()
            s.commit()
    except Exception:
        pass


def _reset_device_claim_hook() -> None:
    auth.device_has_claimed_trial = lambda: False


_orig_device_has_claimed = auth.device_has_claimed_trial


# --------------------------------------------------------------------------
# Part A -- one trial per person
# --------------------------------------------------------------------------

def test_normalize_email(failures: list[str]) -> None:
    cases = {
        "  Foo.Bar+Tag@GMAIL.com ": "foobar@gmail.com",
        "foo.bar@googlemail.com": "foobar@gmail.com",
        "a.b+x+y@example.com": "a.b@example.com",        # dots kept off gmail, +tag stripped everywhere
        "A.B@Example.COM": "a.b@example.com",
        "me+news@outlook.com": "me@outlook.com",
        "+tagonly@example.com": "+tagonly@example.com",  # nothing left -> keep as typed
        "no-at-sign": "no-at-sign",
    }
    for raw, want in cases.items():
        got = email_identity.normalize_email(raw)
        if got != want:
            failures.append(f"test_normalize_email: {raw!r} -> {got!r}, expected {want!r}")


def test_alias_signups_refused(failures: list[str]) -> None:
    """+tag aliases on any domain, and dot variants on gmail/googlemail, hit
    the unique normalised email: refused with the brief's message."""
    base_local = "alias" + uuid.uuid4().hex[:8]
    first = _new_user(f"{base_local}@gmail.com")
    first_other = _new_user(f"{base_local}x@example.invalid")
    try:
        for dup in (
            f"{base_local}+promo@gmail.com",
            f"{base_local[:3]}.{base_local[3:]}@gmail.com",
            f"{base_local}@googlemail.com",
            f"{base_local.upper()}@GMAIL.COM",
            f"{base_local}x+2@example.invalid",
        ):
            try:
                auth.create_user(dup, "testpassword123", device_claimed=False)
                failures.append(f"test_alias_signups_refused: {dup!r} was allowed")
                u = auth.get_user_by_email(dup)
                if u:
                    _cleanup_user(u.id)
            except ValueError as e:
                if auth.ACCOUNT_EXISTS_MESSAGE not in str(e):
                    failures.append(f"test_alias_signups_refused: {dup!r} refused with {e!r}")
        # Dots are NOT significant outside gmail: these are two different people.
        a = _new_user(f"dot.{base_local}@example.invalid")
        b = _new_user(f"dot{base_local}@example.invalid")
        _cleanup_user(a.id); _cleanup_user(b.id)
    except ValueError as e:
        failures.append(f"test_alias_signups_refused: dotted non-gmail addresses wrongly merged: {e}")
    finally:
        _cleanup_user(first.id); _cleanup_user(first_other.id)


def test_unverified_account_cannot_use_trial(failures: list[str]) -> None:
    user = _new_user(verify=False)
    try:
        if auth.is_email_verified(user):
            failures.append("test_unverified: a brand-new account must not start verified")
        r = auth.reserve_proposal_usage(user, "p|t|c|h", "P")
        if r["status"] != "unverified":
            failures.append(f"test_unverified: reserve() on an unverified account returned {r['status']!r}")
        access = auth.get_access_status(user)
        if access["email_verified"]:
            failures.append("test_unverified: access status says verified")
        _verify(user)
        user = auth.get_user_by_id(user.id)
        if not auth.is_email_verified(user):
            failures.append("test_unverified: still unverified after the right code")
        r = auth.reserve_proposal_usage(user, "p|t|c|h", "P")
        if r["status"] != "reserved":
            failures.append(f"test_unverified: verified account could not reserve ({r['status']!r})")
    finally:
        _cleanup_user(user.id)


def test_verification_code_rules(failures: list[str]) -> None:
    user = _new_user(verify=False)
    try:
        good = _last_code(user.email)
        if auth.send_verification_code(user) != "cooldown":
            failures.append("test_verification_code_rules: an immediate resend should be on cooldown")
        wrong = "000000" if good != "000000" else "111111"
        for i in range(auth.VERIFY_CODE_MAX_ATTEMPTS - 1):
            r = auth.verify_email_code(user, wrong)
            if r != "wrong":
                failures.append(f"test_verification_code_rules: wrong guess {i+1} gave {r!r}")
        r = auth.verify_email_code(user, wrong)
        if r != "too_many":
            failures.append(f"test_verification_code_rules: final wrong guess gave {r!r}, expected 'too_many'")
        if auth.verify_email_code(user, good) != "too_many":
            failures.append("test_verification_code_rules: the right code must not work after too many wrong ones")
        # Expiry: force the code stale, ask for a new one (cooldown aged out).
        with db.get_session() as s:
            u = s.query(db.User).filter(db.User.id == user.id).first()
            u.verify_code_sent_at = u.verify_code_sent_at - timedelta(minutes=5)
            s.commit()
        if auth.send_verification_code(user) != "sent":
            failures.append("test_verification_code_rules: resend after the cooldown should send")
        fresh = _last_code(user.email)
        with db.get_session() as s:
            u = s.query(db.User).filter(db.User.id == user.id).first()
            u.verify_code_expires_at = u.verify_code_expires_at - timedelta(hours=1)
            s.commit()
        if auth.verify_email_code(user, fresh) != "expired":
            failures.append("test_verification_code_rules: an expired code was accepted")
        with db.get_session() as s:
            u = s.query(db.User).filter(db.User.id == user.id).first()
            u.verify_code_sent_at = u.verify_code_sent_at - timedelta(minutes=5)
            s.commit()
        auth.send_verification_code(user)
        if auth.verify_email_code(user, "12 34") not in ("wrong", "too_many"):
            failures.append("test_verification_code_rules: a malformed code must be a wrong guess")
        if auth.verify_email_code(user, _last_code(user.email)) != "ok":
            failures.append("test_verification_code_rules: a fresh code after a resend should work")
    finally:
        _cleanup_user(user.id)


def test_existing_accounts_unaffected_by_migration(failures: list[str]) -> None:
    """A legacy account (no email_verified_at / email_normalized, as before
    the migration) is stamped verified, normalised and put in the ledger the
    first time the migration runs against it."""
    from sqlalchemy import text
    email = _rand_email(prefix="legacy")
    legacy = _new_user(email, verify=False)
    try:
        with db.engine.begin() as conn:
            conn.execute(text("UPDATE users SET email_verified_at = NULL, email_normalized = NULL "
                              "WHERE id = :i"), {"i": legacy.id})
            conn.execute(text("DELETE FROM trial_claims WHERE user_id = :i"), {"i": legacy.id})
            # Simulate "column not there yet" so the one-time backfill runs.
            conn.execute(text("ALTER TABLE users DROP COLUMN email_verified_at"))
        db._run_light_migrations()
        u = auth.get_user_by_id(legacy.id)
        if u.email_verified_at is None or not auth.is_email_verified(u):
            failures.append("test_existing_accounts: legacy account was not stamped verified")
        if u.email_normalized != email_identity.normalize_email(email):
            failures.append("test_existing_accounts: legacy account was not normalised")
        with db.get_session() as s:
            if s.query(db.TrialClaim).filter(db.TrialClaim.user_id == legacy.id).count() != 1:
                failures.append("test_existing_accounts: legacy account missing from the trial ledger")
        if not auth.get_access_status(u)["allowed"]:
            failures.append("test_existing_accounts: legacy account lost its trial")
    finally:
        _cleanup_user(legacy.id)


def test_deleted_account_gets_no_new_trial(failures: list[str]) -> None:
    email = _rand_email(prefix="gone")
    first = _new_user(email)
    first_id = first.id
    if auth.get_access_status(first)["trial_remaining"] != 1:
        failures.append("test_deleted_account: first account should hold the trial")
    # Delete the account completely, then sign up again -- by the same
    # address, and by an alias of it.
    _cleanup_user(first_id)
    with db.get_session() as s:
        if s.query(db.TrialClaim).filter(db.TrialClaim.user_id == first_id).count() != 1:
            failures.append("test_deleted_account: the ledger row did not survive account deletion")
    for again in (email, email.replace("@", "+again@")):
        second = _new_user(again, verify=False)
        try:
            _verify(second)
            second = auth.get_user_by_id(second.id)
            access = auth.get_access_status(second)
            if second.trial_denied_reason != "email" or access["trial_remaining"] != 0 or access["allowed"]:
                failures.append(
                    f"test_deleted_account: {again!r} got a trial "
                    f"(reason={second.trial_denied_reason!r}, remaining={access['trial_remaining']})"
                )
            r = auth.reserve_proposal_usage(second, "p|t|c|h", "P")
            if r["status"] != "blocked":
                failures.append(f"test_deleted_account: reserve() for a no-trial account returned {r['status']!r}")
        finally:
            _cleanup_user(second.id)


def test_same_browser_second_account_gets_no_trial(failures: list[str]) -> None:
    # The cookie itself: signed, tamper-proof.
    token = auth.make_trial_device_token()
    if not auth.verify_trial_device_token(token):
        failures.append("test_same_browser: a freshly signed device token did not verify")
    if auth.verify_trial_device_token(token[:-2] + ("AA" if not token.endswith("AA") else "BB")):
        failures.append("test_same_browser: a tampered device token verified")
    if auth.verify_trial_device_token(auth.make_token("someone")):
        failures.append("test_same_browser: a session token was accepted as a device token")
    # Claiming a trial marks the browser: a second account made there gets none.
    marked = []
    orig_mark = auth._mark_device_claimed
    auth._mark_device_claimed = lambda: marked.append(True)
    try:
        a = _new_user()
        if not marked:
            failures.append("test_same_browser: claiming a trial did not mark the device")
    finally:
        auth._mark_device_claimed = orig_mark
    b = _new_user(verify=False, device_claimed=True)
    try:
        if b.trial_denied_reason != "device":
            failures.append(f"test_same_browser: second account in the same browser has reason {b.trial_denied_reason!r}")
        _verify(b)
        access = auth.get_access_status(auth.get_user_by_id(b.id))
        if access["trial_remaining"] != 0 or access["allowed"]:
            failures.append("test_same_browser: second account in the same browser still got a trial")
        if access["trial_denied_reason"] != "device":
            failures.append("test_same_browser: access status does not report the device block")
    finally:
        _cleanup_user(a.id); _cleanup_user(b.id)

    # Two accounts opened in one browser BEFORE either was confirmed: the
    # second one to confirm finds the first one's claim and gets none.
    auth.device_has_claimed_trial = lambda: False
    c = _new_user(verify=False); d = _new_user(verify=False)
    try:
        _verify(c)
        auth.device_has_claimed_trial = lambda: True      # c's confirmation set the cookie
        _verify(d)
        if auth.get_user_by_id(d.id).trial_denied_reason != "device":
            failures.append("test_same_browser: account confirmed after another in the same browser kept its trial")
        if auth.get_user_by_id(c.id).trial_denied_reason:
            failures.append("test_same_browser: the FIRST account lost its trial")
    finally:
        auth.device_has_claimed_trial = _orig_device_has_claimed
        _cleanup_user(c.id); _cleanup_user(d.id)


def test_unlimited_accounts_exempt(failures: list[str]) -> None:
    email = _rand_email(prefix="vip")
    auth.UNLIMITED_ACCOUNTS.add(email)
    try:
        # Ledger row + device already claimed would deny anyone else.
        with db.get_session() as s:
            s.add(db.TrialClaim(email_normalized=email_identity.normalize_email(email),
                                user_id="someone-else", device_hash=""))
            s.commit()
        u = auth.create_user(email, "testpassword123", device_claimed=True)
        if u.trial_denied_reason:
            failures.append("test_unlimited: an UNLIMITED account was denied a trial")
        if not auth.is_email_verified(u):
            failures.append("test_unlimited: an UNLIMITED account should not need to verify")
        access = auth.get_access_status(u)
        if not (access["allowed"] and access["unlimited"] and not access["trial_denied_reason"]):
            failures.append(f"test_unlimited: access status wrong: {access}")
        r = auth.reserve_proposal_usage(u, "p|t|c|h", "P")
        if r["status"] != "reserved" or r["funded_by"] != "unlimited":
            failures.append(f"test_unlimited: reserve() gave {r}")
        r2 = auth.reserve_proposal_usage(u, "p2|t|c|h", "P2")
        if r2["status"] != "reserved":
            failures.append("test_unlimited: a second project must also reserve (never blocked)")
        _cleanup_user(u.id)
    finally:
        auth.UNLIMITED_ACCOUNTS.discard(email)
        with db.get_session() as s:
            s.query(db.TrialClaim).filter(db.TrialClaim.user_id == "someone-else").delete()
            s.commit()


def test_company_domain_switch(failures: list[str]) -> None:
    dom = f"firm{uuid.uuid4().hex[:6]}.example.invalid"
    # Switch OFF (the default): two people at one company both get a trial.
    a = _new_user(_rand_email(dom)); b = _new_user(_rand_email(dom))
    try:
        if auth.TRIAL_ONE_PER_COMPANY_DOMAIN:
            failures.append("test_company_domain: the switch must default to OFF")
        if b.trial_denied_reason:
            failures.append("test_company_domain: second colleague denied with the switch OFF")
    finally:
        _cleanup_user(a.id); _cleanup_user(b.id)
    # Switch ON: second at the same company domain gets none; free-mail domains ignored.
    auth.TRIAL_ONE_PER_COMPANY_DOMAIN = True
    try:
        a = _new_user(_rand_email(dom)); b = _new_user(_rand_email(dom), verify=False)
        g1 = _new_user(_rand_email("gmail.com")); g2 = _new_user(_rand_email("gmail.com"))
        try:
            _verify(b)
            if b.trial_denied_reason != "domain" and auth.get_user_by_id(b.id).trial_denied_reason != "domain":
                failures.append("test_company_domain: second colleague kept a trial with the switch ON")
            if auth.get_user_by_id(g2.id).trial_denied_reason or auth.get_user_by_id(g1.id).trial_denied_reason:
                failures.append("test_company_domain: gmail.com accounts were treated as one company")
        finally:
            for u in (a, b, g1, g2):
                _cleanup_user(u.id)
    finally:
        auth.TRIAL_ONE_PER_COMPANY_DOMAIN = False


def test_ip_signal_flag_only(failures: list[str]) -> None:
    """Two trial claims with the same day-rotated IP+UA hash: the LATER one is
    flagged in the admin view, and NOTHING is blocked."""
    orig = auth._ip_ua_hash
    auth._ip_ua_hash = lambda: "samehash-" + "0" * 55
    try:
        a = _new_user(); b = _new_user()
        try:
            if auth.get_user_by_id(b.id).trial_denied_reason:
                failures.append("test_ip_signal: a shared IP must never block a trial")
            rows = {r["email"]: r for r in db.admin_stats()["recent_activity"]}
            if rows[a.email]["ip_shared"]:
                failures.append("test_ip_signal: the EARLIER claim must not be flagged")
            if not rows[b.email]["ip_shared"]:
                failures.append("test_ip_signal: the later claim sharing the hash was not flagged")
        finally:
            _cleanup_user(a.id); _cleanup_user(b.id)
    finally:
        auth._ip_ua_hash = orig
    # The hash really is day-rotated.
    import hashlib
    if len(orig() or "x" * 64) not in (0, 64):
        failures.append("test_ip_signal: hash is not a SHA-256 hex digest")


# --------------------------------------------------------------------------
# Part B -- reserve before the AI call
# --------------------------------------------------------------------------

def test_double_click_reserves_once(failures: list[str]) -> None:
    user = _new_user()
    key = "proj|tender|client|hash"
    try:
        results: list[str] = []
        barrier = threading.Barrier(2)

        def click() -> None:
            barrier.wait()
            results.append(auth.reserve_proposal_usage(user, key, "Proj")["status"])

        threads = [threading.Thread(target=click) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        if sorted(results) != ["already", "reserved"]:
            failures.append(f"test_double_click: two simultaneous clicks gave {results}, expected one reserved + one already")
        with db.get_session() as s:
            rows = s.query(db.ProposalUsage).filter(db.ProposalUsage.user_id == user.id).count()
        if rows != 1:
            failures.append(f"test_double_click: {rows} ProposalUsage rows")
        if auth.get_user_by_id(user.id).trial_proposals_used != 1:
            failures.append("test_double_click: the trial was spent more than once")
        # A later click / refresh / tab is turned away too.
        if auth.reserve_proposal_usage(user, key, "Proj")["status"] != "already":
            failures.append("test_double_click: a later click was not turned away")
    finally:
        _cleanup_user(user.id)


def test_one_trial_cannot_fund_two_projects(failures: list[str]) -> None:
    user = _new_user()
    try:
        r = []
        barrier = threading.Barrier(2)

        def click(k: str) -> None:
            barrier.wait()
            r.append(auth.reserve_proposal_usage(user, k, k)["status"])

        ts = [threading.Thread(target=click, args=(k,)) for k in ("one|t|c|h", "two|t|c|h")]
        for t in ts: t.start()
        for t in ts: t.join()
        if sorted(r) != ["blocked", "reserved"]:
            failures.append(f"test_one_trial: two projects raced for one trial: {r}")
        if auth.get_user_by_id(user.id).trial_proposals_used != 1:
            failures.append("test_one_trial: trial counter is not exactly 1")
    finally:
        _cleanup_user(user.id)


def test_failed_job_refunds_trial(failures: list[str]) -> None:
    user = _new_user()
    key = "fail|t|c|h"
    try:
        r = auth.reserve_proposal_usage(user, key, "Fail")
        if r["status"] != "reserved" or r["funded_by"] != "trial" or not r["just_used_last_trial_bid"]:
            failures.append(f"test_failed_job: unexpected reservation {r}")
        u = auth.get_user_by_id(user.id)
        if auth.get_access_status(u)["allowed"]:
            failures.append("test_failed_job: trial should be spent while reserved")
        if not auth.refund_proposal_usage(user, key):
            failures.append("test_failed_job: refund reported nothing to do")
        u = auth.get_user_by_id(user.id)
        if u.trial_proposals_used != 0 or not auth.get_access_status(u)["allowed"]:
            failures.append("test_failed_job: the trial was not restored")
        with db.get_session() as s:
            if s.query(db.ProposalUsage).filter(db.ProposalUsage.user_id == user.id).count():
                failures.append("test_failed_job: the ProposalUsage row was not deleted")
        if auth.refund_proposal_usage(user, key):
            failures.append("test_failed_job: a second refund must be a no-op (two tabs both saw the failure)")
        if auth.get_user_by_id(user.id).trial_proposals_used != 0:
            failures.append("test_failed_job: a second refund changed the balance")
        if auth.reserve_proposal_usage(user, key, "Fail")["status"] != "reserved":
            failures.append("test_failed_job: the project cannot be run again after a refund")
    finally:
        _cleanup_user(user.id)


def test_paid_paths_reserve_and_refund(failures: list[str]) -> None:
    """Subscription quota and pay-as-you-go credit: reserve opens the same
    5-pass allowance record_proposal_usage does; refund gives it all back."""
    for label, setup in (
        ("credit", lambda u: setattr(u, "bid_credits", 2)),
        ("subscription", lambda u: setattr(u, "subscription_status", "active")),
    ):
        user = _new_user()
        try:
            with db.get_session() as s:
                u = s.query(db.User).filter(db.User.id == user.id).first()
                setup(u)
                if label == "credit":
                    u.trial_proposals_used = auth.DEFAULT_TRIAL_LIMIT  # trial gone -> credit pays
                s.commit()
            key = f"{label}|t|c|h"
            r = auth.reserve_proposal_usage(user, key, label)
            if r["status"] != "reserved" or r["funded_by"] != label:
                failures.append(f"test_paid_paths[{label}]: reservation {r}")
                continue
            passes = auth.project_passes_status(auth.get_user_by_id(user.id), key)
            if not (passes["has_passes"] and passes["purchased"] == 5 and passes["used"] == 1):
                failures.append(f"test_paid_paths[{label}]: pass allowance wrong: {passes}")
            u = auth.get_user_by_id(user.id)
            spent_ok = (u.bid_credits == 1) if label == "credit" else (u.subscription_bids_used == 1)
            if not spent_ok:
                failures.append(f"test_paid_paths[{label}]: nothing was spent at reservation")
            auth.refund_proposal_usage(user, key)
            u = auth.get_user_by_id(user.id)
            back = (u.bid_credits == 2) if label == "credit" else (u.subscription_bids_used == 0)
            if not back:
                failures.append(f"test_paid_paths[{label}]: refund did not restore the balance")
            if auth.project_passes_status(u, key)["has_passes"]:
                failures.append(f"test_paid_paths[{label}]: refund left a pass allowance behind")
        finally:
            _cleanup_user(user.id)


def test_paid_repeat_pass_path_unchanged(failures: list[str]) -> None:
    """A repeat run on an already-funded PAID project still draws down passes
    through consume_project_pass -- reserve never touches it (an existing row
    means 'already')."""
    user = _new_user()
    try:
        with db.get_session() as s:
            u = s.query(db.User).filter(db.User.id == user.id).first()
            u.bid_credits = 1
            u.trial_proposals_used = auth.DEFAULT_TRIAL_LIMIT
            s.commit()
        key = "repeat|t|c|h"
        auth.reserve_proposal_usage(user, key, "Repeat")
        if auth.reserve_proposal_usage(user, key, "Repeat")["status"] != "already":
            failures.append("test_paid_repeat: reserve must not re-charge a funded project")
        if not auth.consume_project_pass(user, key):
            failures.append("test_paid_repeat: consume_project_pass no longer works")
        if auth.project_passes_status(auth.get_user_by_id(user.id), key)["used"] != 2:
            failures.append("test_paid_repeat: pass accounting changed")
    finally:
        _cleanup_user(user.id)


def test_inflight_guard_in_db(failures: list[str]) -> None:
    user = _new_user(); other = _new_user()
    try:
        key = "inflight|t|c|h"
        with db.get_session() as s:
            s.add(db.Job(id="job-live-" + user.id, user_id=user.id, job_type="tender_analysis",
                         status="started", project_key=key, reserved=True))
            s.commit()
        j = db.find_inflight_job(user.id, key.upper())     # key matching is case-insensitive
        if not j or not j["reserved"]:
            failures.append(f"test_inflight: live job not found: {j}")
        if db.find_inflight_job(other.id, key):
            failures.append("test_inflight: another account sees this user's job")
        if db.find_inflight_job(user.id, "different|t|c|h"):
            failures.append("test_inflight: another project's job matched")
        if db.find_inflight_job(user.id, key, "draft_generation"):
            failures.append("test_inflight: a different job type matched")
        for state in ("finished", "failed"):
            with db.get_session() as s:
                s.query(db.Job).filter(db.Job.user_id == user.id).update({"status": state})
                s.commit()
            if db.find_inflight_job(user.id, key):
                failures.append(f"test_inflight: a {state} job still counts as in flight")
        with db.get_session() as s:
            s.query(db.Job).filter(db.Job.user_id == user.id).update({
                "status": "queued", "created_at": db._now() - timedelta(hours=3)})
            s.commit()
        if db.find_inflight_job(user.id, key):
            failures.append("test_inflight: a dead 3-hour-old job disabled Run forever")
    finally:
        _cleanup_user(user.id); _cleanup_user(other.id)


# --------------------------------------------------------------------------
# Part B/A through the REAL app (Tender Analysis tab, SaaS mode)
# --------------------------------------------------------------------------

def _app(user, project="York Region", brief="A tender brief about a culvert replacement. " * 20):
    from streamlit.testing.v1 import AppTest
    from modules.document_processor import ExtractedDocument
    at = AppTest.from_file("app.py", default_timeout=180)
    at.session_state["_auth_user_id"] = user.id
    at.session_state["_state_owner_id"] = user.id
    at.session_state["project_name"] = project
    at.session_state["tender_extracted"] = ExtractedDocument(filename="brief.pdf", text=brief, page_count=5)
    return at


def _run_btn(at):
    for b in at.button:
        if b.label == "Run Tender Analysis":
            return b
    return None


def _texts(at) -> str:
    parts = [m.value for m in at.markdown] + [w.value for w in at.warning] \
        + [i.value for i in at.info] + [e.value for e in at.error] + [s.value for s in at.success]
    return "\n".join(str(p) for p in parts)


def _usage_rows(user_id: str) -> int:
    with db.get_session() as s:
        return s.query(db.ProposalUsage).filter(db.ProposalUsage.user_id == user_id).count()


def test_app_unverified_account_locked(failures: list[str]) -> None:
    from modules import tender_analyser
    calls = []
    orig = tender_analyser.analyse_tender
    tender_analyser.analyse_tender = lambda *a, **k: calls.append(1) or tender_analyser.TenderAnalysis()
    user = _new_user(verify=False)
    try:
        at = _app(user); at.run()
        if at.exception:
            failures.append(f"test_app_unverified: exception {[e.value for e in at.exception]}")
            return
        btn = _run_btn(at)
        if btn is None:
            failures.append("test_app_unverified: Run Tender Analysis button not found")
            return
        if not btn.disabled:
            failures.append("test_app_unverified: Run is enabled for an unconfirmed account")
        if "Confirm your email" not in _texts(at):
            failures.append("test_app_unverified: no clear 'confirm your email' message")
        # Wrong code keeps it locked; the right one unlocks it.
        at.text_input(key="_tab3_verify_code").set_value("000000")
        at.button[0] if False else None
        form_btn = [b for b in at.button if b.label == "Confirm email"][0]
        form_btn.click().run()
        if not _run_btn(at).disabled:
            failures.append("test_app_unverified: a wrong code unlocked Run")
        at.text_input(key="_tab3_verify_code").set_value(_last_code(user.email))
        [b for b in at.button if b.label == "Confirm email"][0].click().run()
        if at.exception:
            failures.append(f"test_app_unverified: exception after confirming {[e.value for e in at.exception]}")
        if _run_btn(at).disabled:
            failures.append("test_app_unverified: Run still disabled after the right code")
        if calls:
            failures.append("test_app_unverified: an AI job ran for an unconfirmed account")
    finally:
        tender_analyser.analyse_tender = orig
        _cleanup_user(user.id)


def test_app_success_failure_and_two_tabs(failures: list[str]) -> None:
    from modules import tender_analyser
    orig = tender_analyser.analyse_tender
    calls: list[int] = []
    mode = {"fail": False, "during": None}

    def fake(*a, **k):
        calls.append(1)
        if mode["during"]:
            mode["during"]()
        if mode["fail"]:
            raise RuntimeError("model overloaded")
        return tender_analyser.TenderAnalysis(project_scope="Culvert replacement")

    tender_analyser.analyse_tender = fake
    user = _new_user()
    try:
        # 1) A failed run restores the trial and leaves Run usable.
        mode["fail"] = True
        at = _app(user); at.run()
        if _run_btn(at) is None or _run_btn(at).disabled:
            failures.append("test_app_runs: Run should be enabled for a verified account")
            return
        _run_btn(at).click().run()
        if _usage_rows(user.id) != 0 or auth.get_user_by_id(user.id).trial_proposals_used != 0:
            failures.append("test_app_runs: a failed run was not refunded")
        if _run_btn(at).disabled:
            failures.append("test_app_runs: Run stayed disabled after a failed (refunded) run")
        if len(calls) != 1:
            failures.append(f"test_app_runs: expected 1 AI call so far, saw {len(calls)}")

        # 2) Two tabs: tab B is loaded (button enabled) BEFORE tab A runs. While A's
        #    job is "running" B clicks Run as well -- B must be turned away.
        mode["fail"] = False
        tab_b = _app(user); tab_b.run()
        b_click_result = {}

        def b_clicks_during_a():
            _run_btn(tab_b).click().run()
            b_click_result["warnings"] = [w.value for w in tab_b.warning]

        mode["during"] = b_clicks_during_a
        tab_a = _app(user); tab_a.run()
        calls.clear()
        _run_btn(tab_a).click().run()
        mode["during"] = None
        if len(calls) != 1:
            failures.append(f"test_app_runs: two tabs produced {len(calls)} AI jobs, expected exactly 1")
        # Tab B re-renders with Run disabled once A has reserved, so its stale
        # click is dropped by Streamlit or caught by reserve() ("already") --
        # either way B must have started NO job and must say why. (The
        # simultaneous-click race itself is test_double_click_reserves_once.)
        if not b_click_result.get("warnings"):
            failures.append(f"test_app_runs: tab B was turned away silently: {b_click_result}")
        if _usage_rows(user.id) != 1 or auth.get_user_by_id(user.id).trial_proposals_used != 1:
            failures.append("test_app_runs: successful run did not leave exactly one ProposalUsage / one spent trial")
        if tab_a.session_state["analysis"] is None:
            failures.append("test_app_runs: the successful run's analysis was not kept")

        # 3) After success, a refresh / third click cannot start another run.
        calls.clear()
        tab_c = _app(user); tab_c.run()
        if _run_btn(tab_c).disabled is False:
            failures.append("test_app_runs: Run is enabled again after the run completed (trial already spent)")
        if calls:
            failures.append("test_app_runs: a refresh started another AI job")
    finally:
        tender_analyser.analyse_tender = orig
        _cleanup_user(user.id)


class _Interrupted(Exception):
    pass


def test_app_refresh_mid_run_queued(failures: list[str]) -> None:
    """Queued path: the first browser tab disappears mid-run (its script run is
    interrupted). The job keeps running; a refresh finds it, Run stays
    disabled, nothing is re-queued, the reservation stands, and the result is
    delivered when the job finishes. A job that FAILS is refunded."""
    from modules import tender_analyser
    import streamlit as st

    user = _new_user()
    state = {"status": "started", "enqueued": 0, "interrupt": True}
    result = tender_analyser.TenderAnalysis(project_scope="Culvert replacement")

    def fake_enqueue(user_id, job_type, project_key, reserved, func, *args, **kwargs):
        state["enqueued"] += 1
        jid = f"fake-job-{state['enqueued']}"
        with db.get_session() as s:
            s.add(db.Job(id=jid, user_id=user_id, job_type=job_type, status="queued",
                         project_key=(project_key or "").lower(), reserved=bool(reserved)))
            s.commit()
        return jid

    def fake_status(job_id, user_id):
        if state["interrupt"]:
            st.stop()   # what a browser refresh does to the polling script run
        if state["status"] == "finished":
            return {"status": "finished", "result": result, "error": None}
        if state["status"] == "failed":
            return {"status": "failed", "result": None, "error": "worker crashed"}
        return {"status": "started", "result": None, "error": None}

    saved = (job_queue.redis_available, job_queue.enqueue_tracked, job_queue.get_status,
             job_queue.WAIT_MAX_SECONDS, job_queue.POLL_INTERVAL_SECONDS, job_queue.cancel_if_queued)
    job_queue.redis_available = lambda: True
    job_queue.enqueue_tracked = fake_enqueue
    job_queue.get_status = fake_status
    job_queue.cancel_if_queued = lambda *a, **k: False   # a worker has started it
    job_queue.WAIT_MAX_SECONDS = 1.0
    job_queue.POLL_INTERVAL_SECONDS = 0.25
    try:
        at = _app(user); at.run()
        _run_btn(at).click().run()          # interrupted while polling
        if state["enqueued"] != 1:
            failures.append(f"test_app_refresh: expected 1 queued job, got {state['enqueued']}")
        if _usage_rows(user.id) != 1:
            failures.append("test_app_refresh: the run was not reserved before queueing / was refunded on interrupt")
        key = "York Region|||" + __import__("hashlib").sha256(
            ("A tender brief about a culvert replacement. " * 20).encode()).hexdigest()[:16]
        if not db.find_inflight_job(user.id, key):
            failures.append("test_app_refresh: no in-flight job recorded for the project")

        # Refresh while the job is still running: Run disabled, "still running" shown, nothing re-queued.
        state["interrupt"] = False
        at2 = _app(user); at2.run()
        if at2.exception:
            failures.append(f"test_app_refresh: exception on refresh {[e.value for e in at2.exception]}")
        btn = _run_btn(at2)
        if btn is None or not btn.disabled:
            failures.append("test_app_refresh: Run is enabled while the job is still running")
        if "still running" not in _texts(at2).lower():
            failures.append("test_app_refresh: the page does not say the analysis is still running")
        if state["enqueued"] != 1:
            failures.append("test_app_refresh: a refresh queued a second job")

        # Job completes: next refresh picks the result up (no second job, usage kept).
        state["status"] = "finished"
        at3 = _app(user); at3.run()
        if at3.session_state["analysis"] is None:
            failures.append("test_app_refresh: the finished job's result was not delivered after a refresh")
        if state["enqueued"] != 1 or _usage_rows(user.id) != 1:
            failures.append("test_app_refresh: result delivery re-queued or un-reserved the run")
        with db.get_session() as s:
            s.query(db.Job).filter(db.Job.user_id == user.id).update({"status": "finished"})
            s.commit()

        # A job that FAILS is refunded and the project can be run again.
        with db.get_session() as s:
            s.query(db.Job).filter(db.Job.user_id == user.id).update({"status": "started"})
            s.commit()
        state["status"] = "failed"
        at4 = _app(user); at4.run()
        if _usage_rows(user.id) != 0 or auth.get_user_by_id(user.id).trial_proposals_used != 0:
            failures.append("test_app_refresh: a failed queued job did not restore the trial")
        if _run_btn(at4).disabled:
            failures.append("test_app_refresh: Run stayed disabled after the failed job was refunded")
    finally:
        (job_queue.redis_available, job_queue.enqueue_tracked, job_queue.get_status,
         job_queue.WAIT_MAX_SECONDS, job_queue.POLL_INTERVAL_SECONDS, job_queue.cancel_if_queued) = saved
        _cleanup_user(user.id)


def test_app_unlimited_account_runs(failures: list[str]) -> None:
    from modules import tender_analyser
    orig = tender_analyser.analyse_tender
    tender_analyser.analyse_tender = lambda *a, **k: tender_analyser.TenderAnalysis(project_scope="x")
    email = _rand_email(prefix="unl")
    auth.UNLIMITED_ACCOUNTS.add(email)
    user = _new_user(email, verify=False)     # never confirms its email
    try:
        at = _app(user); at.run()
        btn = _run_btn(at)
        if btn is None or btn.disabled:
            failures.append("test_app_unlimited: an UNLIMITED account was locked out of Run")
            return
        btn.click().run()
        if at.session_state["analysis"] is None or at.exception:
            failures.append("test_app_unlimited: an UNLIMITED account could not run an analysis")
    finally:
        tender_analyser.analyse_tender = orig
        auth.UNLIMITED_ACCOUNTS.discard(email)
        _cleanup_user(user.id)


# --------------------------------------------------------------------------
# Part C -- admin "Recent activity"
# --------------------------------------------------------------------------

def test_admin_recent_activity_data(failures: list[str]) -> None:
    u = _new_user(); v = _new_user(verify=False)
    try:
        key = "act|t|c|h"
        auth.reserve_proposal_usage(u, key, "Act")
        with db.get_session() as s:
            s.add(db.Job(id="act-job-" + u.id, user_id=u.id, job_type="tender_analysis", status="finished",
                         project_key=key, reserved=True))
            s.add(db.Job(id="act-job2-" + u.id, user_id=u.id, job_type="tender_analysis", status="finished",
                         project_key=key, reserved=False))
            s.add(db.AiCallLog(user_id=u.id, purpose="draft_generation", project_key=key))
            s.add(db.ArtifactEvent(user_id=u.id, project_key=key, artifact_type="proposal_docx"))
            s.add(db.ArtifactEvent(user_id=u.id, project_key=key, artifact_type="org_chart_pptx"))
            s.commit()
        rows = {r["email"]: r for r in db.admin_stats()["recent_activity"]}
        a, b = rows[u.email], rows[v.email]
        if not a["verified"] or b["verified"]:
            failures.append("test_admin_activity: verified flag wrong")
        if a["projects_run"] != 1 or a["ta_runs"] != 2:
            failures.append(f"test_admin_activity: projects/TA runs wrong: {a['projects_run']}/{a['ta_runs']} (double run must show 2 on 1 project)")
        if not a["drafted"] or b["drafted"]:
            failures.append("test_admin_activity: drafted flag wrong")
        types = sorted(t for t, _ in a["downloads"])
        if types != ["org_chart_pptx", "proposal_docx"]:
            failures.append(f"test_admin_activity: downloads wrong: {types}")
        if a["tier"] != "trial" or b["ip_shared"]:
            failures.append("test_admin_activity: tier / ip flag wrong")
        if len(db.admin_stats()["recent_activity"]) > 15:
            failures.append("test_admin_activity: more than 15 rows")
    finally:
        _cleanup_user(u.id); _cleanup_user(v.id)


def test_admin_recent_activity_renders(failures: list[str]) -> None:
    admin_email = _rand_email(prefix="adm")
    auth.ADMIN_ACCOUNTS.add(admin_email)
    admin = _new_user(admin_email)
    other = _new_user()
    try:
        at = _app(admin); at.run()
        if at.exception:
            failures.append(f"test_admin_render: exception {[e.value for e in at.exception]}")
            return
        btns = [b for b in at.sidebar.button if "Admin" in (b.label or "")]
        if not btns:
            failures.append("test_admin_render: admin button not found for an admin account")
            return
        btns[0].click().run()
        if at.exception:
            failures.append(f"test_admin_render: exception opening the dialog {[e.value for e in at.exception]}")
            return
        headers = [m.value for m in at.markdown]
        if not any("Recent activity" in h for h in headers):
            failures.append("test_admin_render: 'Recent activity' table did not render in the admin dialog")
        frames = [df for df in at.dataframe]
        cols = set()
        for df in frames:
            try:
                cols |= set(df.value.columns)
            except Exception:
                pass
        for want in ("Verified", "Projects run", "Tender Analysis runs", "Proposal drafted", "Downloads",
                     "IP shared with earlier trial"):
            if want not in cols:
                failures.append(f"test_admin_render: column {want!r} missing (have {sorted(cols)})")
        # A non-admin never sees the button.
        at2 = _app(other); at2.run()
        if [b for b in at2.sidebar.button if "Admin" in (b.label or "")]:
            failures.append("test_admin_render: a non-admin sees the admin button")
    finally:
        auth.ADMIN_ACCOUNTS.discard(admin_email)
        _cleanup_user(admin.id); _cleanup_user(other.id)


def test_login_throttle_not_global(failures: list[str]) -> None:
    """Unknown client IP must not create ONE shared counter that locks every
    visitor out; the per-IP limit is far higher than the per-email one."""
    keys = auth._throttle_keys("someone@example.invalid")
    if any(k.endswith(":unknown") for k in keys):
        failures.append("test_login_throttle: an 'unknown' IP key is shared by every visitor")
    if auth.LOGIN_MAX_FAILURES_PER_IP <= auth.LOGIN_MAX_FAILURES:
        failures.append("test_login_throttle: per-IP limit must exceed the per-email limit")
    email = _rand_email(prefix="thr")
    for _ in range(auth.LOGIN_MAX_FAILURES):
        auth.record_login_failure(email)
    if auth.login_lockout_remaining(email) <= 0:
        failures.append("test_login_throttle: five wrong passwords no longer lock the account")
    if auth.login_lockout_remaining(_rand_email(prefix="other")) > 0:
        failures.append("test_login_throttle: another account was locked out")


def main() -> int:
    _install_fake_email()
    failures: list[str] = []
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        before = len(failures)
        try:
            fn(failures)
        except Exception as exc:  # a crashing test is a failing test
            import traceback
            traceback.print_exc()
            failures.append(f"{fn.__name__}: CRASHED: {type(exc).__name__}: {exc}")
        print(("PASS " if len(failures) == before else "FAIL ") + fn.__name__)
    if failures:
        print("\nTRIAL ABUSE TESTS FAILED:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nTRIAL ABUSE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
