"""
org_chart_pptx.py

Builds the org chart PowerPoint FROM SCRATCH, straight from a project's
resourcing plan -- no template file to edit or keep in sync.

An earlier version of this module worked by surgically editing a fixed
template (assets/org_chart_template.pptx): filling in [Name] placeholders,
deleting boxes for disciplines not on this project, adding ad hoc boxes for
disciplines the template had no box for. That approach kept breaking in new
ways as real projects were tried against it -- deleting a box could leave
its connector line behind, dangling with nothing below it; a discipline
outside the template's fixed ~11-box allowlist got exiled to an ugly
disconnected strip; removing boxes left the remaining ones asymmetrically
spaced. Every fix was another special case bolted onto a fundamentally
static layout.

This version has no static layout at all. Every discipline in the
project's resourcing plan becomes one card, evenly spaced and centered
across the slide -- 2 disciplines or 9, doesn't matter, the spacing is
recomputed every time from however many are actually present. There is
nothing to delete and nothing to leave dangling, because nothing is ever
there that shouldn't be. Cards never shrink past a legible minimum width;
once a single row can't fit them all at that width, the remaining
disciplines wrap onto additional card rows (still centered, still
data-driven) instead of squeezing text into unreadable slivers.

Matches what the resourcing plan actually tracks: one lead name per
discipline/management role, PLUS any support members added under a
discipline lead (resourcing.ResourceAssignment.custom_title -- e.g. "Ryan
Swagemakers, Bridge Engineer" added under the "Structural" lead) -- each
gets its own extra row on that lead's card, titled with whatever the user
typed, never invented. The client's own PM counterpart and subconsultant
firms still have no equivalent in the app's data, so this module doesn't
invent placeholder rows for those. An unassigned role still gets its card
(so the chart's shape reflects the project's actual structure), just with
red "TBC" instead of a name.

A "Peer Review" box in the top-right lists every discipline with a red
"TBC" next to it (e.g. "Structural - TBC") -- the app has no reviewer data
anywhere, so this is never an invented name, just a checklist the user
fills in by hand once reviewers are confirmed.
"""

from __future__ import annotations

import io

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# ---- palette -------------------------------------------------------------
# The fallback palette, used when no proposal theme is given. Everything
# below is now themed from divider_designer.THEME_COLOURS instead (see
# _resolve_palette) -- this chart was the last generated artefact still
# hardcoded to navy/cyan, so a Government-themed pack exported a green
# cover, green dividers, green tables and then one cyan org chart.
_NAVY = RGBColor(0x00, 0x37, 0x63)
_BLACK = RGBColor(0x00, 0x00, 0x00)
_CYAN_HEADER = RGBColor(0x00, 0xB0, 0xF0)
_CYAN_BODY = RGBColor(0xE9, 0xF9, 0xFD)
_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_DARK_TEXT = RGBColor(0x1A, 0x1A, 0x1A)
_GREY_TEXT = RGBColor(0x59, 0x59, 0x59)
_RED_TBC = RGBColor(0xC0, 0x00, 0x00)
_RED_TBC_ON_DARK = RGBColor(0xFF, 0x8A, 0x80)
_LINE_COLOR = RGBColor(0x59, 0x59, 0x59)
_BORDER_COLOR = RGBColor(0xBF, 0xBF, 0xBF)

_FONT = "Calibri"

_SLIDE_W = Inches(13.333)
_SLIDE_H = Inches(7.5)

_MGMT_W = Inches(2.3)
_MGMT_H = Inches(0.62)
_MGMT_ROW_GAP = Inches(0.35)

_DISC_W_DEFAULT = Inches(2.05)
_DISC_W_MIN = Inches(1.55)  # never shrink narrower than this -- wrap to another row instead
_DISC_HEADER_H = Inches(0.32)
_DISC_ROLE_H = Inches(0.42)  # the Lead sub-row
_COL_MARGIN = Inches(0.4)
_MIN_GAP = Inches(0.22)
_ROW_GAP = Inches(0.45)  # vertical gap between wrapped rows of discipline cards

