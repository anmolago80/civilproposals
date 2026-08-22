"""
methodology_render.py

The delivery methodology's shared column model, and four PNG renderers used
for the live preview next to the Design stages grid (Draft Responses tab) --
the same pattern org_chart_render.py and program_render.py already use: ONE
build_columns() normalises the reviewed stage grid (or, before that grid
exists, the brief's own scope items) into a single list of column dicts, and
methodology_pptx.py's four PPTX builders read the SAME list -- see that
module, which imports everything below rather than keeping its own copy --
so the live preview and the exported PowerPoint can never describe a
different table.

WHAT IS AND ISN'T INVENTED
---------------------------
Every task, activity, outcome and deliverable comes straight from the
reviewed methodology_stages.MethodologyStage grid (or, before that grid has
been generated/filled in, from the brief's own scope items) -- see
methodology_stages.py's module docstring for the no-invention contract the
AI assignment step itself is under. This module only lays the same cells
out four different ways; it adds no content of its own, with one narrow
exception: whether a stage "carries a hold point" for the Programme-matched
style's gate diamonds is DERIVED, never asserted, from whether that stage's
own engagement activities or outcome text actually says so ("hold point")
-- see stage_carries_hold_point(). A brief that never mentions one draws
none, on any stage.

STAGE COLOURS
--------------
Fixed and colourblind-validated -- the same four hues org_chart_render.py
and program_render.py use, in the same order, so "Stage 2" reads as the
same colour everywhere in the pack. Cycles past the fourth stage; identity
is always carried by the stage NAME, never colour alone. Only the
"chevrons", "programme" and "spine" styles colour by stage -- "matrix"
keeps the original polished-navy header instead, matching the classic
formal-grid look these packs have always shipped with.

WHY A LIVE PREVIEW HERE, A DIFFERENT RENDERER IN THE PPTX
-----------------------------------------------------------
Exactly like org_chart_render.py (matplotlib, for the UI/DOCX PNG) versus
org_chart_pptx.py (native python-pptx shapes, for the download) and
program_render.py versus program_pptx.py: this module draws with
matplotlib for a fast, in-app preview; methodology_pptx.py draws the same
columns with native PowerPoint shapes so the download is a real, editable
deck rather than a pasted image. Both read the identical column list, so a
style picked here and exported there can never drift apart in content --
only in exact pixel layout, which is the same trade-off the org chart and
program pickers already make.
"""

from __future__ import annotations

STYLES = ("matrix", "chevrons", "programme", "spine")
DEFAULT_STYLE = "matrix"

STYLE_LABELS = {
    "matrix": "Boardroom matrix",
    "chevrons": "Stage chevrons",
    "programme": "Programme-matched columns",
    "spine": "Timeline spine",
}

STYLE_DESCRIPTIONS = {
    "matrix": "Classic grid -- tasks / engagement / outcome / deliverables rows against stage columns (most conservative)",
    "chevrons": "Arrowed stage banners, a card of coloured section labels and deliverable chips below each",
    "programme": "Stage-coloured column cards (What we do / With you / You receive) with hold-point gates",
    "spine": "Vertical timeline -- one full-width band per stage, most visual",
}

# Fixed and colourblind-validated. Do not substitute hues -- see the module
# docstring. Shared (by value, not import) with org_chart_render.STAGE_COLOURS
# and program_render.STAGE_COLOURS; each renderer module keeps its own copy
# of this literal, same convention as those two.
STAGE_COLOURS = ["#1D4ED8", "#0D9488", "#F97316", "#6D28D9"]

INK = "#1A2233"
MUTED = "#5B6472"
RED_TBC = "#C00000"
GRIDLINE = "#E4E8EE"
CARD_BG = "#FFFFFF"


def stage_colour(index: int) -> str:
    return STAGE_COLOURS[index % len(STAGE_COLOURS)]


def is_placeholder(text) -> bool:
    """A cell the reader must act on: either an explicit [BRACKETED] note
    from the legacy boilerplate, or the literal TBC the stage drafter emits
    when the brief doesn't support a cell."""
    text = str(text or "").strip()
    return text.startswith("[") or text.upper() == "TBC"


def stage_carries_hold_point(column: dict) -> bool:
    """Derived, never asserted -- see the module docstring. A stage only
    gets a Programme-style gate diamond after it if its OWN engagement
    activities or outcome text actually names a hold point."""
    haystack = " ".join(str(x) for x in (column.get("engagement") or []))
    haystack += " " + str(column.get("outcome") or "")
    return "hold point" in haystack.lower()


# ---------------------------------------------------------------------------
# Column model -- one column per stage, real content only. This is the exact
# shape methodology_pptx.py's four style builders consume.
# ---------------------------------------------------------------------------

