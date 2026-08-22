"""
program_render.py

The delivery program's shared data model, and four PNG renderers -- one per
user-selectable presentation style.

WHY ONE MODEL AND FOUR RENDERERS
--------------------------------
The program has to appear in three places: the UI preview, the letter pack's
DOCX, and the companion PowerPoint. Before this, each of those derived its
own view of the same schedule, which is how a preview and an export drift
apart. _program_model() normalises the schedule ONCE -- items with their
first/last active week, week labels (real dates when the anticipated start
date exists), month bands, stage assignment, milestones -- and every
renderer, in every output, consumes that one object.

WHAT IS AND ISN'T INVENTED
--------------------------
Everything here is derived arithmetic over things the user entered: the
weeks they ticked, the start date they typed, the stages they reviewed, the
submission date the brief stated. Milestones appear ONLY where those inputs
exist. There is no "assume a design review at 50%", no inferred hold point,
no default milestone -- an empty inputs set produces an empty milestone
list, and the program simply has none.

STYLE VOCABULARY (shared by all four)
-------------------------------------
No cell borders anywhere. Thin light vertical week gridlines. Slim
fully-rounded bars with a small bold white duration label centred in them.
Orange milestone diamonds with labels below the grid and a faint vertical
orange rule. A legend row. "Wk N" headers in bold with the date beneath
when known.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

STYLES = ("gantt", "swimlanes", "table", "timeline")
DEFAULT_STYLE = "swimlanes"

STYLE_LABELS = {
    "gantt": "Refined Gantt",
    "swimlanes": "Stage swimlanes",
    "table": "Formal table",
    "timeline": "Modern timeline",
}

STYLE_DESCRIPTIONS = {
    "gantt": "Slim rounded bars, row banding, milestones (classic)",
    "swimlanes": "Activities grouped and colour-coded by design stage",
    "table": "Commence/complete/duration columns + inline timeline (most conservative)",
    "timeline": "Labels inside full-width bars, month banding (most visual)",
}

# Fixed and colourblind-validated. Do not substitute hues: these four are
# distinguishable under deuteranopia and protanopia, which a "nicer" set
# picked by eye generally is not.
STAGE_COLOURS = ["#1D4ED8", "#0D9488", "#F97316", "#6D28D9"]

BAR_BLUE = "#1D4ED8"
BAR_BLUE_LIGHT = "#3B6FE8"
MILESTONE_ORANGE = "#F97316"
GRIDLINE = "#EEF1F4"
ROW_BAND = "#F7F9FC"
TRACK_GREY = "#EDEFF2"
INK = "#1A2233"
MUTED = "#7A8598"


@dataclass
class ProgramItem:
    label: str
    start_week: int          # 1-based, inclusive
    end_week: int            # 1-based, inclusive
    stage_index: int | None = None   # index into the model's stages

    @property
    def weeks(self) -> int:
        return max(1, self.end_week - self.start_week + 1)


@dataclass
class Milestone:
    label: str
    week: int                # 1-based


@dataclass
class ProgramModel:
    items: list[ProgramItem] = field(default_factory=list)
    week_labels: list[str] = field(default_factory=list)
    week_dates: list[str] = field(default_factory=list)   # "" where unknown
    month_bands: list[tuple[str, int, int]] = field(default_factory=list)  # (name, first_week, last_week)
    stages: list[str] = field(default_factory=list)
    milestones: list[Milestone] = field(default_factory=list)
    start_date_text: str = ""
    project_name: str = ""
    client_name: str = ""

    @property
    def week_count(self) -> int:
        return len(self.week_labels)

    @property
    def is_empty(self) -> bool:
        return not self.items or not self.week_labels

    @property
    def has_stages(self) -> bool:
        return bool(self.stages) and any(i.stage_index is not None for i in self.items)


def _split_week_label(label: str) -> tuple[str, str]:
    """program_schedule.week_labels() produces "Wk 3" or "Wk 3 - 20 Oct".
    The renderers want those two parts separately."""
    text = str(label or "")
    if " - " in text:
        head, _, tail = text.partition(" - ")
        return head.strip(), tail.strip()
    return text.strip(), ""


def build_model(program_schedule: dict | None,
                week_labels: list | None,
                methodology_stages: list | None = None,
                start_date=None,
                analysis=None,
                project_name: str = "",
                client_name: str = "") -> ProgramModel:
    """Normalise everything the four renderers need. Pure derivation -- see
    the module note on what is never invented."""
    model = ProgramModel(project_name=project_name or "", client_name=client_name or "")
    labels = [str(l) for l in (week_labels or [])]
    model.week_labels = [_split_week_label(l)[0] for l in labels]
    model.week_dates = [_split_week_label(l)[1] for l in labels]

    for title, weeks in (program_schedule or {}).items():
        active = [i + 1 for i, on in enumerate(weeks or []) if on]
        if not active:
            # An item with no weeks ticked isn't programmed; showing a
            # zero-length bar would imply it happens instantaneously.
            continue
        model.items.append(ProgramItem(str(title), active[0], active[-1]))

    # Month bands, only derivable when real dates exist.
    if start_date is not None and model.week_labels:
        from datetime import timedelta
        current = None
        for index in range(len(model.week_labels)):
            month = (start_date + timedelta(weeks=index)).strftime("%B").upper()
            if current and current[0] == month:
                model.month_bands[-1] = (month, current[1], index + 1)
                current = (month, current[1], index + 1)
            else:
                model.month_bands.append((month, index + 1, index + 1))
                current = (month, index + 1, index + 1)
        model.start_date_text = f"{start_date.day} {start_date.strftime('%b %Y')}"

    # Stage assignment: the stage whose week range contains an item's start.
    stages = [s for s in (methodology_stages or []) if getattr(s, "name", "")]
    if stages:
        model.stages = [str(getattr(s, "name", "") or "") for s in stages]
        for item in model.items:
            # Stage week ranges routinely overlap (a concept stage starting
            # while initiation finishes), so first-match would file an item
            # under whichever stage merely began earliest. Among the stages
            # that contain this item's start week, take the one that begins
            # LATEST -- the most specific fit, and the one a reader would
            # name if asked which stage the work belongs to.
            candidates = [
                (getattr(stage, "week_start", None) or 0, index)
                for index, stage in enumerate(stages)
                if (getattr(stage, "week_start", None)
                    and (getattr(stage, "week_end", None) or getattr(stage, "week_start"))
                    and getattr(stage, "week_start") <= item.start_week
                    <= (getattr(stage, "week_end", None) or getattr(stage, "week_start")))
            ]
            if candidates:
                item.stage_index = max(candidates)[1]

    # Milestones -- only from inputs that actually exist.
    for index, stage in enumerate(stages):
        end = getattr(stage, "week_end", None)
        activities = [str(a).lower() for a in (getattr(stage, "engagement_activities", None) or [])]
        holds = [a for a in activities if "hold point" in a and a.strip().upper() != "TBC"]
        if end and holds:
            model.milestones.append(Milestone("Client hold point", int(end)))
    submission_week = _submission_week(analysis, start_date, len(model.week_labels))
    if submission_week:
        model.milestones.append(Milestone("Submission", submission_week))

    return model


def _submission_week(analysis, start_date, week_count: int) -> int | None:
    """The submission date as a week number, when both the date and a start
    date exist and it lands inside the program. Never guessed."""
    if analysis is None or start_date is None or not week_count:
        return None
    raw = (getattr(analysis, "submission_date", "") or "").strip()
    if not raw:
        return None
    parsed = _parse_date(raw)
    if parsed is None:
        return None
    delta_days = (parsed - start_date).days
    if delta_days < 0:
        return None
    week = delta_days // 7 + 1
    return week if 1 <= week <= week_count else None


def _parse_date(text: str):
    """Best-effort parse of a human-written date. Returns None rather than
    guessing -- a wrong milestone date on a client-facing program is worse
    than no milestone."""
    import re
    from datetime import date

    months = {m: i + 1 for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
    lowered = (text or "").lower()
    year_match = re.search(r"\b(20\d{2})\b", lowered)
    if not year_match:
        return None
    year = int(year_match.group(1))
    month = next((n for m, n in months.items() if m in lowered), None)
    numbers = [int(n) for n in re.findall(r"\b(\d{1,2})\b", lowered)]
    if month is None:
        if len(numbers) < 2:
            return None
        day, month = numbers[0], numbers[1]
    else:
        day = numbers[0] if numbers else 1
    try:
        return date(year, month, day)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# PNG rendering
# ---------------------------------------------------------------------------
#
# SCALE-TO-FILL, LIKE THE ORG CHART
# ----------------------------------
# This used to render every row/lane at a fixed size and then grow (or crop)
# the canvas to whatever that produced -- so a 4-item program drew four small
# rows at the top of a mostly-empty page. The page is now the fixed A4
# landscape sheet every export in this pack uses (see PAGE_W_IN/PAGE_H_IN
# below); each style instead measures its content at a reference scale,
# picks ONE scale factor from how much of the fixed page it needs to fill,
# and derives row height, bar thickness, gridline weight, milestone size and
# every font from that one number -- the exact approach org_chart_render.py
# takes for the org chart, applied here to a grid instead of a hierarchy.
#
# The one deliberate difference: an org chart wraps to more columns when a
# team is too wide; a program can't "wrap" weeks or scope items. So instead
# of a per-row-candidate search, the scale is a straight height fit, and at
# the extreme end (very many items or weeks) the MIN_SCALE floor stops
# shrinking text below the readable minimum and grows the page instead --
# the same overflow escape valve program_pptx.py's _grow() already uses for
# the companion PowerPoint, now shared by the PNG that feeds the preview and
# the letter pack.

EMPTY_NOTE = ("[NO PROGRAM ENTERED -- build the delivery program in the Fees & Program tab, "
              "then re-generate this]")

# Same precise A4 landscape page (297mm x 210mm) as every other generated
# artefact in this pack (org_chart_render.py, program_pptx.py,
# methodology_pptx.py). Coordinates for every style below are real inches on
# this page, not axes-fractions: the axes limits are set to (0, PAGE_W_IN)
# and (0, total_height_in), so 1 data unit == 1 inch on BOTH axes and a
# patch's width/height come out physically equal without the aspect
# correction org_chart_render.py needs for its avatar circles.
PAGE_W_IN = 11.6929
PAGE_H_IN = 8.2677
_MARGIN_IN = 0.35
_TITLE_BAND_IN = 0.62

CONTENT_LEFT_IN = _MARGIN_IN
CONTENT_RIGHT_IN = PAGE_W_IN - _MARGIN_IN
AVAIL_W_IN = CONTENT_RIGHT_IN - CONTENT_LEFT_IN

# The scale factor is clamped to this range in the ordinary case. Below
# MIN_SCALE the page grows instead of shrinking further (see _fit_height
# below) -- a 25-item program should still be readable, not a page of
# 5pt text. MAX_SCALE stops a 3-item program from blowing its rows up to a
# cartoonish size just because the page is mostly empty.
MIN_SCALE = 0.55
MAX_SCALE = 1.25


def render_png(model: ProgramModel, style: str = DEFAULT_STYLE,
               theme_accent: str | None = None) -> bytes | None:
    """The program as a PNG, in the requested style.

    Returns None on any failure -- the callers all fall back to something
    that still communicates the program, never to nothing.
    """
    style = style if style in STYLES else DEFAULT_STYLE
    # Swimlanes without methodology stages has nothing to group by, so it
    # degrades to the Gantt rather than drawing one meaningless lane.
    if style == "swimlanes" and not model.has_stages:
        style = "gantt"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        renderer = {
            "gantt": _render_gantt,
            "swimlanes": _render_swimlanes,
            "table": _render_table,
            "timeline": _render_timeline,
        }[style]
        fig = renderer(model, theme_accent or BAR_BLUE)
        buffer = io.BytesIO()
        # No bbox_inches="tight": that silently re-crops the saved PNG back
        # to the drawn content regardless of the figure's declared size --
        # exactly the mechanism that defeated the org chart's first attempt
        # at a truly fixed page (see org_chart_render.py's render_png()).
        fig.savefig(buffer, format="png", dpi=170,
                    facecolor="white", edgecolor="none")
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


def effective_style(model: ProgramModel, style: str) -> str:
    """The style that will actually be drawn -- swimlanes falls back to the
    Gantt without stages, and the UI says so rather than silently showing
    something other than what was picked."""
    style = style if style in STYLES else DEFAULT_STYLE
    if style == "swimlanes" and not model.has_stages:
        return "gantt"
    return style


# --- shared drawing helpers ------------------------------------------------

def _new_page(total_h_in: float):
    """A page PAGE_W_IN wide and `total_h_in` tall (== PAGE_H_IN except in
    the rare overflow case -- see _fit_height), whose axes fill the ENTIRE
    figure and whose data coordinates are real inches: (0, 0) is the
    page's bottom-left corner, (PAGE_W_IN, total_h_in) its top-right.
    add_axes([0, 0, 1, 1]) rather than plt.subplots()'s default inset, so
    the mapping is exact -- the same fix org_chart_render._new_figure()
    applies, for the same reason (a hidden matplotlib margin otherwise eats
    into the page)."""
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(PAGE_W_IN, total_h_in))
    axes = figure.add_axes((0.0, 0.0, 1.0, 1.0))
    axes.set_axis_off()
    axes.set_xlim(0, PAGE_W_IN)
    axes.set_ylim(0, total_h_in)
    return figure, axes


def _fit_height(natural_h_in: float) -> tuple[float, float, float]:
    """(scale, total_page_h_in, avail_h_in) for content whose natural
    (scale=1.0) height is `natural_h_in`.

    Ordinary case: scale = clamp(avail_h/natural_h, MIN_SCALE, MAX_SCALE),
    drawn on the fixed PAGE_H_IN page -- content reaches MIN_SCALE only when
    it would otherwise need to shrink past it.

    Overflow case: even MIN_SCALE would spill past the fixed page (a very
    long item/lane list). Rather than shrinking text past the readable
    floor, the page grows by exactly the overflow -- content is drawn at
    MIN_SCALE and the extra room it needs becomes extra page, the same
    escape valve program_pptx.py's _grow() already gives the PowerPoint."""
    content_top_in = PAGE_H_IN - _MARGIN_IN - _TITLE_BAND_IN
    avail_h_in = content_top_in - _MARGIN_IN
    if natural_h_in <= 0:
        return MAX_SCALE, PAGE_H_IN, avail_h_in
    scale = max(MIN_SCALE, min(MAX_SCALE, avail_h_in / natural_h_in))
    needed_in = natural_h_in * scale
    if needed_in <= avail_h_in + 1e-9:
        return scale, PAGE_H_IN, avail_h_in
    overflow_in = needed_in - avail_h_in
    return scale, PAGE_H_IN + overflow_in, avail_h_in + overflow_in


