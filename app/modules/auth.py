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

from modules import db, email_utils

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

    st.markdown(
        branding.brand_html(logo_size=44, wordmark_size="1.5rem", show_beta=True, href="https://civilproposals.com"),
        unsafe_allow_html=True,
    )
    st.markdown("### Before you continue")
    st.write(
        "Please review and accept the terms below -- this only takes a second, and you "
        "won't be asked again."
    )
    st.markdown(
        f'<div style="margin-top:6px;padding:16px 18px;background:#F8FAFC;border:1px solid #E2E8F0;'
        f'border-radius:10px;font-size:.92rem;color:#334155;line-height:1.6;max-width:640px;">{TERMS_TEXT} '
        f'This is a summary of the AI-output disclaimer in our '
        f'<a href="https://civilproposals.com/terms-of-service.html" target="_blank">Terms of Service</a>, '
        f'which governs your use of CivilProposals in full.</div>',
        unsafe_allow_html=True,
    )
    accepted = st.checkbox("I have read and accept these terms and the Terms of Service.", key="_terms_gate_checkbox")
    gate_col1, gate_col2 = st.columns([1, 4])
    with gate_col1:
        if st.button("Accept and continue", type="primary", disabled=not accepted, key="_terms_gate_accept_btn"):
            accept_terms(user)
            st.rerun()
    with gate_col2:
        if st.button("Log out instead", key="_terms_gate_logout_btn"):
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
        if user.accepted_terms_at is None:
            _render_terms_gate(user)  # always st.stop()s
        return user

    from modules import branding  # imported here to avoid a circular import at module load time

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

    left, right = st.columns([1.15, 1], gap="large")

    with left:
        # Built as single-line, unindented HTML strings on purpose -- see
        # the comment in branding.brand_html() about st.markdown() treating
        # indented multi-line blocks as literal Markdown code blocks even
        # with unsafe_allow_html=True.
        headline_html = (
            branding.brand_html(logo_size=52, wordmark_size="1.9rem", show_beta=True, href="https://civilproposals.com")
            + '<div style="margin-top:22px;font-size:2rem;font-weight:800;letter-spacing:-0.02em;color:#0F172A;line-height:1.2;">Built by Civil Engineers, for Civil Engineers</div>'
            + '<div style="margin-top:12px;color:#5A6B7A;font-size:1.02rem;line-height:1.6;max-width:560px;">'
            + 'We know the challenges you face every day because we face them too. Whether it&#39;s a small '
            + 'project with a simple scope, a brief buried in an email, a client who isn&#39;t quite sure what '
            + 'they want, or a major tender that takes days to read and weeks to prepare, CivilProposals is '
            + 'designed to help. Built by civil engineers, for civil engineers, the platform assists you in '
            + 'creating professional, well structured proposals faster, allowing you to focus on understanding '
            + 'client needs and developing winning solutions.</div>'
        )
        st.markdown(headline_html, unsafe_allow_html=True)

        beta_html = (
            '<div style="margin-top:26px;padding:16px 18px;background:#FFF8EE;border:1px solid #F3D9AE;border-radius:12px;font-size:.88rem;color:#7A4A0A;">'
            "🚀 <strong>Beta Access.</strong> This product is currently in beta. Features and pricing may "
            "change, and occasional issues may occur. Always review and verify AI generated content before "
            "using it in tender submissions or other formal documentation. If something doesn't look right, "
            "please let us know."
            "</div>"
        )
        st.markdown(beta_html, unsafe_allow_html=True)

    with right:
        tab_login, tab_signup = st.tabs(["Log in", "Create account"])

        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
            if submitted:
                user = authenticate(email, password)
                if user:
                    log_in(user)
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

            with st.popover("Forgot password?"):
                st.caption("Enter your account email and we'll send a link to reset your password.")
                with st.form("forgot_password_form"):
                    forgot_email = st.text_input("Email", key="_forgot_pw_email")
                    forgot_submitted = st.form_submit_button("Send reset link")
                if forgot_submitted:
                    status = request_password_reset(forgot_email)
                    if status == "not_configured":
                        st.error("Password reset isn't set up yet -- contact support directly for now.")
                    else:
                        st.success(
                            "If an account exists for that email, we've sent a reset link -- check your inbox "
                            "(and spam folder). It's valid for 1 hour."
                        )

        with tab_signup:
            with st.form("signup_form"):
                name = st.text_input("Your name")
                firm_name = st.text_input("Firm name")
                email = st.text_input("Work email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_password",
                                          help="At least 8 characters.")
                confirm_password = st.text_input("Confirm password", type="password", key="signup_confirm_password")
                st.caption(f"Free trial: {DEFAULT_TRIAL_LIMIT} full bid, no card required. "
                           f"Then pay per bid, or subscribe monthly -- see pricing on the homepage.")
                with st.expander("Terms you're agreeing to"):
                    st.markdown(
                        f'<div style="font-size:.85rem;color:#475569;line-height:1.6;">{TERMS_TEXT} '
                        f'This is a summary of the AI-output disclaimer in our '
                        f'<a href="https://civilproposals.com/terms-of-service.html" target="_blank">Terms of Service</a>, '
                        f'which governs your use of CivilProposals in full.</div>',
                        unsafe_allow_html=True,
                    )
                agreed_terms = st.checkbox("I have read and accept the terms above and the Terms of Service.", key="signup_terms_checkbox")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                if password != confirm_password:
                    st.error("Passwords don't match -- please re-enter them.")
                elif not agreed_terms:
                    st.error("Please accept the terms above to create an account.")
                else:
                    try:
                        user = create_user(email, password, name, firm_name)
                        accept_terms(user)
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
        st.success("Password updated -- you can log in with your new password now.")
        if st.button("Continue to log in", type="primary"):
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