# English defaults -- the sole reader that still needs these as plain
# constants is render_png() (the live PNG preview), which has no language
# support yet (Round 3, Part 4b's own territory). build_columns()'s PPTX
# caller (methodology_pptx.py) passes a real `language` and gets the
# translated versions via export_i18n instead -- see _legacy_columns() below.
_STAGE_HEADERS = [
    "Project Initiation",
    "15% design stage",
    "15% developed to 50% design stage",
    "50% developed to Final stage",
]

_PROJECT_INITIATION_TASKS = [
    "Liaison with the client",
    "",
    ("Including:", True),  # (text, no_bullet)
    "Inception (prestart) meeting",
    "Site inspection",
    "Confirmation of delivery program and team availability",
    "Establishing communication protocols",
    "Initial progress reporting setup",
    "Draft Quality Plan for discussion",
]
_PROJECT_INITIATION_ENGAGEMENT = ["Inception meeting", "Site inspection walkover"]
_PROJECT_INITIATION_OUTCOME = "Project governance, scope, and collaboration framework established."
_PROJECT_INITIATION_DELIVERABLES = ["Inception meeting minutes", "Communication protocols document"]

_NO_SCOPE_PLACEHOLDER = (
    "[DESCRIBE APPROACH FOR THIS STAGE -- analyse the brief (Tender Analysis tab) "
    "to prefill this from the brief's real scope items]"
)
_CONFIRM_ENGAGEMENT = "[CONFIRM ENGAGEMENT / WORKSHOP ACTIVITIES FOR THIS STAGE]"
_CONFIRM_OUTCOME = "[CONFIRM OUTCOME FOR THIS STAGE]"
_CONFIRM_DELIVERABLES = "[CONFIRM DELIVERABLE(S) FOR THIS STAGE]"
_CONFIRM_TASKS = "[CONFIRM TASKS FOR THIS STAGE]"
_CONFIRM_DATE_RANGE = "[Date range]"


def _legacy_strings(language: str) -> dict:
    """The same legacy boilerplate content as the module-level English
    constants above, resolved through export_i18n for a real `language`.
    Only build_columns()'s PPTX path calls this -- render_png() (the live
    preview) still reads the English constants directly until Part 4b gives
    it language support too."""
    from modules import export_i18n as ei
    t = lambda key, **fmt: ei.export_t(key, language, **fmt)  # noqa: E731
    return {
        "stage_headers": [
            t("pptx_legacy_stage1_name"), t("pptx_legacy_stage2_name"),
            t("pptx_legacy_stage3_name"), t("pptx_legacy_stage4_name"),
        ],
        "tasks": [
            t("pptx_legacy_task_liaison"),
            "",
            (t("pptx_legacy_task_including"), True),
            t("pptx_legacy_task_inception"),
            t("pptx_legacy_task_site_inspection"),
            t("pptx_legacy_task_confirm_program"),
            t("pptx_legacy_task_comm_protocols"),
            t("pptx_legacy_task_progress_setup"),
            t("pptx_legacy_task_quality_plan"),
        ],
        "engagement": [t("pptx_legacy_engagement_inception"), t("pptx_legacy_engagement_site_walkover")],
        "outcome": t("pptx_legacy_outcome"),
        "deliverables": [t("pptx_legacy_deliverable_minutes"), t("pptx_legacy_deliverable_comm_doc")],
        "no_scope_placeholder": t("pptx_no_scope_placeholder"),
        "confirm_engagement": t("pptx_confirm_engagement_stage"),
        "confirm_outcome": t("pptx_confirm_outcome_stage"),
        "confirm_deliverables": t("pptx_confirm_deliverables_stage"),
        "confirm_tasks": t("pptx_confirm_tasks_stage"),
        "confirm_date_range": t("pptx_confirm_date_range"),
        "untitled_scope_item": t("export_untitled_scope_item"),
    }


def _stage2_tasks(scope_items: list, no_scope_placeholder: str = _NO_SCOPE_PLACEHOLDER,
                  untitled_label: str = "[UNTITLED SCOPE ITEM]") -> list:
    if not scope_items:
        return [no_scope_placeholder]
    lines = []
    for item in scope_items:
        title = (getattr(item, "title", "") or untitled_label).strip()
        tasks = getattr(item, "tasks", None) or []
        lines.append(f"{title}: {'; '.join(tasks)}" if tasks else title)
    return lines