class _VFlow:
    """A vertical sequence of blocks (drawable content, fixed reference
    height), gaps (spacing that STRETCHES to absorb leftover page height)
    and fixed items (drawable content whose height is already final and
    must NOT be multiplied by scale again -- see the table style's row-
    height cap), each given a height in real inches. See
    org_chart_render._Flow for the identical idea applied to the org
    chart's hierarchy; this is the same mechanism turned sideways onto a
    grid instead of a tree, so a program with few rows gets its leftover
    room back as breathing space between sections (header, rows,
    milestones, legend) rather than one dead band under everything.

    Every draw(y_top, y_bottom, scale) callback receives its own span in
    real page inches, plus the scale itself for anything that needs it
    directly (font sizes, line weights)."""

    def __init__(self):
        self._items: list[dict] = []

    def block(self, h_in: float, draw=None) -> None:
        self._items.append({"kind": "block", "h": max(0.0, h_in), "draw": draw})

    def gap(self, h_in: float, draw=None) -> None:
        self._items.append({"kind": "gap", "h": max(0.0, h_in), "draw": draw})

    def fixed(self, h_in: float, draw=None) -> None:
        """A block whose height is ALREADY final (e.g. a table row clamped
        to a maximum) -- render() uses it as-is rather than multiplying by
        scale a second time."""
        self._items.append({"kind": "fixed", "h": max(0.0, h_in), "draw": draw})

    def render(self, top_y_in: float, scale: float, avail_h_in: float) -> float:
        """Draws every item top-down and returns the final bottom y."""
        n_gaps = sum(1 for it in self._items if it["kind"] == "gap")
        used_in = sum(it["h"] if it["kind"] == "fixed" else it["h"] * scale
                      for it in self._items)
        leftover_in = max(0.0, avail_h_in - used_in)
        extra_per_gap_in = (leftover_in / n_gaps) if n_gaps else 0.0
        y = top_y_in
        for it in self._items:
            if it["kind"] == "fixed":
                h_in = it["h"]
            else:
                h_in = it["h"] * scale + (extra_per_gap_in if it["kind"] == "gap" else 0.0)
            y_bottom = y - h_in
            if it["draw"] is not None:
                it["draw"](y, y_bottom, scale)
            y = y_bottom
        return y