# The Monthly plan's advertised "3 bids included" (see the landing page
# pricing card) -- an active subscription used to be treated as fully
# unlimited in code, which didn't match that promise. Spent via
# db.User.subscription_bids_used, reset each real Stripe billing period by
# billing.refresh_subscription_status(); see get_access_status/
# record_proposal_usage below for how it's actually enforced.
SUBSCRIPTION_MONTHLY_BID_LIMIT = 3

# Accounts that get real, unconditional unlimited access -- never blocked,
# never shown a trial-limit or upgrade banner, no matter how many bids they
# run. This used to also fake-show the normal "trial limit reached" banner
# so the account holder could preview its design on a live account (see
# UNLIMITED_PREVIEW_ACCOUNTS in git history) -- dropped in favour of just
# treating these accounts as fully unlimited with no caveat, per product
# decision. Lowercased/stripped to match how emails are stored (see
# create_user()).
UNLIMITED_ACCOUNTS = {"anmolago@icloud.com"}


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

    An ACTIVE subscription is capped at SUBSCRIPTION_MONTHLY_BID_LIMIT (3)
    bids per real Stripe billing period -- matches the landing page's "3
    bids included" promise, which the code used to silently ignore (treating
    "subscribed" as fully unlimited). Once that monthly quota is used up,
    bid_credits (pay-as-you-go purchases) still work on top of it, same as
    for a non-subscriber.

    PAST_DUE is a short payment-recovery grace period -- deliberately left
    uncapped (always allowed) rather than also enforcing the monthly quota
    on top of an already-failing card; this is unchanged from before.

    bid_credits is the pay-as-you-go balance (see db.User.bid_credits) --
    real, paid credits from $50 one-time Stripe Checkouts.

    "limit_reached" mirrors "not allowed" for everyone except
    UNLIMITED_ACCOUNTS, who never see it go true -- see "unlimited" below.
    """
    is_unlimited = (user.email or "").strip().lower() in UNLIMITED_ACCOUNTS
    trial_remaining = max(0, DEFAULT_TRIAL_LIMIT - (user.trial_proposals_used or 0))
    bid_credits = max(0, user.bid_credits or 0)
    subscription_bids_remaining = max(0, SUBSCRIPTION_MONTHLY_BID_LIMIT - (user.subscription_bids_used or 0))

    if user.subscription_status == "active":
        allowed = is_unlimited or subscription_bids_remaining > 0 or bid_credits > 0
        limit_reached = not allowed
    elif user.subscription_status == "past_due":
        allowed = True  # grace period, unchanged
        limit_reached = False
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
    project (project_key should be a stable identifier for that project --
    e.g. project name + tender name). If this project hasn't already been
    counted, spends one credit, in priority order:
      - ACTIVE subscription: the current billing period's monthly quota
        (SUBSCRIPTION_MONTHLY_BID_LIMIT) first, then a purchased
        pay-as-you-go bid_credit once that's used up.
      - Otherwise (trial/canceled): the free trial credit first, then a
        bid_credit once the trial is exhausted.
      - PAST_DUE: neither balance is touched -- short grace period, see
        get_access_status.
    Returns True if this call actually consumed a credit of some kind
    (idempotent otherwise -- re-analysing the same project never
    double-counts, and this also returns True in that "nothing left to
    spend" edge case since the project itself still got recorded -- the
    caller is expected to have already checked get_access_status().allowed
    before letting this run at all).
    """
    project_key = (project_key or "").strip().lower()
    if not project_key:
        return False

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

        s.add(db.ProposalUsage(user_id=db_user.id, project_key=project_key, project_name=project_name))
        if db_user.subscription_status == "active":
            sub_remaining = max(0, SUBSCRIPTION_MONTHLY_BID_LIMIT - (db_user.subscription_bids_used or 0))
            if sub_remaining > 0:
                db_user.subscription_bids_used = (db_user.subscription_bids_used or 0) + 1
            elif (db_user.bid_credits or 0) > 0:
                db_user.bid_credits = db_user.bid_credits - 1
        elif db_user.subscription_status != "past_due":
            trial_remaining = max(0, DEFAULT_TRIAL_LIMIT - (db_user.trial_proposals_used or 0))
            if trial_remaining > 0:
                db_user.trial_proposals_used = (db_user.trial_proposals_used or 0) + 1
            elif (db_user.bid_credits or 0) > 0:
                db_user.bid_credits = db_user.bid_credits - 1
        s.commit()
        return True
