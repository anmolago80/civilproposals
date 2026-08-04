"""
auth.py

Account signup/login, session persistence (via a signed browser cookie), and
free-trial / subscription access gating for the CivilProposals SaaS build.

Design notes:
  - Passwords are hashed with bcrypt, never stored or logged in plain text.
  - "Logged in" is proven by a signed, timestamped token (itsdangerous)
    stored in a browser cookie via extra_streamlit_components.CookieManager
    -- Streamlit has no built-in multi-user session concept, so without a
    cookie every browser refresh would log the user out.
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

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import streamlit as st
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
# Cookie manager (one instance per session, cached in session_state)
# ---------------------------------------------------------------------------

def _cookie_manager():
    import extra_streamlit_components as stx
    if "_cookie_manager" not in st.session_state:
        st.session_state["_cookie_manager"] = stx.CookieManager(key="cp_cookie_manager")
    return st.session_state["_cookie_manager"]


# Sentinel returned by _get_cookie_token() when the browser-side cookie
# component hasn't reported back yet -- distinct from a real "no session
# cookie", which current_user() treats as "not logged in".
_COOKIES_LOADING = object()


def _get_cookie_token():
    cm = _cookie_manager()
    # Deliberately cm.get_all() here, not cm.get(COOKIE_NAME). extra_
    # streamlit_components' CookieManager only populates self.cookies once,
    # when its underlying browser component is first constructed, and
    # .get() just reads that frozen snapshot forever after -- see its
    # source (CookieManager.__init__ vs .get()). That very first read
    # always happens before the browser-side component has had a chance to
    # actually report back what's in document.cookie (it's a real round
    # trip through an iframe), so the snapshot is reliably empty. Combined
    # with the object above being cached in session_state across reruns
    # (needed so logging in/out -- which reads the cookie, then writes it,
    # in the same script run -- doesn't re-declare the component with the
    # same key and crash), nothing was ever calling get_all() again to
    # pick up the real value afterwards. That's what was logging returning
    # users out on every single browser refresh: the cookie was sitting in
    # the browser the whole time, this code just never looked again after
    # its first (always-empty) look. Calling get_all() explicitly here
    # re-queries the component fresh on every call (via its own default
    # key, "get_all", distinct from the "cp_cookie_manager" construction
    # key above, so it can't collide with it), which correctly picks up
    # the real cookie value as soon as the browser has reported it.
    #
    # That fix alone still leaves one gap under real network latency
    # (custom domain, TLS handshake, slower than the near-instant round
    # trip on localhost): the very first script run after every fresh page
    # load still gets an empty read back, because the component genuinely
    # hasn't had time to report anything yet. Locally that self-corrects
    # via Streamlit's automatic rerun so fast it's invisible; over a real
    # network it can be slow enough that a returning user briefly sees the
    # login screen before it corrects itself -- exactly what "checked
    # immediately, it was instant" described. An entirely empty cookies
    # dict is the tell: Streamlit itself always sets at least an XSRF
    # cookie on the very first HTTP response, before any client-side JS
    # (including this component) even runs, so a real completed read is
    # never truly empty -- only "hasn't loaded yet" is. Returning a
    # sentinel here instead of None lets current_user() wait for the next
    # rerun rather than concluding "logged out" from an incomplete read.
    cookies = cm.get_all()
    if not cookies:
        return _COOKIES_LOADING
    return cookies.get(COOKIE_NAME)


def _set_cookie_token(token: str) -> None:
    cm = _cookie_manager()
    # extra_streamlit_components.CookieManager.set() calls .isoformat() on
    # expires_at internally, so this must be a real datetime -- a Unix
    # timestamp (time.time()) crashes with "float object has no attribute
    # isoformat".
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=COOKIE_MAX_AGE_SECONDS)
    cm.set(COOKIE_NAME, token, expires_at=expires_at, key="cp_cookie_set")


def _clear_cookie_token() -> None:
    cm = _cookie_manager()
    try:
        cm.delete(COOKIE_NAME, key="cp_cookie_delete")
    except KeyError:
        pass


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
    if st.session_state.get("_auth_user_id"):
        return get_user_by_id(st.session_state["_auth_user_id"])

    token = _get_cookie_token()
    if token is _COOKIES_LOADING:
        # The browser hasn't reported its cookies back yet -- true for at
        # least the very first script run after every fresh page load, and
        # potentially a couple more under real network latency. Don't
        # decide "not logged in" from an incomplete read: wait for the
        # rerun that fires automatically once the cookie component
        # actually reports a value (same mechanism as any other Streamlit
        # widget picking up its real value after the frontend responds).
        # A user who's genuinely never logged in also passes through here
        # once or twice before landing on the login screen -- one brief,
        # unlabelled instant is a fair trade for not bouncing a returning
        # user's session on every refresh.
        st.stop()
    user_id = verify_token(token) if token else None
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if user:
        st.session_state["_auth_user_id"] = user.id
    return user


def log_in(user: db.User) -> None:
    st.session_state["_auth_user_id"] = user.id
    _set_cookie_token(make_token(user.id))


def log_out() -> None:
    st.session_state.pop("_auth_user_id", None)
    _clear_cookie_token()


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
