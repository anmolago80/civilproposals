"""
methodology_pptx.py

Builds the methodology-table PowerPoint FROM SCRATCH, straight from a
project's tender analysis -- no template file to edit or keep in sync
(same approach as org_chart_pptx.py, for the same reasons: nothing to
delete, nothing to leave dangling).

Structure is fixed and generic across every proposal this app produces:
four stage columns (Project Initiation, then three progressively-developed
design stages) against four standard rows (Key tasks, Key engagement
activities, Outcome, Deliverables). Column 1 is always the same
boilerplate; column 2's Key tasks are the REAL scope items/tasks from the
brief (tender_analyser.ScopeItem) -- never invented. Columns 3 and 4 cover
stages the brief doesn't describe (future/contingent work), so their cells
stay explicit "[CONFIRM ...]" placeholders rather than guessed content,
same no-invention rule as everywhere else in this tool.

The client name in the top-right legend is the one piece of real,
project-specific data this chart needs beyond the scope items -- pulled
straight from Project Setup (client_name), never invented; shows a red
placeholder if not entered yet, matching every other missing-field
convention in this app.

Colours are pulled from the SAME theme palette the rest of the proposal
uses (divider_designer.THEME_COLOURS), so this chart never looks like a
foreign template dropped into an otherwise-themed document.
"""

from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from modules.divider_designer import THEME_COLOURS

_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_DARK_TEXT = RGBColor(0x1A, 0x1A, 0x1A)
_RED = RGBColor(0xC0, 0x00, 0x00)
_FONT = "Calibri"

# A4 landscape
_SLIDE_W = Inches(11.6929)
_SLIDE_H = Inches(8.2677)

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


def _tint(rgb: RGBColor, amount: float) -> RGBColor:
    """Mixes `rgb` toward white by `amount` (0 = original colour, 1 = white)."""
    def mix(c):
        return round(c + (255 - c) * amount)
    return RGBColor(mix(rgb[0]), mix(rgb[1]), mix(rgb[2]))


def _resolve_palette(theme_name: str | None) -> dict:
    colours = THEME_COLOURS.get(theme_name, THEME_COLOURS["Corporate"])
    primary = RGBColor(*colours["primary"])
    accent = RGBColor(*colours["accent"])
    # Minimalist's "primary" is a light near-white wash by design (its reversed
    # light-on-dark convention elsewhere in the app) -- same special case
    # export_docx._theme_colours() applies to heading colour.
    dark_role = RGBColor(0x2A, 0x2A, 0x2A) if theme_name == "Minimalist" else primary
    return {
        "header_bg": dark_role,
        "tasks_bg": _tint(primary, 0.88),
        "eng_bg": _tint(primary, 0.78),
        "outcome_deliv_bg": _tint(accent, 0.82),
        "icon_fill": dark_role,
        "engagement_fill": accent,
        "chevron_bg": dark_role,
    }


# ---------------------------------------------------------------------------
# Icons -- rendered with PIL, entirely self-contained (no bundled asset files
# to keep in sync with this module, same reasoning as org_chart_pptx.py).
# ---------------------------------------------------------------------------

