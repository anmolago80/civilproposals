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


def workflow_stepper_html(steps: list[dict]) -> str:
    """Renders a horizontal progress stepper across the top of the main
    workflow -- a numbered/checkmarked circle per step, connected by a line,
    in the same palette as the landing page (PRIMARY blue, INK, SURFACE,
    BORDER). Purely informational: Streamlit's st.tabs() has no way to tell
    the Python side which tab is currently being viewed (tab content all
    runs every rerun regardless of which one is visually active), so this
    only ever shows done-vs-not-done per step, never a "current step"
    highlight -- showing a fake "current" position would be misleading.

    `steps`: [{"label": str, "done": bool}, ...], in display order. Caller
    (app.py) decides "done" per step from session_state, since this module
    stays Streamlit/session-state-free on purpose (see module docstring).

    Built as single-line, unindented HTML for the same reason as
    brand_html() above -- st.markdown() treats indented multi-line blocks as
    a Markdown code block even with unsafe_allow_html=True."""
    if not steps:
        return ""

    n = len(steps)
    segments = []
    for i, step in enumerate(steps):
        done = bool(step.get("done"))
        label = step.get("label", "")

        if done:
            circle = (
                f'<div style="width:26px;height:26px;border-radius:50%;background:{PRIMARY};'
                f'color:#fff;display:flex;align-items:center;justify-content:center;'
                f'font-size:.78rem;font-weight:800;flex-shrink:0;">&#10003;</div>'
            )
            label_color = INK
            label_weight = 700
        else:
            circle = (
                f'<div style="width:26px;height:26px;border-radius:50%;background:#fff;'
                f'border:1.5px solid {BORDER};color:#94A3B8;display:flex;align-items:center;'
                f'justify-content:center;font-size:.76rem;font-weight:700;flex-shrink:0;">{i + 1}</div>'
            )
            label_color = "#94A3B8"
            label_weight = 600

        node = (
            '<div style="display:flex;flex-direction:column;align-items:center;gap:6px;min-width:64px;">'
            f'{circle}'
            f'<span style="font-size:.68rem;font-weight:{label_weight};color:{label_color};'
            f'text-align:center;line-height:1.2;white-space:nowrap;">{label}</span>'
            '</div>'
        )
        segments.append(node)

        if i < n - 1:
            line_color = PRIMARY if done and steps[i + 1].get("done") else BORDER
            segments.append(
                f'<div style="flex:1;height:2px;background:{line_color};margin:0 2px 20px;min-width:12px;"></div>'
            )

    inner = "".join(segments)
    return (
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;'
        f'overflow-x:auto;padding:14px 6px 16px;background:{SURFACE};border:1px solid {BORDER};'
        'border-radius:14px;margin-bottom:18px;">'
        f'{inner}'
        '</div>'
    )
