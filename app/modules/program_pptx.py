"""
program_pptx.py

Builds the delivery program as a standalone PowerPoint, straight from a
project's program_schedule + program_week_labels -- no template file to keep
in sync (same from-scratch approach as org_chart_pptx.py /
methodology_pptx.py, for the same reasons).

FOUR STYLES, ONE MODEL
----------------------
The program is drawn in whichever of the four presentation styles the user
picked (program_render.STYLES). The shapes here are built from the SAME
program_render.build_model() object the on-screen preview and the letter
pack render from, so the deck cannot show a different program from the one
the user approved -- which is exactly what happened while each output
derived its own view of the ticked weeks.

Everything is native PowerPoint shapes (and, for the formal-table style, a
real PowerPoint table), not a pasted picture: the whole point of the
companion deck is that it can be tidied up further in PowerPoint.

Every row and every bar comes straight from program_schedule.py's output or
the user's own edits to it (see the Fee Estimate tab's "Delivery program"
editor) -- nothing here is invented; an empty schedule renders an explicit
red placeholder slide instead of a blank grid, same no-invention convention
as the rest of this tool.
"""

from __future__ import annotations

import io
import math

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from modules import program_render
from modules.divider_designer import THEME_COLOURS

_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_DARK_TEXT = RGBColor(0x1A, 0x1A, 0x1A)
_LIGHT_GREY = RGBColor(0xD9, 0xD9, 0xD9)
_RED = RGBColor(0xC0, 0x00, 0x00)
_FONT = "Calibri"

_INK = RGBColor(0x1A, 0x22, 0x33)
_MUTED = RGBColor(0x7A, 0x85, 0x98)
_GRIDLINE = RGBColor(0xEE, 0xF1, 0xF4)
_ROW_BAND = RGBColor(0xF7, 0xF9, 0xFC)
_TRACK_GREY = RGBColor(0xED, 0xEF, 0xF2)
_MILESTONE_ORANGE = RGBColor(0xF9, 0x73, 0x16)

# A4 landscape -- same slide size as org_chart_pptx.py / methodology_pptx.py
_SLIDE_W = Inches(11.6929)
_SLIDE_H = Inches(8.2677)
_M = Inches(0.3)

# Below this a program row is too thin to read the scope item in; the slide
# grows rather than squeezing past it.
_MIN_ROW_H = Inches(0.3)

# Narrower than this and consecutive "Wk 12" headers touch, exactly as they
# did in the rendered preview -- so the labels thin out and the every-week
# gridlines carry the detail instead.
_MIN_HEADER_PITCH = Inches(0.42)

EMPTY_NOTE = ("[NO PROGRAM ENTERED -- build the delivery program in the Fee Estimate tab, then "
              "re-download this PowerPoint]")


def _resolve_palette(theme_name: str | None) -> dict:
    colours = THEME_COLOURS.get(theme_name, THEME_COLOURS["Corporate"])
    primary = RGBColor(*colours["primary"])
    accent = RGBColor(*colours["accent"])
    # Minimalist's "primary" is a light near-white wash by design -- same special
    # case export_docx._theme_colours() / methodology_pptx._resolve_palette() apply.
    dark_role = RGBColor(0x2A, 0x2A, 0x2A) if theme_name == "Minimalist" else primary
    return {"header_bg": dark_role, "active_bg": accent}


def _hex(value: str) -> RGBColor:
    return RGBColor.from_string(str(value).lstrip("#").upper())


def _tint(colour: RGBColor, towards_white: float) -> RGBColor:
    """`colour` mixed `towards_white` of the way to white -- the lane washes."""
    r, g, b = colour[0], colour[1], colour[2]
    mix = lambda c: int(round(c + (255 - c) * towards_white))  # noqa: E731
    return RGBColor(mix(r), mix(g), mix(b))


