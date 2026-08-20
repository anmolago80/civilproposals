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


def _is_placeholder(text) -> bool:
    """A cell the reader must act on: either an explicit [BRACKETED] note
    from the legacy content below, or the literal TBC the stage drafter
    emits when the brief doesn't support a cell."""
    text = str(text or "").strip()
    return text.startswith("[") or text.upper() == "TBC"


def _fit_size(lines, width_emu, height_emu, start_pt: float, min_pt: float = 4.2):
    """Shrink text until it fits the box, then cap what still doesn't.

    Returns (size_pt, lines). The old code rendered every list at a fixed
    5.6pt inside a fixed-height text box, so a brief with ten scope items
    simply spilled its last items out of the bottom of the box -- invisibly,
    because PowerPoint clips nothing and the shapes below just overlapped
    them. Shrinking first preserves the content; capping with an explicit
    "+N more" line at the floor is honest about the rest, which silent
    overflow never was."""
    texts = [t if not isinstance(t, tuple) else t[0] for t in lines]
    size = start_pt
    while size > min_pt:
        chars_per_line = max(8, int((width_emu / 914400) * (1.85 / (size / 72))))
        line_h = (size * 1.28) / 72 * 914400
        needed = sum(max(1, -(-len(str(t)) // chars_per_line)) for t in texts)
        if needed * line_h <= height_emu:
            return size, lines
        size -= 0.2

    chars_per_line = max(8, int((width_emu / 914400) * (1.85 / (min_pt / 72))))
    line_h = (min_pt * 1.28) / 72 * 914400
    budget = max(1, int(height_emu // line_h)) - 1  # leave a row for the note
    kept, used = [], 0
    for item, text in zip(lines, texts):
        cost = max(1, -(-len(str(text)) // chars_per_line))
        if used + cost > budget:
            break
        kept.append(item)
        used += cost
    dropped = len(lines) - len(kept)
    if dropped:
        kept.append((f"(+{dropped} more -- see the written methodology section)", True))
    return min_pt, kept


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


def _legacy_columns(analysis) -> list[dict]:
    """The pre-stages content: one real column built from scope items, and
    three columns of placeholders. Kept so a project that has not run the
    stage drafter exports exactly what it did before."""
    return [
        {
            "name": _STAGE_HEADERS[0],
            "tasks": list(_PROJECT_INITIATION_TASKS),
            "engagement": list(_PROJECT_INITIATION_ENGAGEMENT),
            "outcome": _PROJECT_INITIATION_OUTCOME,
            "deliverables": list(_PROJECT_INITIATION_DELIVERABLES),
            "chevron": _CONFIRM_DATE_RANGE,
        },
        {
            "name": _STAGE_HEADERS[1],
            "tasks": _stage2_tasks(getattr(analysis, "scope_items", None) or []),
            "engagement": [_CONFIRM_ENGAGEMENT],
            "outcome": _CONFIRM_OUTCOME,
            "deliverables": [_CONFIRM_DELIVERABLES],
            "chevron": _CONFIRM_DATE_RANGE,
        },
    ] + [
        {
            "name": header,
            "tasks": [_CONFIRM_TASKS],
            "engagement": [_CONFIRM_ENGAGEMENT],
            "outcome": _CONFIRM_OUTCOME,
            "deliverables": [_CONFIRM_DELIVERABLES],
            "chevron": _CONFIRM_DATE_RANGE,
        }
        for header in _STAGE_HEADERS[2:]
    ]


def _render_cell_lines(slide, tf, lines, size_pt):
    """One list cell. Placeholder/TBC entries render red italic; real
    content renders as ordinary bullets, so a mixed cell shows at a glance
    which half still needs work."""
    for i, item in enumerate(lines):
        no_bullet = False
        text = item
        if isinstance(item, tuple):
            text, no_bullet = item
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        run = p.add_run()
        prefix = "" if (no_bullet or not text) else "\u2013  "
        run.text = f"{prefix}{text}"
        run.font.size = Pt(size_pt)
        run.font.name = _FONT
        placeholder = _is_placeholder(text)
        run.font.italic = placeholder
        run.font.color.rgb = _RED if placeholder else _DARK_TEXT


WVR_STATEMENT = "All design deliverables will be issued with completed Work Verification Records (WVRs)"
WVR_CONFIRM_PLACEHOLDER = "[CONFIRM WVR / QA STATEMENT FOR THIS FIRM]"


def populate_methodology(
    analysis, client_name: str = "", project_name: str = "", theme_name: str | None = None,
    stages: list | None = None, week_labels: list | None = None,
    wvr_confirmed: bool = False,
) -> bytes:
    """
    Builds a fresh A4-landscape .pptx (returned as bytes) of the delivery
    methodology table, coloured to match `theme_name` (see
    divider_designer.THEME_COLOURS).

    `stages`: the reviewed methodology_stages.MethodologyStage list from the
    Draft Responses tab. When supplied, every column -- name, key tasks,
    engagement activities, outcome, deliverables and the date chevron --
    comes from it, and cells the brief didn't support render as red TBC.
    When it is empty (the stage drafter hasn't been run), the table falls
    back to exactly what it produced before: one column of standard
    initiation boilerplate, one built from the brief's scope items, and two
    of placeholders.

    `week_labels`: the delivery program's own week labels, used for the date
    chevrons -- so they read "Wk 1 - Wk 3" normally and "6 Oct - 20 Oct"
    once a program start date is set, with no regeneration needed.

    `wvr_confirmed`: whether the user has confirmed their firm actually
    issues Work Verification Records. This statement used to be printed as
    fact in every export -- the one line in this module that asserted
    something about the bidder that the app had never been told.

    `client_name` fills the legend's hold-point label and `project_name` the
    title -- both shown in red if not yet entered, same convention as every
    other missing field here.
    """
    P = _resolve_palette(theme_name)
    hold_icon = _render_icon_png("hold_point")
    eng_icon = _render_icon_png("engagement")

    columns_data = _columns_from_stages(stages, week_labels) if stages else _legacy_columns(analysis)
    from_stages = bool(stages)
    n = len(columns_data)

    prs = Presentation()
    prs.slide_width = _SLIDE_W
    prs.slide_height = _SLIDE_H
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    M = Inches(0.14)
    row_label_x, row_label_w = M, Inches(0.17)
    content_x = Emu(int(row_label_x + row_label_w + Inches(0.04)))
    right_edge = Emu(int(_SLIDE_W - M))
    gap = Inches(0.20)

    if from_stages:
        # Every column is a real stage now, so they share the width evenly
        # rather than reserving a narrow first column for boilerplate.
        col_w = Emu(int((right_edge - content_x - (n - 1) * gap) / max(n, 1)))
        cols = [(Emu(int(content_x + i * (col_w + gap))), col_w) for i in range(n)]
    else:
        col1_w = Inches(1.55)
        col2_x = Emu(int(content_x + col1_w + Inches(0.05)))
        stage_w = Emu(int((right_edge - col2_x - 2 * gap) / 3))
        cols = [(content_x, col1_w)] + [
            (Emu(int(col2_x + i * (stage_w + gap))), stage_w) for i in range(3)
        ]
        cols = cols[:n]
    col3_x = cols[2][0] if n > 2 else right_edge
    col4_x = cols[3][0] if n > 3 else right_edge

    y_top = M
    # Slightly taller than it used to be: the title block now carries the
    # project name on a second line beneath the heading. Total column height
    # still lands inside the A4 landscape slide.
    h_title = Inches(0.40)
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
    # Heading plus the project name, in ONE box so the two lines can't
    # drift into the stage headers below. project_name was accepted by this
    # function and never rendered anywhere, so every exported methodology
    # table was anonymous -- indistinguishable from another bid's once saved
    # to disk.
    title_box, title_tf = _textbox(slide, M, y_top, Inches(7.5), h_title)
    title_tf.vertical_anchor = MSO_ANCHOR.TOP
    tp = title_tf.paragraphs[0]
    tp.alignment = PP_ALIGN.LEFT
    tr = tp.add_run()
    tr.text = "Our proposed methodology"
    tr.font.size = Pt(15)
    tr.font.bold = True
    tr.font.name = _FONT
    tr.font.color.rgb = _DARK_TEXT
    sp = title_tf.add_paragraph()
    sp.alignment = PP_ALIGN.LEFT
    sr = sp.add_run()
    sr.text = (project_name or "").strip() or "[Insert project name]"
    sr.font.size = Pt(7.5)
    sr.font.name = _FONT
    sr.font.color.rgb = _DARK_TEXT if (project_name or "").strip() else _RED

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
    for (cx, cw), column in zip(cols, columns_data):
        _rect(slide, cx, y_header, cw, h_header, P["header_bg"])
        _centered_text(slide, cx, y_header, cw, h_header, column["name"], 9.5,
                       _RED if _is_placeholder(column["name"]) else _WHITE)

    # ---- KEY TASKS ---------------------------------------------------------
    _rect(slide, row_label_x, y_tasks, row_label_w, h_tasks, P["tasks_bg"])
    for (cx, cw), column in zip(cols, columns_data):
        _rect(slide, cx, y_tasks, cw, h_tasks, P["tasks_bg"])
        box_w = Emu(int(cw - Inches(0.1)))
        box_h = Emu(int(h_tasks - Inches(0.08)))
        box, tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_tasks + Inches(0.04))), box_w, box_h)
        size, lines = _fit_size(column["tasks"], box_w, box_h, 5.6)
        _render_cell_lines(slide, tf, lines, size)
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_tasks + h_tasks / 2)), Emu(int(h_tasks - Inches(0.1))), row_label_w, "KEY TASKS", 6.5, _DARK_TEXT)
    if n > 2:
        _icon(slide, hold_icon, Emu(int(col3_x - gap / 2)), Emu(int(y_tasks + h_tasks - Inches(0.13))), Inches(0.15))
    if n > 3:
        _icon(slide, hold_icon, Emu(int(col4_x - gap / 2)), Emu(int(y_tasks + h_tasks - Inches(0.13))), Inches(0.15))

    # ---- KEY ENGAGEMENT ACTIVITIES -----------------------------------------
    _rect(slide, row_label_x, y_eng, row_label_w, h_eng, P["eng_bg"])
    for (cx, cw), column in zip(cols, columns_data):
        _rect(slide, cx, y_eng, cw, h_eng, P["eng_bg"])
        box_w = Emu(int(cw - Inches(0.2)))
        box_h = Emu(int(h_eng - Inches(0.06)))
        box, tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_eng + Inches(0.03))), box_w, box_h)
        size, lines = _fit_size(column["engagement"], box_w, box_h, 5.4)
        _render_cell_lines(slide, tf, lines, size)
        _icon(slide, eng_icon, Emu(int(cx + cw - Inches(0.11))), Emu(int(y_eng + h_eng / 2)), Inches(0.16))
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_eng + h_eng / 2)), Emu(int(h_eng - Inches(0.06))), row_label_w, "KEY ENGAGEMENT\nACTIVITIES", 5.2, _DARK_TEXT)

    # ---- OUTCOME ------------------------------------------------------------
    _rect(slide, row_label_x, y_outcome, row_label_w, h_outcome, P["outcome_deliv_bg"])
    for (cx, cw), column in zip(cols, columns_data):
        _rect(slide, cx, y_outcome, cw, h_outcome, P["outcome_deliv_bg"])
        text = column["outcome"]
        placeholder = _is_placeholder(text)
        _centered_text(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_outcome + Inches(0.02))), Emu(int(cw - Inches(0.1))), Emu(int(h_outcome - Inches(0.04))),
                        text, 5.2 if len(str(text)) > 90 else 5.6,
                        _RED if placeholder else _DARK_TEXT, bold=not placeholder, italic=placeholder)
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_outcome + h_outcome / 2)), Emu(int(h_outcome - Inches(0.05))), row_label_w, "OUTCOME", 5.6, _DARK_TEXT)

    # ---- DELIVERABLES ---------------------------------------------------------
    _rect(slide, row_label_x, y_deliv, row_label_w, h_deliv, P["outcome_deliv_bg"])
    note_h = Inches(0.2)
    list_h = Emu(int(h_deliv - note_h - Inches(0.06)))
    for (cx, cw), column in zip(cols, columns_data):
        _rect(slide, cx, y_deliv, cw, h_deliv, P["outcome_deliv_bg"])
        box_w = Emu(int(cw - Inches(0.1)))
        box, tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_deliv + Inches(0.03))), box_w, list_h)
        size, lines = _fit_size(column["deliverables"], box_w, list_h, 5.0)
        _render_cell_lines(slide, tf, lines, size)
        # The WVR line asserts a QA practice about the BIDDER. The app was
        # never told whether this firm issues Work Verification Records, so
        # printing it as fact in every export was the one no-invention
        # breach in this module. It now only appears once confirmed.
        note_box, note_tf = _textbox(slide, Emu(int(cx + Inches(0.05))), Emu(int(y_deliv + list_h + Inches(0.02))), box_w, note_h)
        nr = note_tf.paragraphs[0].add_run()
        nr.text = WVR_STATEMENT if wvr_confirmed else WVR_CONFIRM_PLACEHOLDER
        nr.font.size = Pt(5.0)
        nr.font.italic = True
        nr.font.name = _FONT
        nr.font.color.rgb = _DARK_TEXT if wvr_confirmed else _RED
    _rotated_label(slide, Emu(int(row_label_x + row_label_w / 2)), Emu(int(y_deliv + h_deliv / 2)), Emu(int(h_deliv - Inches(0.1))), row_label_w, "DELIVERABLES", 6.5, _DARK_TEXT)
    if n > 2:
        _icon(slide, hold_icon, Emu(int(col3_x - gap / 2)), Emu(int(y_deliv + h_deliv * 0.12)), Inches(0.15))
    if n > 3:
        _icon(slide, hold_icon, Emu(int(col4_x - gap / 2)), Emu(int(y_deliv + h_deliv * 0.12)), Inches(0.15))

    # ---- TIMELINE ---------------------------------------------------------
    for (cx, cw), column in zip(cols, columns_data):
        chevron_text = column["chevron"]
        _chevron(slide, cx, y_timeline, cw, h_timeline, P["chevron_bg"],
                 chevron_text if chevron_text else _CONFIRM_DATE_RANGE, 5.4)
    if n > 2:
        _icon(slide, hold_icon, Emu(int(col3_x - gap / 2)), Emu(int(y_timeline + h_timeline / 2)), Inches(0.16))
    if n > 3:
        _icon(slide, hold_icon, Emu(int(col4_x - gap / 2)), Emu(int(y_timeline + h_timeline / 2)), Inches(0.16))

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.read()