def _fw(inches: float) -> float:
    """Inches -> fraction of the (fixed-width) page, for _fit_label's
    max_frac argument -- _text_width_frac measures a fraction of the axes'
    PIXEL width, and the axes is exactly PAGE_W_IN inches wide whatever the
    page's height, so this conversion never needs the page height."""
    return max(0.0, inches) / PAGE_W_IN


def _rounded_bar(ax, x0: float, x1: float, y: float, height: float, colour: str,
                 label: str = "", label_colour: str = "white", fontsize: float = 6.5,
                 label_align: str = "center", shadow: bool = False):
    """A fully-rounded pill. Radius is half the height, which is what makes
    the ends read as round rather than as a rounded rectangle -- and, with
    the axes' data units running 1:1 with real inches on both x and y (see
    _new_page), that radius comes out an actual circle-cap without the
    aspect correction org_chart_render.py needs for its avatar circles."""
    from matplotlib.patches import FancyBboxPatch

    width = max(x1 - x0, height * 0.6)
    patch = FancyBboxPatch(
        (x0, y - height / 2), width, height,
        boxstyle=f"round,pad=0,rounding_size={height / 2}",
        linewidth=0, facecolor=colour, mutation_aspect=1,
    )
    if shadow:
        from matplotlib.patheffects import withSimplePatchShadow
        patch.set_path_effects([withSimplePatchShadow(offset=(0.6, -0.9), alpha=0.16)])
    ax.add_patch(patch)
    if label:
        if label_align == "left":
            ax.text(x0 + height * 0.55, y, label, color=label_colour, fontsize=fontsize,
                    fontweight="bold", va="center", ha="left")
        else:
            ax.text((x0 + x0 + width) / 2, y, label, color=label_colour, fontsize=fontsize,
                    fontweight="bold", va="center", ha="center")
    return patch


def _text_width_frac(fig, artist) -> float:
    """A text artist's width as a fraction of the AXES width.

    Measured from the real renderer rather than estimated from a
    characters-per-inch guess: two guesses at this in a row were wrong in
    opposite directions, over-ellipsizing labels that fitted and then
    letting labels run past the end of their bar.

    Against the AXES and not the figure, because every width this is
    compared with is a data-space measurement in the axes' own inch-real
    coordinates. The axes does not fill the figure by default (matplotlib's
    default subplot margins leave roughly a quarter of it outside) -- but
    _new_page() uses add_axes([0, 0, 1, 1]), so here it does; measuring
    against the figure would still have worked, but matching the axes is
    what the fraction this returns is actually compared against.
    """
    try:
        renderer = fig.canvas.get_renderer()
    except Exception:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    bbox = artist.get_window_extent(renderer=renderer)
    axes = getattr(artist, "axes", None)
    reference = axes.get_window_extent(renderer=renderer).width if axes is not None else fig.bbox.width
    return bbox.width / max(1.0, reference)