def _rect(slide, x, y, w, h, fill_color, line_color=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(0.5)
    else:
        shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


# Average glyph advance for bold Calibri over mixed-case text, as a fraction
# of the point size. An estimate, because there is no renderer here to
# measure with -- unlike the preview, which measures. Deliberately on the
# generous side: a label that shrinks half a point more than it had to is
# invisible, a label that runs out past the end of its bar is not.
_AVG_CHAR_EM = 0.50


def _fit_label(label: str, inner_pt: float, size_pt: float, lines: int = 1,
               min_pt: float = 7.0) -> tuple[str, float]:
    """Shrink a label to fit its shape, then ellipsize if it still will not.

    Shrinking first keeps the whole label readable; ellipsizing is the last
    resort, and an ellipsis is visibly an ellipsis rather than text that
    silently runs off the end of a bar."""
    capacity = max(1.0, inner_pt) * max(1, lines)
    while size_pt > min_pt and len(label) * _AVG_CHAR_EM * size_pt > capacity:
        size_pt -= 0.5
    max_chars = int(capacity / max(0.1, _AVG_CHAR_EM * size_pt))
    if len(label) > max_chars:
        label = label[:max(1, max_chars - 1)].rstrip() + "…"
    return label, size_pt


def _inner_points(width_emu: float, margin_pt: float = 6.0) -> float:
    return width_emu / 12700.0 - 2 * margin_pt


def _pill(slide, x, y, w, h, fill_color, label: str = "", size_pt: float = 9.0,
          align=PP_ALIGN.CENTER):
    """A fully-rounded bar. ROUNDED_RECTANGLE with its adjustment pushed to
    the maximum, which is what makes the ends read as round rather than as a
    rounded rectangle."""
    w = max(int(w), int(h))
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Emu(int(w)), h)
    try:
        shape.adjustments[0] = 0.5
    except (IndexError, KeyError):
        pass
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    shape.shadow.inherit = False
    if label:
        # The label lives INSIDE its bar, and a PowerPoint shape happily
        # paints text straight out past its own edge.
        label, size_pt = _fit_label(label, _inner_points(w), size_pt)
        frame = shape.text_frame
        frame.word_wrap = False
        frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        frame.margin_left = Pt(6)
        frame.margin_right = Pt(6)
        frame.margin_top = Pt(0)
        frame.margin_bottom = Pt(0)
        paragraph = frame.paragraphs[0]
        paragraph.alignment = align
        run = paragraph.add_run()
        run.text = label
        run.font.size = Pt(size_pt)
        run.font.bold = True
        run.font.name = _FONT
        run.font.color.rgb = _WHITE
    return shape


def _line(slide, x, y, w, h, colour):
    """A hairline drawn as a filled rect -- a connector would be one more
    shape type for the user to fight with when they edit the slide."""
    return _rect(slide, Emu(int(x)), Emu(int(y)), Emu(max(1, int(w))), Emu(max(1, int(h))), colour)


