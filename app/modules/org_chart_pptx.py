"""
org_chart_pptx.py

Builds the org chart PowerPoint FROM SCRATCH, straight from a project's
resourcing plan -- no template file to edit or keep in sync -- in whichever
of the four approved presentation styles the user picked.

An earlier version worked by surgically editing a fixed template: filling in
[Name] placeholders, deleting boxes for disciplines not on this project,
adding ad hoc boxes for disciplines the template had no box for. That kept
breaking in new ways as real projects were tried against it -- a deleted box
left its connector dangling, a discipline outside the template's fixed
allowlist got exiled to a disconnected strip, removing boxes left the rest
asymmetrically spaced. Every fix was another special case bolted onto a
fundamentally static layout.

The version after that had no static layout, but it did have one hardcoded
look, and one hardcoded four-box management chain. This one has neither. It
builds from the shared model in modules/org_chart_render.py -- the SAME
object the on-screen preview and the pack's embedded chart render from, so
they cannot show different teams -- and dispatches to one of four style
renderers. Every row comes from the plan: 2 disciplines or 9, with or
without a Design Manager, with or without a reviewer. Columns wrap to
further rows rather than shrinking past legibility, and the slide grows
rather than storing its last row off the bottom edge (which PowerPoint
renders as simply not there).

Everything is native PowerPoint shapes, not a pasted picture: the point of
the companion deck is that it can be tidied up further in PowerPoint.

Nothing here is invented. An unassigned slot is a dashed red TBC. A role the
user removed is absent, with no TBC -- deliberate absence is not a gap. A
person's card shows exactly two lines, name and role/title -- qualifications
never appear here (see the Word pack's Key Personnel profiles for those). An
assurance element (a dedicated reviewer role) appears only where the plan
actually holds one; the separate Peer Review element -- one row per
discipline against its nominated reviewer, red TBC until one is entered --
is unconditional, appearing in every style whenever the plan has at least
one discipline, because every discipline's work needs a reviewer eventually,
not only once one has been named.
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


# ---------------------------------------------------------------------------
# Four presentation styles -- see modules/org_chart_render.py, which holds the
# shared model and draws the same four styles as PNGs for the preview and the
# pack. The shapes below are built from that SAME model object, so the deck
# cannot show a different team from the one the user approved on screen.
#
# Everything is native PowerPoint shapes, not a pasted picture: the point of
# the companion deck is that it can be tidied up further in PowerPoint.
# ---------------------------------------------------------------------------

_STYLE_MARGIN = Inches(0.35)
_CARD_EDGE = RGBColor(0xE4, 0xE8, 0xEF)
_CLIENT_DARK = RGBColor(0x13, 0x1A, 0x2A)
_INK = RGBColor(0x11, 0x18, 0x27)
_MUTED = RGBColor(0x7A, 0x85, 0x98)
_TBC_FILL = RGBColor(0xFE, 0xF2, 0xF2)
_ASSURANCE_AMBER = RGBColor(0xB4, 0x53, 0x09)
_ASSURANCE_FILL = RGBColor(0xFF, 0xF7, 0xED)
_LANE_FILL = RGBColor(0xF7, 0xF9, 0xFC)


def _hex(value: str) -> RGBColor:
    return RGBColor.from_string(str(value).lstrip("#").upper())


def _round(slide, x, y, w, h, fill, line=None, dashed=False, radius=0.14):
    from pptx.enum.dml import MSO_LINE_DASH_STYLE

    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                   Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
    try:
        shape.adjustments[0] = radius
    except (IndexError, KeyError):
        pass
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = Pt(1.0)
        if dashed:
            shape.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    shape.shadow.inherit = False
    return shape


def _bar(slide, x, y, w, h, fill):
    return _rect(slide, Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)), fill)


def _circle(slide, cx, cy, d, fill, text, text_colour):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Emu(int(cx - d / 2)), Emu(int(cy - d / 2)),
                                   Emu(int(d)), Emu(int(d)))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    shape.shadow.inherit = False
    _set_text(shape.text_frame, [(text, 9, True, text_colour)], align=PP_ALIGN.CENTER)
    # An oval's text frame insets are wide enough that two initials wrapped
    # onto two lines -- "AD" came out as "A" over "D".
    frame = shape.text_frame
    frame.word_wrap = False
    frame.margin_left = Pt(0)
    frame.margin_right = Pt(0)
    frame.margin_top = Pt(0)
    frame.margin_bottom = Pt(0)
    return shape


def _stack(slide, x, y, w, h, lines, align=PP_ALIGN.LEFT):
    """A textbox holding a person's stacked lines, vertically centred."""
    box = slide.shapes.add_textbox(Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(int(h)))
    _set_text(box.text_frame, lines, align=align)
    return box