def _render_icon_png(kind: str, size: int = 240) -> bytes:
    ss = 4
    big = size * ss
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = int(big * 0.03)
    d.ellipse([pad, pad, big - pad, big - pad], fill=(0, 0, 0, 255))
    cx = cy = big / 2

    if kind == "hold_point":
        body_w, body_h = big * 0.375, big * 0.475
        bx0, by0 = cx - body_w / 2, cy - body_h / 2 + big * 0.03
        bx1, by1 = cx + body_w / 2, cy + body_h / 2 + big * 0.03
        d.rounded_rectangle([bx0, by0, bx1, by1], radius=big * 0.035, outline=(255, 255, 255, 255), width=int(big * 0.0225))
        clip_w, clip_h = big * 0.16, big * 0.065
        d.rounded_rectangle([cx - clip_w / 2, by0 - clip_h / 2, cx + clip_w / 2, by0 + clip_h / 2],
                             radius=big * 0.025, fill=(255, 255, 255, 255))
        sq = big * 0.035
        line_x0 = bx0 + big * 0.055
        line_x1 = bx1 - big * 0.05
        for frac in (0.24, 0.43, 0.62):
            ry = by0 + body_h * frac
            d.rectangle([line_x0, ry - sq / 2, line_x0 + sq, ry + sq / 2], outline=(255, 255, 255, 255), width=int(big * 0.0125))
            d.line([line_x0 + sq + big * 0.03, ry, line_x1, ry], fill=(255, 255, 255, 255), width=int(big * 0.0225))
    else:  # collaborative engagement -- hub and spoke
        hub_r, node_r, spoke_len = big * 0.065, big * 0.04, big * 0.23
        n_nodes = 5
        for i in range(n_nodes):
            angle = math.radians(-90 + i * (360 / n_nodes))
            nx, ny = cx + spoke_len * math.cos(angle), cy + spoke_len * math.sin(angle)
            d.line([cx, cy, nx, ny], fill=(255, 255, 255, 255), width=int(big * 0.025))
        for i in range(n_nodes):
            angle = math.radians(-90 + i * (360 / n_nodes))
            nx, ny = cx + spoke_len * math.cos(angle), cy + spoke_len * math.sin(angle)
            d.ellipse([nx - node_r, ny - node_r, nx + node_r, ny + node_r], fill=(255, 255, 255, 255))
        d.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r], fill=(255, 255, 255, 255))

    im = im.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Shape/text helpers (Emu-precise, mirroring org_chart_pptx.py's conventions)
# ---------------------------------------------------------------------------

def _rect(slide, x, y, w, h, fill_color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _textbox(slide, x, y, w, h):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(2)
    tf.margin_right = Pt(2)
    tf.margin_top = Pt(1)
    tf.margin_bottom = Pt(1)
    return box, tf


def _lines_to_paragraphs(tf, lines, size_pt, color, bullet=True, align=PP_ALIGN.LEFT):
    for i, item in enumerate(lines):
        no_bullet = False
        text = item
        if isinstance(item, tuple):
            text, no_bullet = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        run = p.add_run()
        prefix = "" if (no_bullet or not bullet or not text) else "–  "
        run.text = f"{prefix}{text}"
        run.font.size = Pt(size_pt)
        run.font.name = _FONT
        run.font.color.rgb = color


def _placeholder_bullets(tf, text, size_pt):
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = f"–  {text}"
    run.font.size = Pt(size_pt)
    run.font.name = _FONT
    run.font.italic = True
    run.font.color.rgb = _RED


def _centered_text(slide, x, y, w, h, text, size_pt, color, bold=True, italic=False):
    box, tf = _textbox(slide, x, y, w, h)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = _FONT
    run.font.color.rgb = color
    return box


def _rotated_label(slide, cx, cy, visual_len, visual_thick, text, size_pt, color):
    w, h = visual_len, visual_thick
    x, y = Emu(int(cx - w / 2)), Emu(int(cy - h / 2))
    box, tf = _textbox(slide, x, y, w, h)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, line in enumerate(text.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = line
        run.font.size = Pt(size_pt)
        run.font.bold = True
        run.font.name = _FONT
        run.font.color.rgb = color
    box.rotation = 270
    return box


def _icon(slide, png_bytes, cx, cy, d):
    x, y = Emu(int(cx - d / 2)), Emu(int(cy - d / 2))
    slide.shapes.add_picture(io.BytesIO(png_bytes), x, y, d, d)


def _chevron(slide, x, y, w, h, fill_color, text, size_pt):
    shape = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.fill.background()
    shape.shadow.inherit = False
    tf = shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Pt(2)
    tf.margin_right = Pt(10)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size_pt)
    run.font.bold = True
    run.font.name = _FONT
    run.font.color.rgb = _WHITE
    return shape


# ---------------------------------------------------------------------------
# Content assembly -- the only part that touches real project data
# ---------------------------------------------------------------------------

def _stage2_tasks(scope_items: list) -> list:
    if not scope_items:
        return [_NO_SCOPE_PLACEHOLDER]
    lines = []
    for item in scope_items:
        title = (getattr(item, "title", "") or "[UNTITLED SCOPE ITEM]").strip()
        tasks = getattr(item, "tasks", None) or []
        lines.append(f"{title}: {'; '.join(tasks)}" if tasks else title)
    return lines


def populate_methodology(
    analysis, client_name: str = "", project_name: str = "", theme_name: str | None = None,
) -> bytes:
    """
    Builds a fresh A4-landscape .pptx (returned as bytes): four fixed stage
    columns (see _STAGE_HEADERS), coloured to match `theme_name` (see
    divider_designer.THEME_COLOURS). Column 1 is standard boilerplate;
    column 2's Key tasks come straight from `analysis.scope_items` (the
    brief's real scope of work); columns 3-4 are contingent/future stages
    the brief doesn't describe, so they stay explicit placeholders.
    `client_name` fills the legend's hold-point label -- shown in red if
    not yet entered, same convention as every other missing field here.
    """
    P = _resolve_palette(theme_name)
    hold_icon = _render_icon_png("hold_point")
    eng_icon = _render_icon_png("engagement")

    prs = Presentation()
    prs.slide_width = _SLIDE_W
    prs.slide_height = _SLIDE_H
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    M = Inches(0.14)
    row_label_x, row_label_w = M, Inches(0.17)
    col1_x, col1_w = Emu(int(row_label_x + row_label_w + Inches(0.04))), Inches(1.55)
    gap = Inches(0.20)
    col2_x = Emu(int(col1_x + col1_w + Inches(0.05)))
    right_edge = Emu(int(_SLIDE_W - M))
    stage_w = Emu(int((right_edge - col2_x - 2 * gap) / 3))
    col3_x = Emu(int(col2_x + stage_w + gap))
    col4_x = Emu(int(col3_x + stage_w + gap))
    cols = [(col1_x, col1_w), (col2_x, stage_w), (col3_x, stage_w), (col4_x, stage_w)]

    y_top = M
    h_title = Inches(0.32)
    y_header = Emu(int(y_top + h_title + Inches(0.04)))
    h_header = Inches(0.46)

    y_tasks = Emu(int(y_header + h_header))
    h_tasks = Inches(3.35)
    y_eng = Emu(int(y_tasks + h_tasks))
    h_eng = Inches(0.70)
    y_outcome = Emu(int(y_eng + h_eng))
    h_outcome = Inches(0.50)
    y_deliv = Emu(int(y_outcome + h_outcome))
    h_deliv = Inches(2.30)
    y_timeline = Emu(int(y_deliv + h_deliv + Inches(0.03)))
    h_timeline = Inches(0.30)

    # ---- title + KEY legend --------------------------------------------
    _centered_text(slide, M, y_top, Inches(7.5), h_title, "Our proposed methodology", 15, _DARK_TEXT)
    slide.shapes[-1].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

    key_box, key_tf = _textbox(slide, Emu(int(right_edge - Inches(2.7))), Emu(int(y_top + Inches(0.02))), Inches(0.55), Emu(int(h_title * 0.5)))
    key_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    kr = key_tf.paragraphs[0].add_run()
    kr.text = "KEY"
    kr.font.size = Pt(8)
    kr.font.bold = True
    kr.font.name = _FONT
    kr.font.color.rgb = _DARK_TEXT

    _icon(slide, hold_icon, Emu(int(right_edge - Inches(2.1))), Emu(int(y_top + Inches(0.06) + Inches(0.085))), Inches(0.17))
    label_box, label_tf = _textbox(slide, Emu(int(right_edge - Inches(1.93))), y_top, Inches(1.93), Emu(int(h_title * 0.5)))
    label_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p1 = label_tf.paragraphs[0]
    client_display = (client_name or "").strip() or "[Insert client name]"
    r1 = p1.add_run()
    r1.text = client_display
    r1.font.size = Pt(6.5)
    r1.font.name = _FONT
    r1.font.color.rgb = _DARK_TEXT if (client_name or "").strip() else _RED
    r2 = p1.add_run()
    r2.text = " hold point"
    r2.font.size = Pt(6.5)
    r2.font.name = _FONT
    r2.font.color.rgb = _DARK_TEXT

    _icon(slide, eng_icon, Emu(int(right_edge - Inches(2.1))), Emu(int(y_top + Inches(0.24) + Inches(0.085))), Inches(0.17))
    _centered_text(slide, Emu(int(right_edge - Inches(1.93))), Emu(int(y_top + Inches(0.18))), Inches(1.9), Emu(int(h_title * 0.5)),
                    "Collaborative engagement", 6.5, _DARK_TEXT, bold=False)
    slide.shapes[-1].text_frame.paragraphs[0].alignment = PP_ALIGN.LEFT

    # ---- stage headers ----------------------------------------------------
    for (cx, cw), header in zip(cols, _STAGE_HEADERS):
        _rect(slide, cx, y_header, cw, h_header, P["header_bg"])
        _centered_text(slide, cx, y_header, cw, h_header, header, 9.5, _WHITE)

    # ---- KEY TASKS ---------------------------------------------------------
    _rect(slide, row_label_x, y_tasks, row_label_w, h_tasks, P["tasks_bg"])
    task_lines = [
        _PROJECT_INITIATION_TASKS,
        _stage2_tasks(getattr(analysis, "scope_items", None) or []),
        [_CONFIRM_TASKS],
        [_CONFIRM_TASKS],
    ]
    for (cx, cw), lines in zip(cols, task_lines):
        _rect(slide, cx, y_tasks, cw, h_tasks, P["tasks_bg"])
        box, tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_tasks + Inches(0.04))), Emu(int(cw - Inches(0.1))), Emu(int(h_tasks - Inches(0.08))))
        if lines and lines[0] in (_CONFIRM_TASKS, _NO_SCOPE_PLACEHOLDER):
            _placeholder_bullets(tf, lines[0], 5.6)
        else:
            _lines_to_paragraphs(tf, lines, 5.6, _DARK_TEXT)
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_tasks + h_tasks / 2)), Emu(int(h_tasks - Inches(0.1))), row_label_w, "KEY TASKS", 6.5, _DARK_TEXT)
    _icon(slide, hold_icon, Emu(int(col3_x - gap / 2)), Emu(int(y_tasks + h_tasks - Inches(0.13))), Inches(0.15))
    _icon(slide, hold_icon, Emu(int(col4_x - gap / 2)), Emu(int(y_tasks + h_tasks - Inches(0.13))), Inches(0.15))

    # ---- KEY ENGAGEMENT ACTIVITIES -----------------------------------------
    _rect(slide, row_label_x, y_eng, row_label_w, h_eng, P["eng_bg"])
    eng_lines = [_PROJECT_INITIATION_ENGAGEMENT, [_CONFIRM_ENGAGEMENT], [_CONFIRM_ENGAGEMENT], [_CONFIRM_ENGAGEMENT]]
    for idx, ((cx, cw), lines) in enumerate(zip(cols, eng_lines)):
        _rect(slide, cx, y_eng, cw, h_eng, P["eng_bg"])
        box, tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_eng + Inches(0.03))), Emu(int(cw - Inches(0.2))), Emu(int(h_eng - Inches(0.06))))
        if idx > 0:
            _placeholder_bullets(tf, lines[0], 5.4)
        else:
            _lines_to_paragraphs(tf, lines, 5.4, _DARK_TEXT)
        _icon(slide, eng_icon, Emu(int(cx + cw - Inches(0.11))), Emu(int(y_eng + h_eng / 2)), Inches(0.16))
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_eng + h_eng / 2)), Emu(int(h_eng - Inches(0.06))), row_label_w, "KEY ENGAGEMENT\nACTIVITIES", 5.2, _DARK_TEXT)

    # ---- OUTCOME ------------------------------------------------------------
    _rect(slide, row_label_x, y_outcome, row_label_w, h_outcome, P["outcome_deliv_bg"])
    outcome_texts = [_PROJECT_INITIATION_OUTCOME, _CONFIRM_OUTCOME, _CONFIRM_OUTCOME, _CONFIRM_OUTCOME]
    for idx, ((cx, cw), text) in enumerate(zip(cols, outcome_texts)):
        _rect(slide, cx, y_outcome, cw, h_outcome, P["outcome_deliv_bg"])
        is_placeholder = idx > 0
        _centered_text(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_outcome + Inches(0.02))), Emu(int(cw - Inches(0.1))), Emu(int(h_outcome - Inches(0.04))),
                        text, 5.2 if idx >= 2 else 5.6, _RED if is_placeholder else _DARK_TEXT, bold=not is_placeholder, italic=is_placeholder)
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_outcome + h_outcome / 2)), Emu(int(h_outcome - Inches(0.05))), row_label_w, "OUTCOME", 5.6, _DARK_TEXT)

    # ---- DELIVERABLES ---------------------------------------------------------
    _rect(slide, row_label_x, y_deliv, row_label_w, h_deliv, P["outcome_deliv_bg"])
    note_h = Inches(0.2)
    list_h = Emu(int(h_deliv - note_h - Inches(0.06)))
    deliv_lines = [_PROJECT_INITIATION_DELIVERABLES, [_CONFIRM_DELIVERABLES], [_CONFIRM_DELIVERABLES], [_CONFIRM_DELIVERABLES]]
    for idx, ((cx, cw), lines) in enumerate(zip(cols, deliv_lines)):
        _rect(slide, cx, y_deliv, cw, h_deliv, P["outcome_deliv_bg"])
        box, tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_deliv + Inches(0.03))), Emu(int(cw - Inches(0.1))), list_h)
        if idx > 0:
            _placeholder_bullets(tf, lines[0], 5.0)
        else:
            _lines_to_paragraphs(tf, lines, 5.0, _DARK_TEXT)
        if idx > 0:
            note_box, note_tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_deliv + list_h + Inches(0.02))), Emu(int(cw - Inches(0.1))), note_h)
            nr = note_tf.paragraphs[0].add_run()
            nr.text = "All design deliverables will be issued with completed Work Verification Records (WVRs)"
            nr.font.size = Pt(5.0)
            nr.font.italic = True
            nr.font.name = _FONT
            nr.font.color.rgb = _DARK_TEXT
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_deliv + h_deliv / 2)), Emu(int(h_deliv - Inches(0.1))), row_label_w, "DELIVERABLES", 6.5, _DARK_TEXT)
    _icon(slide, hold_icon, Emu(int(col3_x - gap / 2)), Emu(int(y_deliv + h_deliv * 0.12)), Inches(0.15))
    _icon(slide, hold_icon, Emu(int(col4_x - gap / 2)), Emu(int(y_deliv + h_deliv * 0.12)), Inches(0.15))

    # ---- TIMELINE ---------------------------------------------------------
    for cx, cw in cols:
        _chevron(slide, cx, y_timeline, cw, h_timeline, P["chevron_bg"], _CONFIRM_DATE_RANGE, 5.4)
    _icon(slide, hold_icon, Emu(int(col3_x - gap / 2)), Emu(int(y_timeline + h_timeline / 2)), Inches(0.16))
    _icon(slide, hold_icon, Emu(int(col4_x - gap / 2)), Emu(int(y_timeline + h_timeline / 2)), Inches(0.16))

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.read()
