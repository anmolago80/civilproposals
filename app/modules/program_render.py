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

EMPTY_NOTE = ("[NO PROGRAM ENTERED -- build the delivery program in the Fees & Program tab, "
              "then re-generate this]")


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
        fig.savefig(buffer, format="png", dpi=170, bbox_inches="tight",
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

# Inches of figure per 1.0 of vertical data space. Fixed so that bar
# heights, text sizes and gaps stay identical whatever the row count -- the
# figure grows, the drawing does not rescale.
_V_SCALE = 8.0
_TOP = 1.06


def _new_figure(width: float, height: float):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    return fig, ax


def _finalise(fig, ax, lowest: float, width: float = 11.0):
    """Crop the canvas to the content and size the figure to match.

    Without this every style rendered into a fixed-height box and left a
    band of empty white below the legend -- which looks like a mistake in a
    proposal, and wastes a third of the page it is pasted onto."""
    lowest = min(lowest, _TOP - 0.12)
    ax.set_ylim(lowest, _TOP)
    fig.set_size_inches(width, max(1.6, (_TOP - lowest) * _V_SCALE))
    return fig


def _rounded_bar(ax, x0: float, x1: float, y: float, height: float, colour: str,
                 label: str = "", label_colour: str = "white", fontsize: float = 6.5,
                 label_align: str = "center", shadow: bool = False):
    """A fully-rounded pill. Radius is half the height, which is what makes
    the ends read as round rather than as a rounded rectangle."""
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
    compared with is an x-coordinate in the axes' own 0..1 space. The axes
    does not fill the figure (matplotlib's default subplot margins leave
    roughly a quarter of it outside), so measuring against the figure made
    every label look about a quarter narrower than it really was -- which
    is exactly how labels still ran off the end of their bars after the
    fitting pass was added.
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


def _header_step(week_w: float) -> int:
    """Label every Nth week, where N is the smallest number that stops the
    headers touching.

    A 14-week program labels every week. A 40-week one cannot -- at that
    density "Wk 9Wk 10Wk 11" ran together into an unreadable smear. The
    gridlines still mark every week, so nothing is lost: only the labels
    thin out, exactly as a printed program's would.
    """
    import math
    return max(1, math.ceil(_HEADER_MIN_PITCH / max(week_w, 1e-6)))


# The narrowest a "Wk NN" header can sit next to its neighbour, as a fraction
# of the axes width, before the two touch. Measured from the rendered text at
# the header font size rather than guessed.
_HEADER_MIN_PITCH = 0.045


def _header_indices(model: ProgramModel, week_w: float) -> list[int]:
    """Which week indices get a header label. Always the first and the last,
    then every Nth in between -- and never the second-to-last kept one when
    it would crowd the final week."""
    count = len(model.week_labels)
    if count <= 1:
        return list(range(count))
    step = _header_step(week_w)
    kept = list(range(0, count, step))
    last = count - 1
    if kept[-1] != last:
        while kept and last - kept[-1] < step:
            kept.pop()
        kept.append(last)
    return kept


def _draw_week_header(ax, model: ProgramModel, left: float, right: float, y: float,
                      show_dates: bool = True):
    _, week_w = _week_geometry(model, left, right)
    for index in _header_indices(model, week_w):
        label = model.week_labels[index]
        centre = left + (index + 0.5) * week_w
        ax.text(centre, y, label, fontsize=6.4, fontweight="bold", color=INK,
                ha="center", va="bottom")
        date_text = model.week_dates[index] if index < len(model.week_dates) else ""
        if show_dates and date_text:
            ax.text(centre, y - 0.022, date_text, fontsize=5.6, color=MUTED,
                    ha="center", va="top")


def _draw_gridlines(ax, model: ProgramModel, left: float, right: float,
                    top: float, bottom: float):
    _, week_w = _week_geometry(model, left, right)
    for index in range(model.week_count + 1):
        x = left + index * week_w
        ax.plot([x, x], [bottom, top], color=GRIDLINE, linewidth=0.7, zorder=0)


def _draw_milestones(ax, model: ProgramModel, left: float, right: float,
                     top: float, bottom: float, label_y: float):
    _, week_w = _week_geometry(model, left, right)
    seen = set()
    for milestone in model.milestones:
        if milestone.week in seen:
            continue
        seen.add(milestone.week)
        x = left + milestone.week * week_w
        ax.plot([x, x], [bottom, top], color=MILESTONE_ORANGE, linewidth=0.8,
                alpha=0.55, zorder=1)
        ax.plot([x], [bottom], marker="D", markersize=5.5, color=MILESTONE_ORANGE, zorder=3)
        # A milestone on the final week sits on the right edge, where a
        # centred label runs off the canvas -- anchor those to the edge
        # instead.
        align = "center"
        if x > right - 0.06:
            align = "right"
        elif x < left + 0.06:
            align = "left"
        ax.text(x, label_y, milestone.label, fontsize=5.8, fontweight="bold",
                color=MILESTONE_ORANGE, ha=align, va="top")


def _draw_title(ax, model: ProgramModel, subtitle: str = ""):
    ax.text(0.0, 1.0, "Delivery program", fontsize=15, fontweight="bold",
            color="#111827", ha="left", va="top")
    if subtitle:
        ax.text(0.0, 0.955, subtitle, fontsize=6.6, color=MUTED, ha="left", va="top")
    heading = " — ".join(p for p in (model.project_name, model.client_name) if p)
    if heading:
        ax.text(1.0, 1.0, heading, fontsize=8.2, fontweight="bold", color="#6B7280",
                ha="right", va="top")


def _draw_legend(ax, entries: list[tuple[str, str]], y: float, x: float = 0.0):
    """entries: [(colour, label)] -- a swatch row. The milestone entry draws
    a diamond rather than a square so it matches the marks on the chart."""
    from matplotlib.patches import Rectangle
    cursor = x
    for colour, label in entries:
        if label.lower().startswith("milestone"):
            ax.plot([cursor + 0.006], [y], marker="D", markersize=5,
                    color=MILESTONE_ORANGE)
        else:
            ax.add_patch(Rectangle((cursor, y - 0.008), 0.012, 0.016,
                                   facecolor=colour, linewidth=0))
        ax.text(cursor + 0.018, y, label, fontsize=6.2, fontweight="bold",
                color=INK, ha="left", va="center")
        cursor += 0.022 + 0.009 * len(label)


def _empty_figure(model: ProgramModel):
    fig, ax = _new_figure(11.0, 3.0)
    _draw_title(ax, model)
    # Sits just under the title rather than mid-canvas: a placeholder that
    # floats in a half-page of white reads as a broken image, which is the
    # opposite of the point -- it has to read as a note to the writer.
    ax.text(0.5, 0.88, EMPTY_NOTE, fontsize=8, color="#C00000", style="italic",
            ha="center", va="center", wrap=True)
    return _finalise(fig, ax, 0.82)


# --- A. Refined Gantt ------------------------------------------------------

def _render_gantt(model: ProgramModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)
    from matplotlib.patches import Rectangle

    rows = len(model.items)
    fig, ax = _new_figure(11.0, max(3.2, 1.9 + 0.42 * rows))

    left, right = 0.28, 1.0
    top, bottom = 0.86, 0.86 - 0.055 * rows
    _draw_title(ax, model)
    _draw_week_header(ax, model, left, right, top + 0.035)
    _draw_gridlines(ax, model, left, right, top, bottom)
    _, week_w = _week_geometry(model, left, right)

    # Row labels sit in the left margin (0 -> `left`); the "N wk" pill labels
    # sit inside their bar. Both can outrun their space on a real project --
    # a long activity name, or a one-week bar -- so each is measured against
    # the width it actually has and fitted after the figure is finalised.
    labels: list[tuple[object, float]] = []
    for index, item in enumerate(model.items):
        y = top - 0.055 * (index + 0.5)
        if index % 2 == 1:
            ax.add_patch(Rectangle((0.0, y - 0.0275), right, 0.055,
                                   facecolor=ROW_BAND, linewidth=0, zorder=0))
        ax.text(0.0, y, item.label, fontsize=6.8, fontweight="bold", color=INK,
                ha="left", va="center")
        labels.append((ax.texts[-1], left - 0.02))
        x0 = left + (item.start_week - 1) * week_w
        x1 = left + item.end_week * week_w
        _rounded_bar(ax, x0 + 0.002, x1 - 0.002, y, 0.030, accent, f"{item.weeks} wk")
        labels.append((ax.texts[-1], max(0.02, (x1 - x0) - 0.034)))

    _draw_milestones(ax, model, left, right, top, bottom, bottom - 0.022)
    legend_y = bottom - (0.10 if model.milestones else 0.05)
    _draw_legend(ax, [(accent, "Scheduled activity"), (MILESTONE_ORANGE, "Milestone / hold point")],
                 legend_y)
    figure = _finalise(fig, ax, legend_y - 0.03)
    for artist, max_frac in labels:
        _fit_label(figure, artist, max_frac, artist.get_fontsize())
    return figure


# --- B. Stage swimlanes ----------------------------------------------------

def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


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
    lane_header_h, row_h = 0.030, 0.050
    fig, ax = _new_figure(11.0, max(3.4, 2.0 + 0.40 * total_rows + 0.22 * len(grouped)))

    left, right = 0.28, 1.0
    top = 0.86
    _draw_title(ax, model)
    _draw_week_header(ax, model, left, right, top + 0.035)
    _, week_w = _week_geometry(model, left, right)

    y = top
    # Lane names and row names both live in the left margin, and the bar
    # labels inside their pill -- all three get measured and fitted once the
    # figure has been cropped to its final size.
    labels: list[tuple[object, float]] = []
    for stage_index, members in grouped:
        colour = (STAGE_COLOURS[stage_index % len(STAGE_COLOURS)]
                  if stage_index is not None else MUTED)
        lane_h = lane_header_h + row_h * len(members)
        # ~5% tint of the stage colour: enough to group the rows, never
        # enough to fight the bars sitting on it.
        rgb = _hex_to_rgb(colour)
        tint = tuple(c + (1 - c) * 0.95 for c in rgb)
        ax.add_patch(Rectangle((0.0, y - lane_h), right, lane_h,
                               facecolor=tint, linewidth=0, zorder=0))
        name = (model.stages[stage_index] if stage_index is not None else "Unassigned").upper()
        ax.text(0.012, y - lane_header_h * 0.62, name, fontsize=6.2, fontweight="bold",
                color=colour, ha="left", va="center")
        labels.append((ax.texts[-1], right - 0.024))
        row_y = y - lane_header_h
        for item in members:
            centre = row_y - row_h / 2
            ax.text(0.024, centre, item.label, fontsize=6.6, fontweight="bold",
                    color=INK, ha="left", va="center")
            labels.append((ax.texts[-1], left - 0.040))
            x0 = left + (item.start_week - 1) * week_w
            x1 = left + item.end_week * week_w
            _rounded_bar(ax, x0 + 0.002, x1 - 0.002, centre, 0.030, colour, f"{item.weeks} wk")
            labels.append((ax.texts[-1], max(0.02, (x1 - x0) - 0.034)))
            row_y -= row_h
        y -= lane_h

    _draw_gridlines(ax, model, left, right, top, y)
    _draw_milestones(ax, model, left, right, top, y, y - 0.022)
    legend = [(STAGE_COLOURS[i % len(STAGE_COLOURS)], name)
              for i, name in enumerate(model.stages)]
    legend.append((MILESTONE_ORANGE, "Milestone"))
    legend_y = y - (0.10 if model.milestones else 0.05)
    _draw_legend(ax, legend, legend_y)
    figure = _finalise(fig, ax, legend_y - 0.03)
    for artist, max_frac in labels:
        _fit_label(figure, artist, max_frac, artist.get_fontsize())
    return figure


# --- C. Formal table -------------------------------------------------------

def _render_table(model: ProgramModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)

    rows = len(model.items)
    fig, ax = _new_figure(11.0, max(3.0, 1.9 + 0.34 * rows))
    _draw_title(ax, model)

    columns = [0.0, 0.36, 0.47, 0.58, 0.66]
    top = 0.86
    row_h = 0.045

    for label, x in zip(["SCOPE ITEM", "COMMENCE", "COMPLETE", "DURATION", "TIMELINE"], columns):
        ax.text(x, top, label, fontsize=6.2, fontweight="bold", color=MUTED,
                ha="left", va="bottom")
    ax.plot([0.0, 1.0], [top - 0.012, top - 0.012], color="#333A45", linewidth=1.0)

    def _week_text(week: int) -> str:
        label = model.week_labels[week - 1] if week - 1 < len(model.week_labels) else f"Wk {week}"
        date_text = model.week_dates[week - 1] if week - 1 < len(model.week_dates) else ""
        return f"{label} · {date_text}" if date_text else label

    y = top - 0.012
    # The scope-item column is the only one that can hold an arbitrarily long
    # string, and it is a real column here rather than a margin -- an
    # unfitted name runs straight through COMMENCE and COMPLETE.
    name_labels: list[tuple[object, float]] = []
    for item in model.items:
        y -= row_h
        centre = y + row_h / 2
        ax.text(columns[0], centre, item.label, fontsize=6.8, fontweight="bold",
                color=INK, ha="left", va="center")
        name_labels.append((ax.texts[-1], columns[1] - columns[0] - 0.015))
        ax.text(columns[1], centre, _week_text(item.start_week), fontsize=6.4,
                color="#3C4657", ha="left", va="center")
        ax.text(columns[2], centre, _week_text(item.end_week), fontsize=6.4,
                color="#3C4657", ha="left", va="center")
        ax.text(columns[3], centre, f"{item.weeks} week{'s' if item.weeks != 1 else ''}",
                fontsize=6.4, color="#3C4657", ha="left", va="center")
        track_l, track_r = columns[4], 1.0
        _rounded_bar(ax, track_l, track_r, centre, 0.018, TRACK_GREY)
        span = max(1, model.week_count)
        unit = (track_r - track_l) / span
        _rounded_bar(ax, track_l + (item.start_week - 1) * unit,
                     track_l + item.end_week * unit, centre, 0.018, accent)
        ax.plot([0.0, 1.0], [y, y], color=GRIDLINE, linewidth=0.7)

    legend_y = y - 0.05
    _draw_legend(ax, [(accent, "Scheduled duration")], legend_y)
    if model.start_date_text:
        ax.text(0.20, legend_y,
                f"Program anchored to an anticipated commencement of {model.start_date_text} "
                f"— dates shift with the actual award date.",
                fontsize=6.0, fontweight="bold", color="#B6BCC7", ha="left", va="center")
    figure = _finalise(fig, ax, legend_y - 0.03)
    for artist, max_frac in name_labels:
        _fit_label(figure, artist, max_frac, artist.get_fontsize())
    return figure


# --- D. Modern timeline ----------------------------------------------------

def _render_timeline(model: ProgramModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)
    from matplotlib.patches import Rectangle

    rows = len(model.items)
    fig, ax = _new_figure(11.0, max(3.4, 2.0 + 0.46 * rows))
    left, right = 0.0, 1.0
    _draw_title(ax, model)

    top = 0.86
    _, week_w = _week_geometry(model, left, right)

    # Month band row above the week numbers -- only where real dates gave us
    # months to band by.
    if model.month_bands:
        for name, first, last in model.month_bands:
            x0 = left + (first - 1) * week_w
            x1 = left + last * week_w
            ax.add_patch(Rectangle((x0 + 0.002, top + 0.045), x1 - x0 - 0.004, 0.030,
                                   facecolor="#EEF3FE", linewidth=0))
            ax.text((x0 + x1) / 2, top + 0.060, name, fontsize=6.2, fontweight="bold",
                    color=BAR_BLUE, ha="center", va="center")

    _draw_week_header(ax, model, left, right, top + 0.014, show_dates=False)
    bottom = top - 0.062 * rows
    _draw_gridlines(ax, model, left, right, top, bottom)

    labels = []
    for index, item in enumerate(model.items):
        y = top - 0.062 * (index + 0.5)
        x0 = left + (item.start_week - 1) * week_w
        x1 = left + item.end_week * week_w
        _rounded_bar(ax, x0 + 0.002, x1 - 0.002, y, 0.044, accent, item.label,
                     fontsize=6.6, label_align="left", shadow=True)
        # The label lives INSIDE its bar, so it has to fit that bar -- and
        # how wide the text really is can only be known from the renderer.
        # Reserve the left inset the label starts at (height * 0.55) plus
        # the rounded cap at the far end (height / 2) -- text drawn into
        # either of those sits on the pill's curve, not inside it.
        labels.append((ax.texts[-1], max(0.02, (x1 - x0) - 0.048)))

    _draw_milestones(ax, model, left, right, top, bottom, bottom - 0.022)
    legend_y = bottom - (0.10 if model.milestones else 0.05)
    _draw_legend(ax, [(accent, "Scheduled activity"), (MILESTONE_ORANGE, "Milestone / hold point")],
                 legend_y)
    figure = _finalise(fig, ax, legend_y - 0.03)
    for artist, max_frac in labels:
        _fit_label(figure, artist, max_frac, 6.6)
    return figure