def _person_lines(person, role_colour: RGBColor):
    """The (text, size, bold, colour) rows for one person -- ALWAYS exactly
    two: name (or "TBC"), then role/title. Qualifications are deliberately
    never drawn on the chart (see org_chart_render's module docstring); a
    full CV sentence on a card overflowed the card and collided with
    whatever sat above it."""
    if person.is_tbc:
        return [("TBC", 11, True, _RED_TBC),
                (person.role or "", 8.5, True, _RED_TBC)]
    lines = [(person.name, 11, True, _INK)]
    if person.role:
        if person.role_is_placeholder:
            colour = _RED_TBC
        else:
            colour = role_colour if person.is_lead else _GREY_TEXT
        lines.append((person.role, 8.5, True, colour))
    return lines


def _title_block(slide, model, style_note: str = ""):
    box = slide.shapes.add_textbox(_STYLE_MARGIN, Inches(0.22),
                                   Emu(int(_SLIDE_W - 2 * _STYLE_MARGIN)), Inches(0.7))
    box.text_frame.word_wrap = True
    _set_text(box.text_frame, [("Project organisation", 20, True, _DARK_TEXT)],
              align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    if model.heading:
        right = slide.shapes.add_textbox(Emu(int(_SLIDE_W / 2)), Inches(0.24),
                                         Emu(int(_SLIDE_W / 2 - _STYLE_MARGIN)), Inches(0.32))
        _set_text(right.text_frame, [(model.heading, 11, True, _GREY_TEXT)],
                  align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.TOP)
    return int(Inches(0.95))


def _grow(prs, needed: float) -> None:
    """A taller slide is a normal thing to paste from; a chart whose last row
    is stored off the bottom edge -- which PowerPoint renders as simply not
    there -- is not."""
    if int(needed) > int(prs.slide_height):
        prs.slide_height = Emu(int(needed))


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


def _wrap_columns(count: int, available: float, min_w: float, gap: float, max_w: float):
    """How many columns fit per row, and how wide they are, without squeezing
    any of them below a legible width. Past a handful of disciplines a single
    row makes every card too narrow to hold a name, so wrap instead."""
    count = max(1, count)
    per_row = max(1, int((available + gap) // (min_w + gap)))
    rows = -(-count // per_row)
    per_row = -(-count // rows)
    width = min(max_w, (available - (per_row - 1) * gap) / per_row)
    return per_row, width


def _client_label(model) -> tuple[str, RGBColor]:
    name = (model.client_name or "").strip()
    return (name or "[CLIENT NAME]", _WHITE if name else _RED_TBC_ON_DARK)


def _peer_review_panel(slide, x, y, w, model) -> int:
    """A bordered "Peer Review" panel: one row per discipline against its
    nominated reviewer (resourcing.ResourceAssignment.peer_reviewer, on the
    discipline's lead row), red TBC until one is entered. Unconditional
    whenever the plan has at least one discipline -- see
    org_chart_render's module docstring for why this, unlike the assurance
    strip, never depends on whether a reviewer has been named yet. Returns
    the panel's bottom y (EMU) so callers can make sure whatever comes next
    clears it rather than overlapping it."""
    if not model.disciplines:
        return int(y)
    row_h = int(Inches(0.30))
    title_h = int(Inches(0.26))
    panel_h = title_h + row_h * len(model.disciplines)
    _round(slide, Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(panel_h),
           _ASSURANCE_FILL, line=_ASSURANCE_AMBER, radius=0.05)
    _stack(slide, Emu(int(x)), Emu(int(y)), Emu(int(w)), Emu(title_h),
           [("PEER REVIEW", 9, True, _ASSURANCE_AMBER)], align=PP_ALIGN.CENTER)
    row_y = int(y) + title_h
    pad = int(Inches(0.08))
    for group in model.disciplines:
        reviewer = (group.peer_reviewer or "").strip()
        tbc = not reviewer
        _stack(slide, Emu(int(x + pad)), Emu(row_y), Emu(int(w * 0.56 - pad)), Emu(row_h),
               [(group.name, 8.5, True, _INK)], align=PP_ALIGN.LEFT)
        _stack(slide, Emu(int(x + w * 0.56)), Emu(row_y), Emu(int(w * 0.44 - pad)), Emu(row_h),
               [(reviewer or "TBC", 8.5, True, _RED_TBC if tbc else _ASSURANCE_AMBER)],
               align=PP_ALIGN.RIGHT)
        row_y += row_h
    return int(y) + panel_h


# --- A. Executive cards ----------------------------------------------------

def _slide_cards(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    y = _title_block(slide, model)

    centre = int(_SLIDE_W / 2)
    card_w, card_h = Inches(2.5), Inches(0.72)
    gap = Inches(0.22)

    client_w, client_h = Inches(2.9), Inches(0.5)
    _round(slide, centre - client_w / 2, y, client_w, client_h, _CLIENT_DARK)
    label, colour = _client_label(model)
    _stack(slide, centre - client_w / 2, y, client_w, client_h,
           [(label, 12, True, colour), (model.client_role, 8, True, _GREY_TEXT)],
           align=PP_ALIGN.CENTER)
    y += int(client_h)

    def card(x, top, w, person, badge=""):
        tbc = person.is_tbc
        _round(slide, x, top, w, card_h,
               _TBC_FILL if tbc else _WHITE,
               line=_RED_TBC if tbc else _CARD_EDGE, dashed=tbc)
        bar_colour = _ASSURANCE_AMBER if badge else accent
        if not tbc and person.is_lead:
            _bar(slide, x + Inches(0.06), top + Inches(0.02), w - Inches(0.12),
                 Inches(0.05), bar_colour)
        if badge and not tbc:
            _round(slide, x + w * 0.5, top - Inches(0.06), w * 0.5, Inches(0.19),
                   _ASSURANCE_FILL, line=_ASSURANCE_AMBER, radius=0.3)
            _stack(slide, x + w * 0.5, top - Inches(0.06), w * 0.5, Inches(0.19),
                   [(badge.upper(), 7, True, _ASSURANCE_AMBER)], align=PP_ALIGN.CENTER)
        avatar = Inches(0.34)
        _circle(slide, x + Inches(0.30), top + card_h / 2, avatar,
                _TBC_FILL if tbc else _tint(bar_colour, 0.86),
                person.initials, _RED_TBC if tbc else bar_colour)
        _stack(slide, x + Inches(0.52), top, w - Inches(0.6), card_h,
               _person_lines(person, bar_colour))

    leadership = list(model.leadership)
    top_person = leadership.pop(0) if leadership else None
    if top_person is not None:
        y += int(Inches(0.22))
        _connector(slide, MSO_CONNECTOR.STRAIGHT, centre, y - Inches(0.22), centre, y)
        card(centre - card_w / 2, y, card_w, top_person)
        y += int(card_h)

    rank = [(person, "") for person in leadership]
    rank += [(person, "QA / Review") for person in model.assurance]
    if rank:
        y += int(Inches(0.28))
        _connector(slide, MSO_CONNECTOR.STRAIGHT, centre, y - Inches(0.28), centre, y)
        # Wrapped like the discipline columns below, rather than one
        # fixed-width row -- several co-leads plus a reviewer could
        # otherwise run the end cards off the slide's left/right edge.
        available = int(_SLIDE_W - 2 * _STYLE_MARGIN)
        per_row, rank_w = _wrap_columns(len(rank), available, int(Inches(2.15)), int(gap), int(card_w))
        rank_chunks = [rank[i:i + per_row] for i in range(0, len(rank), per_row)]
        for chunk in rank_chunks:
            total = len(chunk) * rank_w + (len(chunk) - 1) * int(gap)
            x = int(centre - total / 2)
            for person, badge in chunk:
                card(x, y, rank_w, person, badge=badge)
                x += rank_w + int(gap)
            y += int(card_h + Inches(0.12))
        y -= int(Inches(0.12))  # undo the last row's trailing gap

    # Peer Review panel, top-right -- unconditional whenever the plan has at
    # least one discipline. Anchored under the title rather than the
    # flowing cursor above, so it never depends on how tall the leadership
    # rows happened to be -- but the discipline columns below still have to
    # start below it, not underneath it.
    panel_w = int(Inches(3.4))
    panel_bottom = _peer_review_panel(
        slide, int(_SLIDE_W - _STYLE_MARGIN - panel_w), int(Inches(0.95)), panel_w, model)
    y = max(y, panel_bottom)

    if model.disciplines:
        available = int(_SLIDE_W - 2 * _STYLE_MARGIN)
        per_row, col_w = _wrap_columns(len(model.disciplines), available,
                                       int(Inches(2.15)), int(gap), int(card_w))
        chunks = [model.disciplines[i:i + per_row]
                  for i in range(0, len(model.disciplines), per_row)]
        for chunk_index, chunk in enumerate(chunks):
            bus_y = y + int(Inches(0.26))
            if chunk_index == 0:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, centre, y, centre, bus_y)
            total = len(chunk) * col_w + (len(chunk) - 1) * int(gap)
            x = int(_SLIDE_W / 2 - total / 2)
            centres = []
            row_bottom = bus_y
            for group in chunk:
                centres.append(int(x + col_w / 2))
                _stack(slide, x, bus_y + Inches(0.04), col_w, Inches(0.22),
                       [(group.name.upper(), 9, True, _MUTED)], align=PP_ALIGN.CENTER)
                card_y = bus_y + int(Inches(0.28))
                for person in group.people:
                    card(x, card_y, col_w, person)
                    card_y += int(card_h + Inches(0.12))
                row_bottom = max(row_bottom, card_y)
                x += col_w + int(gap)
            if len(centres) > 1:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, min(centres), bus_y,
                           max(centres), bus_y)
            for column_centre in centres:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, column_centre, bus_y,
                           column_centre, bus_y + Inches(0.04))
            y = row_bottom + int(Inches(0.10))

    _grow(prs, y + Inches(0.3))
    return _save(prs)


# --- B. Discipline columns -------------------------------------------------

def _slide_columns(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    y = _title_block(slide, model)

    centre = int(_SLIDE_W / 2)
    pill_h = Inches(0.46)
    client_w = Inches(3.6)
    _round(slide, centre - client_w / 2, y, client_w, pill_h, _CLIENT_DARK, radius=0.2)
    label, colour = _client_label(model)
    _stack(slide, centre - client_w / 2, y, client_w, pill_h,
           [(f"{label} — Client", 12, True, colour)], align=PP_ALIGN.CENTER)
    y += int(pill_h)

    for index, person in enumerate(model.leadership):
        y += int(Inches(0.2))
        _connector(slide, MSO_CONNECTOR.STRAIGHT, centre, y - Inches(0.2), centre, y)
        width = Inches(3.2) if index == 0 else Inches(2.6)
        fill = accent if index == 0 else _tint(accent, 0.18)
        tbc = person.is_tbc
        _round(slide, centre - width / 2, y, width, pill_h,
               _TBC_FILL if tbc else fill,
               line=_RED_TBC if tbc else None, dashed=tbc, radius=0.2)
        sub = person.role
        _stack(slide, centre - width / 2, y, width, pill_h,
               [(person.name or "TBC", 12, True, _RED_TBC if tbc else _text_on(fill)),
                (sub, 9, True, _RED_TBC if tbc else _text_on(fill))],
               align=PP_ALIGN.CENTER)
        y += int(pill_h)

    if model.disciplines:
        y += int(Inches(0.3))
        gap = int(Inches(0.16))
        available = int(_SLIDE_W - 2 * _STYLE_MARGIN)
        per_row, lane_w = _wrap_columns(len(model.disciplines), available,
                                        int(Inches(2.3)), gap, int(Inches(3.0)))
        chunks = [model.disciplines[i:i + per_row]
                  for i in range(0, len(model.disciplines), per_row)]
        row_h = Inches(0.62)
        for chunk in chunks:
            total = len(chunk) * lane_w + (len(chunk) - 1) * gap
            x = int(_SLIDE_W / 2 - total / 2)
            tallest = max(len(g.people) for g in chunk)
            lane_h = int(Inches(0.36) + tallest * (row_h + Inches(0.1)) + Inches(0.1))
            for group in chunk:
                colour = _hex(_discipline_colour_for(model, group))
                _round(slide, x, y, lane_w, lane_h, _LANE_FILL, radius=0.06)
                _bar(slide, x, y, lane_w, Inches(0.06), colour)
                _stack(slide, x, y + Inches(0.06), lane_w, Inches(0.28),
                       [(group.name.upper(), 10, True, colour)], align=PP_ALIGN.CENTER)
                card_y = y + int(Inches(0.38))
                for person in group.people:
                    tbc = person.is_tbc
                    _round(slide, x + Inches(0.1), card_y, lane_w - Inches(0.2), row_h,
                           _TBC_FILL if tbc else _WHITE,
                           line=_RED_TBC if tbc else _CARD_EDGE, dashed=tbc, radius=0.1)
                    _stack(slide, x + Inches(0.1), card_y, lane_w - Inches(0.2), row_h,
                           _person_lines(person, colour), align=PP_ALIGN.CENTER)
                    card_y += int(row_h + Inches(0.1))
                x += lane_w + gap
            y += lane_h + int(Inches(0.16))

    # The amber independent-review strip, ONLY when the plan holds such a slot.
    if model.assurance:
        y += int(Inches(0.2))
        strip_w, strip_h = Inches(6.4), Inches(0.44)
        _round(slide, centre - strip_w / 2, y, strip_w, strip_h, _ASSURANCE_FILL,
               line=RGBColor(0xFB, 0xBF, 0x24), radius=0.2)
        text = " · ".join(f"{p.name or 'TBC'} — {p.role}" for p in model.assurance)
        _stack(slide, centre - strip_w / 2, y, strip_w, strip_h,
               [(f"★ Independent review: {text}", 10, True, _ASSURANCE_AMBER)],
               align=PP_ALIGN.CENTER)
        y += int(strip_h)

    # A right-hand-panel equivalent, unconditional (see the module docstring):
    # every discipline against its nominated peer reviewer, red TBC until one
    # is entered -- separate from the amber strip above, which only exists
    # for a dedicated reviewer role.
    if model.disciplines:
        y += int(Inches(0.2))
        panel_w = Inches(6.4)
        panel_bottom = _peer_review_panel(slide, int(centre - panel_w / 2), int(y), int(panel_w), model)
        y = panel_bottom

    _grow(prs, y + Inches(0.3))
    return _save(prs)


def _discipline_colour_for(model, group) -> str:
    from modules.org_chart_render import DISCIPLINE_COLOURS

    index = group.people[0].group_index if group.people else model.disciplines.index(group)
    return DISCIPLINE_COLOURS[index % len(DISCIPLINE_COLOURS)]


# --- C. Governance bands ---------------------------------------------------

def _slide_bands(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    y = _title_block(slide, model)

    label_w = Inches(1.5)
    band_x = int(_STYLE_MARGIN + label_w)
    band_w = int(_SLIDE_W - _STYLE_MARGIN - band_x)
    chip_h = Inches(0.62)
    chip_gap = int(Inches(0.12))
    pad = int(Inches(0.12))

    def band(title, chips, fill, chip_edge=_CARD_EDGE):
        nonlocal y
        if not chips:
            return
        widths = [min(int(Inches(2.7)),
                      max(int(Inches(1.5)), int(Inches(0.35) + Inches(0.085) * max(
                          len(name), len(role)))))
                  for name, role, *_rest in chips]
        rows, used = [[]], 0
        for index, width in enumerate(widths):
            if rows[-1] and used + width + chip_gap > band_w - 2 * pad:
                rows.append([])
                used = 0
            rows[-1].append(index)
            used += width + chip_gap
        band_h = int(2 * pad + len(rows) * chip_h + (len(rows) - 1) * chip_gap)
        _round(slide, band_x, y, band_w, band_h, fill, radius=0.06)
        _stack(slide, _STYLE_MARGIN, y, label_w - Inches(0.12), band_h,
               [(title.upper(), 9, True, _MUTED)], align=PP_ALIGN.RIGHT)
        chip_y = y + pad
        for row in rows:
            x = band_x + pad
            for index in row:
                name, role, tbc, role_colour = chips[index]
                width = widths[index]
                _round(slide, x, chip_y, width, chip_h,
                       _TBC_FILL if tbc else _WHITE,
                       line=_RED_TBC if tbc else chip_edge, dashed=tbc, radius=0.1)
                lines = [(name, 10.5, True, _RED_TBC if tbc else _INK),
                         (role, 8.5, True, _RED_TBC if tbc else role_colour)]
                _stack(slide, x, chip_y, width, chip_h, [l for l in lines if l[0]])
                x += width + chip_gap
            chip_y += int(chip_h + chip_gap)
        y += band_h + int(Inches(0.16))

    band("Client", [(_client_label(model)[0], model.client_role, False, _MUTED)],
         _CLIENT_DARK, chip_edge=_CLIENT_DARK)
    band("Leadership",
         [(p.name or "TBC", p.role, p.is_tbc, accent) for p in model.leadership],
         _tint(accent, 0.94))
    delivery = []
    for group in model.disciplines:
        colour = _hex(_discipline_colour_for(model, group))
        for person in group.people:
            role = (person.role if person.role.startswith(group.name)
                    else f"{person.role} · {group.name}")
            delivery.append((person.name or "TBC", role, person.is_tbc,
                             colour if person.is_lead else _GREY_TEXT))
    from modules.org_chart_render import DISCIPLINE_COLOURS

    band("Delivery team", delivery, _tint(_hex(DISCIPLINE_COLOURS[1]), 0.95))
    # The Assurance band now ALWAYS carries the Peer Review element -- one
    # row per discipline, red TBC until a reviewer is entered -- alongside
    # any dedicated reviewer role the plan holds, so the band appears
    # whenever there is at least one discipline rather than only once a
    # reviewer slot exists.
    assurance_chips = [(p.name or "TBC", p.role, p.is_tbc, _ASSURANCE_AMBER) for p in model.assurance]
    assurance_chips += [
        (group.peer_reviewer or "TBC", f"Peer review — {group.name}",
         not bool((group.peer_reviewer or "").strip()), _ASSURANCE_AMBER)
        for group in model.disciplines
    ]
    band("Assurance", assurance_chips, _tint(_ASSURANCE_AMBER, 0.93))

    _stack(slide, _STYLE_MARGIN, y, Emu(int(_SLIDE_W - 2 * _STYLE_MARGIN)), Inches(0.3),
           [(("Solid reporting lines run top-down; the assurance band reviews independently "
              "of the delivery team.") if (model.has_assurance or model.disciplines) else
             "Solid reporting lines run top-down.", 9, True, _MUTED)])
    _grow(prs, y + Inches(0.5))
    return _save(prs)


# --- D. Classic tree -------------------------------------------------------

def _slide_tree(model, accent: RGBColor) -> bytes:
    prs, slide = _new_deck()
    y = _title_block(slide, model)

    centre = int(_SLIDE_W / 2)
    box_w, box_h = Inches(2.6), Inches(0.72)
    gap = int(Inches(0.3))

    def box(x, top, w, lines, outline=_INK, tbc=False, width_pt=1.0):
        _round(slide, x, top, w, box_h, _WHITE,
               line=_RED_TBC if tbc else outline, dashed=tbc, radius=0.08)
        _stack(slide, x, top, w, box_h, lines, align=PP_ALIGN.CENTER)

    label, colour = _client_label(model)
    box(centre - box_w / 2, y, box_w,
        [(label, 12, True, _INK if model.client_name else _RED_TBC),
         (model.client_role, 9, True, _GREY_TEXT)])
    y += int(box_h)

    # Tracks the rightmost edge reached by any box at the director level (the
    # top-role box plus however many co-lead/assurance boxes end up in the
    # rank row below it), so the Peer Review box placed beside it (see below)
    # never has to guess how wide that level got and overlap it.
    director_right = int(centre + box_w / 2)

    leadership = list(model.leadership)
    top_person = leadership.pop(0) if leadership else None
    if top_person is not None:
        y += int(Inches(0.26))
        _connector(slide, MSO_CONNECTOR.STRAIGHT, centre, y - Inches(0.26), centre, y)
        box(centre - box_w / 2, y, box_w, _person_lines(top_person, _INK),
            outline=accent, tbc=top_person.is_tbc)
        y += int(box_h)

    rank = leadership + model.assurance
    if rank:
        y += int(Inches(0.28))
        _connector(slide, MSO_CONNECTOR.STRAIGHT, centre, y - Inches(0.28), centre, y)
        # Wrapped rather than one fixed-width row -- several co-leads plus a
        # reviewer could otherwise run the end boxes off the slide edge.
        available = int(_SLIDE_W - 2 * _STYLE_MARGIN)
        per_row, rank_w = _wrap_columns(len(rank), available, int(Inches(2.2)), gap, int(box_w))
        rank_chunks = [rank[i:i + per_row] for i in range(0, len(rank), per_row)]
        for chunk in rank_chunks:
            total = len(chunk) * rank_w + (len(chunk) - 1) * gap
            x = int(centre - total / 2)
            for person in chunk:
                box(x, y, rank_w, _person_lines(person, _INK), tbc=person.is_tbc)
                x += int(rank_w) + gap
            director_right = max(director_right, x - gap)
            y += int(box_h + Inches(0.14))
        y -= int(Inches(0.14))  # undo the last row's trailing gap

    # Peer Review box, to the right of the director level -- unconditional
    # whenever the plan has at least one discipline. Placed clear of
    # whatever the director level actually drew (director_right, tracked
    # above) rather than assuming a fixed width for it -- several co-leads
    # can run wider than a single director box, and a fixed offset collided
    # with them. Anchored to the director row rather than the flowing
    # cursor, so it sits in the same place regardless of how tall the rank
    # row ended up -- but the discipline columns below still have to clear
    # its bottom edge.
    if model.disciplines:
        min_panel_w = int(Inches(2.0))
        panel_x = min(int(_SLIDE_W - _STYLE_MARGIN - min_panel_w), director_right + int(Inches(0.25)))
        panel_w = max(min_panel_w, int(_SLIDE_W - _STYLE_MARGIN - panel_x))
        director_row_top = int(Inches(0.95)) + int(box_h) + int(Inches(0.26))
        panel_bottom = _peer_review_panel(slide, panel_x, director_row_top, panel_w, model)
        y = max(y, panel_bottom)

    if model.disciplines:
        available = int(_SLIDE_W - 2 * _STYLE_MARGIN)
        per_row, col_w = _wrap_columns(len(model.disciplines), available,
                                       int(Inches(2.2)), gap, int(box_w))
        chunks = [model.disciplines[i:i + per_row]
                  for i in range(0, len(model.disciplines), per_row)]
        for chunk_index, chunk in enumerate(chunks):
            bus_y = y + int(Inches(0.28))
            if chunk_index == 0:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, centre, y, centre, bus_y)
            total = len(chunk) * col_w + (len(chunk) - 1) * gap
            x = int(_SLIDE_W / 2 - total / 2)
            centres = []
            row_bottom = bus_y
            for group in chunk:
                centres.append(int(x + col_w / 2))
                box_y = bus_y + int(Inches(0.26))
                for person in group.people:
                    box(x, box_y, col_w, _person_lines(person, _INK), tbc=person.is_tbc)
                    box_y += int(box_h + Inches(0.14))
                row_bottom = max(row_bottom, box_y)
                x += col_w + gap
            if len(centres) > 1:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, min(centres), bus_y,
                           max(centres), bus_y)
            for column_centre in centres:
                _connector(slide, MSO_CONNECTOR.STRAIGHT, column_centre, bus_y,
                           column_centre, bus_y + Inches(0.26))
            y = row_bottom + int(Inches(0.10))

    _grow(prs, y + Inches(0.3))
    return _save(prs)


_STYLE_RENDERERS = {
    "cards": _slide_cards,
    "columns": _slide_columns,
    "bands": _slide_bands,
    "tree": _slide_tree,
}


def _empty_slide(model) -> bytes:
    prs, slide = _new_deck()
    y = _title_block(slide, model)
    _stack(slide, _STYLE_MARGIN, y + Inches(0.4),
           Emu(int(_SLIDE_W - 2 * _STYLE_MARGIN)), Inches(0.6),
           [(_ORG_EMPTY_NOTE, 14, False, _RED_TBC)], align=PP_ALIGN.CENTER)
    return _save(prs)


_ORG_EMPTY_NOTE = ("[NO TEAM ASSIGNED -- add the management roles and discipline leads in "
                   "the Team & Resourcing tab, then re-download this PowerPoint]")


def populate_org_chart(resource_plan: list, client_name: str = "", project_name: str = "",
                       tender_name: str = "", theme_name: str | None = None,
                       style: str | None = None) -> bytes:
    """
    Builds a fresh .pptx (returned as bytes) of the project organisation
    chart, in the user's chosen presentation style.

    `style` is one of org_chart_render.STYLES; anything else (including None)
    falls back to org_chart_render.DEFAULT_STYLE, so the deck always matches
    the style the preview drew.

    Everything comes from `resource_plan` (a list of
    resourcing.ResourceAssignment). An unassigned slot is drawn as a dashed
    red TBC; a role the user REMOVED (see resourcing.OPTIONAL_MANAGEMENT_ROLES)
    is absent from the plan and so absent from the chart, with no TBC --
    deliberate absence is not a gap. An assurance/reviewer element appears
    only where the plan actually holds such a slot; this module never adds
    one. An empty plan renders a placeholder slide rather than a bare chart.
    """
    from modules import org_chart_render

    model = org_chart_render.build_model(resource_plan, client_name, project_name,
                                         tender_name)
    if model.is_empty:
        return _empty_slide(model)
    resolved = org_chart_render.effective_style(
        model, style or org_chart_render.DEFAULT_STYLE)
    accent = _resolve_palette(theme_name)["header"]
    return _STYLE_RENDERERS[resolved](model, accent)
