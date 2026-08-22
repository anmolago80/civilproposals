"""
auth.py

Account signup/login, session persistence (via a signed browser cookie), and
free-trial / subscription access gating for the CivilProposals SaaS build.

Design notes:
  - Passwords are hashed with bcrypt, never stored or logged in plain text.
  - "Logged in" is proven by a signed, timestamped token (itsdangerous)
    stored in a browser cookie -- Streamlit has no built-in multi-user
    session concept, so without a cookie every browser refresh would log
    the user out. The cookie is READ server-side via st.context.cookies
    (the real HTTP request headers -- synchronous, no round trip) and
    WRITTEN client-side via a tiny inline <script>document.cookie=...
    injected through components.v1.html (see _write_cookie_js()) -- not
    via a third-party custom component. That's not an arbitrary choice:
    extra_streamlit_components.CookieManager was tried first and measured
    to silently never write the cookie at all on any network with real
    latency, because it has to fetch and boot a separate JS bundle in its
    own iframe before it can do anything, and that fetch loses the race
    against Streamlit's own next script rerun often enough to make
    "signed in" not survive a single page refresh in production. The
    inline-script approach has no separate bundle to fetch -- the script
    is already part of the iframe's initial content -- so there's nothing
    for a slow network to race.
  - The trial is usage-based (N distinct proposals), not time-based, per
    product decision: 1 free bid on sign up, then pay per bid or subscribe
    monthly (see the landing page pricing section) -- the app no longer
    asks each user for their own AI provider key in SAAS_MODE (see app.py).
    Both real tiers are wired to Stripe: the $120/month subscription
    (STRIPE_PRICE_ID, mode="subscription", unlimited while active) and the
    $50/bid pay-as-you-go (STRIPE_BID_PRICE_ID, mode="payment", each
    purchase adds one db.User.bid_credits, spent by record_proposal_usage
    only after the free trial runs out -- see billing.py).
  - Nothing in this module trusts st.session_state alone for "is this user
    allowed in" -- session_state is rebuilt from the verified cookie token
    on every rerun, so a user can't fake being logged in by manipulating
    client-side state.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import bcrypt
import streamlit as st
import streamlit.components.v1 as components
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from modules import db, email_utils, i18n

APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "").strip()
if not APP_SECRET_KEY:
    # Fine for local dev (sessions just won't survive a process restart);
    # Railway deployment MUST set a real APP_SECRET_KEY env var, or every
    # deploy invalidates every logged-in user's cookie.
    APP_SECRET_KEY = "dev-only-insecure-secret-change-me"

# Same default/behaviour as billing.APP_BASE_URL -- duplicated rather than
# imported from there on purpose, so auth.py doesn't have to depend on
# billing.py (which pulls in the stripe SDK) just for one constant.
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")

COOKIE_NAME = "civilproposals_session"
COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 days

_serializer = URLSafeTimedSerializer(APP_SECRET_KEY, salt="civilproposals-auth")

# A separate serializer (distinct salt) for password-reset links -- kept
# apart from the session-cookie serializer above so the two token kinds can
# never be confused for one another even though they share the same
# underlying secret key.
_reset_serializer = URLSafeTimedSerializer(APP_SECRET_KEY, salt="civilproposals-pwreset")
RESET_TOKEN_MAX_AGE_SECONDS = 60 * 60  # 1 hour


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Signed session tokens
# ---------------------------------------------------------------------------

def make_token(user_id: str) -> str:
    return _serializer.dumps({"uid": user_id})


def verify_token(token: str) -> str | None:
    """Returns the user_id if the token is valid and not expired, else None."""
    if not token:
        return None
    try:
        data = _serializer.loads(token, max_age=COOKIE_MAX_AGE_SECONDS)
        return data.get("uid")
    except (BadSignature, SignatureExpired, Exception):
        return None


# ---------------------------------------------------------------------------
# Password-reset tokens -- separate from the session tokens above (see
# _reset_serializer). Used by the emailed reset link (see
# request_password_reset() / render_password_reset_screen()).
# ---------------------------------------------------------------------------

def _password_fingerprint(password_hash: str) -> str:
    """A short, one-way fingerprint of a user's CURRENT bcrypt hash, folded
    into every reset token issued for them. This is what makes a reset
    token single-use without needing any extra DB column or "used" table:
    the moment the token is actually used (reset_password() below), the
    user's password_hash changes, so this fingerprint no longer matches --
    the same token (or any other still-unexpired token issued before that
    point, e.g. from clicking an old email twice) fails verification on
    its next use. Truncated SHA-256, not the raw bcrypt hash itself -- no
    reason to put even a hash of the password hash's full value in a URL
    that might end up in a browser history or a proxy log."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def make_reset_token(user: db.User) -> str:
    return _reset_serializer.dumps({"uid": user.id, "pwh": _password_fingerprint(user.password_hash)})


def verify_reset_token(token: str) -> db.User | None:
    """Returns the User the token was issued for if it's valid, not
    expired (see RESET_TOKEN_MAX_AGE_SECONDS), AND not already used --
    otherwise None. Deliberately doesn't distinguish these failure reasons
    to the caller (see render_password_reset_screen(), which shows one
    generic "invalid or expired" message either way) -- there's no benefit
    to a stranger knowing which one it was."""
    if not token:
        return None
    try:
        data = _reset_serializer.loads(token, max_age=RESET_TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, Exception):
        return None
    user = get_user_by_id(data.get("uid", ""))
    if not user:
        return None
    if _password_fingerprint(user.password_hash) != data.get("pwh"):
        return None
    return user


# ---------------------------------------------------------------------------
# Cookie read/write
# ---------------------------------------------------------------------------

def _get_cookie_token():
    # st.context.cookies is the actual Cookie header Streamlit's server
    # received on this request -- populated synchronously before any
    # Python runs, on every full page load. No component, no iframe, no
    # round trip, so no "hasn't reported back yet" state to handle.
    # Available since Streamlit 1.35, confirmed present in the 1.60.0
    # build this app runs.
    return st.context.cookies.get(COOKIE_NAME)


def _is_secure_request() -> bool:
    """True if this request reached us over HTTPS -- determines whether the
    cookie can carry the Secure flag. Railway (and any standard reverse
    proxy) terminates TLS and forwards X-Forwarded-Proto, so the Python
    process itself always sees plain HTTP; this header is the only way to
    tell. Defaults to False (no Secure flag) when the header is missing,
    which is what local dev over http://localhost needs -- a Secure cookie
    is silently refused by the browser on a non-HTTPS origin."""
    try:
        return (st.context.headers.get("X-Forwarded-Proto", "") or "").lower() == "https"
    except Exception:
        return False


def _write_cookie_js(cookie_str: str) -> None:
    # A minimal, dependency-free inline script, delivered as part of the
    # iframe's own initial content (components.v1.html's srcdoc) -- nothing
    # extra to fetch over the network before it can run. This replaces an
    # earlier approach built on extra_streamlit_components.CookieManager,
    # a full custom Streamlit component with its own separate JS bundle:
    # measured directly (browser cookie jar inspected before/after, with
    # Chrome DevTools Protocol network throttling standing in for a slow or
    # high-latency real connection) to simply never write the cookie at all
    # once any real network latency was involved -- not delayed, never.
    # That bundle has to be fetched and booted inside its own iframe before
    # any of its JS can run, and that fetch reliably lost the race against
    # Streamlit's own next script rerun (the login flow's rerun right after
    # log_in(), which tears down not-yet-mounted components) on anything
    # slower than localhost. This inline script has no separate bundle to
    # race for -- it's already sitting in the iframe's srcdoc the instant
    # the iframe exists -- so there's nothing left for a slow network to
    # lose.
    components.html(f"<script>document.cookie = {json.dumps(cookie_str)};</script>", height=0)


def _set_cookie_token(token: str) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=COOKIE_MAX_AGE_SECONDS)
    expires_str = expires_at.strftime("%a, %d %b %Y %H:%M:%S GMT")
    parts = [f"{COOKIE_NAME}={token}", f"expires={expires_str}", "path=/", "SameSite=Lax"]
    if _is_secure_request():
        parts.append("Secure")
    _write_cookie_js("; ".join(parts))