def _fit_label(fig, artist, max_frac: float, start_size: float, min_size: float = 5.0) -> None:
    """Shrink a bar's inner label to fit, then ellipsize if it still won't.

    Shrinking first keeps the whole label readable; ellipsizing is the last
    resort, and it is visibly an ellipsis rather than text that silently
    runs off the end of its bar."""
    size = start_size
    while size > min_size and _text_width_frac(fig, artist) > max_frac:
        size -= 0.2
        artist.set_fontsize(size)
    text = artist.get_text()
    while len(text) > 4 and _text_width_frac(fig, artist) > max_frac:
        text = text[:-2]
        artist.set_text(text.rstrip() + "…")


def _week_geometry(model: ProgramModel, left: float, right: float):
    span = max(1, model.week_count)
    width = (right - left) / span
    return left, width


# The narrowest a "Wk NN" header can sit next to its neighbour, in inches at
# scale=1.0, before the two touch -- scales with everything else so a large,
# large-font program still thins its labels at the point they'd actually
# collide, not the point a fixed reference would have.
_HEADER_MIN_PITCH_IN = 0.50


def _header_indices(model: ProgramModel, week_w_in: float, scale: float = 1.0,
                    ax=None, pt: float | None = None) -> list[int]:
    """Which week indices get a header label. Always the first and the last,
    then every Nth in between -- and never the second-to-last kept one when
    it would crowd the final week.

    A 14-week program labels every week. A 40-week one cannot -- at that
    density "Wk 9Wk 10Wk 11" ran together into an unreadable smear. The
    gridlines still mark every week, so nothing is lost: only the labels
    thin out, exactly as a printed program's would.

    The minimum pitch is the WIDER of a flat per-scale guess and the actual
    rendered width of the longest week label (measured via the real
    renderer when `ax`/`pt` are given, the same way _fit_label measures bar
    labels) -- a flat guess alone missed exactly the case its own docstring
    describes: "Wk 9" and "Wk 10" both clear a geometric pitch built for
    single-digit weeks, but "Wk 10"/"Wk 11"/"Wk 12" are visibly wider once
    the header font scales up toward MAX_SCALE, and ran together anyway."""
    import math
    count = len(model.week_labels)
    if count <= 1:
        return list(range(count))
    pitch_in = _HEADER_MIN_PITCH_IN * max(scale, 1e-6)
    if ax is not None and pt is not None and model.week_labels:
        widest = max(model.week_labels, key=len)
        probe = ax.text(0, 0, widest, fontsize=pt, fontweight="bold")
        try:
            label_w_in = _text_width_frac(ax.figure, probe) * PAGE_W_IN
        finally:
            probe.remove()
        pitch_in = max(pitch_in, label_w_in * 1.15)
    step = max(1, math.ceil(pitch_in / max(week_w_in, 1e-6)))
    kept = list(range(0, count, step))
    last = count - 1
    if kept[-1] != last:
        while kept and last - kept[-1] < step:
            kept.pop()
        kept.append(last)
    return kept


def _draw_week_header(ax, model: ProgramModel, left: float, right: float, y: float,
                      scale: float, show_dates: bool = True):
    _, week_w = _week_geometry(model, left, right)
    pt = max(_WEEK_PT_MIN, _WEEK_PT_REF * scale)
    date_pt = max(_WEEK_DATE_PT_MIN, _WEEK_DATE_PT_REF * scale)
    for index in _header_indices(model, week_w, scale, ax=ax, pt=pt):
        label = model.week_labels[index]
        centre = left + (index + 0.5) * week_w
        ax.text(centre, y, label, fontsize=pt, fontweight="bold", color=INK,
                ha="center", va="top")
        date_text = model.week_dates[index] if index < len(model.week_dates) else ""
        if show_dates and date_text:
            ax.text(centre, y - 0.20 * scale, date_text, fontsize=date_pt, color=MUTED,
                    ha="center", va="top")


def _draw_gridlines(ax, model: ProgramModel, left: float, right: float,
                    top: float, bottom: float, scale: float):
    _, week_w = _week_geometry(model, left, right)
    lw = max(0.5, 0.7 * scale)
    for index in range(model.week_count + 1):
        x = left + index * week_w
        ax.plot([x, x], [bottom, top], color=GRIDLINE, linewidth=lw, zorder=0)


def _draw_milestones(ax, model: ProgramModel, left: float, right: float,
                     top: float, bottom: float, label_y: float, scale: float):
    _, week_w = _week_geometry(model, left, right)
    seen = set()
    marker = max(4.0, 5.5 * scale)
    lw = max(0.6, 0.8 * scale)
    pt = max(_MILESTONE_PT_MIN, _MILESTONE_PT_REF * scale)
    for milestone in model.milestones:
        if milestone.week in seen:
            continue
        seen.add(milestone.week)
        x = left + milestone.week * week_w
        ax.plot([x, x], [bottom, top], color=MILESTONE_ORANGE, linewidth=lw,
                alpha=0.55, zorder=1)
        ax.plot([x], [bottom], marker="D", markersize=marker, color=MILESTONE_ORANGE, zorder=3)
        # A milestone on the final week sits on the right edge, where a
        # centred label runs off the canvas -- anchor those to the edge
        # instead.
        align = "center"
        if x > right - 0.55:
            align = "right"
        elif x < left + 0.55:
            align = "left"
        ax.text(x, label_y, milestone.label, fontsize=pt, fontweight="bold",
                color=MILESTONE_ORANGE, ha=align, va="top")


def _draw_title(ax, model: ProgramModel, total_h_in: float, subtitle: str = ""):
    top_y = total_h_in - _MARGIN_IN
    ax.text(CONTENT_LEFT_IN, top_y, "Delivery program", fontsize=15, fontweight="bold",
            color="#111827", ha="left", va="top")
    if subtitle:
        ax.text(CONTENT_LEFT_IN, top_y - 0.24, subtitle, fontsize=6.6, color=MUTED, ha="left", va="top")
    heading = " — ".join(p for p in (model.project_name, model.client_name) if p)
    if heading:
        ax.text(CONTENT_RIGHT_IN, top_y, heading, fontsize=8.2, fontweight="bold",
                color="#6B7280", ha="right", va="top")


