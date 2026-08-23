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
dashboard (Prices are immutable once created -- you can't edit $120 into
$150 on the same Price object) and update the matching env var in Railway,
then redeploy (or just restart the service). No code change needed.

Two products, one Checkout entry point each:
  - Monthly subscription (STRIPE_PRICE_ID) -- mode="subscription",
    create_checkout_session(). Capped at auth.SUBSCRIPTION_MONTHLY_BID_LIMIT
    (4) full generation cycles per real Stripe billing period while active
    (see auth.get_access_status/record_proposal_usage) -- neither trial nor
    bid_credits balance is ever touched while subscription_status=="active";
    bid_credits still work on top of the monthly cap once it's used up.
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
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import stripe
from sqlalchemy.exc import IntegrityError

from modules import db, email_utils

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


def create_bid_checkout_session(user: db.User, topup_project_key: str | None = None) -> str:
    """Creates a Stripe Checkout session for a single $50 pay-as-you-go bid
    and returns the URL to redirect the user to -- mode="payment" (a
    one-time charge), NOT "subscription". Shares the exact same success/
    cancel URL shape as create_checkout_session, so both flows land back on
    the same ?checkout=success&session_id=... redirect handler below, which
    tells them apart by the completed session's own `mode` field.

    Part B2's "$50 top-up -> +5 passes on the SAME project" reuses this
    exact same $50 Stripe price rather than a second one -- the brief's own
    words are "the same $50 bid price"; the only difference is what the
    payment is FOR, which is carried through Stripe as Checkout Session
    metadata (topup_project_key) and read back by handle_checkout_redirect()
    below. When given, the completed payment adds 5 passes to that project
    instead of the normal "+1 bid_credit, starts a new project" outcome."""
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
    if topup_project_key:
        kwargs["metadata"] = {"topup_project_key": topup_project_key.strip().lower()}
    if user.stripe_customer_id:
        kwargs["customer"] = user.stripe_customer_id
    else:
        kwargs["customer_email"] = user.email

    session = stripe.checkout.Session.create(**kwargs)
    return session.url


@dataclass
class CheckoutRedirectResult:
    """Return value of handle_checkout_redirect().

    `applied` is True whenever the purchase was actually applied to
    client_reference_id in the database -- including a replay of an
    already-applied session, and including the case where nobody (or the
    wrong somebody) is logged in in THIS browser session. It says nothing
    about who is looking at the result; it says whether the money moved.

    `user`/`purchase_kind` are populated ONLY when auth.current_user() in
    this same request is confirmed to be the exact account the purchase
    was applied to -- see the Part 4b comment below for why. When
    `applied` is True but `user` is None, the caller must NOT treat this
    as "nothing happened": the purchase went through, there's just nobody
    here it can be safely shown to. Keep the session_id in the URL in
    that case (see 00_init.py) so the next matching-session load of this
    same redirect resolves `user` for real, off the now-idempotent
    ProcessedCheckoutSession row, instead of losing the retry path."""
    user: "db.User | None" = None
    purchase_kind: "str | None" = None
    applied: bool = False


