"""
branding.py

Shared brand lockup (icon + wordmark + optional Beta badge) used on both the
login/signup screen (auth.py) and the in-app sidebar (app.py), so the two
don't drift out of sync. Renders as an <img> with a base64-embedded PNG
rather than a file:// path, since that's the one approach guaranteed to
work regardless of Streamlit's static-file-serving quirks across
environments (local dev, Railway, behind a proxy, etc.).

Palette reference (kept in one place -- also mirrored in .streamlit/config.toml
and landing/index.html's CSS variables; update all three together if the
brand colors ever change):
  Ink (text):        #0F172A
  Primary (brand):   #1D4ED8
  Primary, dark:     #1E3A8A
  Accent (CTA/beta):  #F97316
  Surface:           #F8FAFC
  Border:             #E2E8F0
"""

from __future__ import annotations

import base64
from pathlib import Path

_LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "brand" / "logo_mark.png"

try:
    LOGO_B64 = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
except FileNotFoundError:
    LOGO_B64 = ""

INK = "#0F172A"
PRIMARY = "#1D4ED8"
PRIMARY_DARK = "#1E3A8A"
ACCENT = "#F97316"
SURFACE = "#F8FAFC"
BORDER = "#E2E8F0"


def brand_html(logo_size: int = 40, wordmark_size: str = "1.5rem", show_beta: bool = True,
               show_tagline: bool = False) -> str:
    """Returns an HTML snippet (for st.markdown(..., unsafe_allow_html=True))
    with the logo mark, "CivilProposals" wordmark, and an optional Beta
    pill -- the one brand lockup used everywhere in the app."""
    logo_img = (
        f'<img src="data:image/png;base64,{LOGO_B64}" '
        f'style="width:{logo_size}px;height:{logo_size}px;border-radius:{logo_size * 0.24:.0f}px;'
        f'flex-shrink:0;" />'
    ) if LOGO_B64 else ""

    beta_pill = (
        f'<span style="font-size:.68rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;'
        f'background:#FFF3E0;color:#B8600A;border:1px solid #F3D9AE;padding:2px 9px;border-radius:20px;'
        f'margin-left:2px;">Beta</span>'
    ) if show_beta else ""

    tagline = (
        '<div style="color:#5A6B7A;font-size:.85rem;margin-top:2px;">'
        'AI-assisted tender &amp; proposal drafting for civil engineering firms</div>'
    ) if show_tagline else ""

    # Deliberately built as ONE line with no leading whitespace on any part.
    # Streamlit's st.markdown() runs content through a Markdown parser
    # before honoring unsafe_allow_html -- a block indented 4+ spaces is
    # Markdown's own "this is a code block" rule and gets rendered as
    # literal text instead of HTML, regardless of unsafe_allow_html. Multi-
    # line, indented triple-quoted HTML strings hit this constantly; a
    # single unindented line sidesteps it entirely.
    return (
        '<div style="display:flex;align-items:center;gap:10px;">'
        f'{logo_img}'
        '<div>'
        '<div style="display:flex;align-items:center;gap:8px;">'
        f'<span style="font-weight:800;font-size:{wordmark_size};color:{INK};letter-spacing:-0.01em;">CivilProposals</span>'
        f'{beta_pill}'
        '</div>'
        f'{tagline}'
        '</div>'
        '</div>'
    )