def _columns_from_stages(stages, week_labels) -> list[dict]:
    """The reviewed stage grid, as render-ready columns."""
    from modules.methodology_stages import stage_week_label

    columns = []
    for stage in stages:
        columns.append({
            "name": (getattr(stage, "name", "") or "TBC"),
            "tasks": list(getattr(stage, "key_tasks", None) or ["TBC"]),
            "engagement": list(getattr(stage, "engagement_activities", None) or ["TBC"]),
            "outcome": (getattr(stage, "outcome", "") or "TBC"),
            "deliverables": list(getattr(stage, "deliverables", None) or ["TBC"]),
            "chevron": stage_week_label(stage, week_labels),
        })
    return columns


def _legacy_columns(analysis, language: str | None = None) -> list[dict]:
    """The pre-stages content: one real column built from scope items, and
    three columns of placeholders. Kept so a project that has not run the
    stage drafter exports exactly what it did before.

    `language`: None (render_png()'s live-preview caller, Part 4b's own
    territory) keeps the plain English module constants; a real language
    (methodology_pptx.py's PPTX caller) resolves every string through
    export_i18n instead -- Round 3, Part 2, since this boilerplate is what
    a Spanish project not yet through the stage drafter actually exports."""
    if language is None:
        headers = _STAGE_HEADERS
        tasks1, engagement1, outcome1, deliverables1 = (
            _PROJECT_INITIATION_TASKS, _PROJECT_INITIATION_ENGAGEMENT,
            _PROJECT_INITIATION_OUTCOME, _PROJECT_INITIATION_DELIVERABLES)
        no_scope, confirm_eng, confirm_out, confirm_deliv, confirm_tasks, date_range, untitled = (
            _NO_SCOPE_PLACEHOLDER, _CONFIRM_ENGAGEMENT, _CONFIRM_OUTCOME, _CONFIRM_DELIVERABLES,
            _CONFIRM_TASKS, _CONFIRM_DATE_RANGE, "[UNTITLED SCOPE ITEM]")
    else:
        s = _legacy_strings(language)
        headers = s["stage_headers"]
        tasks1, engagement1, outcome1, deliverables1 = (
            s["tasks"], s["engagement"], s["outcome"], s["deliverables"])
        no_scope, confirm_eng, confirm_out, confirm_deliv, confirm_tasks, date_range, untitled = (
            s["no_scope_placeholder"], s["confirm_engagement"], s["confirm_outcome"],
            s["confirm_deliverables"], s["confirm_tasks"], s["confirm_date_range"],
            s["untitled_scope_item"])

    return [
        {
            "name": headers[0],
            "tasks": list(tasks1),
            "engagement": list(engagement1),
            "outcome": outcome1,
            "deliverables": list(deliverables1),
            "chevron": date_range,
        },
        {
            "name": headers[1],
            "tasks": _stage2_tasks(getattr(analysis, "scope_items", None) or [], no_scope, untitled),
            "engagement": [confirm_eng],
            "outcome": confirm_out,
            "deliverables": [confirm_deliv],
            "chevron": date_range,
        },
    ] + [
        {
            "name": header,
            "tasks": [confirm_tasks],
            "engagement": [confirm_eng],
            "outcome": confirm_out,
            "deliverables": [confirm_deliv],
            "chevron": date_range,
        }
        for header in headers[2:]
    ]


def build_columns(analysis, stages, week_labels, language: str | None = None) -> list[dict]:
    """The one normalised view of the methodology every renderer -- this
    module's four PNG previews, and methodology_pptx.py's four PPTX
    builders -- reads. `stages` (the reviewed methodology_stages.
    MethodologyStage list) wins whenever it exists; otherwise this falls
    back to exactly the pre-stages boilerplate the table always used to
    show, built from the brief's own scope items.

    `language`: forwarded to _legacy_columns() -- see its docstring. Has no
    effect when `stages` is supplied, since _columns_from_stages() reads
    real reviewed content (already in whatever language the stage drafter
    produced it in), not this module's own boilerplate."""
    if stages:
        return _columns_from_stages(stages, week_labels)
    return _legacy_columns(analysis, language)


# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------

_V_SCALE = 7.5
_TOP = 0.98


def _new_figure(width: float, height: float):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return fig, ax


def _finalise(fig, ax, lowest: float, width: float = 12.0):
    """Crop the canvas to the content and size the figure to match -- no
    band of empty white below the last row, same convention as
    program_render._finalise / org_chart_render's per-style cropping."""
    lowest = min(lowest, _TOP - 0.08)
    ax.set_ylim(lowest, _TOP)
    fig.set_size_inches(width, max(1.8, (_TOP - lowest) * _V_SCALE))
    return fig


