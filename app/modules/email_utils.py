"""
email_utils.py

Transactional email via Resend (https://resend.com) -- currently used only
for password-reset links (see auth.request_password_reset() and
auth.render_password_reset_screen()). A thin wrapper around Resend's plain
REST API (POST https://api.resend.com/emails) via `requests` (already a
dependency -- see requirements.txt) rather than their Python SDK, to avoid
adding one more dependency for what's a single API call.

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


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """Sends the password-reset link. Raises RuntimeError (with Resend's
    own error detail folded in) on failure -- auth.request_password_reset()
    is the only caller today, and it deliberately catches this rather than
    letting it surface to the end user, since telling a stranger "email
    delivery failed" for an address you don't control is not actionable
    for them and would just be noise."""
    if not is_configured():
        raise RuntimeError("Resend isn't configured yet -- set RESEND_API_KEY and RESEND_FROM_EMAIL.")

    html = (
        '<div style="font-family:sans-serif;font-size:15px;color:#0F172A;line-height:1.6;">'
        "<p>We received a request to reset your CivilProposals password.</p>"
        f'<p><a href="{reset_url}" style="background:#1D4ED8;color:#fff;padding:10px 20px;'
        'border-radius:8px;text-decoration:none;display:inline-block;">Reset your password</a></p>'
        '<p style="color:#5A6B7A;font-size:13px;">This link expires in 1 hour and only works once. '
        "If you didn't request this, you can safely ignore this email -- your password hasn't been "
        "changed.</p>"
        "</div>"
    )

    resp = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "Reset your CivilProposals password",
            "html": html,
        },
        timeout=15,
    )
    if resp.status_code >= 300:
        try:
            detail = resp.json().get("message", resp.text)
        except Exception:
            detail = resp.text
        raise RuntimeError(f"Resend API error ({resp.status_code}): {detail}")