# ---- Peer Review box (top-right) -----------------------------------------
_PEER_COL_W = Inches(1.95)
_PEER_COL_GAP = Inches(0.2)
_PEER_LINE_H = Inches(0.23)
_PEER_RIGHT_MARGIN = Inches(0.35)
_PEER_MAX_ROWS_PER_COL = 14

# Fixed management chain, always shown top to bottom in this order (see
# resourcing.CLIENT_ROLE / FIRM_MANAGEMENT_ROLES) -- every other slot in the
# plan is a discipline and gets its own column below it.
_MANAGEMENT_CHAIN = ["Client Project Manager", "Project Director", "Project Manager", "Design Manager"]


def _tint(rgb: RGBColor, amount: float) -> RGBColor:
    """Blend towards white. amount=0 -> unchanged, 1 -> white."""
    return RGBColor(*(int(c + (255 - c) * amount) for c in (rgb[0], rgb[1], rgb[2])))


def _text_on(bg: RGBColor) -> RGBColor:
    """Readable text colour for a given fill. A themed accent can be light
    (Minimalist) or dark (Corporate); white-on-everything was safe while the
    header was always cyan and isn't any more."""
    luminance = (0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) / 255
    return _DARK_TEXT if luminance > 0.62 else _WHITE


def _resolve_palette(theme_name: str | None) -> dict:
    """The chart's colours, from the same divider_designer.THEME_COLOURS every
    other generated graphic uses. No theme (or an unknown one) keeps the
    original navy/cyan look, so nothing changes for a project that never
    picked a theme."""
    from modules.divider_designer import THEME_COLOURS

    colours = THEME_COLOURS.get(theme_name or "")
    if not colours:
        return {
            "mgmt": _NAVY, "mgmt_text": _WHITE,
            "header": _CYAN_HEADER, "header_text": _WHITE,
            "body": _CYAN_BODY,
        }
    primary = RGBColor(*colours["primary"])
    accent = RGBColor(*colours["accent"])
    # Minimalist's "primary" is a near-white wash by design -- the same
    # special case export_docx._theme_colours() and program_pptx apply.
    mgmt = RGBColor(0x2A, 0x2A, 0x2A) if theme_name == "Minimalist" else primary
    return {
        "mgmt": mgmt, "mgmt_text": _text_on(mgmt),
        "header": accent, "header_text": _text_on(accent),
        "body": _tint(accent, 0.88),
    }


def _set_text(text_frame, lines, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE):
    """lines: list of (text, size_pt, bold, color) tuples, one per paragraph."""
    text_frame.word_wrap = True
    text_frame.vertical_anchor = anchor
    text_frame.margin_left = Pt(4)
    text_frame.margin_right = Pt(4)
    text_frame.margin_top = Pt(2)
    text_frame.margin_bottom = Pt(2)
    for i, (text, size, bold, color) in enumerate(lines):
        p = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.name = _FONT
        run.font.color.rgb = color