def _activity_legend(model: ProgramModel, accent: str) -> list[tuple[str, str]]:
    """A legend key for a mark that isn't on the chart is noise -- and the
    milestone key is the same orange as the third stage colour, so an unused
    one actively misleads."""
    entries = [(accent, "Scheduled activity")]
    if model.milestones:
        entries.append((MILESTONE_ORANGE, "Milestone / hold point"))
    return entries


def _draw_legend(ax, entries: list[tuple[str, str]], y: float, x: float, scale: float):
    """entries: [(colour, label)] -- a swatch row. The milestone entry draws
    a diamond rather than a square so it matches the marks on the chart."""
    from matplotlib.patches import Rectangle
    fig = ax.figure
    cursor = x
    swatch = 0.13 * scale
    pt = max(_LEGEND_PT_MIN, _LEGEND_PT_REF * scale)
    for colour, label in entries:
        if label.lower().startswith("milestone"):
            ax.plot([cursor + swatch * 0.5], [y], marker="D", markersize=max(4.0, 5.0 * scale),
                    color=MILESTONE_ORANGE)
        else:
            ax.add_patch(Rectangle((cursor, y - swatch * 0.42), swatch, swatch * 0.84,
                                   facecolor=colour, linewidth=0))
        text = ax.text(cursor + swatch * 1.7, y, label, fontsize=pt, fontweight="bold",
                       color=INK, ha="left", va="center")
        # The label's ACTUAL rendered width, not a characters-times-scale
        # guess: legend text is floored at _LEGEND_PT_MIN rather than
        # shrinking all the way with scale, so near MIN_SCALE the true text
        # is noticeably wider than `scale` alone would predict -- an
        # estimate built from `scale` under-measured it there and let a
        # long-programme legend's entries (and, at the far end, the
        # milestone diamond) crowd into the previous label. Measuring the
        # real text extent, the same way the bar/row labels already do via
        # _text_width_frac, is exact regardless of where the size floor
        # kicked in.
        width_in = _text_width_frac(fig, text) * PAGE_W_IN
        cursor += swatch * 1.7 + width_in + 0.14 * max(scale, 0.6)


def _empty_figure(model: ProgramModel):
    figure, axes = _new_page(PAGE_H_IN)
    _draw_title(axes, model, PAGE_H_IN)
    # Sits just under the title rather than mid-canvas: a placeholder that
    # floats in a half-page of white reads as a broken image, which is the
    # opposite of the point -- it has to read as a note to the writer.
    axes.text(PAGE_W_IN / 2, PAGE_H_IN * 0.60, EMPTY_NOTE, fontsize=11, color="#C00000",
             style="italic", ha="center", va="center", wrap=True)
    return figure


# Font sizes at scale=1.0, and the floor each is allowed to shrink to. Chosen
# so a typical program (7 items x 10 weeks, where the natural size lands
# close to scale=1) puts scope-item labels in the ~12-14pt band and week
# headers in the ~11-12pt band the fix brief asks for; MAX_SCALE then makes
# a smaller program's text visibly larger still, and MIN_SCALE (below which
# the page grows -- see _fit_height) keeps a very large one legible.
_ROW_LABEL_PT_REF, _ROW_LABEL_PT_MIN = 12.5, 7.0
_BAR_LABEL_PT_REF, _BAR_LABEL_PT_MIN = 9.5, 6.0
_WEEK_PT_REF, _WEEK_PT_MIN = 11.0, 6.0
_WEEK_DATE_PT_REF, _WEEK_DATE_PT_MIN = 8.8, 5.5
_MILESTONE_PT_REF, _MILESTONE_PT_MIN = 9.5, 6.0
_LEGEND_PT_REF, _LEGEND_PT_MIN = 9.5, 6.5
_LANE_PT_REF, _LANE_PT_MIN = 10.5, 6.5


# --- A. Refined Gantt ------------------------------------------------------

_GANTT_LABEL_COL_REF_IN = 2.5
_GANTT_HEADER_H_REF = 0.46
_GANTT_ROW_H_REF = 0.80
_GANTT_GAP_REF = 0.14
_GANTT_MILESTONE_H_REF = 0.42
_GANTT_LEGEND_H_REF = 0.34


def _render_gantt(model: ProgramModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)
    from matplotlib.patches import Rectangle

    n = len(model.items)
    has_ms = bool(model.milestones)
    natural_h = (_GANTT_HEADER_H_REF + _GANTT_GAP_REF
                + n * _GANTT_ROW_H_REF + _GANTT_GAP_REF
                + (_GANTT_MILESTONE_H_REF + _GANTT_GAP_REF if has_ms else 0.0)
                + _GANTT_LEGEND_H_REF)
    scale, total_h_in, avail_h_in = _fit_height(natural_h)

    figure, axes = _new_page(total_h_in)
    _draw_title(axes, model, total_h_in)

    label_col_w = _GANTT_LABEL_COL_REF_IN * scale
    left_in = CONTENT_LEFT_IN + label_col_w
    right_in = CONTENT_RIGHT_IN
    content_top_in = total_h_in - _MARGIN_IN - _TITLE_BAND_IN

    _, week_w_in = _week_geometry(model, left_in, right_in)
    labels: list[tuple[object, float]] = []
    bounds: dict[str, float] = {}
    flow = _VFlow()

    def draw_header(y_top, y_bottom, scale):
        _draw_week_header(axes, model, left_in, right_in, y_top, scale)
        bounds["grid_top"] = y_bottom
    flow.block(_GANTT_HEADER_H_REF, draw_header)
    flow.gap(_GANTT_GAP_REF)

    # Row labels sit in the left margin; the "N wk" pill labels sit inside
    # their bar. Both can outrun their space on a real project -- a long
    # activity name, or a one-week bar -- so each is measured against the
    # width it actually has and fitted once the figure is complete.
    for index, item in enumerate(model.items):
        def draw_row(y_top, y_bottom, scale, index=index, item=item):
            centre_y = (y_top + y_bottom) / 2
            if index % 2 == 1:
                axes.add_patch(Rectangle((CONTENT_LEFT_IN, y_bottom), right_in - CONTENT_LEFT_IN,
                                         y_top - y_bottom, facecolor=ROW_BAND, linewidth=0, zorder=0))
            pt = max(_ROW_LABEL_PT_MIN, _ROW_LABEL_PT_REF * scale)
            axes.text(CONTENT_LEFT_IN, centre_y, item.label, fontsize=pt, fontweight="bold",
                     color=INK, ha="left", va="center")
            labels.append((axes.texts[-1], _fw(label_col_w - 0.16 * scale)))
            x0 = left_in + (item.start_week - 1) * week_w_in
            x1 = left_in + item.end_week * week_w_in
            bar_h = (y_top - y_bottom) * 0.45
            bar_pt = max(_BAR_LABEL_PT_MIN, _BAR_LABEL_PT_REF * scale)
            _rounded_bar(axes, x0 + 0.02 * scale, x1 - 0.02 * scale, centre_y, bar_h, accent,
                        f"{item.weeks} wk", fontsize=bar_pt)
            labels.append((axes.texts[-1], _fw(max(0.05, x1 - x0 - 0.06 * scale))))
            bounds["grid_bottom"] = y_bottom
        flow.block(_GANTT_ROW_H_REF, draw_row)

    flow.gap(_GANTT_GAP_REF)

    if has_ms:
        def draw_ms_anchor(y_top, y_bottom, scale):
            bounds["ms_y"] = y_top
        flow.block(_GANTT_MILESTONE_H_REF, draw_ms_anchor)
        flow.gap(_GANTT_GAP_REF)

    def draw_legend_anchor(y_top, y_bottom, scale):
        bounds["legend_y"] = y_top
    flow.block(_GANTT_LEGEND_H_REF, draw_legend_anchor)

    flow.render(content_top_in, scale, avail_h_in)

    _draw_gridlines(axes, model, left_in, right_in, bounds["grid_top"], bounds["grid_bottom"], scale)
    if has_ms:
        _draw_milestones(axes, model, left_in, right_in, bounds["grid_top"], bounds["grid_bottom"],
                         bounds["ms_y"] - 0.05 * scale, scale)
    _draw_legend(axes, _activity_legend(model, accent), bounds["legend_y"] - 0.06 * scale,
                CONTENT_LEFT_IN, scale)

    for artist, max_frac in labels:
        _fit_label(figure, artist, max_frac, artist.get_fontsize())
    return figure