def _measure_frac(fig, ax, text: str, size: float, weight: str = "normal") -> float:
    """A text string's real rendered width, as a fraction of the AXES
    width -- measured from the actual renderer (same approach
    program_render._text_width_frac uses), not guessed from a
    characters-per-inch formula. A static formula was tried first here and
    under-estimated matplotlib's bold DejaVu Sans widely enough that stage
    headers still overflowed into the next column; text is genuinely
    different widths in different fonts/renderers, so this measures the
    one that is actually about to be drawn."""
    probe = ax.text(0, 0, text, fontsize=size, fontweight=weight, alpha=0)
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    bbox = probe.get_window_extent(renderer=renderer)
    axes_w = ax.get_window_extent(renderer=renderer).width
    probe.remove()
    return bbox.width / max(1.0, axes_w)


def _wrap(fig, ax, text, max_frac: float, size: float, weight: str = "normal") -> list[str]:
    """Word-wrap `text` so every line's real rendered width stays within
    `max_frac` of the axes width. A single word wider than the box on its
    own is left whole rather than mid-word split -- the same trade-off
    program_render._fit_label's ellipsis makes, minus the ellipsis, since a
    wrapped multi-line block has nowhere to put one."""
    text = str(text or "").strip()
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and _measure_frac(fig, ax, trial, size, weight) > max_frac:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [text]


def _cap_items(items, max_items):
    """Keep at most `max_items` bullets, and say honestly how many were
    dropped rather than silently truncating -- mirrors
    methodology_pptx._fit_size's convention for the PPTX export. A
    (text, no_bullet) tuple -- the legacy Project Initiation boilerplate's
    "Including:" sub-header -- is reduced to its text; the preview always
    bullets it (cosmetic only, unlike the PPTX export which honours the
    no-bullet flag exactly as it always has)."""
    items = [str(i[0]) if isinstance(i, tuple) else str(i) for i in (items or []) if str(i[0] if isinstance(i, tuple) else i).strip()]
    if len(items) <= max_items:
        return items, 0
    return items[:max_items], len(items) - max_items


def _is_red_line(line: str) -> bool:
    """A rendered bullet/continuation line that must show red -- either a
    "+N more" honesty line, or a bullet whose own text is a placeholder
    (TBC, or a [BRACKETED] confirm-me note from the pre-stages fallback)."""
    if line.startswith("+"):
        return True
    return is_placeholder(line.strip().lstrip("–").strip())


def _bullet_lines(fig, ax, items, max_items, max_frac: float, size: float) -> list[str]:
    kept, dropped = _cap_items(items, max_items)
    lines = []
    for item in kept:
        # The bullet glyph eats a little width -- wrap continuation lines
        # to the same box, first line included, since the glyph is narrow.
        wrapped = _wrap(fig, ax, item, max_frac, size)
        lines.append(f"– {wrapped[0]}")
        lines.extend(f"   {w}" for w in wrapped[1:])
    if dropped:
        lines.append(f"+{dropped} more — see full methodology")
    return lines


def _text_block(ax, x, y, lines, size, colour=INK, weight="normal", italic_last=False):
    """Left-aligned stack of lines, top-down. Returns the y just below the
    last line drawn."""
    line_h = size / 72 * 1.35
    for i, line in enumerate(lines):
        style = "italic" if (italic_last and i == len(lines) - 1) else "normal"
        ax.text(x, y, line, fontsize=size, color=colour, fontweight=weight,
                fontstyle=style, va="top", ha="left")
        y -= line_h
    return y


def _chip_row(ax, x, right, y, labels, fill, text_colour, size=6.5, row_h=0.028):
    """Wrapped rounded chips flowing left to right, returns the y below the
    last chip row drawn (deliverables-as-chips look used by three of the
    four styles)."""
    from matplotlib.patches import FancyBboxPatch

    cx = x
    row_top = y
    for label in labels:
        w = min(right - x, 0.02 + len(label) * size * 0.0016)
        w = max(w, 0.05)
        if cx + w > right:
            cx = x
            row_top -= row_h + 0.006
        patch = FancyBboxPatch((cx, row_top - row_h), w, row_h,
                               boxstyle=f"round,pad=0,rounding_size={row_h / 2}",
                               linewidth=0.6, edgecolor=GRIDLINE, facecolor=fill)
        ax.add_patch(patch)
        ax.text(cx + w / 2, row_top - row_h / 2, label, fontsize=size, color=text_colour,
                ha="center", va="center", fontweight="bold")
        cx += w + 0.008
    return row_top - row_h


