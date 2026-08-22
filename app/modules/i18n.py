# modules/i18n.py -- dual-language (English/Spanish) foundations for
# CivilProposals, Part A0 of the EN/ES + one-pass-free-tier brief.
#
# Design intent, deliberately kept simple:
#   - ONE selected language lives in st.session_state["_lang"] at a time --
#     this is a per-browser-tab UI language, not a per-document setting (see
#     modules/pages/10_state_helpers.py's `output_language` PLAIN_KEYS entry
#     for the separate, per-PROJECT choice of what language a generated
#     proposal/tender-summary/org-chart comes out in -- Part A3).
#   - t(key, **fmt) is a plain dict lookup against modules/translations/en.py
#     and modules/translations/es.py, never a runtime translation call --
#     no network dependency, no per-render cost, and a missing key fails
#     LOUD in a way that's easy to spot (falls back to English, then to the
#     bare key itself wrapped in [[ ]] so a missing translation is visually
#     obvious in the Spanish UI instead of silently showing English text
#     that looks intentional).
#   - Persisted to the account (db.User.preferred_language) once someone is
#     logged in, so the choice survives a login on a different device/
#     browser -- but session_state is always the live source of truth for
#     the CURRENT rerun, since a signed-out visitor (or local-mode user)
#     has no account row to persist to at all.
from __future__ import annotations

import streamlit as st

from modules.translations import en as _en, es as _es

LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Español",
}
LANGUAGE_FLAGS: dict[str, str] = {
    "en": "🇬🇧",
    "es": "🇪🇸",
}
DEFAULT_LANGUAGE = "en"

_CATALOGS: dict[str, dict[str, str]] = {
    "en": _en.STRINGS,
    "es": _es.STRINGS,
}


def _normalize(code: str | None) -> str:
    code = (code or "").strip().lower()[:2]
    return code if code in LANGUAGES else DEFAULT_LANGUAGE


def language_from_accept_header(header_value: str | None) -> str:
    """Parses a raw `Accept-Language` header (e.g. "es-MX,es;q=0.9,en;q=0.8")
    and returns the first supported language found, else DEFAULT_LANGUAGE.
    Used once, the very first time a visitor with no stored preference and
    no session choice yet is seen (see current_language() below) -- never
    overrides an explicit pick."""
    if not header_value:
        return DEFAULT_LANGUAGE
    for part in header_value.split(","):
        tag = part.split(";")[0].strip()
        code = _normalize(tag.split("-")[0])
        if tag[:2].lower() in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def current_language() -> str:
    """The language this rerun should render in. Resolution order:
    1. An explicit pick already made this session (st.session_state["_lang"]).
    2. The signed-in account's saved preference (db.User.preferred_language),
       adopted into session_state the first time it's seen so later reruns
       don't need a DB read.
    3. The browser's Accept-Language header (best-effort, via
       st.context.headers -- absent in some embedding contexts, so this is
       wrapped defensively).
    4. DEFAULT_LANGUAGE.
    Never raises -- a language picker is not something that should ever be
    able to take the rest of the page down with it."""
    existing = st.session_state.get("_lang")
    if existing in LANGUAGES:
        return existing

    try:
        from modules import auth
        user = auth.current_user()
    except Exception:
        user = None
    if user is not None and getattr(user, "preferred_language", None) in LANGUAGES:
        st.session_state["_lang"] = user.preferred_language
        return user.preferred_language

    try:
        header = st.context.headers.get("Accept-Language")
    except Exception:
        header = None
    detected = language_from_accept_header(header)
    st.session_state["_lang"] = detected
    return detected


def set_language(code: str, persist_for_user=None) -> None:
    """Sets the language for the rest of THIS session immediately, and --
    when a logged-in user is given -- persists it to their account so it's
    remembered on their next login too. Persisting is best-effort: a DB
    hiccup here must never block someone from just switching the UI
    language they're looking at right now."""
    code = _normalize(code)
    st.session_state["_lang"] = code
    if persist_for_user is not None:
        try:
            from modules import db
            with db.get_session() as s:
                db_user = s.get(db.User, persist_for_user.id)
                if db_user is not None and db_user.preferred_language != code:
                    db_user.preferred_language = code
                    s.commit()
        except Exception:
            pass


def t(key: str, **fmt) -> str:
    """Looks up `key` in the current language's catalog, falling back to
    English, then to a visibly-broken `[[key]]` marker so a missing
    translation is obvious in testing instead of silently showing the
    wrong (or no) text. `**fmt` is applied with str.format_map against the
    resolved string when given, e.g. t("trial_remaining", n=2)."""
    lang = current_language()
    catalog = _CATALOGS.get(lang, _CATALOGS[DEFAULT_LANGUAGE])
    text = catalog.get(key) or _CATALOGS[DEFAULT_LANGUAGE].get(key)
    if text is None:
        return f"[[{key}]]"
    if fmt:
        try:
            return text.format(**fmt)
        except Exception:
            return text
    return text


def language_picker(key: str = "_lang_picker", persist_for_user=None) -> None:
    """Renders a small flag + name selectbox that switches the UI language
    immediately (st.rerun()s on change). Safe to call from more than one
    place in the same script run (sidebar AND a logged-out auth screen
    never both render in the same run, so there's no duplicate-widget-key
    risk in practice, but each CALL SITE should still pass its own `key`
    if that ever changes)."""
    codes = list(LANGUAGES.keys())
    current = current_language()
    labels = [f"{LANGUAGE_FLAGS.get(c, '')} {LANGUAGES[c]}".strip() for c in codes]
    try:
        idx = codes.index(current)
    except ValueError:
        idx = 0
    picked_label = st.selectbox(
        t("language_picker_label"), labels, index=idx, key=key, label_visibility="collapsed",
    )
    picked_code = codes[labels.index(picked_label)]
    if picked_code != current:
        set_language(picked_code, persist_for_user=persist_for_user)
        st.rerun()