# --- B. Stage swimlanes ----------------------------------------------------

def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


_SWIM_LANE_HEADER_H_REF = 0.34
_SWIM_ROW_H_REF = 0.62
_SWIM_GAP_REF = 0.10
_SWIM_LABEL_COL_REF_IN = 2.5
_SWIM_HEADER_H_REF = 0.46
_SWIM_MILESTONE_H_REF = 0.42
_SWIM_LEGEND_H_REF = 0.34


def _render_swimlanes(model: ProgramModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)
    from matplotlib.patches import Rectangle

    grouped: list[tuple[int | None, list[ProgramItem]]] = []
    for stage_index in list(range(len(model.stages))) + [None]:
        members = [i for i in model.items if i.stage_index == stage_index]
        if members:
            grouped.append((stage_index, members))

    total_rows = sum(len(m) for _, m in grouped)
    has_ms = bool(model.milestones)
    natural_h = (_SWIM_HEADER_H_REF + _SWIM_GAP_REF
                + len(grouped) * _SWIM_LANE_HEADER_H_REF + total_rows * _SWIM_ROW_H_REF
                + max(0, len(grouped) - 1) * _SWIM_GAP_REF
                + _SWIM_GAP_REF
                + (_SWIM_MILESTONE_H_REF + _SWIM_GAP_REF if has_ms else 0.0)
                + _SWIM_LEGEND_H_REF)
    scale, total_h_in, avail_h_in = _fit_height(natural_h)

    figure, axes = _new_page(total_h_in)
    _draw_title(axes, model, total_h_in)

    label_col_w = _SWIM_LABEL_COL_REF_IN * scale
    left_in = CONTENT_LEFT_IN + label_col_w
    right_in = CONTENT_RIGHT_IN
    content_top_in = total_h_in - _MARGIN_IN - _TITLE_BAND_IN

    _, week_w_in = _week_geometry(model, left_in, right_in)
    labels: list[tuple[object, float]] = []
    bounds: dict[str, float] = {}
    flow = _VFlow()

    def draw_header(y_top, y_bottom, scale):
        _draw_week_header(axes, model, left_in, right_in, y_top, scale)
        bounds["grid_top"] = y_bottom
    flow.block(_SWIM_HEADER_H_REF, draw_header)
    flow.gap(_SWIM_GAP_REF)

    for lane_index, (stage_index, members) in enumerate(grouped):
        colour = (STAGE_COLOURS[stage_index % len(STAGE_COLOURS)]
                  if stage_index is not None else MUTED)

        def draw_lane_header(y_top, y_bottom, scale, stage_index=stage_index, colour=colour,
                             members=members):
            # ~5% tint of the stage colour: enough to group the rows, never
            # enough to fight the bars sitting on it. The tint spans the
            # WHOLE lane (header + its member rows), so it's drawn using the
            # member-row count even though this callback only owns the
            # header's own band.
            member_h = (y_top - y_bottom) + len(members) * (_SWIM_ROW_H_REF * scale)
            rgb = _hex_to_rgb(colour)
            tint = tuple(c + (1 - c) * 0.95 for c in rgb)
            axes.add_patch(Rectangle((CONTENT_LEFT_IN, y_top - member_h), right_in - CONTENT_LEFT_IN,
                                     member_h, facecolor=tint, linewidth=0, zorder=0))
            name = (model.stages[stage_index] if stage_index is not None else "Unassigned").upper()
            pt = max(_LANE_PT_MIN, _LANE_PT_REF * scale)
            axes.text(CONTENT_LEFT_IN + 0.05 * scale, (y_top + y_bottom) / 2, name, fontsize=pt,
                     fontweight="bold", color=colour, ha="left", va="center")
            labels.append((axes.texts[-1], _fw(right_in - CONTENT_LEFT_IN - 0.10 * scale)))
        flow.block(_SWIM_LANE_HEADER_H_REF, draw_lane_header)

        for item in members:
            def draw_row(y_top, y_bottom, scale, item=item, colour=colour):
                centre_y = (y_top + y_bottom) / 2
                pt = max(_ROW_LABEL_PT_MIN, _ROW_LABEL_PT_REF * 0.92 * scale)
                axes.text(CONTENT_LEFT_IN + 0.10 * scale, centre_y, item.label, fontsize=pt,
                         fontweight="bold", color=INK, ha="left", va="center")
                labels.append((axes.texts[-1], _fw(label_col_w - 0.24 * scale)))
                x0 = left_in + (item.start_week - 1) * week_w_in
                x1 = left_in + item.end_week * week_w_in
                bar_h = (y_top - y_bottom) * 0.48
                bar_pt = max(_BAR_LABEL_PT_MIN, _BAR_LABEL_PT_REF * scale)
                _rounded_bar(axes, x0 + 0.02 * scale, x1 - 0.02 * scale, centre_y, bar_h, colour,
                            f"{item.weeks} wk", fontsize=bar_pt)
                labels.append((axes.texts[-1], _fw(max(0.05, x1 - x0 - 0.06 * scale))))
                bounds["grid_bottom"] = y_bottom
            flow.block(_SWIM_ROW_H_REF, draw_row)

        if lane_index < len(grouped) - 1:
            flow.gap(_SWIM_GAP_REF)

    flow.gap(_SWIM_GAP_REF)

    if has_ms:
        def draw_ms_anchor(y_top, y_bottom, scale):
            bounds["ms_y"] = y_top
        flow.block(_SWIM_MILESTONE_H_REF, draw_ms_anchor)
        flow.gap(_SWIM_GAP_REF)

    def draw_legend_anchor(y_top, y_bottom, scale):
        bounds["legend_y"] = y_top
    flow.block(_SWIM_LEGEND_H_REF, draw_legend_anchor)

    flow.render(content_top_in, scale, avail_h_in)

    _draw_gridlines(axes, model, left_in, right_in, bounds["grid_top"], bounds["grid_bottom"], scale)
    if has_ms:
        _draw_milestones(axes, model, left_in, right_in, bounds["grid_top"], bounds["grid_bottom"],
                         bounds["ms_y"] - 0.05 * scale, scale)
    legend = [(STAGE_COLOURS[i % len(STAGE_COLOURS)], name)
              for i, name in enumerate(model.stages)]
    if has_ms:
        legend.append((MILESTONE_ORANGE, "Milestone"))
    _draw_legend(axes, legend, bounds["legend_y"] - 0.06 * scale, CONTENT_LEFT_IN, scale)

    for artist, max_frac in labels:
        _fit_label(figure, artist, max_frac, artist.get_fontsize())
    return figure