def render_png(analysis, style: str = DEFAULT_STYLE, stages: list | None = None,
               week_labels: list | None = None, client_name: str = "",
               project_name: str = "") -> bytes | None:
    """The methodology, in the requested style, as a PNG for the live
    preview. Returns None on any failure -- a missing preview must never
    take the Draft Responses tab down."""
    style = style if style in STYLES else DEFAULT_STYLE
    try:
        import io as _io

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        columns = build_columns(analysis, stages, week_labels)
        renderer = {
            "matrix": _render_matrix,
            "chevrons": _render_chevrons,
            "programme": _render_programme,
            "spine": _render_spine,
        }[style]
        fig = renderer(columns, project_name, client_name)
        buffer = _io.BytesIO()
        fig.savefig(buffer, format="png", dpi=170, bbox_inches="tight",
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 1. Boardroom matrix -- classic grid, navy headers, LEFT row labels.
# ---------------------------------------------------------------------------

def _render_matrix(columns, project_name, client_name):
    n = max(len(columns), 1)
    fig_w = 12.0
    fig, ax = _new_figure(fig_w, 6.0)

    margin = 0.02
    label_w = 0.09
    content_x = margin + label_w
    col_gap = 0.012
    col_w = (1 - margin - content_x - (n - 1) * col_gap) / n

    y = _TOP
    ax.text(margin, y, "Our proposed methodology", fontsize=13, fontweight="bold", color=INK,
            va="top", ha="left")
    if (project_name or "").strip():
        ax.text(margin, y - 0.045, project_name.strip(), fontsize=8, color=MUTED, va="top", ha="left")
    y -= 0.09

    # Header height sizes to content too -- a long stage name wraps to two
    # lines rather than overflowing into the next column.
    header_size = 7.5
    header_frac = col_w * 0.92
    header_lines_by_col = [_wrap(fig, ax, col["name"], header_frac, header_size, "bold") for col in columns]
    header_h = max(0.05, max(len(lines) for lines in header_lines_by_col) * 0.026 + 0.014)
    for i, col in enumerate(columns):
        cx = content_x + i * (col_w + col_gap)
        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((cx, y - header_h), col_w, header_h, facecolor="#0F2A5C", edgecolor="none"))
        name_colour = RED_TBC if is_placeholder(col["name"]) else "white"
        lines = header_lines_by_col[i]
        ty = y - (header_h - (len(lines) - 1) * 0.026) / 2 - 0.006
        for line in lines:
            ax.text(cx + col_w / 2, ty, line, fontsize=header_size, color=name_colour,
                    fontweight="bold", ha="center", va="center")
            ty -= 0.026
    y -= header_h + 0.01

    body_size = 5.4
    rows = [
        ("KEY TASKS", "tasks", 6, "#EAF0FB"),
        ("ENGAGEMENT", "engagement", 4, "#F5F8FE"),
        ("OUTCOME", "outcome", None, "#EFF6F4"),
        ("DELIVERABLES", "deliverables", 6, "#EFF6F4"),
    ]
    body_frac = col_w * 0.92
    for label, key, cap, tint in rows:
        # Content-sized: measure every column's needed line count FIRST, at a
        # fixed size, so a thin stage doesn't inherit a tall row a busy
        # neighbour needed and a busy stage never gets clipped to a fixed box.
        col_lines = []
        for col in columns:
            value = col[key]
            if cap is None:
                text = str(value)
                lines = [f"– {w}" if j == 0 else f"   {w}"
                        for j, w in enumerate(_wrap(fig, ax, text, body_frac, body_size))]
            else:
                lines = _bullet_lines(fig, ax, value, cap, body_frac, body_size)
            col_lines.append(lines or [""])
        row_h = max(0.035, max(len(lines) for lines in col_lines) * 0.024 + 0.012)

        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((margin, y - row_h), label_w - 0.006, row_h, facecolor="#DCE6F7", edgecolor="none"))
        ax.text(margin + (label_w - 0.006) / 2, y - row_h / 2, label, fontsize=5.6, color="#0F2A5C",
                fontweight="bold", ha="center", va="center", rotation=90)

        for i, (col, lines) in enumerate(zip(columns, col_lines)):
            cx = content_x + i * (col_w + col_gap)
            from matplotlib.patches import Rectangle as _R
            ax.add_patch(_R((cx, y - row_h), col_w, row_h, facecolor=tint, edgecolor=GRIDLINE, linewidth=0.5))
            ty = y - 0.008
            for ln in lines:
                red = _is_red_line(ln)
                ax.text(cx + 0.006, ty, ln, fontsize=5.4,
                        color=RED_TBC if red else INK, va="top", ha="left")
                ty -= 0.021
        y -= row_h + 0.006

    return _finalise(fig, ax, y - 0.01)


# ---------------------------------------------------------------------------
# 2. Stage chevrons -- arrowed banner per stage, card with chip deliverables.
# ---------------------------------------------------------------------------

