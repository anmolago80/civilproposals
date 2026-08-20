"""
firm_profile.py

Read/write access to the bidding firm's standing facts (db.FirmProfile),
and the helpers that let the rest of the app consume them.

WHY THIS EXISTS
---------------
A large share of the red placeholders in every exported pack were never
"the AI couldn't work this out" -- they were facts about the bidder that
the app had no field for and had never asked anyone. The firm's ABN,
registered address, logo, PI/PL/WC insurances, ISO certifications, the
person who signs, where its offices are, its standard rates, its standing
terms of engagement. All identical on every bid this firm will ever write,
all re-typed (or left red) every time.

One row per account fixes the whole class at once, and every consumer
below follows the same rule: a value that IS in the profile becomes real
content; a value that isn't stays exactly the placeholder it is today.
A blank profile must leave the app behaving precisely as it did before
this module existed -- that is the property the tests pin.

Nothing here ever guesses. There is no "derive the ACN from the ABN", no
"assume PI cover meets the requirement". The profile is user-entered fact
or it is absent.
"""

from __future__ import annotations

import json

from modules import db

# The three insurances a civil/infrastructure brief asks about, in the order
# schedules normally list them. Fixed, for the same reason blog.CATEGORIES
# is fixed: free-form insurance names sprawl and then stop matching the
# label synonyms that make them useful.
INSURANCE_TYPES = [
    "Professional Indemnity",
    "Public Liability",
    "Workers Compensation",
]

INSURANCE_FIELDS = ["type", "insurer", "policy_no", "cover", "expiry"]

# Local mode has no logged-in user; the whole local path is single-user, so
# one fixed key stands in for the account.
LOCAL_USER_ID = "__local__"


def _key(user_id: str | None) -> str:
    return (user_id or "").strip() or LOCAL_USER_ID


def _loads(raw, fallback):
    try:
        value = json.loads(raw or "")
    except (TypeError, ValueError):
        return fallback
    return value if isinstance(value, type(fallback)) else fallback


def get_profile(user_id: str | None) -> "db.FirmProfile | None":
    with db.get_session() as session:
        return session.query(db.FirmProfile).filter(
            db.FirmProfile.user_id == _key(user_id)
        ).first()


def get_or_create(user_id: str | None) -> "db.FirmProfile":
    with db.get_session() as session:
        key = _key(user_id)
        profile = session.query(db.FirmProfile).filter(db.FirmProfile.user_id == key).first()
        if profile is None:
            profile = db.FirmProfile(user_id=key)
            session.add(profile)
            session.commit()
            session.refresh(profile)
        return profile


def save_profile(user_id: str | None, **fields) -> "db.FirmProfile":
    """Updates only the fields passed. Unknown keys are ignored rather than
    raising, so the editor can hand over a dict of widget values."""
    allowed = {
        "company_name", "abn", "acn", "registered_address", "logo_bytes", "logo_filename",
        "signatory_name", "signatory_title", "signatory_phone", "signatory_email",
        "insurances_json", "certifications_json", "rate_card_json",
        "offices_text", "community_text", "leadership_text",
        "terms_of_engagement_text", "qa_statement",
    }
    with db.get_session() as session:
        key = _key(user_id)
        profile = session.query(db.FirmProfile).filter(db.FirmProfile.user_id == key).first()
        if profile is None:
            profile = db.FirmProfile(user_id=key)
            session.add(profile)
        for name, value in fields.items():
            if name in allowed:
                setattr(profile, name, value)
        session.commit()
        session.refresh(profile)
        return profile


# ---------------------------------------------------------------------------
# Reading structured fields
# ---------------------------------------------------------------------------

def insurances(profile) -> list[dict]:
    """[{type, insurer, policy_no, cover, expiry}] -- only rows with at least
    an insurer or a policy number, so a half-filled editor grid doesn't
    export a row of blanks."""
    rows = _loads(getattr(profile, "insurances_json", ""), [])
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        clean = {field: str(row.get(field) or "").strip() for field in INSURANCE_FIELDS}
        if clean["insurer"] or clean["policy_no"] or clean["cover"]:
            out.append(clean)
    return out


def certifications(profile) -> list[str]:
    return [str(c).strip() for c in _loads(getattr(profile, "certifications_json", ""), []) if str(c or "").strip()]


def rate_card(profile) -> dict:
    raw = _loads(getattr(profile, "rate_card_json", ""), {})
    out = {}
    for discipline, rate in raw.items():
        try:
            out[str(discipline)] = float(rate)
        except (TypeError, ValueError):
            continue
    return out


def dumps_insurances(rows: list[dict]) -> str:
    return json.dumps([
        {field: str(row.get(field) or "").strip() for field in INSURANCE_FIELDS}
        for row in (rows or [])
    ])


def dumps_certifications(values: list[str]) -> str:
    return json.dumps([str(v).strip() for v in (values or []) if str(v or "").strip()])


def dumps_rate_card(rows: dict) -> str:
    return json.dumps({str(k): float(v) for k, v in (rows or {}).items() if str(k or "").strip()})


# ---------------------------------------------------------------------------
# What the rest of the app asks the profile
# ---------------------------------------------------------------------------