def handle_checkout_redirect(session_id: str) -> CheckoutRedirectResult:
    """Call this when the app loads with ?checkout=success&session_id=...
    in the URL. Verifies the session with Stripe directly (never trust the
    query string alone) and updates the user's row. Handles BOTH checkout
    flows -- distinguishes them by the verified session's own `mode` field
    ("subscription" activates the monthly plan; "payment" is a pay-as-you-go
    bid purchase, credited as +1 db.User.bid_credits) -- rather than needing
    two separate redirect handlers wired to two different query params.

    Idempotent against replays of the same session_id (see
    db.ProcessedCheckoutSession) -- this URL is a plain GET that survives in
    browser history/bookmarks/refresh, so without this check, re-visiting it
    would re-apply the purchase every single time (another +1 bid_credit, or
    silently re-running the subscription branch). A Stripe API error (network
    issue, Stripe outage) is allowed to raise here rather than being caught
    -- see app.py's caller, which distinguishes "genuinely wasn't paid"
    (CheckoutRedirectResult(applied=False), not an error) from "couldn't
    verify" (raises, shown to the customer with a retry path) on purpose;
    swallowing errors in here would make that distinction impossible for
    the caller to make.

    Returns a CheckoutRedirectResult (see its own docstring for the
    applied/user split -- READ IT before changing this function; it's the
    whole point of the Round 6 fix below). purchase_kind, when set, is
    "topup" when this payment specifically added passes to an existing
    project (see the _topup_project_key branch below) and None for every
    other outcome, INCLUDING a topup checkout that fell back to a plain bid
    credit (no matching project) and a replay of an already-processed
    session -- the caller (00_init.py) uses it only to choose between the
    generic "payment confirmed" toast and the more specific "N passes added
    to this project" one, so None just means "show the generic one",
    never an error. Kept separate from _receipt_kind below (which still
    only distinguishes "subscription"/"bid" and drives the receipt EMAIL's
    wording) -- widening _receipt_kind itself to a third value would also
    change what the topup receipt email says, which is a separate, unnamed
    change this pass doesn't make.

    FIX BRIEF ROUND 6, Part 1: the Part 4b guard used to live right here,
    before any of the money-applying work below, and returned early on a
    session-identity mismatch -- which meant a customer whose browser had
    no valid session cookie at the exact moment Stripe redirected them
    back (uncommon, but a real possibility -- a fresh tab, a cleared
    cookie jar, a corporate proxy that strips it) was charged by Stripe
    and got NOTHING: no subscription activated, no bid credited, and
    (because 00_init.py's caller took the "wasn't paid" branch and
    cleared the query params) no session_id left in the URL to retry
    with. This module is deliberately webhook-free (see the module
    docstring) -- handle_checkout_redirect() is the ONLY code path that
    ever applies a Checkout Session, so returning early here didn't just
    skip showing a confirmation, it skipped the purchase itself, with no
    second chance. Money must never depend on who happens to be logged in
    at the exact millisecond a redirect lands; it must depend only on
    client_reference_id, which is what actually got charged. The identity
    check still happens -- Part 4b's real goal, never leaking a foreign
    User object into the wrong request, is still met -- it just happens
    at the RETURN, after the purchase is applied, via
    CheckoutRedirectResult.applied vs .user, not before it."""
    if not stripe.api_key or not session_id:
        return CheckoutRedirectResult()

    session = stripe.checkout.Session.retrieve(session_id)
    # payment_status is the only field that actually says money changed
    # hands. session.status=="complete" just means the Checkout FORM was
    # completed -- for async payment methods (bank debits, some
    # wallets/vouchers) that happens immediately while payment_status stays
    # "unpaid" for hours/days until it actually settles (or fails). The
    # previous `... and session.get("status") != "complete"` here was an
    # AND, not an OR, so a complete-but-unpaid session slipped straight
    # through and got credited immediately -- an attacker (or just an
    # unlucky async payment) could get a bid/subscription for free, or for
    # a payment that later fails entirely. payment_status alone is the
    # correct and sufficient check; status is irrelevant to "was this
    # actually paid".
    if session.get("payment_status") not in ("paid", "no_payment_required"):
        return CheckoutRedirectResult()

    user_id = session.get("client_reference_id")
    if not user_id:
        return CheckoutRedirectResult()

    # Resolved once, up front, purely to decide what's SAFE TO RETURN --
    # never used to decide whether to apply the purchase below. See
    # CheckoutRedirectResult's docstring and the Round 6 note above.
    from modules import auth
    _requesting_user = auth.current_user()

    def _result_for(applied_user_id: str, user_row, purchase_kind) -> CheckoutRedirectResult:
        if _requesting_user is not None and _requesting_user.id == applied_user_id:
            return CheckoutRedirectResult(user=user_row, purchase_kind=purchase_kind, applied=True)
        return CheckoutRedirectResult(user=None, purchase_kind=None, applied=True)

    with db.get_session() as s:
        already = s.query(db.ProcessedCheckoutSession).filter(
            db.ProcessedCheckoutSession.session_id == session_id,
        ).first()
        if already:
            # Already applied -- return the user's current state (not a
            # re-application) so the caller still sees a "success" outcome
            # for a plain refresh/replay, without spending anything twice.
            # purchase_kind is None here (not re-derived) -- a replay
            # showing the generic toast instead of the specific topup one
            # is a cosmetic difference only, not worth re-querying for.
            already_user = s.query(db.User).filter(db.User.id == already.user_id).first()
            return _result_for(already.user_id, already_user, None)

        db_user = s.query(db.User).filter(db.User.id == user_id).first()
        if not db_user:
            return CheckoutRedirectResult()
        db_user.stripe_customer_id = session.get("customer") or db_user.stripe_customer_id
        _topup_project_key = ((session.get("metadata") or {}).get("topup_project_key") or "").strip().lower()
        _purchase_kind = None
        if session.get("mode") == "subscription":
            db_user.stripe_subscription_id = session.get("subscription") or db_user.stripe_subscription_id
            db_user.subscription_status = "active"
            _receipt_kind = "subscription"
        elif _topup_project_key:
            # Part 1a/1b of the audit fix brief: this $50 payment is
            # earmarked (via Checkout Session metadata -- see
            # create_bid_checkout_session) for a SPECIFIC project, either to
            # unlock a trial-funded project that's stuck (buying a bid must
            # actually unlock it, not just land as an unrelated account
            # credit) or to top up an already-paid project's pass
            # allowance (Part B2). auth.apply_project_bid_topup() figures
            # out which case this is and applies it directly inside THIS
            # session/transaction -- not a separate session opened after
            # this one commits, which is what Part 1b's audit finding was
            # about: a crash between the two would leave a customer charged
            # with nothing granted, and the idempotency row below would
            # make sure that never got retried either. One transaction, one
            # commit, both succeed or neither does.
            from modules import auth
            _topup_result = auth.apply_project_bid_topup(s, db_user.id, _topup_project_key, passes=5)
            if _topup_result == "no_project":
                # Nothing recorded for this project yet (shouldn't normally
                # happen -- the UI only offers a project-specific top-up
                # button once a project has actually been analysed -- but
                # never silently drop a real $50 payment over it) -- fall
                # back to the plain pay-as-you-go credit below.
                db_user.bid_credits = (db_user.bid_credits or 0) + 1
            else:
                _purchase_kind = "topup"
            _receipt_kind = "bid"
        else:
            # Pay-as-you-go: always +1 -- create_bid_checkout_session always
            # requests quantity=1, so there's no line-item quantity to read.
            db_user.bid_credits = (db_user.bid_credits or 0) + 1
            _receipt_kind = "bid"
        s.add(db.ProcessedCheckoutSession(session_id=session_id, user_id=db_user.id))
        try:
            s.commit()
        except IntegrityError:
            # The `already` check above and this insert aren't atomic --
            # two tabs/requests hitting this same success URL at once (a
            # very plausible double-tab scenario: someone completes
            # checkout, then hits back+refresh, or Stripe's own redirect
            # double-fires) can both pass the check before either commits,
            # so the second commit here hits ProcessedCheckoutSession's
            # session_id primary key and raises. Without this, that
            # IntegrityError propagated all the way to the customer as a
            # scary generic error screen immediately after paying
            # successfully. Roll back this attempt's (redundant) credit and
            # return the OTHER commit's already-applied result instead --
            # same outcome as the `already` branch above, just discovered a
            # few lines later.
            s.rollback()
            raced_user = s.query(db.User).filter(db.User.id == user_id).first()
            return _result_for(user_id, raced_user, None)
        s.refresh(db_user)

    # Best-effort receipt email -- the purchase itself is already committed
    # above regardless of whether this send succeeds, since a paying
    # customer must never have their payment silently lost over an email
    # provider hiccup. Previously Stripe's own receipt (generic, no mention
    # of what CivilProposals-specific thing it unlocked) was the only
    # confirmation anyone got.
    try:
        email_utils.send_purchase_receipt_email(db_user.email, _receipt_kind)
    except Exception as exc:
        print(f"[purchase_receipt_email] failed for {db_user.email}: {exc}", file=sys.stderr)

    return _result_for(user_id, db_user, _purchase_kind)


def refresh_subscription_status(user: db.User) -> db.User:
    """Pulls the live subscription status from Stripe and syncs it to the
    DB. Safe to call often (e.g. once per login) -- a no-op if the user has
    never subscribed. Also resets the Monthly plan's "4 bids included"
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
        _entering_past_due = new_status == "past_due" and user.subscription_status != "past_due"
        with db.get_session() as s:
            db_user = s.query(db.User).filter(db.User.id == user.id).first()
            if db_user:
                db_user.subscription_status = new_status
                if period_rolled_over:
                    db_user.subscription_bids_used = 0
                    db_user.subscription_period_end = new_period_end
                s.commit()
                s.refresh(db_user)

                # Best-effort failed-payment nudge -- fires once, on the
                # transition INTO past_due (not on every subsequent login
                # while still stuck there, since this runs on every login
                # and would otherwise re-send every single time). Previously
                # a failing card produced no outbound signal at all; the
                # customer would only find out from the in-app banner on
                # their next visit, if they even came back.
                if _entering_past_due:
                    try:
                        email_utils.send_payment_failed_email(db_user.email)
                    except Exception as exc:
                        print(f"[payment_failed_email] failed for {db_user.email}: {exc}", file=sys.stderr)

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