def _clear_cookie_token() -> None:
    parts = [f"{COOKIE_NAME}=", "expires=Thu, 01 Jan 1970 00:00:00 GMT", "path=/", "SameSite=Lax"]
    if _is_secure_request():
        parts.append("Secure")
    cookie_str = "; ".join(parts)
    # Deliberately NOT using _write_cookie_js() here (unlike _set_cookie_token
    # above) -- logout needs one extra thing login doesn't: a REAL browser
    # navigation reload, not just Streamlit's own st.rerun(). Reported bug:
    # after clicking "Log out", the top-right "My Proposals" / "Proposal
    # Library" / "Project Reference Library" actions bar (a keyed
    # st.container in app.py, pinned via `position: fixed` CSS so it can
    # float over the whole viewport) kept visually appearing on top of the
    # login screen even though the script run that renders the login screen
    # never re-declares that container at all. st.rerun() only replays the
    # Python script and diffs the resulting element tree -- it doesn't
    # guarantee the browser discards every previously-mounted DOM node, and
    # a keyed container pinned outside normal document flow is exactly the
    # kind of element that can survive a diff it should have been removed
    # by. A full page reload sidesteps the question of exactly why the diff
    # missed it -- a fresh navigation always starts from a completely empty
    # DOM, the same guarantee manually closing and reopening the tab gives.
    # window.parent.location.reload(), not window.location.reload(): this
    # script runs inside the sandboxed iframe components.html() mounts it
    # in, so window.location here refers to that iframe, not the actual app
    # page -- reloading it would do nothing visible. The cookie clear is set
    # first, synchronously, in the same script, so the fresh page load that
    # follows sees an already-cleared cookie rather than racing it.
    components.html(
        f"<script>document.cookie = {json.dumps(cookie_str)}; "
        f"window.parent.location.reload();</script>",
        height=0,
    )


# ---------------------------------------------------------------------------
# Login attempt throttling
#
# 5 failed attempts (per email OR per client IP) inside a 15-minute window
# locks that email/IP out of the login form for 15 minutes, with a clear
# message saying so. Counters live in Redis (same REDIS_URL the job queue
# uses) so they're shared across the web process's threads AND survive a
# redeploy mid-attack; when Redis isn't configured or is down, a
# per-process in-memory fallback keeps the throttle working locally rather
# than silently switching off. Every failure path here degrades to "allow
# the attempt" -- a rate limiter outage must never lock legitimate users
# out of their accounts.
# ---------------------------------------------------------------------------

LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 15 * 60
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60

_LOGIN_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
_login_redis_client = None
# In-memory fallback: {key: (failure_count, window_expiry_ts, lockout_expiry_ts)}
_login_failures_local: dict[str, tuple[int, float, float]] = {}


def _login_redis():
    """Lazy Redis client with short timeouts -- None when unavailable."""
    global _login_redis_client
    if not _LOGIN_REDIS_URL:
        return None
    if _login_redis_client is None:
        try:
            import redis as _redis
            _login_redis_client = _redis.Redis.from_url(
                _LOGIN_REDIS_URL, socket_timeout=2, socket_connect_timeout=2,
            )
        except Exception:
            return None
    return _login_redis_client


def _client_ip() -> str:
    """Best-effort client IP. Railway (and any standard reverse proxy)
    forwards the real client address in X-Forwarded-For; the first entry is
    the original client. Falls back to a fixed placeholder -- which
    effectively makes the IP counter a global one -- rather than failing."""
    try:
        forwarded = (st.context.headers.get("X-Forwarded-For", "") or "").strip()
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    except Exception:
        pass
    return "unknown"


def _throttle_keys(email: str) -> list[str]:
    email_norm = (email or "").strip().lower()
    email_digest = hashlib.sha256(email_norm.encode("utf-8")).hexdigest()[:24]
    return [f"cp:loginfail:email:{email_digest}", f"cp:loginfail:ip:{_client_ip()}"]


def login_lockout_remaining(email: str) -> int:
    """Seconds until this email/IP may try logging in again -- 0 when not
    locked out. Checks both the per-email and per-IP lockouts and returns
    the longer one."""
    remaining = 0
    r = _login_redis()
    for key in _throttle_keys(email):
        lock_key = key + ":lock"
        if r is not None:
            try:
                ttl = r.ttl(lock_key)
                if ttl and ttl > 0:
                    remaining = max(remaining, int(ttl))
                continue
            except Exception:
                pass  # fall through to local
        entry = _login_failures_local.get(key)
        if entry:
            _, _, lock_until = entry
            now = datetime.now(timezone.utc).timestamp()
            if lock_until > now:
                remaining = max(remaining, int(lock_until - now))
    return remaining


def record_login_failure(email: str) -> int:
    """Registers one failed login attempt against both the email and the
    client IP. Returns how many attempts remain before lockout (0 means the
    lockout just started). Never raises."""
    remaining_attempts = LOGIN_MAX_FAILURES
    r = _login_redis()
    now = datetime.now(timezone.utc).timestamp()
    for key in _throttle_keys(email):
        count = None
        if r is not None:
            try:
                pipe = r.pipeline()
                pipe.incr(key)
                pipe.expire(key, LOGIN_FAILURE_WINDOW_SECONDS)
                count = int(pipe.execute()[0])
                if count >= LOGIN_MAX_FAILURES:
                    r.set(key + ":lock", "1", ex=LOGIN_LOCKOUT_SECONDS)
            except Exception:
                count = None
        if count is None:
            # Local fallback (per-process). Reset the window if it expired.
            prev_count, window_until, lock_until = _login_failures_local.get(key, (0, 0.0, 0.0))
            if window_until < now:
                prev_count = 0
            count = prev_count + 1
            new_lock_until = lock_until
            if count >= LOGIN_MAX_FAILURES:
                new_lock_until = now + LOGIN_LOCKOUT_SECONDS
            _login_failures_local[key] = (count, now + LOGIN_FAILURE_WINDOW_SECONDS, new_lock_until)
            # Opportunistic cleanup so this dict can't grow unboundedly.
            if len(_login_failures_local) > 5000:
                _login_failures_local.clear()
        remaining_attempts = min(remaining_attempts, max(0, LOGIN_MAX_FAILURES - count))
    return remaining_attempts


def clear_login_failures(email: str) -> None:
    """Called on a successful login -- a legitimate user who finally got
    their password right shouldn't stay one typo away from lockout. The
    lockout keys themselves are deliberately NOT cleared: a success during
    an active lockout shouldn't be possible (the form is blocked), and
    clearing them here would let an attacker reset the lock by knowing one
    valid password for any account at the same IP. Never raises."""
    r = _login_redis()
    for key in _throttle_keys(email):
        if r is not None:
            try:
                r.delete(key)
                continue
            except Exception:
                pass
        # Local fallback: reset the failure count but keep any active
        # lockout, mirroring the Redis behaviour above (which deletes the
        # counter key but not the separate :lock key).
        entry = _login_failures_local.get(key)
        if entry:
            _, _, lock_until = entry
            if lock_until > datetime.now(timezone.utc).timestamp():
                _login_failures_local[key] = (0, 0.0, lock_until)
            else:
                _login_failures_local.pop(key, None)


# ---------------------------------------------------------------------------
# User lookup / creation
# ---------------------------------------------------------------------------

def get_user_by_email(email: str) -> db.User | None:
    email = (email or "").strip().lower()
    with db.get_session() as s:
        return s.query(db.User).filter(db.User.email == email).first()


def get_user_by_id(user_id: str) -> db.User | None:
    with db.get_session() as s:
        return s.query(db.User).filter(db.User.id == user_id).first()


def create_user(email: str, password: str, name: str = "", firm_name: str = "") -> db.User:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Enter a valid email address.")
    if len(password or "") < 8:
        raise ValueError("Password must be at least 8 characters.")
    if get_user_by_email(email):
        raise ValueError("An account with that email already exists. Try logging in instead.")

    user = db.User(
        email=email,
        password_hash=hash_password(password),
        name=(name or "").strip(),
        firm_name=(firm_name or "").strip(),
    )
    with db.get_session() as s:
        s.add(user)
        s.commit()
        s.refresh(user)

    # Best-effort welcome email -- signup itself already succeeded (the
    # commit above went through), so a Resend hiccup here must never look
    # like signup failed. Previously a new account got zero confirmation
    # email at all; this was the first of the missing conversion-loop
    # emails.
    try:
        email_utils.send_welcome_email(user.email, user.name)
    except Exception as exc:
        print(f"[welcome_email] failed for {user.email}: {exc}", file=sys.stderr)

    return user