def _render_chevrons(columns, project_name, client_name):
    n = max(len(columns), 1)
    fig_w = 12.0
    fig, ax = _new_figure(fig_w, 6.0)

    margin = 0.02
    gap = 0.014
    col_w = (1 - 2 * margin - (n - 1) * gap) / n

    y = _TOP
    ax.text(margin, y, "Our proposed methodology" + (f" — {project_name.strip()}" if (project_name or "").strip() else ""),
            fontsize=12, fontweight="bold", color=INK, va="top", ha="left")
    y -= 0.075

    # The chevron body is narrower than the column (the arrowhead eats
    # width), so wrap against that -- and grow the banner to fit two lines
    # rather than letting a long stage name spill past the arrowhead.
    header_size = 6.6
    header_frac = col_w * 0.74
    header_lines_by_col = []
    for col in columns:
        lines = _wrap(fig, ax, col["name"], header_frac, header_size, "bold")
        if col.get("chevron") and not is_placeholder(col["chevron"]):
            lines = lines + [col["chevron"]]
        header_lines_by_col.append(lines)
    chevron_h = max(0.06, max(len(lines) for lines in header_lines_by_col) * 0.024 + 0.024)
    for i, col in enumerate(columns):
        cx = margin + i * (col_w + gap)
        colour = stage_colour(i)
        from matplotlib.patches import FancyArrow
        ax.add_patch(FancyArrow(cx, y - chevron_h / 2, col_w * 0.94, 0, width=chevron_h,
                                head_width=chevron_h * 1.25, head_length=col_w * 0.14,
                                length_includes_head=True, facecolor=colour, edgecolor="none"))
        lines = header_lines_by_col[i]
        ty = y - chevron_h / 2 + (len(lines) - 1) * 0.012
        for line in lines:
            ax.text(cx + col_w * 0.42, ty, line, fontsize=header_size, color="white",
                    fontweight="bold", ha="center", va="center")
            ty -= 0.024
    y -= chevron_h + 0.02

    card_top = y
    body_size = 5.2
    section_frac = col_w * 0.9
    sections = [("KEY TASKS", "tasks", 4), ("ENGAGEMENT", "engagement", 3), ("OUTCOME", None, None)]
    for i, col in enumerate(columns):
        cx = margin + i * (col_w + gap)
        colour = stage_colour(i)
        cy = card_top
        for label, key, cap in sections:
            ax.text(cx + 0.006, cy, label, fontsize=5.4, color=colour, fontweight="bold", va="top", ha="left")
            cy -= 0.022
            if key is None:
                lines = _wrap(fig, ax, col["outcome"], section_frac, body_size)
            else:
                lines = _bullet_lines(fig, ax, col[key], cap, section_frac, body_size)
            for ln in lines:
                red = _is_red_line(ln)
                ax.text(cx + 0.006, cy, ln, fontsize=5.2, color=RED_TBC if red else INK, va="top", ha="left")
                cy -= 0.019
            cy -= 0.008
        # Deliverables as tinted chips.
        ax.text(cx + 0.006, cy, "DELIVERABLES", fontsize=5.4, color=colour, fontweight="bold", va="top", ha="left")
        cy -= 0.024
        kept, dropped = _cap_items(col["deliverables"], 5)
        placeholder = any(is_placeholder(d) for d in kept)
        cy = _chip_row(ax, cx + 0.004, cx + col_w - 0.004, cy, kept,
                       fill="#FCE8E8" if placeholder else colour,
                       text_colour=RED_TBC if placeholder else "white", size=5.0)
        if dropped:
            cy -= 0.006
            ax.text(cx + 0.006, cy, f"+{dropped} more — see full methodology", fontsize=4.8,
                    color=MUTED, style="italic", va="top", ha="left")
            cy -= 0.018
        # Card border.
        from matplotlib.patches import FancyBboxPatch
        ax.add_patch(FancyBboxPatch((cx, cy - 0.006), col_w, card_top - cy + 0.012,
                                    boxstyle="round,pad=0,rounding_size=0.006",
                                    linewidth=0.8, edgecolor=colour, facecolor="none"))
        y = min(y, cy - 0.02)

    return _finalise(fig, ax, y)


def _tint_hex(hex_colour: str, amount: float) -> str:
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda c: round(c + (255 - c) * amount)
    return f"#{mix(r):02X}{mix(g):02X}{mix(b):02X}"


# ---------------------------------------------------------------------------
# 3. Programme-matched columns -- What we do / With you / You receive.
# ---------------------------------------------------------------------------

