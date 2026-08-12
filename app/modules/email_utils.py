"""
email_utils.py

Transactional email via Resend (https://resend.com). Originally just
password-reset links (see auth.request_password_reset()); also sends the
rest of the conversion-loop emails a real paid product needs and this one
was missing entirely -- a welcome email on signup, a receipt after any
Stripe purchase, a nudge the moment someone's free trial bid is spent (with
a clear next step instead of just hitting a paywall with no warning), and a
heads-up when a subscription's payment fails. Every sender function here
follows the same rule as send_password_reset_email(): raise on failure, and
let the CALLER decide whether/how to swallow it -- callers all wrap these in
try/except and log to stderr rather than letting an email hiccup break the
actual thing the user was doing (signing up, paying, running analysis).
A thin wrapper around Resend's plain REST API (POST
https://api.resend.com/emails) via `requests` (already a dependency -- see
requirements.txt) rather than their Python SDK, to avoid adding one more
dependency for what's a handful of API calls.

Setup -- real account/DNS steps, not something this code can do for you:
  1. Create a free account at https://resend.com (free tier covers this
     easily -- 3,000 emails/month).
  2. Add civilproposals.com (or a subdomain, e.g. mail.civilproposals.com)
     as a sending domain in Resend, then add the DNS records Resend gives
     you (SPF/DKIM TXT records) at your DNS provider -- Cloudflare, per the
     domain's WHOIS registrar. Until that domain shows "Verified" in
     Resend, it will only actually deliver mail to your own Resend account
     email, not to real users -- fine for testing this yourself, not for
     real password resets.
  3. Create an API key in the Resend dashboard (Settings -> API Keys),
     starts with `re_` -- set it as RESEND_API_KEY in Railway.
  4. Set RESEND_FROM_EMAIL in Railway too, e.g.
     "CivilProposals <noreply@civilproposals.com>" -- the address part
     must be on the domain you verified in step 2.

Both env vars are required (see is_configured()) -- deliberately no
fallback default for RESEND_FROM_EMAIL (unlike, say, APP_BASE_URL
elsewhere), so an unconfigured deploy fails closed: auth.
request_password_reset() detects this and returns "not_configured" so the
UI can show a clear "not available yet" message, instead of silently
trying to send from an address that was never verified (which would just
bounce, leaving a real user waiting forever for an email that can't
arrive).
"""

from __future__ import annotations

import os

import requests

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "").strip()
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")

RESEND_API_URL = "https://api.resend.com/emails"


def is_configured() -> bool:
    return bool(RESEND_API_KEY and RESEND_FROM_EMAIL)


def _describe_key(key: str) -> str:
    if not key:
        return "NOT SET (empty)"
    prefix = key[:8]
    suffix = key[-4:] if len(key) > 12 else ""
    looks_valid = key.startswith("re_")
    desc = f"len={len(key)}, starts with `{prefix}`, ends with `{suffix}`"
    if not looks_valid:
        desc += " -- does NOT start with re_, so this is not a valid Resend API key"
    return desc


def debug_key_info() -> str:
    """Masked, safe-to-display diagnostic -- same pattern as
    billing.debug_key_info(), for the same reason: a copy-paste mistake or
    a saved-but-not-yet-deployed Railway variable can be diagnosed from one
    screenshot instead of several rounds of guessing."""
    return (
        f"RESEND_API_KEY: {_describe_key(RESEND_API_KEY)} | "
        f"RESEND_FROM_EMAIL: {RESEND_FROM_EMAIL or 'NOT SET (empty)'}"
    )


def _wrap(body_html: str) -> str:
    """Shared envelope every email below renders inside -- keeps font/color/
    spacing consistent without repeating the same style attributes five
    times."""
    return f'<div style="font-family:sans-serif;font-size:15px;color:#0F172A;line-height:1.6;">{body_html}</div>'


def _button(label: str, url: str) -> str:
    return (
        f'<p><a href="{url}" style="background:#1D4ED8;color:#fff;padding:10px 20px;'
        f'border-radius:8px;text-decoration:none;display:inline-block;">{label}</a></p>'
    )


