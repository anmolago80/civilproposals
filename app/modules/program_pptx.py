"""
program_pptx.py

Builds the delivery program (week-by-scope-item Gantt-style grid) as a
standalone PowerPoint, straight from a project's program_schedule +
program_week_labels -- no template file to keep in sync (same from-scratch
approach as org_chart_pptx.py / methodology_pptx.py, for the same reasons).

The grid is one row per scope item, one column per week, with active weeks
shaded in the proposal's theme accent colour (divider_designer.THEME_COLOURS,
same palette every other export in this tool uses) -- a plain, editable
table meant to be pasted straight into a program/methodology slide or
tidied up further in PowerPoint. Every row/cell comes straight from
program_schedule.py's output or the user's own edits to it (see the Fee
Estimate tab's "Delivery program" editor) -- nothing here is invented; an
empty schedule renders an explicit red placeholder slide instead of a blank
grid, same no-invention convention as the rest of this tool.
"""

from __future__ import annotations

import io

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from modules.divider_designer import THEME_COLOURS

_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_DARK_TEXT = RGBColor(0x1A, 0x1A, 0x1A)
_LIGHT_GREY = RGBColor(0xD9, 0xD9, 0xD9)
_RED = RGBColor(0xC0, 0x00, 0x00)
_FONT = "Calibri"

# A4 landscape -- same slide size as org_chart_pptx.py / methodology_pptx.py
_SLIDE_W = Inches(11.6929)
_SLIDE_H = Inches(8.2677)


def _resolve_palette(theme_name: str | None) -> dict:
    colours = THEME_COLOURS.get(theme_name, THEME_COLOURS["Corporate"])
    primary = RGBColor(*colours["primary"])
    accent = RGBColor(*colours["accent"])
    # Minimalist's "primary" is a light near-white wash by design -- same special
    # case export_docx._theme_colours() / methodology_pptx._resolve_palette() apply.
    dark_role = RGBColor(0x2A, 0x2A, 0x2A) if theme_name == "Minimalist" else primary
    return {"header_bg": dark_role, "active_bg": accent}


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


def populate_program(
    program_schedule: dict[str, list[bool]],
    week_labels: list[str],
    client_name: str = "",
    project_name: str = "",
    theme_name: str | None = None,
) -> bytes:
    """
    Builds a fresh A4-landscape .pptx (returned as bytes): a Gantt-style grid,
    one row per scope item (program_schedule's keys, in order) and one column
    per week (week_labels), active weeks shaded in `theme_name`'s accent
    colour. project_name fills the subtitle -- shown in red if not yet
    entered, same convention as methodology_pptx.py's client-name legend.
    An empty/missing schedule renders a single placeholder slide rather than
    an empty grid.
    """
    P = _resolve_palette(theme_name)
    prs = Presentation()
    prs.slide_width = _SLIDE_W
    prs.slide_height = _SLIDE_H
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    M = Inches(0.3)
    title_h = Inches(0.5)
    _text(slide, M, M, Emu(int(_SLIDE_W - 2 * M)), title_h, "Delivery program", 20, _DARK_TEXT, bold=True)
    subtitle = (project_name or "").strip() or "[Insert project name]"
    _text(slide, M, Emu(int(M + title_h)), Emu(int(_SLIDE_W - 2 * M)), Inches(0.3), subtitle, 11,
          _DARK_TEXT if (project_name or "").strip() else _RED)

    items = list((program_schedule or {}).items())
    labels = week_labels or []

    if not items or not labels:
        _text(
            slide, M, Emu(int(_SLIDE_H / 2 - Inches(0.3))), Emu(int(_SLIDE_W - 2 * M)), Inches(0.6),
            "[NO PROGRAM ENTERED -- build the delivery program in the Fee Estimate tab, then "
            "re-download this PowerPoint]",
            14, _RED, align=PP_ALIGN.CENTER,
        )
        buffer = io.BytesIO()
        prs.save(buffer)
        buffer.seek(0)
        return buffer.read()

    grid_top = Emu(int(M + title_h + Inches(0.45)))
    grid_bottom = Emu(int(_SLIDE_H - M))
    grid_left = M
    grid_right = Emu(int(_SLIDE_W - M))

    label_col_w = Inches(3.0)
    week_col_w = Emu(int((grid_right - grid_left - label_col_w) / len(labels)))

    header_h = Inches(0.4)
    row_h = Emu(int((grid_bottom - grid_top - header_h) / len(items)))
    row_h = Emu(max(int(row_h), int(Inches(0.3))))

    # Header row
    _rect(slide, grid_left, grid_top, label_col_w, header_h, P["header_bg"])
    _text(slide, grid_left, grid_top, label_col_w, header_h, "Scope item", 11, _WHITE, bold=True)
    for i, lbl in enumerate(labels):
        cx = Emu(int(grid_left + label_col_w + i * week_col_w))
        _rect(slide, cx, grid_top, week_col_w, header_h, P["header_bg"])
        _text(slide, cx, grid_top, week_col_w, header_h, lbl, 10, _WHITE, bold=True, align=PP_ALIGN.CENTER)

    # Body rows
    for r, (title, active_weeks) in enumerate(items):
        ry = Emu(int(grid_top + header_h + r * row_h))
        _rect(slide, grid_left, ry, label_col_w, row_h, _WHITE, line_color=_LIGHT_GREY)
        _text(slide, grid_left, ry, label_col_w, row_h, title or "[UNTITLED SCOPE ITEM]", 9.5, _DARK_TEXT)
        for i, lbl in enumerate(labels):
            cx = Emu(int(grid_left + label_col_w + i * week_col_w))
            active = bool(active_weeks[i]) if i < len(active_weeks) else False
            _rect(slide, cx, ry, week_col_w, row_h, P["active_bg"] if active else _WHITE, line_color=_LIGHT_GREY)

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.read()
