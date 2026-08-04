"""
billing.py

Stripe integration for CivilProposals. Deliberately webhook-free for the
MVP: Streamlit apps don't expose arbitrary HTTP routes the way a Flask/
FastAPI app does, so rather than standing up a second Railway service just
to receive Stripe webhooks, this module verifies subscription state by
calling the Stripe API directly (on login, and right after a Checkout
redirect) instead of waiting to be told about it.

Trade-off, stated plainly: a cancellation made in the Stripe customer
portal won't be reflected here until the user's next login (session
refresh), not instantly. For an MVP selling to a small number of
transportation/civil firms, that lag is a reasonable trade for not running
a second service. Revisit with a real webhook endpoint (a small FastAPI
sidecar service, or Railway's function support) once there's a reason to
-- e.g. wanting to cut off access the instant a card fails.

Changing the price later: this module reads STRIPE_PRICE_ID from an
environment variable, never hardcodes an amount. To change the price,
create a new Price in the Stripe dashboard (Prices are immutable once
created -- you can't edit $200 into $250 on the same Price object) and
update the STRIPE_PRICE_ID env var in Railway, then redeploy (or just
restart the service). No code change needed.
"""

from __future__ import annotations

import os

import stripe

from modules import db

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "").strip()

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")


def is_configured() -> bool:
    return bool(stripe.api_key and STRIPE_PRICE_ID)


def debug_key_info() -> str:
    """A masked, safe-to-display summary of what's actually loaded into this
    running process for STRIPE_SECRET_KEY / STRIPE_PRICE_ID -- never the full
    secret. Meant to be shown next to a checkout error so a copy-paste or
    stale-deploy problem can be diagnosed from a single screenshot instead of
    several rounds of guessing. Two things this catches that "check Railway's
    variable value" alone won't: (1) stripe.api_key is read from the
    environment once, at module import time (see top of this file) -- if
    Railway saved the variable but the service never actually redeployed/
    restarted, the *running* process is still holding the old value, and this
    will show that old value's shape; (2) a bad paste (extra characters,
    only a fragment copied, wrong field entirely)."""
    key = stripe.api_key or ""
    price = STRIPE_PRICE_ID or ""

    if not key:
        key_desc = "NOT SET (empty)"
    else:
        prefix = key[:8]
        suffix = key[-4:] if len(key) > 12 else ""
        looks_valid = key.startswith("sk_test_") or key.startswith("sk_live_")
        key_desc = f"len={len(key)}, starts with `{prefix}`, ends with `{suffix}`"
        if not looks_valid:
            key_desc += " -- does NOT start with sk_test_ or sk_live_, so this is not a valid Stripe secret key"

    if not price:
        price_desc = "NOT SET (empty)"
    else:
        price_desc = f"`{price[:10]}...` (len={len(price)})"
        if not price.startswith("price_"):
            price_desc += " -- does NOT start with price_, so this is not a valid Stripe Price ID"

    return f"STRIPE_SECRET_KEY: {key_desc} | STRIPE_PRICE_ID: {price_desc}"


def create_checkout_session(user: db.User) -> str:
    """Creates a Stripe Checkout session for a new subscription and returns
    the URL to redirect the user to. client_reference_id carries our user
    id through so the success redirect can look the user back up."""
    if not is_configured():
        raise RuntimeError(
            "Stripe isn't configured yet -- set STRIPE_SECRET_KEY and STRIPE_PRICE_ID."
        )

    kwargs = dict(
        mode="subscription",
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        client_reference_id=user.id,
        success_url=f"{APP_BASE_URL}/?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{APP_BASE_URL}/?checkout=cancelled",
        allow_promotion_codes=True,
    )
    if user.stripe_customer_id:
        kwargs["customer"] = user.stripe_customer_id
    else:
        kwargs["customer_email"] = user.email

    session = stripe.checkout.Session.create(**kwargs)
    return session.url


def handle_checkout_redirect(session_id: str) -> db.User | None:
    """Call this when the app loads with ?checkout=success&session_id=...
    in the URL. Verifies the session with Stripe directly (never trust the
    query string alone) and updates the user's row. Returns the updated
    user, or None if the session couldn't be verified."""
    if not is_configured() or not session_id:
        return None

    session = stripe.checkout.Session.retrieve(session_id)
    if session.get("payment_status") not in ("paid", "no_payment_required") and session.get("status") != "complete":
        return None

    user_id = session.get("client_reference_id")
    if not user_id:
        return None

    with db.get_session() as s:
        db_user = s.query(db.User).filter(db.User.id == user_id).first()
        if not db_user:
            return None
        db_user.stripe_customer_id = session.get("customer") or db_user.stripe_customer_id
        db_user.stripe_subscription_id = session.get("subscription") or db_user.stripe_subscription_id
        db_user.subscription_status = "active"
        s.commit()
        s.refresh(db_user)
        return db_user


def refresh_subscription_status(user: db.User) -> db.User:
    """Pulls the live subscription status from Stripe and syncs it to the
    DB. Safe to call often (e.g. once per login) -- a no-op if the user has
    never subscribed."""
    if not is_configured() or not user.stripe_subscription_id:
        return user

    try:
        sub = stripe.Subscription.retrieve(user.stripe_subscription_id)
    except stripe.error.StripeError:
        return user

    status_map = {
        "active": "active",
        "trialing": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "incomplete_expired": "canceled",
    }
    new_status = status_map.get(sub.get("status"), user.subscription_status)

    if new_status != user.subscription_status:
        with db.get_session() as s:
            db_user = s.query(db.User).filter(db.User.id == user.id).first()
            if db_user:
                db_user.subscription_status = new_status
                s.commit()
                s.refresh(db_user)
                return db_user
    return user


def create_customer_portal_session(user: db.User) -> str | None:
    """Lets a subscribed user manage/cancel their own subscription without
    you doing it manually in the Stripe dashboard. Returns the portal URL,
    or None if the user has no Stripe customer yet."""
    if not is_configured() or not user.stripe_customer_id:
        return None
    portal = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{APP_BASE_URL}/",
    )
    return portal.url