# --- C. Formal table --------------------------------------------------------

_TABLE_HEADER_H_REF = 0.40
_TABLE_ROW_H_REF = 0.56
_TABLE_ROW_H_MAX_IN = 1.35     # "comfortable maximum" -- a 5-row table
                                # shouldn't grow rows past this even on an
                                # otherwise-empty page.
_TABLE_GAP_REF = 0.16
_TABLE_LEGEND_H_REF = 0.32
_TABLE_COLUMNS_FRAC = (0.0, 0.40, 0.52, 0.63, 0.73)   # fractions of AVAIL_W_IN


def _render_table(model: ProgramModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)

    n = len(model.items)
    # Fit the header/legend chrome the normal way -- at the table's natural
    # size with rows at their reference height -- purely to size fonts and
    # find the scale for everything except the rows themselves. Row height
    # is NOT a straight scale multiply: per the brief it's "distribute
    # across the available height, up to a comfortable maximum", so it's
    # computed below as whatever is left after the chrome, divided across
    # the rows and capped -- otherwise a short table (few rows, generous
    # MAX_SCALE headroom) leaves its leftover stranded in the header gap
    # instead of in the rows the brief is actually asking to grow.
    natural_h = (_TABLE_HEADER_H_REF + _TABLE_GAP_REF
                + n * _TABLE_ROW_H_REF + _TABLE_GAP_REF + _TABLE_LEGEND_H_REF)
    scale, total_h_in, avail_h_in = _fit_height(natural_h)

    header_h = _TABLE_HEADER_H_REF * scale
    gap_h = _TABLE_GAP_REF * scale
    legend_h = _TABLE_LEGEND_H_REF * scale
    chrome_h = header_h + gap_h * 2 + legend_h
    remaining_for_rows = max(0.0, avail_h_in - chrome_h)
    row_h = min(_TABLE_ROW_H_MAX_IN, remaining_for_rows / n) if n else 0.0

    figure, axes = _new_page(total_h_in)
    _draw_title(axes, model, total_h_in)
    content_top_in = total_h_in - _MARGIN_IN - _TITLE_BAND_IN

    columns = [CONTENT_LEFT_IN + f * AVAIL_W_IN for f in _TABLE_COLUMNS_FRAC]
    right_in = CONTENT_RIGHT_IN

    def _week_text(week: int) -> str:
        label = model.week_labels[week - 1] if week - 1 < len(model.week_labels) else f"Wk {week}"
        date_text = model.week_dates[week - 1] if week - 1 < len(model.week_dates) else ""
        return f"{label} · {date_text}" if date_text else label

    name_labels: list[tuple[object, float]] = []
    bounds: dict[str, float] = {}
    flow = _VFlow()

    def draw_header(y_top, y_bottom, scale):
        head_pt = max(6.5, 9.0 * scale)
        for label, x in zip(["SCOPE ITEM", "COMMENCE", "COMPLETE", "DURATION", "TIMELINE"], columns):
            axes.text(x, y_top, label, fontsize=head_pt, fontweight="bold", color=MUTED,
                     ha="left", va="top")
        rule_y = y_bottom + (y_top - y_bottom) * 0.12
        axes.plot([CONTENT_LEFT_IN, right_in], [rule_y, rule_y], color="#333A45",
                 linewidth=max(0.8, 1.0 * scale))
        bounds["rule_y"] = rule_y
    flow.block(_TABLE_HEADER_H_REF, draw_header)
    flow.gap(_TABLE_GAP_REF)

    # Rows are a FIXED (not scale-multiplied) height -- see _TABLE_ROW_H_MAX_IN
    # above -- computed once outside the flow, so a 3-row table on an
    # otherwise-empty page gets generous rows without them ballooning past a
    # size that still reads as a table rather than a poster.
    for item in model.items:
        def draw_row(y_top, y_bottom, scale, item=item):
            centre_y = (y_top + y_bottom) / 2
            name_pt = max(_ROW_LABEL_PT_MIN, _ROW_LABEL_PT_REF * scale)
            cell_pt = max(6.0, 9.0 * scale)
            axes.text(columns[0], centre_y, item.label, fontsize=name_pt, fontweight="bold",
                     color=INK, ha="left", va="center")
            name_labels.append((axes.texts[-1], _fw(columns[1] - columns[0] - 0.08)))
            axes.text(columns[1], centre_y, _week_text(item.start_week), fontsize=cell_pt,
                     color="#3C4657", ha="left", va="center")
            axes.text(columns[2], centre_y, _week_text(item.end_week), fontsize=cell_pt,
                     color="#3C4657", ha="left", va="center")
            axes.text(columns[3], centre_y, f"{item.weeks} week{'s' if item.weeks != 1 else ''}",
                     fontsize=cell_pt, color="#3C4657", ha="left", va="center")
            track_l, track_r = columns[4], right_in
            track_h = max(0.09, 0.11 * scale)
            _rounded_bar(axes, track_l, track_r, centre_y, track_h, TRACK_GREY)
            span = max(1, model.week_count)
            unit = (track_r - track_l) / span
            _rounded_bar(axes, track_l + (item.start_week - 1) * unit,
                        track_l + item.end_week * unit, centre_y, track_h, accent)
            axes.plot([CONTENT_LEFT_IN, right_in], [y_bottom, y_bottom], color=GRIDLINE,
                     linewidth=max(0.5, 0.7 * scale))
        flow.fixed(row_h, draw_row)

    # A second stretch point after the rows: ordinarily row_h already
    # consumed all of remaining_for_rows and both this gap and the one
    # above the rows stay at their small reference size. It only grows when
    # row_h hit _TABLE_ROW_H_MAX_IN (very few rows on a big page) -- at that
    # point the table is already at its most generous row height, and the
    # true leftover splits evenly above and below the rows rather than
    # piling into the header gap alone.
    flow.gap(_TABLE_GAP_REF)

    def draw_legend_anchor(y_top, y_bottom, scale):
        bounds["legend_y"] = y_top
    flow.block(_TABLE_LEGEND_H_REF, draw_legend_anchor)

    flow.render(content_top_in, scale, avail_h_in)

    legend_y = bounds["legend_y"] - 0.06 * scale
    _draw_legend(axes, [(accent, "Scheduled duration")], legend_y, CONTENT_LEFT_IN, scale)
    if model.start_date_text:
        axes.text(CONTENT_LEFT_IN + 2.2 * scale, legend_y,
                 f"Program anchored to an anticipated commencement of {model.start_date_text} "
                 f"— dates shift with the actual award date.",
                 fontsize=max(6.0, 8.0 * scale), fontweight="bold", color="#B6BCC7",
                 ha="left", va="center")

    for artist, max_frac in name_labels:
        _fit_label(figure, artist, max_frac, artist.get_fontsize())
    return figure


