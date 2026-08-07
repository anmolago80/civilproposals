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

Changing the price later: this module reads STRIPE_PRICE_ID (and
STRIPE_BID_PRICE_ID, see below) from environment variables, never hardcodes
an amount. To change either price, create a new Price in the Stripe
dashboard (Prices are immutable once created -- you can't edit $200 into
$250 on the same Price object) and update the matching env var in Railway,
then redeploy (or just restart the service). No code change needed.

Two products, one Checkout entry point each:
  - Monthly subscription (STRIPE_PRICE_ID) -- mode="subscription",
    create_checkout_session(). Unlimited bids while active (see
    auth.get_access_status/record_proposal_usage -- neither trial nor
    bid_credits balance is ever touched while subscription_status=="active").
  - Pay-as-you-go, one bid at a time (STRIPE_BID_PRICE_ID) -- mode=
    "payment", create_bid_checkout_session(). Each completed purchase adds
    exactly one credit to db.User.bid_credits, spent by
    auth.record_proposal_usage() only once the free trial is exhausted.
handle_checkout_redirect() is shared by both flows -- it tells them apart
by the returned Checkout Session's own `mode` field, so there's exactly one
redirect handler, not two.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import stripe

from modules import db

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "").strip()
STRIPE_BID_PRICE_ID = os.environ.get("STRIPE_BID_PRICE_ID", "").strip()

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")


def is_configured() -> bool:
    """The $120/month subscription checkout -- see create_checkout_session."""
    return bool(stripe.api_key and STRIPE_PRICE_ID)


def bid_is_configured() -> bool:
    """The $50/bid pay-as-you-go checkout -- see create_bid_checkout_session."""
    return bool(stripe.api_key and STRIPE_BID_PRICE_ID)


def _describe_price(price: str) -> str:
    if not price:
        return "NOT SET (empty)"
    desc = f"`{price[:10]}...` (len={len(price)})"
    if not price.startswith("price_"):
        desc += " -- does NOT start with price_, so this is not a valid Stripe Price ID"
    return desc


def debug_key_info() -> str:
    """A masked, safe-to-display summary of what's actually loaded into this
    running process for STRIPE_SECRET_KEY / STRIPE_PRICE_ID /
    STRIPE_BID_PRICE_ID -- never the full secret. Meant to be shown next to
    a checkout error (either flow -- subscription or pay-as-you-go) so a
    copy-paste or stale-deploy problem can be diagnosed from a single
    screenshot instead of several rounds of guessing. Two things this
    catches that "check Railway's variable value" alone won't: (1)
    stripe.api_key is read from the environment once, at module import time
    (see top of this file) -- if Railway saved the variable but the service
    never actually redeployed/restarted, the *running* process is still
    holding the old value, and this will show that old value's shape; (2) a
    bad paste (extra characters, only a fragment copied, wrong field
    entirely)."""
    key = stripe.api_key or ""

    if not key:
        key_desc = "NOT SET (empty)"
    else:
        prefix = key[:8]
        suffix = key[-4:] if len(key) > 12 else ""
        looks_valid = key.startswith("sk_test_") or key.startswith("sk_live_")
        key_desc = f"len={len(key)}, starts with `{prefix}`, ends with `{suffix}`"
        if not looks_valid:
            key_desc += " -- does NOT start with sk_test_ or sk_live_, so this is not a valid Stripe secret key"

    return (
        f"STRIPE_SECRET_KEY: {key_desc} | "
        f"STRIPE_PRICE_ID (monthly): {_describe_price(STRIPE_PRICE_ID)} | "
        f"STRIPE_BID_PRICE_ID (pay-as-you-go): {_describe_price(STRIPE_BID_PRICE_ID)}"
    )


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


def create_bid_checkout_session(user: db.User) -> str:
    """Creates a Stripe Checkout session for a single $50 pay-as-you-go bid
    and returns the URL to redirect the user to -- mode="payment" (a
    one-time charge), NOT "subscription". Shares the exact same success/
    cancel URL shape as create_checkout_session, so both flows land back on
    the same ?checkout=success&session_id=... redirect handler below, which
    tells them apart by the completed session's own `mode` field."""
    if not bid_is_configured():
        raise RuntimeError(
            "Pay-as-you-go isn't configured yet -- set STRIPE_SECRET_KEY and STRIPE_BID_PRICE_ID."
        )

    kwargs = dict(
        mode="payment",
        line_items=[{"price": STRIPE_BID_PRICE_ID, "quantity": 1}],
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
    query string alone) and updates the user's row. Handles BOTH checkout
    flows -- distinguishes them by the verified session's own `mode` field
    ("subscription" activates the monthly plan; "payment" is a pay-as-you-go
    bid purchase, credited as +1 db.User.bid_credits) -- rather than needing
    two separate redirect handlers wired to two different query params.
    Returns the updated user, or None if the session couldn't be verified."""
    if not stripe.api_key or not session_id:
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
        if session.get("mode") == "subscription":
            db_user.stripe_subscription_id = session.get("subscription") or db_user.stripe_subscription_id
            db_user.subscription_status = "active"
        else:
            # Pay-as-you-go: always +1 -- create_bid_checkout_session always
            # requests quantity=1, so there's no line-item quantity to read.
            db_user.bid_credits = (db_user.bid_credits or 0) + 1
        s.commit()
        s.refresh(db_user)
        return db_user


def refresh_subscription_status(user: db.User) -> db.User:
    """Pulls the live subscription status from Stripe and syncs it to the
    DB. Safe to call often (e.g. once per login) -- a no-op if the user has
    never subscribed. Also resets the Monthly plan's "3 bids included"
    quota (db.User.subscription_bids_used, see auth.
    SUBSCRIPTION_MONTHLY_BID_LIMIT) when Stripe reports a new billing period
    has started -- detected by comparing the live current_period_end against
    the value stored from the last check, since this module runs webhook-
    free and a login-frequency check is what "reset once a month" actually
    reduces to without one."""
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

    # Naive UTC throughout (not tz-aware) -- matches how SQLite (the local
    # dev fallback) round-trips DateTime columns, so comparing against
    # user.subscription_period_end never risks a naive-vs-aware TypeError.
    period_end_ts = sub.get("current_period_end")
    new_period_end = (
        datetime.fromtimestamp(period_end_ts, tz=timezone.utc).replace(tzinfo=None)
        if period_end_ts else None
    )
    period_rolled_over = (
        new_period_end is not None
        and (user.subscription_period_end is None or new_period_end > user.subscription_period_end)
    )

    if new_status != user.subscription_status or period_rolled_over:
        with db.get_session() as s:
            db_user = s.query(db.User).filter(db.User.id == user.id).first()
            if db_user:
                db_user.subscription_status = new_status
                if period_rolled_over:
                    db_user.subscription_bids_used = 0
                    db_user.subscription_period_end = new_period_end
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