def _render_programme(columns, project_name, client_name):
    n = max(len(columns), 1)
    fig_w = 12.0
    fig, ax = _new_figure(fig_w, 6.0)

    margin = 0.02
    gap = 0.05  # room for hold-point diamonds between columns
    col_w = (1 - 2 * margin - (n - 1) * gap) / n

    y = _TOP
    ax.text(margin, y, "Our proposed methodology" + (f" — {project_name.strip()}" if (project_name or "").strip() else ""),
            fontsize=12, fontweight="bold", color=INK, va="top", ha="left")
    y -= 0.075

    # Header sizes to content -- a long stage name wraps rather than
    # overflowing into the gap column the hold-point diamonds live in.
    header_size = 7.0
    header_frac = col_w * 0.92
    header_lines_by_col = [_wrap(fig, ax, col["name"], header_frac, header_size, "bold") for col in columns]
    has_chevron = [bool(col.get("chevron")) and not is_placeholder(col["chevron"]) for col in columns]
    header_h = max(0.075, max(
        len(lines) + (1 if hc else 0) for lines, hc in zip(header_lines_by_col, has_chevron)
    ) * 0.024 + 0.02)
    lowest = y
    for i, col in enumerate(columns):
        cx = margin + i * (col_w + gap)
        colour = stage_colour(i)
        from matplotlib.patches import FancyBboxPatch, Rectangle
        ax.add_patch(Rectangle((cx, y - header_h), col_w, header_h, facecolor=colour, edgecolor="none"))
        name_colour = "white" if not is_placeholder(col["name"]) else "#FFE8E8"
        lines = header_lines_by_col[i]
        block = lines + ([col["chevron"]] if has_chevron[i] else [])
        ty = y - (header_h - (len(block) - 1) * 0.024) / 2 - 0.008
        for j, line in enumerate(block):
            is_chevron_line = has_chevron[i] and j == len(block) - 1
            ax.text(cx + col_w / 2, ty, line,
                    fontsize=5.5 if is_chevron_line else header_size,
                    fontweight="normal" if is_chevron_line else "bold",
                    color="white" if is_chevron_line else name_colour, ha="center", va="center")
            ty -= 0.024

        cy = y - header_h - 0.015
        body_size = 5.0
        section_frac = col_w * 0.9
        sections = [("WHAT WE DO", "tasks", 4), ("WITH YOU", "engagement", 3)]
        for label, key, cap in sections:
            ax.text(cx + 0.005, cy, label, fontsize=5.2, color=colour, fontweight="bold", va="top", ha="left")
            cy -= 0.02
            for ln in _bullet_lines(fig, ax, col[key], cap, section_frac, body_size):
                red = _is_red_line(ln)
                ax.text(cx + 0.005, cy, ln, fontsize=5.0, color=RED_TBC if red else INK, va="top", ha="left")
                cy -= 0.018
            cy -= 0.006

        ax.text(cx + 0.005, cy, "YOU RECEIVE", fontsize=5.2, color=colour, fontweight="bold", va="top", ha="left")
        cy -= 0.022
        kept, dropped = _cap_items(col["deliverables"], 5)
        placeholder = any(is_placeholder(d) for d in kept)
        cy = _chip_row(ax, cx + 0.003, cx + col_w - 0.003, cy, kept,
                       fill="#FCE8E8" if placeholder else _tint_hex(colour, 0.15),
                       text_colour=RED_TBC if placeholder else "white", size=4.9)
        if dropped:
            cy -= 0.006
            ax.text(cx + 0.005, cy, f"+{dropped} more — see full methodology", fontsize=4.6,
                    color=MUTED, style="italic", va="top", ha="left")
            cy -= 0.016

        from matplotlib.patches import FancyBboxPatch as _FBP
        ax.add_patch(_FBP((cx, cy - 0.004), col_w, (y - header_h) - cy + 0.004,
                          boxstyle="round,pad=0,rounding_size=0.004",
                          linewidth=0.7, edgecolor=GRIDLINE, facecolor="none"))
        lowest = min(lowest, cy - 0.02)

        # Hold-point diamond after this stage, only if it actually carries
        # one -- positioned clear below the header band so it never collides
        # with a wrapped stage name.
        if i < n - 1 and stage_carries_hold_point(col):
            from matplotlib.patches import RegularPolygon
            gx = cx + col_w + gap / 2
            gy = y - header_h - 0.055
            ax.add_patch(RegularPolygon((gx, gy), numVertices=4, radius=gap * 0.28,
                                        orientation=0.785398, facecolor="#F97316", edgecolor="white", linewidth=0.6))
            ax.text(gx, gy - 0.045, "HOLD\nPOINT", fontsize=4.2, color="#F97316", fontweight="bold",
                    ha="center", va="top")
            lowest = min(lowest, gy - 0.09)

    return _finalise(fig, ax, lowest)