def authenticate(email: str, password: str) -> db.User | None:
    user = get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def accept_terms(user: db.User) -> None:
    """Records that user just accepted TERMS_TEXT -- called from the signup
    form (immediately, before their first page load) and from the
    accept-terms gate in require_login() (for anyone signed in whose
    account predates this column, or who hasn't accepted yet)."""
    with db.get_session() as s:
        db_user = s.query(db.User).filter(db.User.id == user.id).first()
        if db_user:
            db_user.accepted_terms_at = datetime.now(timezone.utc)
            s.commit()


# ---------------------------------------------------------------------------
# Password reset -- request a link (emailed via Resend, see email_utils.py),
# then set a new password from that link. See render_password_reset_screen()
# below for the UI side, called from app.py before require_login() (the
# whole point is this has to work for someone who can't log in).
# ---------------------------------------------------------------------------

def request_password_reset(email: str) -> str:
    """Looks up the account and, if one exists and Resend is configured,
    emails a 1-hour reset link. Returns "sent" in every case except one --
    including when no account matches that email -- and "not_configured"
    only when email_utils.is_configured() is False.

    That "sent" no matter what (for a real vs. nonexistent email) is
    deliberate: telling a caller "no account with that email" is a
    textbook user-enumeration leak (it confirms which emails have accounts
    on this app), worth avoiding even for a small beta. "not_configured" is
    the one case that's NOT hidden the same way, and that's deliberate
    too, in the other direction -- that failure is about YOUR setup, not
    about a particular user's email, so there's no enumeration risk in
    surfacing it, and hiding it would leave a real user waiting forever for
    an email that can never arrive with no indication why. See app.py's
    "Forgot password?" form for how the two returned strings map to what's
    actually shown."""
    email = (email or "").strip().lower()
    if not email_utils.is_configured():
        return "not_configured"
    if email:
        user = get_user_by_email(email)
        if user:
            token = make_reset_token(user)
            reset_url = f"{APP_BASE_URL}/?reset_token={token}"
            try:
                email_utils.send_password_reset_email(user.email, reset_url)
                # Printed to stderr (Railway captures this in the service's
                # deploy logs) -- NOT shown to the end user, same reasoning
                # as the except branch below: the person submitting this
                # form isn't necessarily who they're requesting a reset
                # for, so nothing about send success/failure belongs in the
                # UI. This is purely so a real delivery problem (bad API
                # key, Resend rejecting the request, etc.) leaves a trace
                # you can actually go find in Railway's logs, instead of
                # vanishing the way the swallowed exception below used to.
                print(f"[password_reset] Resend accepted the request for {user.email}", file=sys.stderr)
            except Exception as exc:
                # Still swallowed from the CALLER's perspective (the "sent"
                # return value below never changes) -- see the docstring
                # above for why. But logged here rather than silently
                # dropped, so a real failure (bad/missing API key, Resend
                # rejecting the request, a network error, etc.) is at least
                # visible to you in Railway's logs instead of leaving zero
                # trace anywhere.
                print(f"[password_reset] FAILED to send to {user.email}: {exc}", file=sys.stderr)
    return "sent"


def reset_password(user: db.User, new_password: str) -> None:
    """Sets a new password for an already-identified user (the caller --
    render_password_reset_screen() -- has already verified the reset token
    and the new password's length before this is called). Changing
    password_hash here is also what invalidates every reset token issued
    before this point, including the one just used -- see
    _password_fingerprint()."""
    with db.get_session() as s:
        db_user = s.query(db.User).filter(db.User.id == user.id).first()
        if db_user:
            db_user.password_hash = hash_password(new_password)
            s.commit()


# ---------------------------------------------------------------------------
# Terms of use shown at signup and enforced before the main app is reachable
# -- see require_login() below and db.User.accepted_terms_at. Also reused
# as the standing AI-output disclaimer shown under the sidebar step list
# (see app.py) so there's exactly one copy of this wording to keep in sync,
# not two that can quietly drift apart.
# ---------------------------------------------------------------------------
TERMS_TEXT = (
    "CivilProposals is an AI-powered proposal generation assistant. Content generated by "
    "the platform may contain inaccuracies and should not be relied upon as certified "
    "engineering, legal, financial, or professional advice. Users are solely responsible "
    "for reviewing, verifying, and approving all generated content, including, but not "
    "limited to, technical scopes, commercial terms, project requirements, compliance "
    "criteria, assumptions, methodologies, qualifications, credentials, project specific "
    "information, and submission requirements prior to submission. CivilProposals accepts "
    "no liability for any decisions, omissions, errors, or actions arising from the use of "
    "its outputs."
)


# ---------------------------------------------------------------------------
# Login-required gate -- call once near the top of app.py
# ---------------------------------------------------------------------------

def current_user() -> db.User | None:
    """Returns the logged-in user for this script run, resolving from the
    signed cookie if session_state doesn't already have it cached."""
    # Flush any deferred cookie write/clear from a login/logout that just
    # happened -- see log_in()/log_out() for why this can't happen directly
    # in those functions. Doing it here means it fires on the very next
    # call to current_user(), which in practice is the next script run
    # (the one require_login()'s forced st.rerun() triggers) -- a normal
    # run that isn't itself immediately followed by another forced rerun,
    # so the browser-side cookie component this time actually gets to
    # finish mounting and firing before anything cancels it.
    if st.session_state.pop("_cookie_clear_pending", False):
        _clear_cookie_token()
        # This is why "Log out" silently didn't work for any returning user
        # (i.e. anyone whose browser already had a valid session cookie from
        # before this page load -- the common case, not the rare one): the
        # JS just queued above only clears the browser's cookie jar; it
        # can't retroactively change the Cookie header this request already
        # arrived with. Falling through to the st.context.cookies read below
        # would find that same still-valid, not-yet-cleared cookie and log
        # the user straight back in on the very run that was supposed to log
        # them out -- session_state's own record of who's logged in was
        # already cleared by log_out(), but this fallback re-derived it from
        # the stale cookie anyway. We know for certain a logout was just
        # requested this run, so stop here instead of trusting a cookie
        # we've already told the browser to delete.
        #
        # That guard alone only covers the ONE run where the pop() actually
        # fires, because it's a one-shot flag. Every run after that -- in
        # particular the run where the user submits the login form again,
        # possibly for a *different* account -- reaches the code below with
        # this branch never entered at all, and st.context.cookies (see
        # _get_cookie_token()) is a snapshot taken once, when this
        # WebSocket connection was first established, that Streamlit never
        # refreshes on later reruns within the same connection -- it does
        # NOT reflect the document.cookie clear (or a same-tab switch to a
        # different account) that just happened client-side. So the
        # fallback below would keep resolving to whoever was logged in
        # before the logout, no matter what the user types into the login
        # form next. _logged_out_this_session is the persistent (not
        # one-shot) marker that closes that gap: it stays set, forcing
        # every call to current_user() to ignore that stale cookie snapshot,
        # until log_in() clears it on an actual fresh login (below).
        st.session_state["_logged_out_this_session"] = True
        return None

    if st.session_state.get("_auth_user_id"):
        user = get_user_by_id(st.session_state["_auth_user_id"])
        if user and st.session_state.pop("_cookie_write_pending", False):
            _set_cookie_token(make_token(user.id))
        return user

    if st.session_state.get("_logged_out_this_session"):
        # We've explicitly logged out earlier in this same browser session
        # and haven't logged back in since (see log_in(), which clears this
        # flag the moment a fresh login succeeds). Do not fall through to
        # the raw st.context.cookies read below -- see the long comment
        # above for why that snapshot can't be trusted here. A real page
        # reload starts a brand-new session_state (this flag won't exist),
        # so this only ever affects same-session post-logout behaviour,
        # which is exactly the scenario that was broken.
        return None

    token = _get_cookie_token()
    user_id = verify_token(token) if token else None
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if user:
        st.session_state["_auth_user_id"] = user.id
    return user