def _send(to_email: str, subject: str, html: str) -> None:
    """Shared POST to Resend's API -- every send_*_email() function below
    calls this. Raises RuntimeError (with Resend's own error detail folded
    in) on failure; every caller of a send_*_email() function is expected to
    catch that itself and decide how to handle it (see this module's
    docstring) rather than let an email hiccup break the real action that
    triggered it."""
    if not is_configured():
        raise RuntimeError("Resend isn't configured yet -- set RESEND_API_KEY and RESEND_FROM_EMAIL.")
    resp = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": RESEND_FROM_EMAIL, "to": [to_email], "subject": subject, "html": html},
        timeout=15,
    )
    if resp.status_code >= 300:
        try:
            detail = resp.json().get("message", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Resend API error ({resp.status_code}): {detail}")


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """Sends the password-reset link. auth.request_password_reset() is the
    only caller today, and it deliberately catches any failure rather than
    letting it surface to the end user, since telling a stranger "email
    delivery failed" for an address you don't control is not actionable
    for them and would just be noise."""
    html = _wrap(
        "<p>We received a request to reset your CivilProposals password.</p>"
        + _button("Reset your password", reset_url)
        + '<p style="color:#5A6B7A;font-size:13px;">This link expires in 1 hour and only works once. '
        "If you didn't request this, you can safely ignore this email -- your password hasn't been "
        "changed.</p>"
    )
    _send(to_email, "Reset your CivilProposals password", html)


def send_welcome_email(to_email: str, name: str = "") -> None:
    """Sent once, right after signup (see auth.create_user()) -- previously
    the ONLY email anyone got was a password reset, meaning a brand-new
    account had zero confirmation their signup even worked and no pointer
    back to the app. Best-effort: auth.create_user() logs a failure here
    rather than letting it block account creation."""
    greeting = f"Hi {name.strip()}," if (name or "").strip() else "Hi,"
    html = _wrap(
        f"<p>{greeting}</p>"
        "<p>Welcome to CivilProposals -- your account is ready. You've got 1 free tender analysis "
        "to try the whole workflow end to end: upload a real (or test) tender brief, run analysis, "
        "and see a drafted proposal pack come out the other side.</p>"
        + _button("Open CivilProposals", APP_BASE_URL)
        + '<p style="color:#5A6B7A;font-size:13px;">Questions, or something looks broken? Just reply '
        "to this email -- a person reads it.</p>"
    )
    _send(to_email, "Welcome to CivilProposals", html)


def send_purchase_receipt_email(to_email: str, kind: str) -> None:
    """Sent right after a Stripe Checkout completes (see
    billing.handle_checkout_redirect()) -- previously a customer who just
    paid got no confirmation email at all, only whatever Stripe itself
    sends (which doesn't mention CivilProposals-specific details like what
    the purchase actually unlocked). `kind` is "subscription" or "bid",
    matching the same distinction handle_checkout_redirect() already makes
    off the Checkout Session's own `mode` field."""
    if kind == "subscription":
        subject = "You're subscribed to CivilProposals"
        detail = (
            "<p>Your Monthly plan is active -- $120/month, 3 tender analyses included per billing "
            "period. You can manage or cancel anytime from the account menu in the app.</p>"
        )
    else:
        subject = "Your CivilProposals bid credit"
        detail = (
            "<p>You've added 1 pay-as-you-go bid credit ($50) to your account -- it never expires "
            "and stacks on top of any trial or subscription quota you already have.</p>"
        )
    html = _wrap(f"<p>Thanks for the payment.</p>{detail}" + _button("Open CivilProposals", APP_BASE_URL))
    _send(to_email, subject, html)


def send_trial_used_email(to_email: str) -> None:
    """Sent the moment a trial user's one free bid gets spent (see
    auth.record_proposal_usage()) -- previously nothing told them this had
    happened beyond the in-app paywall message on their NEXT visit, so
    anyone who closed the tab right after their one free analysis had no
    reminder to come back and no clear next step. This is the "$50/bid,
    here's how to keep going" follow-up called out as missing."""
    html = _wrap(
        "<p>You just used your free trial analysis on CivilProposals. Hope it was useful --"
        " here's how to keep going when you're ready for the next tender:</p>"
        "<ul style='color:#0F172A;'>"
        "<li><strong>Pay as you go</strong> -- $50 per bid, no subscription.</li>"
        "<li><strong>Monthly</strong> -- $120/month, 3 bids included.</li>"
        "</ul>"
        + _button("See pricing & upgrade", f"{APP_BASE_URL.rstrip('/')}")
    )
    _send(to_email, "You've used your free CivilProposals trial", html)


def send_payment_failed_email(to_email: str) -> None:
    """Sent the moment a subscription flips to past_due (see
    billing.refresh_subscription_status()) -- previously a failing card
    produced no outbound signal at all; the customer would only find out by
    noticing the in-app warning banner on their next visit, or not notice
    until the subscription got cancelled outright. This is the
    "failed-payment nudge" called out as missing."""
    html = _wrap(
        "<p>We weren't able to charge the card on file for your CivilProposals Monthly subscription. "
        "Your account still works for now, but please update your payment method soon to keep it "
        "active.</p>"
        + _button("Update payment method", APP_BASE_URL)
    )
    _send(to_email, "Action needed: CivilProposals payment failed", html)