def _text(slide, x, y, w, h, text, size_pt, color, bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Pt(4)
    tf.margin_right = Pt(4)
    tf.margin_top = Pt(1)
    tf.margin_bottom = Pt(1)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.name = _FONT
    run.font.color.rgb = color
    return box


def _diamond(slide, cx, cy, size, colour):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.DIAMOND, Emu(int(cx - size / 2)), Emu(int(cy - size / 2)),
        Emu(int(size)), Emu(int(size)),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = colour
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _no_borders(cell) -> None:
    """Strip a table cell's four borders.

    python-pptx has no border API, so this writes the a:ln* children
    directly. Without it the "formal table" style arrives in PowerPoint
    wearing the default banded-blue table style -- which is precisely the
    look the formal-table option exists to avoid."""
    tc_pr = cell._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        for existing in tc_pr.findall(qn(tag)):
            tc_pr.remove(existing)
        element = tc_pr.makeelement(qn(tag), {"w": "0", "cap": "flat", "cmpd": "sng", "algn": "ctr"})
        element.append(element.makeelement(qn("a:noFill"), {}))
        tc_pr.insert(0, element)


# ---------------------------------------------------------------------------
# Shared slide furniture
# ---------------------------------------------------------------------------

def _new_deck():
    prs = Presentation()
    prs.slide_width = _SLIDE_W
    prs.slide_height = _SLIDE_H
    return prs, prs.slides.add_slide(prs.slide_layouts[6])


def _save(prs) -> bytes:
    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.read()


def _heading(slide, model) -> int:
    """Title + subtitle. Returns the y the content may start at."""
    title_h = Inches(0.5)
    _text(slide, _M, _M, Emu(int(_SLIDE_W - 2 * _M)), title_h, "Delivery program", 20,
          _DARK_TEXT, bold=True)
    subtitle = (model.project_name or "").strip() or "[Insert project name]"
    if (model.client_name or "").strip():
        subtitle = f"{subtitle} — {model.client_name.strip()}"
    _text(slide, _M, Emu(int(_M + title_h)), Emu(int(_SLIDE_W - 2 * _M)), Inches(0.3), subtitle, 11,
          _DARK_TEXT if (model.project_name or "").strip() else _RED)
    return int(_M + title_h + Inches(0.45))


def _grow(prs, needed_height: float) -> None:
    """Past roughly 15 scope items the rows stop fitting on a standard slide,
    and the minimum row height then pushed the surplus rows straight off the
    bottom edge -- silently, since PowerPoint happily stores shapes outside
    the slide and simply doesn't show them. Grow the slide instead, exactly
    as org_chart_pptx.py already does for wide charts: a taller slide is a
    normal thing to paste from, a program missing its last four scope items
    is not."""
    if int(needed_height) > int(prs.slide_height):
        prs.slide_height = Emu(int(needed_height))


def _header_step(week_col_w: float) -> int:
    return max(1, math.ceil(int(_MIN_HEADER_PITCH) / max(int(week_col_w), 1)))


def _header_indices(count: int, week_col_w: float) -> list[int]:
    if count <= 1:
        return list(range(count))
    step = _header_step(week_col_w)
    kept = list(range(0, count, step))
    last = count - 1
    if kept[-1] != last:
        while kept and last - kept[-1] < step:
            kept.pop()
        kept.append(last)
    return kept


def _week_header(slide, model, grid_left, grid_top, week_col_w, header_h, show_dates=True):
    for index in _header_indices(len(model.week_labels), week_col_w):
        cx = Emu(int(grid_left + index * week_col_w))
        _text(slide, cx, Emu(int(grid_top)), Emu(int(week_col_w)), Emu(int(header_h * 0.6)),
              model.week_labels[index], 9, _INK, bold=True, align=PP_ALIGN.CENTER)
        date_text = model.week_dates[index] if index < len(model.week_dates) else ""
        if show_dates and date_text:
            _text(slide, cx, Emu(int(grid_top + header_h * 0.55)), Emu(int(week_col_w)),
                  Emu(int(header_h * 0.45)), date_text, 7.5, _MUTED, align=PP_ALIGN.CENTER)


def _gridlines(slide, model, grid_left, grid_top, grid_bottom, week_col_w):
    for index in range(len(model.week_labels) + 1):
        _line(slide, grid_left + index * week_col_w, grid_top, Inches(0.008),
              grid_bottom - grid_top, _GRIDLINE)


def _milestones(slide, model, grid_left, grid_top, grid_bottom, week_col_w) -> int:
    """Diamonds on a faint vertical rule, labels underneath. Returns the y
    below the labels (== grid_bottom when there are no milestones -- and
    there are none unless the user's own inputs produced them)."""
    if not model.milestones:
        return int(grid_bottom)
    size = Inches(0.16)
    seen = set()
    for milestone in model.milestones:
        week = max(1, min(int(milestone.week), max(1, len(model.week_labels))))
        cx = grid_left + week * week_col_w
        if week in seen:
            continue
        seen.add(week)
        _line(slide, cx - Inches(0.004), grid_top, Inches(0.008), grid_bottom - grid_top,
              _tint(_MILESTONE_ORANGE, 0.45))
        _diamond(slide, cx, grid_bottom + size * 0.6, size, _MILESTONE_ORANGE)
        # A milestone in the last week sits on the slide's right edge, so a
        # centred label runs off it -- the label swings inboard instead.
        width = Inches(1.6)
        label_x, align = cx - width / 2, PP_ALIGN.CENTER
        if label_x + width > int(_SLIDE_W - _M):
            label_x, align = int(_SLIDE_W - _M) - width, PP_ALIGN.RIGHT
        elif label_x < int(_M):
            label_x, align = int(_M), PP_ALIGN.LEFT
        _text(slide, Emu(int(label_x)), Emu(int(grid_bottom + size * 1.25)),
              Emu(int(width)), Inches(0.22), milestone.label, 8, _MILESTONE_ORANGE,
              bold=True, align=align)
    return int(grid_bottom + size * 1.25 + Inches(0.22))


def _activity_legend(model, accent: RGBColor) -> list[tuple[RGBColor, str]]:
    """See program_render._activity_legend(): no key for a mark that isn't on
    the chart."""
    entries = [(accent, "Scheduled activity")]
    if model.milestones:
        entries.append((_MILESTONE_ORANGE, "Milestone / hold point"))
    return entries


def _legend(slide, entries: list[tuple[RGBColor, str]], y: int) -> None:
    cursor = int(_M)
    swatch = Inches(0.14)
    for colour, label in entries:
        # A diamond for the milestone key, so it matches the marks on the
        # chart -- it shares its orange with the third stage colour, and
        # shape is the only thing telling the two apart.
        if label.lower().startswith("milestone"):
            _diamond(slide, cursor + swatch / 2, y + Inches(0.03) + swatch / 2, swatch,
                     _MILESTONE_ORANGE)
        else:
            _rect(slide, Emu(cursor), Emu(int(y + Inches(0.03))), Emu(int(swatch)),
                  Emu(int(swatch)), colour)
        width = Inches(0.09) * max(6, len(label))
        _text(slide, Emu(int(cursor + swatch * 1.5)), Emu(int(y)), Emu(int(width)), Inches(0.2),
              label, 8.5, _INK, bold=True)
        cursor = int(cursor + swatch * 1.5 + width + Inches(0.15))


def _placeholder_slide(model) -> bytes:
    prs, slide = _new_deck()
    top = _heading(slide, model)
    _text(slide, _M, Emu(int(top + Inches(0.3))), Emu(int(_SLIDE_W - 2 * _M)), Inches(0.6),
          EMPTY_NOTE, 14, _RED, align=PP_ALIGN.CENTER)
    return _save(prs)


# ---------------------------------------------------------------------------
# A. Refined Gantt
# ---------------------------------------------------------------------------

def _slide_gantt(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    top = _heading(slide, model)

    label_col_w = Inches(3.0)
    grid_left = int(_M + label_col_w)
    grid_right = int(_SLIDE_W - _M)
    weeks = max(1, len(model.week_labels))
    week_col_w = (grid_right - grid_left) / weeks

    header_h = Inches(0.42)
    grid_top = int(top + header_h)
    row_h = max(int(_MIN_ROW_H), int(Inches(0.34)))
    grid_bottom = grid_top + row_h * len(model.items)

    _week_header(slide, model, grid_left, top, week_col_w, header_h)

    # Order matters, and only shows up once it is wrong: PowerPoint paints in
    # insertion order, so the row bands go down first, the week gridlines on
    # top of them, and the bars and labels last. Drawing the gridlines first
    # buried them under the bands; drawing them last ruled white lines
    # straight across every bar.
    for index in range(1, len(model.items), 2):
        _rect(slide, _M, Emu(int(grid_top + index * row_h)), Emu(int(grid_right - _M)),
              Emu(int(row_h)), _ROW_BAND)
    _gridlines(slide, model, grid_left, grid_top, grid_bottom, week_col_w)

    for index, item in enumerate(model.items):
        y = grid_top + index * row_h
        _text(slide, _M, Emu(int(y)), Emu(int(label_col_w)), Emu(int(row_h)),
              item.label or "[UNTITLED SCOPE ITEM]", 9.5, _INK, bold=True)
        x0 = grid_left + (item.start_week - 1) * week_col_w
        x1 = grid_left + item.end_week * week_col_w
        bar_h = int(row_h * 0.56)
        _pill(slide, Emu(int(x0 + Inches(0.02))), Emu(int(y + (row_h - bar_h) / 2)),
              x1 - x0 - Inches(0.04), Emu(bar_h), accent, f"{item.weeks} wk", 9.0)

    below = _milestones(slide, model, grid_left, grid_top, grid_bottom, week_col_w)
    _legend(slide, _activity_legend(model, accent), below + int(Inches(0.12)))
    _grow(prs, below + Inches(0.5))
    return _save(prs)


# ---------------------------------------------------------------------------
# B. Stage swimlanes
# ---------------------------------------------------------------------------

def _grouped_by_stage(model):
    grouped = []
    for stage_index in list(range(len(model.stages))) + [None]:
        members = [i for i in model.items if i.stage_index == stage_index]
        if members:
            grouped.append((stage_index, members))
    return grouped


def _slide_swimlanes(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    top = _heading(slide, model)

    label_col_w = Inches(3.0)
    grid_left = int(_M + label_col_w)
    grid_right = int(_SLIDE_W - _M)
    weeks = max(1, len(model.week_labels))
    week_col_w = (grid_right - grid_left) / weeks

    header_h = Inches(0.42)
    grid_top = int(top + header_h)
    lane_header_h = int(Inches(0.26))
    row_h = max(int(_MIN_ROW_H), int(Inches(0.34)))

    _week_header(slide, model, grid_left, top, week_col_w, header_h)

    # Laid out first, then drawn in three passes -- lane washes, gridlines,
    # then bars and labels. See the same note in _slide_gantt(): drawing the
    # gridlines after the bars rules white lines straight across them.
    lanes, y = [], grid_top
    for stage_index, members in _grouped_by_stage(model):
        colour = (_hex(program_render.STAGE_COLOURS[stage_index % len(program_render.STAGE_COLOURS)])
                  if stage_index is not None else _MUTED)
        lane_h = lane_header_h + row_h * len(members)
        lanes.append((stage_index, members, colour, y, lane_h))
        y += lane_h

    for stage_index, _members, colour, lane_y, lane_h in lanes:
        # ~5% tint: enough to group the rows, never enough to fight the bars
        # sitting on it.
        _rect(slide, _M, Emu(int(lane_y)), Emu(int(grid_right - _M)), Emu(int(lane_h)),
              _tint(colour, 0.95))
    _gridlines(slide, model, grid_left, grid_top, y, week_col_w)

    for stage_index, members, colour, lane_y, _lane_h in lanes:
        name = (model.stages[stage_index] if stage_index is not None else "Unassigned").upper()
        _text(slide, _M, Emu(int(lane_y)), Emu(int(grid_right - _M)), Emu(int(lane_header_h)),
              name, 8.5, colour, bold=True)
        row_y = lane_y + lane_header_h
        for item in members:
            _text(slide, Emu(int(_M + Inches(0.12))), Emu(int(row_y)),
                  Emu(int(label_col_w - Inches(0.12))), Emu(int(row_h)),
                  item.label or "[UNTITLED SCOPE ITEM]", 9.5, _INK, bold=True)
            x0 = grid_left + (item.start_week - 1) * week_col_w
            x1 = grid_left + item.end_week * week_col_w
            bar_h = int(row_h * 0.56)
            _pill(slide, Emu(int(x0 + Inches(0.02))), Emu(int(row_y + (row_h - bar_h) / 2)),
                  x1 - x0 - Inches(0.04), Emu(bar_h), colour, f"{item.weeks} wk", 9.0)
            row_y += row_h
    below = _milestones(slide, model, grid_left, grid_top, y, week_col_w)
    legend = [(_hex(program_render.STAGE_COLOURS[i % len(program_render.STAGE_COLOURS)]), name)
              for i, name in enumerate(model.stages)]
    if model.milestones:
        legend.append((_MILESTONE_ORANGE, "Milestone"))
    _legend(slide, legend, below + int(Inches(0.12)))
    _grow(prs, below + Inches(0.5))
    return _save(prs)


# ---------------------------------------------------------------------------
# C. Formal table -- a real PowerPoint table, so it stays editable
# ---------------------------------------------------------------------------

def _slide_table(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    top = _heading(slide, model)

    headers = ["Scope item", "Commence", "Complete", "Duration"]
    widths = [Inches(5.0), Inches(2.1), Inches(2.1), Inches(1.89)]
    rows = len(model.items) + 1
    row_h = max(int(_MIN_ROW_H), int(Inches(0.32)))

    shape = slide.shapes.add_table(
        rows, len(headers), _M, Emu(int(top)), Emu(int(sum(int(w) for w in widths))),
        Emu(int(row_h * rows)),
    )
    table = shape.table
    # No banded fills, no first-row emphasis: the styling below is the whole
    # look, and PowerPoint's default table style would otherwise paint over it.
    table.first_row = False
    table.horz_banding = False
    for index, width in enumerate(widths):
        table.columns[index].width = Emu(int(width))
    for index in range(rows):
        table.rows[index].height = Emu(int(row_h))

    def _fill(cell, colour, text, size, font_colour, bold=False):
        cell.fill.solid()
        cell.fill.fore_color.rgb = colour
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = Pt(6)
        cell.margin_right = Pt(6)
        cell.margin_top = Pt(2)
        cell.margin_bottom = Pt(2)
        paragraph = cell.text_frame.paragraphs[0]
        run = paragraph.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = _FONT
        run.font.color.rgb = font_colour
        _no_borders(cell)

    for index, header in enumerate(headers):
        _fill(table.cell(0, index), accent, header.upper(), 9.5, _WHITE, bold=True)

    def _week_text(week: int) -> str:
        label = model.week_labels[week - 1] if week - 1 < len(model.week_labels) else f"Wk {week}"
        date_text = model.week_dates[week - 1] if week - 1 < len(model.week_dates) else ""
        return f"{label} · {date_text}" if date_text else label

    for row_index, item in enumerate(model.items, start=1):
        band = _WHITE if row_index % 2 else _ROW_BAND
        _fill(table.cell(row_index, 0), band, item.label or "[UNTITLED SCOPE ITEM]", 9.5,
              _INK, bold=True)
        _fill(table.cell(row_index, 1), band, _week_text(item.start_week), 9, _DARK_TEXT)
        _fill(table.cell(row_index, 2), band, _week_text(item.end_week), 9, _DARK_TEXT)
        _fill(table.cell(row_index, 3), band,
              f"{item.weeks} week{'s' if item.weeks != 1 else ''}", 9, _DARK_TEXT)

    bottom = int(top + row_h * rows)
    if model.start_date_text:
        _text(slide, _M, Emu(int(bottom + Inches(0.1))), Emu(int(_SLIDE_W - 2 * _M)), Inches(0.24),
              f"Program anchored to an anticipated commencement of {model.start_date_text} "
              f"— dates shift with the actual award date.", 8.5, _MUTED)
    _grow(prs, bottom + Inches(0.6))
    return _save(prs)


# ---------------------------------------------------------------------------
# D. Modern timeline
# ---------------------------------------------------------------------------

def _slide_timeline(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    top = _heading(slide, model)

    grid_left = int(_M)
    grid_right = int(_SLIDE_W - _M)
    weeks = max(1, len(model.week_labels))
    week_col_w = (grid_right - grid_left) / weeks

    band_h = int(Inches(0.26)) if model.month_bands else 0
    for name, first, last in model.month_bands:
        x0 = grid_left + (first - 1) * week_col_w
        x1 = grid_left + last * week_col_w
        _rect(slide, Emu(int(x0 + Inches(0.01))), Emu(int(top)),
              Emu(int(x1 - x0 - Inches(0.02))), Emu(band_h), _tint(accent, 0.9))
        _text(slide, Emu(int(x0)), Emu(int(top)), Emu(int(x1 - x0)), Emu(band_h),
              name, 8.5, accent, bold=True, align=PP_ALIGN.CENTER)

    header_h = Inches(0.3)
    header_top = int(top + band_h)
    _week_header(slide, model, grid_left, header_top, week_col_w, header_h, show_dates=False)

    grid_top = int(header_top + header_h)
    row_h = max(int(_MIN_ROW_H), int(Inches(0.4)))
    grid_bottom = grid_top + row_h * len(model.items)
    _gridlines(slide, model, grid_left, grid_top, grid_bottom, week_col_w)

    for index, item in enumerate(model.items):
        y = grid_top + index * row_h
        x0 = grid_left + (item.start_week - 1) * week_col_w
        x1 = grid_left + item.end_week * week_col_w
        bar_h = int(row_h * 0.72)
        _pill(slide, Emu(int(x0 + Inches(0.01))), Emu(int(y + (row_h - bar_h) / 2)),
              x1 - x0 - Inches(0.02), Emu(bar_h),
              accent, item.label or "[UNTITLED SCOPE ITEM]", 9.5, align=PP_ALIGN.LEFT)

    below = _milestones(slide, model, grid_left, grid_top, grid_bottom, week_col_w)
    _legend(slide, _activity_legend(model, accent), below + int(Inches(0.12)))
    _grow(prs, below + Inches(0.5))
    return _save(prs)


_RENDERERS = {
    "gantt": _slide_gantt,
    "swimlanes": _slide_swimlanes,
    "table": _slide_table,
    "timeline": _slide_timeline,
}


def populate_program(
    program_schedule: dict[str, list[bool]],
    week_labels: list[str],
    client_name: str = "",
    project_name: str = "",
    theme_name: str | None = None,
    style: str | None = None,
    methodology_stages: list | None = None,
    start_date=None,
    analysis=None,
) -> bytes:
    """
    Builds a fresh A4-landscape .pptx (returned as bytes) of the delivery
    program, in the user's chosen presentation style.

    `style` is one of program_render.STYLES; anything else (including None)
    falls back to program_render.DEFAULT_STYLE, and "swimlanes" without any
    methodology stages to group by falls back to the Gantt -- the same
    fallback the preview shows and says out loud, so the deck can never
    disagree with what the user saw.

    An empty/missing schedule renders a single placeholder slide rather than
    an empty grid.
    """
    model = program_render.build_model(
        program_schedule or {}, week_labels or [], methodology_stages or [],
        start_date, analysis, project_name or "", client_name or "",
    )
    if model.is_empty:
        return _placeholder_slide(model)
    resolved = program_render.effective_style(model, style or program_render.DEFAULT_STYLE)
    accent = _resolve_palette(theme_name)["active_bg"]
    return _RENDERERS[resolved](model, accent)