def is_empty(profile) -> bool:
    """True when nothing has been entered. Consumers use this to keep their
    existing placeholder behaviour byte-for-byte."""
    if profile is None:
        return True
    text_fields = (
        "company_name", "abn", "registered_address", "signatory_name",
        "offices_text", "community_text", "leadership_text",
        "terms_of_engagement_text", "qa_statement",
    )
    if any((getattr(profile, f, "") or "").strip() for f in text_fields):
        return False
    if getattr(profile, "logo_bytes", None):
        return False
    return not (insurances(profile) or certifications(profile) or rate_card(profile))


def footer_line(profile, bidder_name: str = "") -> tuple[str, bool]:
    """(text, is_complete) for the Small Scope pack's per-page footer.

    Returns the real "Firm | ABN 12 345 678 901 | 100 Example St" line when
    the profile has those facts, and the original red placeholder line when
    it doesn't -- so this is a strict improvement, never a regression."""
    name = (getattr(profile, "company_name", "") or "").strip() or (bidder_name or "").strip()
    abn = (getattr(profile, "abn", "") or "").strip()
    address = " ".join((getattr(profile, "registered_address", "") or "").split())

    parts = [name or "[BIDDER COMPANY NAME]",
             f"ABN {abn}" if abn else "ABN [XX XXX XXX XXX]",
             address or "[REGISTERED ADDRESS]"]
    complete = bool(name and abn and address)
    return " | ".join(parts), complete


def schedule_fill_data(profile) -> dict:
    """Firm-level answers for the returnable-schedule filler.

    These labels used to sit in the filler's hard "never known" bucket --
    always placeholdered, because the app genuinely never held them. With a
    profile they become real answers. Signature stays out of it forever:
    nobody should be able to sign a legal form from a saved setting.
    """
    if profile is None:
        return {}
    data = {}
    for key, value in (
        ("company_abn", (getattr(profile, "abn", "") or "").strip()),
        ("company_acn", (getattr(profile, "acn", "") or "").strip()),
        ("company_address", " ".join((getattr(profile, "registered_address", "") or "").split())),
        ("company_legal_name", (getattr(profile, "company_name", "") or "").strip()),
    ):
        if value:
            data[key] = value

    for row in insurances(profile):
        kind = row["type"].lower()
        prefix = None
        if "indemnity" in kind:
            prefix = "professional_indemnity"
        elif "public" in kind:
            prefix = "public_liability"
        elif "workers" in kind or "compensation" in kind:
            prefix = "workers_compensation"
        if not prefix:
            continue
        if row["insurer"]:
            data[f"{prefix}_insurer"] = row["insurer"]
        if row["policy_no"]:
            data[f"{prefix}_policy"] = row["policy_no"]
        if row["cover"]:
            data[f"{prefix}_cover"] = row["cover"]
        if row["expiry"]:
            data[f"{prefix}_expiry"] = row["expiry"]

    certs = certifications(profile)
    if certs:
        data["certifications"] = ", ".join(certs)
    return data


def project_seed(profile) -> dict:
    """Values a NEW project should start from: {session_key: value}.

    Only non-empty values are returned, and the caller only applies them
    where the project's own field is still blank -- a seed must never
    overwrite something the user typed for this particular bid.
    """
    if profile is None:
        return {}
    seed = {}
    for key, value in (
        ("bidder_name", (getattr(profile, "company_name", "") or "").strip()),
        ("letter_sender_name", (getattr(profile, "signatory_name", "") or "").strip()),
        ("letter_sender_title", (getattr(profile, "signatory_title", "") or "").strip()),
        ("letter_sender_phone", (getattr(profile, "signatory_phone", "") or "").strip()),
        ("letter_sender_email", (getattr(profile, "signatory_email", "") or "").strip()),
        ("letter_sender_address", " ".join((getattr(profile, "registered_address", "") or "").split())),
        ("terms_of_engagement_text", (getattr(profile, "terms_of_engagement_text", "") or "").strip()),
    ):
        if value:
            seed[key] = value
    return seed


def export_context(profile, bidder_name: str = "") -> dict:
    """Everything the exporters need from the profile, in one dict.

    One parameter threaded through build_docx()/build_letter_docx() rather
    than six: the profile is read in half a dozen unrelated places (footer,
    cover logo, local content, relationship management, terms, QA
    statement), and six new keyword arguments on two already-long
    signatures would be worse than one named bundle.

    An empty profile produces an empty-ish dict whose every consumer falls
    back to the placeholder it uses today.
    """
    footer_text, footer_complete = footer_line(profile, bidder_name)
    return {
        "logo_bytes": getattr(profile, "logo_bytes", None),
        "footer_line": footer_text,
        "footer_complete": footer_complete,
        "company_name": (getattr(profile, "company_name", "") or "").strip(),
        "offices_text": (getattr(profile, "offices_text", "") or "").strip(),
        "community_text": (getattr(profile, "community_text", "") or "").strip(),
        "leadership_text": (getattr(profile, "leadership_text", "") or "").strip(),
        "qa_statement": (getattr(profile, "qa_statement", "") or "").strip(),
        "certifications": certifications(profile),
        "insurances": insurances(profile),
    }
