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


GREEN = "#16A34A"
GREEN_SOFT = "#DCFCE7"


def vertical_steps_component_html(steps: list[dict]) -> str:
    """Renders the sidebar's vertical progress list -- a checkmark/empty
    circle plus a label per row, connected by a thin line -- and doubles as
    the app's real navigation: each row is clickable and switches to that
    section, entirely without touching st.tabs() or any of the ~10 tabs'
    own code -- every tab's content still renders every rerun exactly as
    before (several rely on that; see the comment above _stepper_steps in
    app.py). Render via st.components.v1.html(vertical_steps_component_html(...),
    height=...) -- NOT st.markdown(). That's not a style preference: this
    used to be two pieces (a plain st.markdown() block for the rows, with
    onclick="..." attributes, plus a separate injected <script> to define
    the click handler) and it silently didn't work -- st.markdown() parses
    HTML through React, and React drops any onclick attribute outright
    (logs "Event handler property `onClick` must be a function, instead
    got type string" and moves on), so the attribute was never actually in
    the rendered DOM at all despite showing up fine in the Python string.
    components.html() renders its content as real, separately-parsed HTML
    inside an iframe -- genuine browser HTML parsing, not React -- so
    onclick (attached here via addEventListener instead, cleaner than an
    inline attribute) actually works. The tradeoff is everything the rows
    need -- their own <style>, the click handler, and the active-tab-sync
    poller below -- has to live inside this same returned document, since
    an iframe can't see the outer page's stylesheet or globals.

    "Done" (green check, computed by the caller from session_state) and
    "currently viewing" (a blue highlight) are two independent things:
    done is baked into this HTML at render time, while active is
    synced by the poller here, watching the real (hidden) tab strip's
    aria-selected state -- something Python genuinely cannot compute
    itself, since st.tabs() never tells the Python side which tab is
    visually active (see workflow_stepper_html()'s docstring for the same
    limitation).

    `steps`: [{"label": str, "done": bool}, ...], in display order."""
    if not steps:
        return ""

    n = len(steps)
    rows = []
    for i, step in enumerate(steps):
        done = bool(step.get("done"))
        label = step.get("label", "")
        is_last = i == n - 1

        if done:
            marker = (
                f'<div style="width:20px;height:20px;border-radius:50%;background:{GREEN};'
                f'color:#fff;display:flex;align-items:center;justify-content:center;'
                f'font-size:.66rem;font-weight:800;flex-shrink:0;z-index:1;">&#10003;</div>'
            )
            label_html = f'<span style="font-size:.8rem;font-weight:650;color:{GREEN};">{label}</span>'
        else:
            marker = (
                f'<div style="width:20px;height:20px;border-radius:50%;background:{SURFACE};'
                f'border:1.5px solid #94A3B8;flex-shrink:0;z-index:1;"></div>'
            )
            # Was #94A3B8 (slate-400) -- too light against the sidebar's
            # off-white background per user feedback ("steps ... get lost
            # with the background"). #334155 (slate-700) keeps not-done
            # steps visually secondary to the green "done" state while
            # staying clearly legible.
            label_html = f'<span style="font-size:.8rem;font-weight:500;color:#334155;">{label}</span>'

        connector = "" if is_last else (
            f'<div style="position:absolute;left:9.5px;top:20px;width:2px;height:100%;'
            f'background:{GREEN if done and steps[i + 1].get("done") else BORDER};"></div>'
        )

        rows.append(
            f'<div class="cp-step-row" data-cp-step="{i}" '
            'style="position:relative;display:flex;align-items:center;gap:10px;'
            'padding:5px 8px;margin:0 -8px;border-radius:8px;cursor:pointer;">'
            f'{connector}{marker}{label_html}'
            '</div>'
        )

    inner = "".join(rows)
    return f"""<!DOCTYPE html><html><head><style>
html, body {{ margin:0; padding:0; background:transparent; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }}
.cp-step-row:hover {{ background:#F1F5F9; }}
.cp-step-row.cp-step-active {{ background:#EFF4FF; }}
</style></head><body>
<div style="padding:2px 2px 6px;">{inner}</div>
<script>
(function(){{
  var topDoc = window.parent.document;
  function navStep(i) {{
    var tabs = topDoc.querySelectorAll('[data-testid="stTabs"] [data-testid="stTab"]');
    if (tabs[i]) {{ tabs[i].click(); }}
  }}
  document.querySelectorAll('.cp-step-row').forEach(function(row){{
    row.addEventListener('click', function(){{
      navStep(parseInt(row.getAttribute('data-cp-step'), 10));
    }});
  }});
  function syncActive(){{
    try {{
      var tabs = topDoc.querySelectorAll('[data-testid="stTabs"] [data-testid="stTab"]');
      var activeIdx = -1;
      tabs.forEach(function(t, idx){{
        if (t.getAttribute('aria-selected') === 'true') {{ activeIdx = idx; }}
      }});
      document.querySelectorAll('.cp-step-row').forEach(function(r){{
        var idx = parseInt(r.getAttribute('data-cp-step'), 10);
        r.classList.toggle('cp-step-active', idx === activeIdx);
      }});
    }} catch (e) {{ /* real tab strip not ready yet -- next poll picks it up */ }}
  }}
  syncActive();
  setInterval(syncActive, 350);
}})();
</script>
</body></html>"""


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
