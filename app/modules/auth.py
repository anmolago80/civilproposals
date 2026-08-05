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
    product decision: 3 free proposals, then a $200/month subscription
    (see billing.py) that also covers AI usage -- the app no longer asks
    each user for their own AI provider key in SAAS_MODE (see app.py).
  - Nothing in this module trusts st.session_state alone for "is this user
    allowed in" -- session_state is rebuilt from the verified cookie token
    on every rerun, so a user can't fake being logged in by manipulating
    client-side state.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import streamlit as st
import streamlit.components.v1 as components
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from modules import db

APP_SECRET_KEY = os.environ.get("APP_SECRET_KEY", "").strip()
if not APP_SECRET_KEY:
    # Fine for local dev (sessions just won't survive a process restart);
    # Railway deployment MUST set a real APP_SECRET_KEY env var, or every
    # deploy invalidates every logged-in user's cookie.
    APP_SECRET_KEY = "dev-only-insecure-secret-change-me"

COOKIE_NAME = "civilproposals_session"
COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60  # 30 days

_serializer = URLSafeTimedSerializer(APP_SECRET_KEY, salt="civilproposals-auth")


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
    _write_cookie_js("; ".join(parts))


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
        return None

    if st.session_state.get("_auth_user_id"):
        user = get_user_by_id(st.session_state["_auth_user_id"])
        if user and st.session_state.pop("_cookie_write_pending", False):
            _set_cookie_token(make_token(user.id))
        return user

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


def log_out() -> None:
    st.session_state.pop("_auth_user_id", None)
    st.session_state.pop("_cookie_write_pending", None)
    # Same reasoning as log_in() above, in reverse: log_out() is always
    # followed immediately by st.rerun() at its call site, which would
    # race out an immediate _clear_cookie_token() call just like it did
    # the cookie write. Deferred so the actual browser-side delete happens
    # on the next (unraced) run instead.
    st.session_state["_cookie_clear_pending"] = True


def require_login() -> db.User:
    """Renders a login/signup screen and st.stop()s if nobody's logged in.
    Returns the logged-in User otherwise. Call this before rendering any of
    the app's real tabs."""
    user = current_user()
    if user:
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
            branding.brand_html(logo_size=52, wordmark_size="1.9rem", show_beta=True)
            + '<div style="margin-top:22px;font-size:2rem;font-weight:800;letter-spacing:-0.02em;color:#0F172A;line-height:1.2;">Turn a tender brief into a first-pass proposal in minutes</div>'
            + '<div style="margin-top:12px;color:#5A6B7A;font-size:1.02rem;line-height:1.55;max-width:480px;">Compliance matrix, weighted structure, first-pass drafts, and a designed Word export -- built specifically for civil engineering firms.</div>'
        )
        st.markdown(headline_html, unsafe_allow_html=True)

        beta_html = (
            '<div style="margin-top:26px;padding:16px 18px;background:#FFF8EE;border:1px solid #F3D9AE;border-radius:12px;font-size:.88rem;color:#7A4A0A;">'
            "🧪 <strong>This product is in Beta.</strong> Features, pricing, and behaviour may still change, "
            "and you may run into rough edges -- always review AI-drafted content before it goes into a real "
            "submission. We'd genuinely appreciate feedback on anything that breaks or feels off."
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

        with tab_signup:
            with st.form("signup_form"):
                name = st.text_input("Your name")
                firm_name = st.text_input("Firm name")
                email = st.text_input("Work email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_password",
                                          help="At least 8 characters.")
                st.caption(f"Free trial: {DEFAULT_TRIAL_LIMIT} full proposals, no card required. "
                           f"Then $200/month, cancel anytime.")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                try:
                    user = create_user(email, password, name, firm_name)
                    log_in(user)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

    st.stop()


DEFAULT_TRIAL_LIMIT = 3


# ---------------------------------------------------------------------------
# Trial / subscription access
# ---------------------------------------------------------------------------

def get_access_status(user: db.User) -> dict:
    """
    Returns {"allowed": bool, "reason": str, "trial_remaining": int,
    "subscribed": bool} -- the single source of truth app.py uses to decide
    whether to show the paywall instead of the tabs, and whether to count a
    new proposal against the trial.
    """
    subscribed = user.subscription_status in ("active", "past_due")  # grace period on past_due
    trial_remaining = max(0, (user.trial_proposals_limit or 0) - (user.trial_proposals_used or 0))
    allowed = subscribed or trial_remaining > 0
    return {
        "allowed": allowed,
        "subscribed": user.subscription_status == "active",
        "past_due": user.subscription_status == "past_due",
        "trial_remaining": trial_remaining,
        "trial_limit": user.trial_proposals_limit or 0,
    }


def record_proposal_usage(user: db.User, project_key: str, project_name: str = "") -> bool:
    """
    Call this once, the first time a user runs Tender Analysis for a given
    project (project_key should be a stable identifier for that project --
    e.g. project name + tender name). If this project hasn't already been
    counted and the user isn't on a paid subscription, increments
    trial_proposals_used. Returns True if this call actually consumed a
    trial credit (idempotent otherwise -- re-analysing the same project
    never double-counts).
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
        if db_user.subscription_status != "active":
            db_user.trial_proposals_used = (db_user.trial_proposals_used or 0) + 1
        s.commit()
        return True