# --- D. Modern timeline ------------------------------------------------------

_TL_HEADER_H_REF = 0.36
_TL_ROW_H_REF = 0.80
_TL_GAP_REF = 0.14
_TL_MONTH_BAND_H_REF = 0.30
_TL_MILESTONE_H_REF = 0.42
_TL_LEGEND_H_REF = 0.34


def _render_timeline(model: ProgramModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)

    n = len(model.items)
    has_ms = bool(model.milestones)
    has_bands = bool(model.month_bands)
    natural_h = ((_TL_MONTH_BAND_H_REF if has_bands else 0.0)
                + _TL_HEADER_H_REF + _TL_GAP_REF
                + n * _TL_ROW_H_REF + _TL_GAP_REF
                + (_TL_MILESTONE_H_REF + _TL_GAP_REF if has_ms else 0.0)
                + _TL_LEGEND_H_REF)
    scale, total_h_in, avail_h_in = _fit_height(natural_h)

    figure, axes = _new_page(total_h_in)
    _draw_title(axes, model, total_h_in)

    left_in = CONTENT_LEFT_IN
    right_in = CONTENT_RIGHT_IN
    content_top_in = total_h_in - _MARGIN_IN - _TITLE_BAND_IN

    _, week_w_in = _week_geometry(model, left_in, right_in)
    labels: list[tuple[object, float]] = []
    bounds: dict[str, float] = {}
    flow = _VFlow()

    if has_bands:
        def draw_bands(y_top, y_bottom, scale):
            band_h = (y_top - y_bottom) * 0.72
            band_y = y_top - band_h
            pt = max(6.0, 8.5 * scale)
            for name, first, last in model.month_bands:
                x0 = left_in + (first - 1) * week_w_in
                x1 = left_in + last * week_w_in
                from matplotlib.patches import Rectangle
                axes.add_patch(Rectangle((x0 + 0.02, band_y), x1 - x0 - 0.04, band_h,
                                         facecolor="#EEF3FE", linewidth=0))
                axes.text((x0 + x1) / 2, band_y + band_h / 2, name, fontsize=pt, fontweight="bold",
                         color=BAR_BLUE, ha="center", va="center")
        flow.block(_TL_MONTH_BAND_H_REF, draw_bands)

    def draw_header(y_top, y_bottom, scale):
        _draw_week_header(axes, model, left_in, right_in, y_top, scale, show_dates=False)
        bounds["grid_top"] = y_bottom
    flow.block(_TL_HEADER_H_REF, draw_header)
    flow.gap(_TL_GAP_REF)

    for index, item in enumerate(model.items):
        def draw_row(y_top, y_bottom, scale, item=item):
            centre_y = (y_top + y_bottom) / 2
            x0 = left_in + (item.start_week - 1) * week_w_in
            x1 = left_in + item.end_week * week_w_in
            bar_h = (y_top - y_bottom) * 0.60
            pt = max(_BAR_LABEL_PT_MIN, _BAR_LABEL_PT_REF * scale + 0.5)
            _rounded_bar(axes, x0 + 0.02 * scale, x1 - 0.02 * scale, centre_y, bar_h, accent,
                        item.label or "[UNTITLED SCOPE ITEM]", fontsize=pt, label_align="left",
                        shadow=True)
            # The label lives INSIDE its bar, so it has to fit that bar --
            # reserve the left inset the label starts at (height * 0.55) plus
            # the rounded cap at the far end (height / 2).
            labels.append((axes.texts[-1], _fw(max(0.05, (x1 - x0) - bar_h * 1.05))))
            bounds["grid_bottom"] = y_bottom
        flow.block(_TL_ROW_H_REF, draw_row)

    flow.gap(_TL_GAP_REF)

    if has_ms:
        def draw_ms_anchor(y_top, y_bottom, scale):
            bounds["ms_y"] = y_top
        flow.block(_TL_MILESTONE_H_REF, draw_ms_anchor)
        flow.gap(_TL_GAP_REF)

    def draw_legend_anchor(y_top, y_bottom, scale):
        bounds["legend_y"] = y_top
    flow.block(_TL_LEGEND_H_REF, draw_legend_anchor)

    flow.render(content_top_in, scale, avail_h_in)

    _draw_gridlines(axes, model, left_in, right_in, bounds["grid_top"], bounds["grid_bottom"], scale)
    if has_ms:
        _draw_milestones(axes, model, left_in, right_in, bounds["grid_top"], bounds["grid_bottom"],
                         bounds["ms_y"] - 0.05 * scale, scale)
    _draw_legend(axes, _activity_legend(model, accent), bounds["legend_y"] - 0.06 * scale,
                CONTENT_LEFT_IN, scale)

    for artist, max_frac in labels:
        _fit_label(figure, artist, max_frac, artist.get_fontsize())
    return figure