def log_in(user: db.User) -> None:
    # Deliberately NOT calling _set_cookie_token() here. log_in() is always
    # called from a form-submit handler that immediately follows with
    # st.rerun() (see require_login()) -- and that immediate rerun races
    # the cookie-set browser component: Streamlit aborts the current script
    # run (and, with it, whatever the not-yet-mounted component iframe was
    # about to do) the instant st.rerun() fires, before the browser has had
    # a chance to actually execute the "set this cookie" JS. Confirmed via
    # direct browser-cookie-jar inspection: with the old immediate
    # log_in()-then-set-cookie-then-rerun sequence, the session cookie
    # never appeared in the browser at all -- not delayed, just never
    # written -- which is why every previous round of "fix the read side"
    # never actually fixed anything: there was nothing to read. Setting a
    # flag here and writing the cookie on the *next* run (see
    # current_user() above) sidesteps the race instead of racing it.
    st.session_state["_auth_user_id"] = user.id
    st.session_state["_cookie_write_pending"] = True
    # A fresh, successful login always wins over a prior logout in this same
    # browser session -- clear the marker that makes current_user() distrust
    # the (possibly stale) cookie fallback, since _auth_user_id being set
    # means that fallback branch is never even reached for this user going
    # forward anyway. Without this, logging out and back in as the SAME
    # account would leave the flag set for no reason (harmless today, but
    # only by accident of check ordering) -- clearing it here is the correct
    # invariant regardless.
    st.session_state.pop("_logged_out_this_session", None)


def log_out() -> None:
    st.session_state.pop("_auth_user_id", None)
    st.session_state.pop("_cookie_write_pending", None)
    # Same reasoning as log_in() above, in reverse: log_out() is always
    # followed immediately by st.rerun() at its call site, which would
    # race out an immediate _clear_cookie_token() call just like it did
    # the cookie write. Deferred so the actual browser-side delete happens
    # on the next (unraced) run instead.
    st.session_state["_cookie_clear_pending"] = True


def _render_terms_gate(user: db.User) -> None:
    """Blocks the main app behind an explicit "I accept" click for any
    signed-in user who hasn't accepted TERMS_TEXT yet (accepted_terms_at is
    None) -- covers every account created before this column existed, not
    just new signups (who tick the same terms on the signup form itself,
    see the "Create account" tab in require_login() below). Always
    st.stop()s -- require_login() relies on the *next* script run (after
    "Accept and continue" sets accepted_terms_at and reruns) seeing that
    field set and skipping this gate entirely, rather than on this function
    ever returning normally."""
    from modules import branding

    _picker_col, _ = st.columns([1, 4])
    with _picker_col:
        i18n.language_picker(key="_terms_gate_lang_picker", persist_for_user=user)

    st.markdown(
        branding.brand_html(logo_size=44, wordmark_size="1.5rem", show_beta=True, href="https://civilproposals.com"),
        unsafe_allow_html=True,
    )
    st.markdown(i18n.t("terms_gate_title"))
    st.write(i18n.t("terms_gate_intro"))
    st.markdown(
        f'<div style="margin-top:6px;padding:16px 18px;background:#F8FAFC;border:1px solid #E2E8F0;'
        f'border-radius:10px;font-size:.92rem;color:#334155;line-height:1.6;max-width:640px;">{TERMS_TEXT} '
        f'This is a summary of the AI-output disclaimer in our '
        f'<a href="https://civilproposals.com/terms-of-service.html" target="_blank">Terms of Service</a>, '
        f'which governs your use of CivilProposals in full.</div>',
        unsafe_allow_html=True,
    )
    accepted = st.checkbox(i18n.t("terms_gate_checkbox"), key="_terms_gate_checkbox")
    gate_col1, gate_col2 = st.columns([1, 4])
    with gate_col1:
        if st.button(i18n.t("terms_gate_accept"), type="primary", disabled=not accepted, key="_terms_gate_accept_btn"):
            accept_terms(user)
            st.rerun()
    with gate_col2:
        if st.button(i18n.t("terms_gate_logout"), key="_terms_gate_logout_btn"):
            log_out()
            st.rerun()
    st.stop()


