"""
email_identity.py

One person, one free trial: the helpers that decide whether two email
addresses are "the same mailbox" for trial purposes.

Kept in its own tiny module (no streamlit, no database) so both db.py (which
backfills db.User.email_normalized when it migrates an existing database) and
auth.py (which normalises on signup) can import it without a cycle.
"""

from __future__ import annotations

# Gmail ignores dots in the local part and treats googlemail.com as the same
# mailbox as gmail.com.
_GMAIL_DOMAINS = frozenset({"gmail.com", "googlemail.com"})

# Consumer mailbox providers -- many unrelated people share these domains, so
# the optional one-trial-per-company-domain switch (auth.
# TRIAL_ONE_PER_COMPANY_DOMAIN) must ignore them.
FREE_EMAIL_DOMAINS = frozenset({
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com", "outlook.com.au",
    "hotmail.com.au", "live.com.au", "hotmail.co.uk", "outlook.es", "hotmail.es",
    "yahoo.com", "yahoo.com.au", "yahoo.co.uk", "yahoo.ca", "ymail.com",
    "rocketmail.com",
    "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "pm.me",
    "aol.com", "gmx.com", "gmx.net", "mail.com", "zoho.com",
    "fastmail.com", "tutanota.com", "tuta.io", "hey.com",
    "qq.com", "163.com", "126.com", "sina.com",
    "bigpond.com", "bigpond.net.au", "optusnet.com.au", "internode.on.net",
})


def normalize_email(email: str) -> str:
    """The canonical form used to decide "same person": lowercased and
    trimmed; any "+tag" stripped from the local part for EVERY domain; dots
    removed from the local part for gmail.com / googlemail.com (which are
    also folded into gmail.com).

    The original address is still what's stored in db.User.email and what
    mail is sent to -- this value is only ever used for comparison."""
    email = (email or "").strip().lower()
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    stripped = local.split("+", 1)[0]
    # An address that is nothing but a tag ("+x@example.com") has no other
    # local part to fall back to -- keep it as typed rather than collapsing
    # every such address into "@example.com".
    local = stripped or local
    if domain in _GMAIL_DOMAINS:
        local = local.replace(".", "") or local
        domain = "gmail.com"
    return f"{local}@{domain}"


def email_domain(email: str) -> str:
    """The (normalised) domain part of an address, or "" if it has none."""
    normalized = normalize_email(email)
    return normalized.rsplit("@", 1)[1] if "@" in normalized else ""


def is_free_email_domain(domain: str) -> bool:
    return (domain or "").strip().lower() in FREE_EMAIL_DOMAINS