def _rect(slide, x, y, w, h, fill_color, line_color=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if line_color is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line_color
        shape.line.width = Pt(0.75)
    shape.shadow.inherit = False
    return shape


def _connector(slide, conn_type, x1, y1, x2, y2):
    c = slide.shapes.add_connector(conn_type, x1, y1, x2, y2)
    c.line.color.rgb = _LINE_COLOR
    c.line.width = Pt(1.0)
    return c


def _name_or_tbc(name: str, on_dark: bool = False):
    name = (name or "").strip()
    if name:
        return (name, 11, False, _WHITE if on_dark else _DARK_TEXT)
    return ("TBC", 11, False, _RED_TBC_ON_DARK if on_dark else _RED_TBC)


def _title_or_confirm(title: str):
    """A support member's own job title on this project.

    Blank used to render the literal words "Team member", which reads in the
    finished chart as a real, deliberate title -- the one place in this module
    where a missing value was filled in rather than marked. It is now the
    standard red placeholder, like every other unknown in this tool."""
    title = (title or "").strip()
    if title:
        return (title, 8, True, _GREY_TEXT)
    return ("[CONFIRM TITLE]", 8, True, _RED_TBC)


def _project_line(tender_name: str, project_name: str) -> str:
    """The chart's third title line. The tender/RFT number was never passed
    in, so this line read "[Project Number] <name>" on every chart even for
    a project whose number had been entered on the Project Setup tab.
    Either part missing keeps its bracket placeholder, same convention as
    the client line above it."""
    number = (tender_name or "").strip() or "[Project Number]"
    name = (project_name or "").strip() or "[Project Name]"
    return f"{number} {name}"


def _management_box(slide, x, y, label, name, fill, text_colour=_WHITE):
    box = _rect(slide, x, y, _MGMT_W, _MGMT_H, fill)
    on_dark = text_colour == _WHITE
    _set_text(box.text_frame, [(label, 11, True, text_colour), _name_or_tbc(name, on_dark=on_dark)])
    return box


def _add_peer_review_box(slide, discipline_names, top, bottom_limit, palette=None):
    """One consolidated list, top-right: every discipline followed by a red
    "TBC" (e.g. "Structural - TBC") for the user to fill in once reviewers
    are confirmed. The app has no peer-reviewer data anywhere, so this is a
    checklist, never an invented name. Wraps into as many side-by-side
    columns as needed to stay within the vertical space above the
    discipline card rows (the same band the management chain occupies) --
    growing sideways rather than colliding with the chart below it."""
    if not discipline_names:
        return
    palette = palette or _resolve_palette(None)
    n = len(discipline_names)
    available_h = max(Emu(bottom_limit - top), _PEER_LINE_H)
    max_rows_by_space = max(1, int(available_h // _PEER_LINE_H))
    max_rows_per_col = min(_PEER_MAX_ROWS_PER_COL, max_rows_by_space)
    columns = max(1, -(-n // max_rows_per_col))  # ceil

    # Never let the box's columns run wide enough to reach the management
    # chain in the middle of the slide -- past a handful of columns, grow
    # taller (more rows per column) instead of wider.
    mgmt_right_edge = Emu(_SLIDE_W // 2 + _MGMT_W // 2 + Inches(0.3))
    available_w = Emu(_SLIDE_W - _PEER_RIGHT_MARGIN - mgmt_right_edge)
    max_columns_by_width = max(1, int((available_w + _PEER_COL_GAP) // (_PEER_COL_W + _PEER_COL_GAP)))
    columns = min(columns, max_columns_by_width)

    rows_per_col = -(-n // columns)  # ceil, balanced across columns

    total_w = columns * _PEER_COL_W + (columns - 1) * _PEER_COL_GAP
    start_x = Emu(_SLIDE_W - _PEER_RIGHT_MARGIN - total_w)

    # Same header-bar-plus-body styling as every discipline card, so this
    # box reads as part of the same chart rather than a bolted-on list.
    header_h = _DISC_HEADER_H
    header = _rect(slide, start_x, top, total_w, header_h, palette["header"])
    _set_text(header.text_frame, [("Peer Review", 11, True, palette["header_text"])])

    list_top = Emu(top + header_h)
    list_h = Emu(rows_per_col * _PEER_LINE_H + Inches(0.1))
    _rect(slide, start_x, list_top, total_w, list_h, palette["body"], line_color=_BORDER_COLOR)

    for c in range(columns):
        chunk = discipline_names[c * rows_per_col:(c + 1) * rows_per_col]
        col_x = Emu(start_x + c * (_PEER_COL_W + _PEER_COL_GAP) + Inches(0.08))
        col_box = slide.shapes.add_textbox(col_x, Emu(list_top + Inches(0.05)),
                                            Emu(_PEER_COL_W - Inches(0.1)), list_h)
        tf = col_box.text_frame
        tf.word_wrap = True
        tf.margin_left = Pt(2)
        tf.margin_right = Pt(2)
        tf.margin_top = Pt(1)
        tf.margin_bottom = Pt(1)
        for i, slot in enumerate(chunk):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = PP_ALIGN.LEFT
            label_run = p.add_run()
            label_run.text = f"{slot} - "
            label_run.font.size = Pt(9)
            label_run.font.name = _FONT
            label_run.font.color.rgb = _DARK_TEXT
            tbc_run = p.add_run()
            tbc_run.text = "TBC"
            tbc_run.font.size = Pt(9)
            tbc_run.font.bold = True
            tbc_run.font.name = _FONT
            tbc_run.font.color.rgb = _RED_TBC


def populate_org_chart(resource_plan: list, client_name: str = "", project_name: str = "",
                       tender_name: str = "", theme_name: str | None = None) -> bytes:
    """
    Builds a fresh .pptx (returned as bytes) from `resource_plan` (a list of
    resourcing.ResourceAssignment): the fixed Client Project Manager ->
    Project Director -> Project Manager -> Design Manager chain down the
    middle, then one evenly-spaced card per discipline in the plan (wrapping
    to further rows once there are too many to stay legible in one), each
    showing that discipline's Lead name and a Peer Review row (always red
    "TBC" -- the app has no reviewer data to show). `client_name`/
    `project_name` fill the title block when given; left as bracket
    placeholders otherwise, same as every other not-yet-known field in this
    tool.
    """
    palette = _resolve_palette(theme_name)

    prs = Presentation()
    prs.slide_width = _SLIDE_W
    prs.slide_height = _SLIDE_H
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout

    # ---- title -----------------------------------------------------------
    title_box = slide.shapes.add_textbox(Inches(0.35), Inches(0.2), Inches(6.5), Inches(1.0))
    tf = title_box.text_frame
    tf.word_wrap = True
    _set_text(tf, [
        ("Design Phase Organisation Chart", 20, True, _DARK_TEXT),
        ((client_name or "").strip() or "[Client / Department]", 12, False, _GREY_TEXT),
        (_project_line(tender_name, project_name), 12, False, _GREY_TEXT),
    ], align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)

    # ---- resourcing lookups -----------------------------------------------
    mgmt_by_slot = {}
    # [slot, lead_name, [(support_name, support_title), ...]] in first-seen
    # order, one entry per slot. A support member (see
    # resourcing.ResourceAssignment.custom_title) is anyone added under a
    # discipline lead -- shown as an extra row on that lead's own card.
    disciplines = []
    slot_index = {}
    for a in resource_plan or []:
        slot = (getattr(a, "slot", "") or "").strip()
        name = (getattr(a, "person_name", "") or "").strip()
        if not slot:
            continue
        if slot in _MANAGEMENT_CHAIN:
            if name and not mgmt_by_slot.get(slot):
                mgmt_by_slot[slot] = name
            continue
        is_lead = getattr(a, "is_lead", True)
        if slot not in slot_index:
            slot_index[slot] = len(disciplines)
            disciplines.append([slot, name if is_lead else "", []])
        entry = disciplines[slot_index[slot]]
        if is_lead:
            if name and not entry[1]:
                entry[1] = name
        else:
            title = (getattr(a, "custom_title", "") or "").strip()
            entry[2].append((name, title))

    # ---- management chain -- single vertical stack ------------------------
    cx = _SLIDE_W // 2
    mgmt_x = cx - _MGMT_W // 2

    client_y = Inches(0.25)
    _management_box(slide, mgmt_x, client_y, "Client Project Manager",
                     mgmt_by_slot.get("Client Project Manager", ""), _BLACK)

    pd_y = Emu(client_y + _MGMT_H + _MGMT_ROW_GAP)
    _management_box(slide, mgmt_x, pd_y, "Project Director",
                     mgmt_by_slot.get("Project Director", ""), palette["mgmt"], palette["mgmt_text"])

    pm_y = Emu(pd_y + _MGMT_H + _MGMT_ROW_GAP)
    _management_box(slide, mgmt_x, pm_y, "Project Manager",
                     mgmt_by_slot.get("Project Manager", ""), palette["mgmt"], palette["mgmt_text"])

    dm_y = Emu(pm_y + _MGMT_H + _MGMT_ROW_GAP)
    _management_box(slide, mgmt_x, dm_y, "Design Manager",
                     mgmt_by_slot.get("Design Manager", ""), palette["mgmt"], palette["mgmt_text"])

    for top_y, bottom_y in (
        (Emu(client_y + _MGMT_H), pd_y),
        (Emu(pd_y + _MGMT_H), pm_y),
        (Emu(pm_y + _MGMT_H), dm_y),
    ):
        _connector(slide, MSO_CONNECTOR.STRAIGHT, cx, top_y, cx, bottom_y)

    # ---- Peer Review box, top-right: one line per discipline ---------------
    _add_peer_review_box(slide, [slot for slot, _name, _supports in disciplines],
                          top=Inches(0.25), bottom_limit=Emu(dm_y + _MGMT_H), palette=palette)

    # ---- discipline cards -- symmetric, fully data-driven, wraps to more
    # rows rather than shrinking past legibility -------------------------
    n = len(disciplines)
    bottom_y = Emu(dm_y + _MGMT_H)
    if n:
        available = _SLIDE_W - 2 * _COL_MARGIN
        max_cols_per_row = max(1, int((available + _MIN_GAP) // (_DISC_W_MIN + _MIN_GAP)))
        num_rows = -(-n // max_cols_per_row)  # ceil
        cols_per_row = -(-n // num_rows)  # ceil, balanced across rows

        rows = [disciplines[i:i + cols_per_row] for i in range(0, n, cols_per_row)]

        prev_bottom_y = Emu(dm_y + _MGMT_H)
        for row in rows:
            row_n = len(row)
            disc_w = _DISC_W_DEFAULT
            if row_n * disc_w + (row_n - 1) * _MIN_GAP > available:
                disc_w = Emu(int((available - (row_n - 1) * _MIN_GAP) / row_n))
            total_w = row_n * disc_w + (row_n - 1) * _MIN_GAP if row_n > 1 else disc_w
            start_x = Emu(int((_SLIDE_W - total_w) / 2))
            spine_y = Emu(prev_bottom_y + _ROW_GAP // 2)
            disc_y = Emu(spine_y + Inches(0.22))

            col_centers = []
            row_bottom_y = Emu(disc_y + _DISC_HEADER_H + _DISC_ROLE_H)
            x = start_x
            for slot, name, supports in row:
                header = _rect(slide, x, disc_y, disc_w, _DISC_HEADER_H, palette["header"])
                _set_text(header.text_frame, [(slot, 10, True, palette["header_text"])])
                lead_y = Emu(disc_y + _DISC_HEADER_H)
                lead_box = _rect(slide, x, lead_y, disc_w, _DISC_ROLE_H, palette["body"], line_color=_BORDER_COLOR)
                _set_text(lead_box.text_frame, [("Lead", 8, True, _GREY_TEXT), _name_or_tbc(name)])
                card_bottom = Emu(lead_y + _DISC_ROLE_H)
                # Support rows: one extra thin row per team member added under
                # this lead, name + their own title (never invented -- "Team
                # member" only if the user hasn't typed a title yet).
                for support_name, support_title in supports:
                    support_box = _rect(slide, x, card_bottom, disc_w, _DISC_ROLE_H,
                                         palette["body"], line_color=_BORDER_COLOR)
                    _set_text(support_box.text_frame, [
                        _title_or_confirm(support_title), _name_or_tbc(support_name),
                    ])
                    card_bottom = Emu(card_bottom + _DISC_ROLE_H)
                row_bottom_y = Emu(max(row_bottom_y, card_bottom))
                col_centers.append(Emu(x + disc_w // 2))
                x = Emu(x + disc_w + _MIN_GAP)

            _connector(slide, MSO_CONNECTOR.STRAIGHT, cx, prev_bottom_y, cx, spine_y)
            if len(col_centers) > 1:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, col_centers[0], spine_y, col_centers[-1], spine_y)
            for ccx in col_centers:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, ccx, spine_y, ccx, disc_y)

            prev_bottom_y = row_bottom_y

        bottom_y = prev_bottom_y

    # Grow the slide to fit everything rather than cramming it -- a taller
    # slide is a normal, expected thing in PowerPoint; illegible text isn't.
    needed_height = Emu(bottom_y + Inches(0.3))
    if needed_height > prs.slide_height:
        prs.slide_height = needed_height

    buffer = io.BytesIO()
    prs.save(buffer)
    buffer.seek(0)
    return buffer.read()