def require_login() -> db.User:
    """Renders a login/signup screen and st.stop()s if nobody's logged in.
    Once logged in, also enforces the terms-acceptance gate above before
    returning -- accepting TERMS_TEXT is a hard requirement to reach the
    real app, not just a checkbox shown once at signup, so an existing
    account that predates this feature gets stopped here exactly once too.
    Returns the logged-in, terms-accepted User otherwise. Call this before
    rendering any of the app's real tabs."""
    user = current_user()
    if user:
        # Deferred signup-funnel event from the run that created the account
        # -- see the signup submit handler below for why it can't fire on
        # that run itself (st.rerun() races the component's mount).
        if st.session_state.pop("_signup_event_pending", False):
            from modules import analytics
            analytics.track_event("Signup Completed", once_per_session=False)
        if user.accepted_terms_at is None:
            _render_terms_gate(user)  # always st.stop()s
        return user

    from modules import branding  # imported here to avoid a circular import at module load time
    from modules import analytics

    # Signup-funnel step 1: someone reached the login/signup screen.
    analytics.track_event("Auth Screen View")

    st.markdown(
        """
        <style>
        div[data-testid="stForm"] {
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            padding: 1.75rem 1.75rem 1rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    _top_picker_col, _ = st.columns([1, 4])
    with _top_picker_col:
        i18n.language_picker(key="_login_lang_picker")

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        # Built as single-line, unindented HTML strings on purpose -- see
        # the comment in branding.brand_html() about st.markdown() treating
        # indented multi-line blocks as literal Markdown code blocks even
        # with unsafe_allow_html=True.
        import html as _html_module
        headline_html = (
            branding.brand_html(logo_size=52, wordmark_size="1.9rem", show_beta=True, href="https://civilproposals.com")
            + f'<div style="margin-top:22px;font-size:2rem;font-weight:800;letter-spacing:-0.02em;color:#0F172A;line-height:1.2;">{_html_module.escape(i18n.t("auth_headline"))}</div>'
            + f'<div style="margin-top:12px;color:#5A6B7A;font-size:1.02rem;line-height:1.6;max-width:560px;">{_html_module.escape(i18n.t("auth_subhead"))}</div>'
        )
        st.markdown(headline_html, unsafe_allow_html=True)

        # A "🚀 Beta Access" banner used to sit here, repeating "this
        # product is currently in beta" on a screen every returning user
        # (trial or paying) sees on every single login -- one more
        # disclosure beyond the three places this audit asked to keep (the
        # nav badge above, the pricing section's beta note, and the
        # security FAQ answer). Its actual legal substance (review AI
        # output before relying on it, we're not liable for errors) is
        # already covered by TERMS_TEXT below, which every account accepts
        # at signup and sees captioned in the sidebar on every screen
        # afterward -- removing this didn't remove any real disclosure,
        # just a redundant repetition of it at the highest-commitment
        # moment in the whole product.

    with right:
        tab_login, tab_signup = st.tabs([i18n.t("auth_tab_login"), i18n.t("auth_tab_signup")])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input(i18n.t("auth_email"))
                password = st.text_input(i18n.t("auth_password"), type="password")
                submitted = st.form_submit_button(i18n.t("auth_login_submit"), type="primary", use_container_width=True)
            if submitted:
                lockout_seconds = login_lockout_remaining(email)
                if lockout_seconds > 0:
                    minutes = max(1, (lockout_seconds + 59) // 60)
                    st.error(
                        f"Too many failed sign-in attempts. For your account's security, "
                        f"logging in is paused for about {minutes} more minute"
                        f"{'s' if minutes != 1 else ''} -- please try again then, or use "
                        f"\"Forgot password?\" below to reset your password."
                    )
                else:
                    user = authenticate(email, password)
                    if user:
                        clear_login_failures(email)
                        log_in(user)
                        st.rerun()
                    else:
                        attempts_left = record_login_failure(email)
                        if attempts_left <= 0:
                            minutes = LOGIN_LOCKOUT_SECONDS // 60
                            st.error(
                                f"Incorrect email or password. Too many failed attempts -- "
                                f"logging in is now paused for {minutes} minutes. You can "
                                f"use \"Forgot password?\" below to reset your password."
                            )
                        elif attempts_left <= 2:
                            st.error(
                                f"Incorrect email or password. {attempts_left} attempt"
                                f"{'s' if attempts_left != 1 else ''} left before sign-in "
                                f"is paused for {LOGIN_LOCKOUT_SECONDS // 60} minutes."
                            )
                        else:
                            st.error(i18n.t("auth_error_bad_login"))

            with st.popover(i18n.t("auth_forgot_password")):
                st.caption(i18n.t("auth_forgot_caption"))
                with st.form("forgot_password_form"):
                    forgot_email = st.text_input(i18n.t("auth_email"), key="_forgot_pw_email")
                    forgot_submitted = st.form_submit_button(i18n.t("auth_forgot_submit"))
                if forgot_submitted:
                    status = request_password_reset(forgot_email)
                    if status == "not_configured":
                        st.error(i18n.t("auth_reset_not_configured"))
                    else:
                        st.success(i18n.t("auth_reset_sent"))

        with tab_signup:
            with st.form("signup_form"):
                name = st.text_input(i18n.t("auth_signup_name"))
                firm_name = st.text_input(i18n.t("auth_signup_firm"))
                email = st.text_input(i18n.t("auth_signup_email"), key="signup_email")
                password = st.text_input(i18n.t("auth_password"), type="password", key="signup_password",
                                          help=i18n.t("auth_signup_password_help"))
                confirm_password = st.text_input(i18n.t("auth_signup_confirm_password"), type="password", key="signup_confirm_password")
                st.caption(i18n.t("auth_signup_trial_caption", limit=DEFAULT_TRIAL_LIMIT))
                with st.expander(i18n.t("auth_signup_terms_expander")):
                    st.markdown(
                        f'<div style="font-size:.85rem;color:#475569;line-height:1.6;">{TERMS_TEXT} '
                        f'This is a summary of the AI-output disclaimer in our '
                        f'<a href="https://civilproposals.com/terms-of-service.html" target="_blank">Terms of Service</a>, '
                        f'which governs your use of CivilProposals in full.</div>',
                        unsafe_allow_html=True,
                    )
                agreed_terms = st.checkbox(i18n.t("auth_signup_terms_checkbox"), key="signup_terms_checkbox")
                submitted = st.form_submit_button(i18n.t("auth_signup_submit"), type="primary", use_container_width=True)
            if submitted:
                if password != confirm_password:
                    st.error(i18n.t("auth_error_passwords_no_match"))
                elif not agreed_terms:
                    st.error(i18n.t("auth_error_must_accept_terms"))
                else:
                    try:
                        user = create_user(email, password, name, firm_name)
                        accept_terms(user)
                        # Signup-funnel step 2: account actually created.
                        # Deferred to the NEXT script run (see the flag
                        # check at the top of require_login) -- firing the
                        # event component here, immediately before
                        # st.rerun(), loses the same mount race the session
                        # cookie write does (see log_in()'s comment): the
                        # rerun tears the component down before its script
                        # ever executes in the browser.
                        st.session_state["_signup_event_pending"] = True
                        log_in(user)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    st.stop()


def render_password_reset_screen(token: str) -> None:
    """Shown INSTEAD OF the normal login screen when the URL carries a
    ?reset_token=... -- see app.py, which checks for this query param and
    calls this function before require_login() ever runs, precisely
    because someone resetting a forgotten password can't log in first.
    Always st.stop()s, same contract as require_login()."""
    from modules import branding

    _reset_picker_col, _ = st.columns([1, 4])
    with _reset_picker_col:
        i18n.language_picker(key="_reset_lang_picker")

    st.markdown(
        branding.brand_html(logo_size=44, wordmark_size="1.5rem", show_beta=True, href="https://civilproposals.com"),
        unsafe_allow_html=True,
    )

    # Checked BEFORE verify_reset_token() below, on purpose: a successful
    # reset changes the user's password_hash, which is exactly what makes
    # the token single-use (see _password_fingerprint()) -- so on the rerun
    # right after a successful reset, re-verifying the same token here
    # would now correctly fail as "already used" and show the wrong
    # (error) branch instead of the success message. This flag lets the
    # success screen render without ever re-checking the now-intentionally-
    # invalidated token.
    if st.session_state.get("_password_reset_done"):
        st.success(i18n.t("pw_reset_success"))
        if st.button(i18n.t("pw_reset_continue"), type="primary"):
            st.session_state.pop("_password_reset_done", None)
            st.query_params.clear()
            st.rerun()
        st.stop()

    user = verify_reset_token(token)
    if not user:
        st.error(
            "This reset link is invalid, expired, or has already been used. Request a new one from the "
            "login screen."
        )
        if st.button("Back to login"):
            st.query_params.clear()
            st.rerun()
        st.stop()

    st.markdown("### Set a new password")
    st.caption(f"Resetting the password for **{user.email}**.")
    with st.form("reset_password_form"):
        new_password = st.text_input("New password", type="password", help="At least 8 characters.")
        confirm_password = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Set new password", type="primary")
    if submitted:
        if len(new_password or "") < 8:
            st.error("Password must be at least 8 characters.")
        elif new_password != confirm_password:
            st.error("Passwords don't match -- please re-enter them.")
        else:
            reset_password(user, new_password)
            st.session_state["_password_reset_done"] = True
            st.rerun()

    st.stop()


DEFAULT_TRIAL_LIMIT = 1

# The Monthly plan's advertised bids-included figure (see the landing page
# pricing card) -- an active subscription used to be treated as fully
# unlimited in code, which didn't match that promise. Spent via
# db.User.subscription_bids_used, reset each real Stripe billing period by
# billing.refresh_subscription_status(); see get_access_status/
# record_proposal_usage below for how it's actually enforced.
#
# Part B2 (owner-confirmed) raised this from 3 to 4 proposal projects/month
# -- every other copy surface that quotes this number (landing page pricing
# card, signup caption, sidebar/paywall messages) reads it from here or
# from modules/translations/*.py's {limit} format placeholders rather than
# hardcoding "3" a second time, specifically so this is the only place the
# figure needs to change again.
SUBSCRIPTION_MONTHLY_BID_LIMIT = 4

# Accounts that get real, unconditional unlimited access -- never blocked,
# never shown a trial-limit or upgrade banner, no matter how many bids they
# run. This used to also fake-show the normal "trial limit reached" banner
# so the account holder could preview its design on a live account (see
# UNLIMITED_PREVIEW_ACCOUNTS in git history) -- dropped in favour of just
# treating these accounts as fully unlimited with no caveat, per product
# decision. Lowercased/stripped to match how emails are stored (see
# create_user()).
#
# Includes both of Andrew's addresses on purpose: anmolago@hotmail.com is
# the one actually used to log into the live production account (this only
# had the icloud address before, which meant testing on the real account
# was quietly burning real paid bids/trial limit). Keeping icloud too in
# case it's a secondary test account.
UNLIMITED_ACCOUNTS = {"anmolago@icloud.com", "anmolago@hotmail.com"}

# Accounts that get the admin panel (the "Admin stats" button in the
# sidebar -- accounts/usage/AI-cost rollups across ALL users). Granted by
# email here, in code, rather than only via the db.User.is_admin flag, so
# admin access survives any database reset and needs no manual SQL to set
# up. The DB flag still works too -- see is_admin_user(). Read-only
# observability: nothing in the admin panel can modify another account.
ADMIN_ACCOUNTS = {"anmolago@icloud.com", "anmolago@hotmail.com"}


def is_admin_user(user: db.User | None) -> bool:
    """True when this account may see the admin panel -- either flagged
    is_admin in the database, or listed in ADMIN_ACCOUNTS above."""
    if user is None:
        return False
    if getattr(user, "is_admin", False):
        return True
    return (user.email or "").strip().lower() in ADMIN_ACCOUNTS


# ---------------------------------------------------------------------------
# Trial / subscription access
# ---------------------------------------------------------------------------

def get_access_status(user: db.User) -> dict:
    """
    Returns {"allowed": bool, "trial_remaining": int, "subscribed": bool,
    "limit_reached": bool, "unlimited": bool, "bid_credits": int,
    "subscription_bids_remaining": int, "subscription_bid_limit": int} --
    the single source of truth app.py uses to decide whether to show the
    paywall instead of the tabs, and whether to count a new proposal
    against the trial/subscription/pay-as-you-go balance (see
    record_proposal_usage).

    trial_limit is always DEFAULT_TRIAL_LIMIT, not user.trial_proposals_limit
    -- the trial size is a single product-wide constant, not something that
    varies per account, so this doesn't trust a per-user DB column that can
    go stale (accounts created back when the trial was 3 bids still have
    trial_proposals_limit=3 sitting in their row; that's an artifact of
    when they signed up, not an entitlement, so it's ignored here in favour
    of whatever DEFAULT_TRIAL_LIMIT currently is).

    An ACTIVE subscription is capped at SUBSCRIPTION_MONTHLY_BID_LIMIT (4)
    bids per real Stripe billing period -- matches the landing page's "4
    bids included" promise, which the code used to silently ignore (treating
    "subscribed" as fully unlimited). Once that monthly quota is used up,
    bid_credits (pay-as-you-go purchases) still work on top of it, same as
    for a non-subscriber.

    PAST_DUE now gets the same treatment as ACTIVE -- capped at the same
    monthly quota, with bid_credits still stacking on top. It used to be
    left fully uncapped (always allowed, no quota check at all) on the
    theory that it's a short payment-recovery grace period and a failing
    card shouldn't also lose you your quota. In practice that "short" grace
    period had no actual time limit: Stripe's own "unpaid" status (what
    Stripe uses once it's stopped retrying, before the subscription is
    actually canceled) maps to this same past_due bucket in
    billing.refresh_subscription_status, and whether/when Stripe moves past
    that to "canceled" depends on a dunning setting in the Stripe dashboard,
    not on anything this app controls. That made "grace period" potentially
    unbounded -- unlimited free usage for as long as a card kept failing.
    Capping it at the normal quota keeps the actual goal (don't cut someone
    off the instant a payment hiccups) without the unbounded-free-usage gap.

    bid_credits is the pay-as-you-go balance (see db.User.bid_credits) --
    real, paid credits from $50 one-time Stripe Checkouts. Unaffected by
    subscription_status entirely: they never expire and stack on top of
    whichever quota (trial, active, or past_due) applies above.

    "limit_reached" mirrors "not allowed" for everyone except
    UNLIMITED_ACCOUNTS, who never see it go true -- see "unlimited" below.
    """
    is_unlimited = (user.email or "").strip().lower() in UNLIMITED_ACCOUNTS
    trial_remaining = max(0, DEFAULT_TRIAL_LIMIT - (user.trial_proposals_used or 0))
    bid_credits = max(0, user.bid_credits or 0)
    subscription_bids_remaining = max(0, SUBSCRIPTION_MONTHLY_BID_LIMIT - (user.subscription_bids_used or 0))

    if user.subscription_status in ("active", "past_due"):
        allowed = is_unlimited or subscription_bids_remaining > 0 or bid_credits > 0
        limit_reached = not allowed
    else:
        allowed = is_unlimited or trial_remaining > 0 or bid_credits > 0
        limit_reached = not allowed

    return {
        "allowed": allowed,
        "subscribed": user.subscription_status == "active",
        "past_due": user.subscription_status == "past_due",
        "trial_remaining": trial_remaining,
        "trial_limit": DEFAULT_TRIAL_LIMIT,
        "bid_credits": bid_credits,
        "subscription_bids_remaining": subscription_bids_remaining,
        "subscription_bid_limit": SUBSCRIPTION_MONTHLY_BID_LIMIT,
        "limit_reached": limit_reached,
        "unlimited": is_unlimited,
    }


def record_proposal_usage(user: db.User, project_key: str, project_name: str = "") -> bool:
    """
    Call this once, the first time a user runs Tender Analysis for a given
    project (project_key should be a stable identifier for that project AND
    that document -- see app.py's Tender Analysis tab, which folds in a hash
    of the brief text itself, not just the user-typed project/tender/client
    names; those alone would let someone keep the project name, swap in a
    different brief, and re-analyse for free). If this project+document
    hasn't already been counted, spends one credit, in priority order:
      - ACTIVE or PAST_DUE subscription: the current billing period's
        monthly quota (SUBSCRIPTION_MONTHLY_BID_LIMIT) first, then a
        purchased pay-as-you-go bid_credit once that's used up. PAST_DUE is
        deliberately treated exactly like ACTIVE here -- see
        get_access_status()'s docstring for why it used to be left
        unmetered (an unbounded free-usage gap) and no longer is.
      - Otherwise (trial/canceled): the free trial credit first, then a
        bid_credit once the trial is exhausted.
    Returns True if this call actually consumed a credit of some kind
    (idempotent otherwise -- re-analysing the exact same project+document
    never double-counts, and this also returns True in that "nothing left
    to spend" edge case since the project itself still got recorded -- the
    caller is expected to have already checked get_access_status().allowed
    before letting this run at all).

    A blank/empty project_key is refused outright (raises ValueError)
    rather than silently returning False: a silent no-op here previously
    meant a proposal that skipped naming a project was never recorded and
    never spent a credit, which in turn meant get_access_status() kept
    reporting the trial as unused forever -- i.e. unlimited free analyses
    for anyone who left Project Setup blank. The caller (app.py) is
    responsible for not letting Tender Analysis run at all without a
    project name in the first place; this is the defense-in-depth backstop
    in case some other code path ever calls this without one.
    """
    project_key = (project_key or "").strip().lower()
    if not project_key:
        raise ValueError(
            "record_proposal_usage() requires a non-empty project_key -- refusing to silently "
            "skip metering. The caller must require a project name before allowing the metered "
            "action to run at all."
        )

    with db.get_session() as s:
        db_user = s.query(db.User).filter(db.User.id == user.id).first()
        if not db_user:
            return False
        already = s.query(db.ProposalUsage).filter(
            db.ProposalUsage.user_id == db_user.id,
            db.ProposalUsage.project_key == project_key,
        ).first()
        if already:
            return False

        # Part B: which tier actually funds this project -- "unlimited" for
        # UNLIMITED_ACCOUNTS (never subject to the free-tier artifact/
        # download rules, see project_funded_by()), else whichever of
        # trial/subscription/credit the branches below actually spend from.
        # Set alongside the row insert (same transaction as the spend
        # itself) so it can never disagree with what was actually charged.
        _is_unlimited_account = (db_user.email or "").strip().lower() in UNLIMITED_ACCOUNTS
        _funded_by = "unlimited" if _is_unlimited_account else ""

        _usage_row = db.ProposalUsage(user_id=db_user.id, project_key=project_key, project_name=project_name)
        s.add(_usage_row)
        _just_used_last_trial_bid = False
        if db_user.subscription_status in ("active", "past_due"):
            sub_remaining = max(0, SUBSCRIPTION_MONTHLY_BID_LIMIT - (db_user.subscription_bids_used or 0))
            if sub_remaining > 0:
                db_user.subscription_bids_used = (db_user.subscription_bids_used or 0) + 1
                _funded_by = _funded_by or "subscription"
            elif (db_user.bid_credits or 0) > 0:
                db_user.bid_credits = db_user.bid_credits - 1
                _funded_by = _funded_by or "credit"
            else:
                _funded_by = _funded_by or "subscription"
        else:
            trial_remaining = max(0, DEFAULT_TRIAL_LIMIT - (db_user.trial_proposals_used or 0))
            if trial_remaining > 0:
                db_user.trial_proposals_used = (db_user.trial_proposals_used or 0) + 1
                _just_used_last_trial_bid = (trial_remaining == 1) and (db_user.bid_credits or 0) == 0
                _funded_by = _funded_by or "trial"
            elif (db_user.bid_credits or 0) > 0:
                db_user.bid_credits = db_user.bid_credits - 1
                _funded_by = _funded_by or "credit"
            else:
                _funded_by = _funded_by or "trial"
        _usage_row.funded_by = _funded_by

        # Part B2: a project funded by real money (subscription quota or a
        # pay-as-you-go credit -- never "trial" or "unlimited") gets its
        # 5-pass allowance opened right here, in the same transaction as the
        # charge that earned it -- see db.ProjectPasses's docstring. This
        # first pass (the analysis run that just got funded) is spent
        # immediately, same as consume_project_pass() would do, so a fresh
        # $50 bid reads as "4 of 5 passes left," not "5 of 5" with the
        # analysis that was just paid for somehow free.
        if _funded_by in ("subscription", "credit"):
            _existing_passes = s.query(db.ProjectPasses).filter(
                db.ProjectPasses.user_id == db_user.id,
                db.ProjectPasses.project_key == project_key,
            ).first()
            if _existing_passes is None:
                s.add(db.ProjectPasses(
                    user_id=db_user.id, project_key=project_key,
                    passes_purchased=5, passes_used=1,
                ))
        try:
            s.commit()
        except IntegrityError:
            # The (user_id, project_key) unique constraint on ProposalUsage
            # (see that model's docstring) just caught exactly the race the
            # "already = ...; if already: return False" check above can't
            # fully close on its own: a Streamlit double-rerun (a
            # double-click, or a rerun triggered mid-click by something else
            # on the page) running this function twice before either commit
            # lands, both seeing "no row yet." The first commit to actually
            # reach the database won -- this one lost, so roll back every
            # change just staged in this session (the credit deduction
            # above included) rather than let it partially apply, and treat
            # it the same as the already-recorded case above: no error
            # shown to the user, no second credit spent.
            s.rollback()
            return False
        user_email = db_user.email

    # Best-effort "you're out of free trial, here's how to keep going"
    # nudge -- fires exactly once, the moment the trial actually runs out
    # (not on every subsequent blocked attempt). Previously nothing ever
    # told a trial user this happened beyond the in-app paywall message
    # they'd only see if they came back -- this was the missing
    # "$50/bid, here's the upgrade path" follow-up. Sent outside the
    # session block above (after commit) so an email hiccup can never roll
    # back or block the actual usage-recording transaction.
    if _just_used_last_trial_bid:
        try:
            email_utils.send_trial_used_email(user_email)
        except Exception as exc:
            print(f"[trial_used_email] failed for {user_email}: {exc}", file=sys.stderr)

    return True


def project_funded_by(user: db.User, project_key: str) -> str:
    """Which tier actually funded THIS project's first Tender Analysis run
    -- "trial", "subscription", "credit", "unlimited", or "" if it hasn't
    been recorded at all yet (record_proposal_usage() hasn't run for it).
    See db.ProposalUsage.funded_by's docstring for what each value means
    and why this is a separate question from "does a ProposalUsage row
    exist" (10_state_helpers.py's _current_project_already_paid()).

    This is the single source of truth Part B's free-tier artifact/download
    gating (modules/pages/80_export.py's _FREE_TIER_ARTIFACTS handling) and
    Part B2's pass-allowance lookup (project_passes_remaining() below) both
    build on: "trial" (or "") means free-tier rules apply; "subscription"/
    "credit"/"unlimited" means paid rules apply."""
    project_key = (project_key or "").strip().lower()
    if not project_key:
        return ""
    with db.get_session() as s:
        row = s.query(db.ProposalUsage).filter(
            db.ProposalUsage.user_id == user.id,
            db.ProposalUsage.project_key == project_key,
        ).first()
        return (row.funded_by or "") if row else ""


def is_trial_funded_project(user: db.User, project_key: str) -> bool:
    """True when THIS project's paid-analysis rules haven't kicked in --
    i.e. it was funded by the free trial (or never funded at all yet).
    Older ProposalUsage rows recorded before the funded_by column existed
    read back as "" (see the migration in db._run_light_migrations()),
    which this treats the same as "trial" -- the conservative choice, since
    every row from before this column existed WAS necessarily either a
    (single-use) trial bid or a real payment, and there's no way to tell
    which after the fact; erring toward "still free-tier-restricted" is
    safer than accidentally granting a pre-existing project unlimited
    downloads it never actually paid for."""
    funded_by = project_funded_by(user, project_key)
    return funded_by in ("", "trial")


# ---------------------------------------------------------------------------
# Part B2 -- pass allowances per plan (owner-confirmed; supersedes Part B's
# flat "one generation pass" description wherever the two disagree -- see
# db.ProjectPasses's docstring). A "pass" is one full generation cycle
# (the initial Tender Analysis run, or a later regeneration once a tracked
# input has actually changed) on ONE paid project. Trial-funded projects
# never get a ProjectPasses row at all -- DEFAULT_TRIAL_LIMIT (1) already
# *is* their one-and-only pass, enforced by the existing trial counters
# above, so there is nothing additional to track for them here.
# ---------------------------------------------------------------------------

def project_passes_status(user: db.User, project_key: str) -> dict:
    """Returns {"has_passes": bool, "purchased": int, "used": int,
    "remaining": int}. "has_passes" is False for a project that has no
    ProjectPasses row yet -- either it's trial-funded (see
    is_trial_funded_project() instead) or record_proposal_usage() simply
    hasn't run for it yet. UNLIMITED_ACCOUNTS should check
    get_access_status()['unlimited'] BEFORE consulting this -- this
    function reports real database numbers only, no bypass baked in, so
    callers stay in control of where the unlimited exemption applies."""
    project_key = (project_key or "").strip().lower()
    if not project_key:
        return {"has_passes": False, "purchased": 0, "used": 0, "remaining": 0}
    with db.get_session() as s:
        row = s.query(db.ProjectPasses).filter(
            db.ProjectPasses.user_id == user.id,
            db.ProjectPasses.project_key == project_key,
        ).first()
        if row is None:
            return {"has_passes": False, "purchased": 0, "used": 0, "remaining": 0}
        remaining = max(0, (row.passes_purchased or 0) - (row.passes_used or 0))
        return {
            "has_passes": True, "purchased": row.passes_purchased or 0,
            "used": row.passes_used or 0, "remaining": remaining,
        }


def consume_project_pass(user: db.User, project_key: str) -> bool:
    """Spends one pass on this (already-paid) project -- call right BEFORE
    a generation cycle actually runs (Tender Analysis, or a regeneration
    once inputs have changed), and check its return value: False means
    nothing was spent and the caller must not run the metered action at
    all (show the existing "no passes left" message instead).

    Audit fix (Part 1c): this used to be a read-check-increment-commit --
    two concurrent calls (a double-click, two browser tabs, a rerun racing
    a click) could both read "1 remaining" before either committed, both
    increment, and both succeed, spending two passes for one that was
    actually available. It was also called AFTER the AI work completed,
    with its return value ignored -- so even a correctly-failing check
    couldn't have stopped the (already-run, already-billed-in-AI-cost)
    generation anyway. Fixed by making the spend a single, atomic,
    guarded UPDATE: `passes_used = passes_used + 1 WHERE ... passes_used <
    passes_purchased`. The database itself is what decides whether there
    was a pass left -- only one of two concurrent UPDATEs can ever match
    that WHERE clause and actually increment a row, so exactly one caller
    gets rowcount > 0 (returns True) and the other gets rowcount == 0
    (returns False), no matter how they interleave. Callers must call this
    before starting the metered action, not after -- see the Tender
    Analysis tab's "Run Analysis" button handler."""
    project_key = (project_key or "").strip().lower()
    if not project_key:
        return False
    with db.get_session() as s:
        result = s.execute(
            text(
                "UPDATE project_passes SET passes_used = passes_used + 1, updated_at = :now "
                "WHERE user_id = :uid AND project_key = :pkey AND passes_used < passes_purchased"
            ),
            {"now": datetime.now(timezone.utc), "uid": user.id, "pkey": project_key},
        )
        s.commit()
        return result.rowcount > 0


def apply_project_bid_topup(s, user_id: str, project_key: str, passes: int = 5) -> str:
    """Core DB logic for a $50 bid/top-up purchase earmarked for a specific
    project (see billing.create_bid_checkout_session's topup_project_key
    parameter) -- factored out of add_project_pass_topup()/
    upgrade_trial_project_to_paid() below so billing.handle_checkout_redirect()
    can run it inside its OWN already-open session, in the exact same
    transaction as the Stripe-session idempotency row it writes right after
    (see db.ProcessedCheckoutSession) -- audit fix Part 1b: the grant and
    the idempotency marker used to be two separate commits (grant in a
    fresh session, opened only AFTER the first session had already
    committed), so a crash or worker restart between the two left a
    customer charged, the checkout session already marked "processed" (so
    a page refresh/replay would never retry it), and the passes/upgrade
    never actually applied. One transaction means both happen or neither
    does. Does NOT commit -- the caller commits.

    Handles Part 1a (buying a bid must unlock the project the user is
    stuck on) and Part B2's ordinary top-up in one place, distinguished by
    what's already on record for this project:

    Returns one of:
      "upgraded_trial" -- a ProposalUsage row existed and was still
        trial-funded ("" or "trial", i.e. the free pass was spent on
        exactly this project and nothing else has paid for it since).
        Upgraded to funded_by="credit" and its ProjectPasses opened (or
        extended) at +`passes` purchased, with 1 already used -- the
        analysis that spent the trial pass already ran, so it counts as
        this project's first spent pass, matching how
        record_proposal_usage() itself treats a freshly-funded project's
        first analysis as immediately spent.
      "topped_up_paid" -- the project was already paid-funded
        (subscription/credit/unlimited); its ProjectPasses purchased
        allowance simply grew by `passes` (the ordinary top-up).
      "no_project" -- no ProposalUsage row exists for this project key at
        all yet (nothing analysed, nothing to attach to) -- the caller
        should fall back to crediting a generic account-level bid_credit
        instead, so the payment is never lost."""
    project_key = (project_key or "").strip().lower()
    if not project_key:
        return "no_project"
    usage_row = s.query(db.ProposalUsage).filter(
        db.ProposalUsage.user_id == user_id,
        db.ProposalUsage.project_key == project_key,
    ).first()
    if usage_row is None:
        return "no_project"
    passes_row = s.query(db.ProjectPasses).filter(
        db.ProjectPasses.user_id == user_id,
        db.ProjectPasses.project_key == project_key,
    ).first()
    if (usage_row.funded_by or "") in ("", "trial"):
        usage_row.funded_by = "credit"
        if passes_row is None:
            s.add(db.ProjectPasses(user_id=user_id, project_key=project_key,
                                    passes_purchased=passes, passes_used=1))
        else:
            passes_row.passes_purchased = (passes_row.passes_purchased or 0) + passes
            passes_row.passes_used = max(passes_row.passes_used or 0, 1)
            passes_row.updated_at = datetime.now(timezone.utc)
        return "upgraded_trial"
    else:
        if passes_row is None:
            s.add(db.ProjectPasses(user_id=user_id, project_key=project_key,
                                    passes_purchased=passes, passes_used=0))
        else:
            passes_row.passes_purchased = (passes_row.passes_purchased or 0) + passes
            passes_row.updated_at = datetime.now(timezone.utc)
        return "topped_up_paid"


def migrate_project_identity(user: db.User, old_key: str, new_key: str) -> bool:
    """Audit fix Part 3b: moves ALL of a project's billing/passes/download
    records (ProposalUsage, ProjectPasses, ArtifactEvent) from `old_key` to
    `new_key` for this user -- called when the rename-confirm dialog's
    "Yes, rename" is clicked on a project that's currently PAID (see
    modules/pages/10_state_helpers.py's _confirm_rename()). Renaming (or
    swapping the uploaded brief on) a paid project computes a brand-new
    project_key -- see _current_project_key()'s docstring: identity folds
    in the typed project/tender/client names AND a hash of the brief text
    -- which used to strand the payment under the old, now-orphaned
    identity forever, with only a warning dialog to explain why. Migrating
    the rows instead of merely warning about them means a rename never
    actually costs anyone their payment.

    Idempotent / defensive: returns False (does nothing) if old_key and
    new_key are the same, if there's no ProposalUsage row under old_key to
    migrate, or if new_key ALREADY has its own ProposalUsage row -- the
    last case means new_key is (or was) itself a distinct project with its
    own billing history, and blindly overwriting its project_key would
    silently merge two unrelated projects' payments into one. In that rare
    collision, the rows are left exactly as they were and the caller's
    dialog keeps warning instead of migrating anything."""
    old_key = (old_key or "").strip().lower()
    new_key = (new_key or "").strip().lower()
    if not old_key or not new_key or old_key == new_key:
        return False
    with db.get_session() as s:
        usage_row = s.query(db.ProposalUsage).filter(
            db.ProposalUsage.user_id == user.id,
            db.ProposalUsage.project_key == old_key,
        ).first()
        if usage_row is None:
            return False
        if s.query(db.ProposalUsage).filter(
            db.ProposalUsage.user_id == user.id,
            db.ProposalUsage.project_key == new_key,
        ).first() is not None:
            return False
        usage_row.project_key = new_key
        for _row in s.query(db.ProjectPasses).filter(
            db.ProjectPasses.user_id == user.id,
            db.ProjectPasses.project_key == old_key,
        ).all():
            _row.project_key = new_key
        for _row in s.query(db.ArtifactEvent).filter(
            db.ArtifactEvent.user_id == user.id,
            db.ArtifactEvent.project_key == old_key,
        ).all():
            _row.project_key = new_key
        try:
            s.commit()
        except IntegrityError:
            s.rollback()
            return False
        return True


def add_project_pass_topup(user: db.User, project_key: str, passes: int = 5) -> bool:
    """+5 (default) passes on an existing project -- the "$50 top-up"
    purchase flow (see billing.create_bid_checkout_session(), reused here
    rather than a separate Stripe price: the brief specifies the SAME $50
    bid price funds either a new project or a top-up on an existing one,
    the choice is just which button the user clicked). Standalone wrapper
    around apply_project_bid_topup() (see that function's docstring for
    exactly what happens for a trial-funded vs. already-paid project) --
    billing.handle_checkout_redirect() calls apply_project_bid_topup()
    directly inside its own transaction instead of this function, so the
    grant and the Stripe-session idempotency row commit atomically (Part
    1b); this wrapper remains for standalone/test callers. Returns True
    unless there's no ProposalUsage row for this project at all yet (see
    "no_project" above) -- in that edge case this is a no-op and the
    caller is responsible for the fallback (billing.py credits a generic
    bid_credit instead)."""
    project_key = (project_key or "").strip().lower()
    if not project_key:
        return False
    with db.get_session() as s:
        result = apply_project_bid_topup(s, user.id, project_key, passes=passes)
        s.commit()
        return result != "no_project"


def upgrade_trial_project_to_paid(user: db.User, project_key: str, passes: int = 5) -> bool:
    """Audit fix Part 1a: upgrades an already-recorded, trial-funded
    project (its one free ProposalUsage/trial pass already spent) to
    "credit"-funded, opening its 5-pass allowance with 1 already used --
    the fix for "buying a $50 bid from the blocked-download / blocked-
    repeat-run screen must unlock THAT project", which previously just
    landed as a generic account-level bid_credit that never touched the
    stuck project at all (leaving funded_by="trial" -- and downloads/
    re-runs blocked -- forever, see is_trial_funded_project()). Thin
    wrapper around apply_project_bid_topup() for standalone/test callers;
    billing.handle_checkout_redirect() calls that shared helper directly
    (see its docstring) so this exact operation and the Stripe-session
    idempotency row commit in one transaction. Returns True only if a
    trial-funded project was actually upgraded; False (no-op) if there's
    no project to attach to yet, or it was already paid-funded -- in
    either case the $50 payment must still land somewhere, which is the
    caller's job (billing.py falls back to a generic bid_credit)."""
    project_key = (project_key or "").strip().lower()
    if not project_key:
        return False
    with db.get_session() as s:
        result = apply_project_bid_topup(s, user.id, project_key, passes=passes)
        s.commit()
        return result == "upgraded_trial"