# ---------------------------------------------------------------------------
# 4. Timeline spine -- vertical node per stage, full-width band.
# ---------------------------------------------------------------------------

def _render_spine(columns, project_name, client_name):
    fig_w = 12.0
    fig, ax = _new_figure(fig_w, 7.5)

    margin = 0.02
    spine_x = margin + 0.012
    band_x = margin + 0.05
    band_right = 1 - margin

    y = _TOP
    ax.text(margin, y, "Our proposed methodology" + (f" — {project_name.strip()}" if (project_name or "").strip() else ""),
            fontsize=12, fontweight="bold", color=INK, va="top", ha="left")
    y -= 0.06

    label_w = (band_right - band_x) * 0.22
    tasks_x = band_x + label_w + 0.01
    tasks_w = (band_right - tasks_x) * 0.55
    deliv_x = tasks_x + tasks_w + 0.015
    deliv_w = band_right - deliv_x

    label_frac = label_w * 0.9
    tasks_frac = tasks_w * 0.9

    node_ys = []
    for i, col in enumerate(columns):
        colour = stage_colour(i)
        label_lines = [col["name"]]
        if col.get("chevron") and not is_placeholder(col["chevron"]):
            label_lines.append(col["chevron"])
        outcome_lines = _wrap(fig, ax, col["outcome"], label_frac, 4.9)
        task_lines = _bullet_lines(fig, ax, col["tasks"], 5, tasks_frac, 4.8)
        deliv_kept, deliv_dropped = _cap_items(col["deliverables"], 5)

        content_lines = max(len(label_lines) + len(outcome_lines), len(task_lines),
                            2 + len(deliv_kept) // 2 + (1 if deliv_dropped else 0))
        band_h = max(0.09, content_lines * 0.021 + 0.02)

        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((band_x, y - band_h), label_w, band_h,
                               facecolor=_tint_hex(colour, 0.85), edgecolor="none"))
        ty = y - 0.014
        ax.text(band_x + 0.006, ty, col["name"], fontsize=6.2, fontweight="bold",
                color=RED_TBC if is_placeholder(col["name"]) else INK, va="top", ha="left")
        ty -= 0.022
        if col.get("chevron") and not is_placeholder(col["chevron"]):
            ax.text(band_x + 0.006, ty, col["chevron"], fontsize=5.0, color=MUTED, va="top", ha="left")
            ty -= 0.02
        for ln in outcome_lines:
            ax.text(band_x + 0.006, ty, ln, fontsize=4.9,
                    color=RED_TBC if is_placeholder(col["outcome"]) else MUTED, va="top", ha="left")
            ty -= 0.018

        ty = y - 0.014
        ax.text(tasks_x, ty, "WHAT WE DO", fontsize=4.9, color=colour, fontweight="bold", va="top", ha="left")
        ty -= 0.02
        for ln in task_lines:
            red = _is_red_line(ln)
            ax.text(tasks_x, ty, ln, fontsize=4.8, color=RED_TBC if red else INK, va="top", ha="left")
            ty -= 0.017

        ty = y - 0.014
        ax.text(deliv_x, ty, "WHAT YOU RECEIVE", fontsize=4.9, color=colour, fontweight="bold", va="top", ha="left")
        ty -= 0.022
        _deliv_placeholder = any(is_placeholder(d) for d in deliv_kept)
        _chip_row(ax, deliv_x, deliv_x + deliv_w, ty, deliv_kept,
                 fill="#FCE8E8" if _deliv_placeholder else _tint_hex(colour, 0.8),
                 text_colour=RED_TBC if _deliv_placeholder else INK, size=4.6, row_h=0.024)
        if deliv_dropped:
            ax.text(deliv_x, ty - 0.05, f"+{deliv_dropped} more — see full methodology", fontsize=4.4,
                    color=MUTED, style="italic", va="top", ha="left")

        from matplotlib.patches import Rectangle as _R
        ax.add_patch(_R((band_x, y - band_h), band_right - band_x, band_h,
                        facecolor="none", edgecolor=GRIDLINE, linewidth=0.6))
        node_ys.append(y - band_h / 2)
        y -= band_h + 0.012

    # Spine line + coloured node per stage, drawn last so it sits on top.
    if node_ys:
        ax.plot([spine_x, spine_x], [node_ys[-1], node_ys[0]], color=GRIDLINE, linewidth=1.4, zorder=1)
    for i, ny in enumerate(node_ys):
        ax.add_patch(__import__("matplotlib").patches.Circle((spine_x, ny), 0.008,
                     facecolor=stage_colour(i), edgecolor="white", linewidth=0.8, zorder=2))

    return _finalise(fig, ax, y)
