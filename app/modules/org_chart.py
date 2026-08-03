"""
org_chart.py

Renders a clean, colour-coded project organisation chart as a PNG -- the kind
that goes in the Key Personnel section of a proposal. It is built entirely from
the resourcing plan the user fills in (resourcing.py), never a stock template:

  Client Project Manager            (top -- the client's side of the table)
            |
  Project Director / Project Manager / Design Manager   (the firm's leadership)
            |
  ---- discipline lead boxes ----   (one per required discipline, incl. PM)

Design choices, kept deliberately simple so it always renders:
  - Plain rectangular boxes with name + role/discipline text. No photos (the
    user can drop headshots into the boxes in Word afterwards if they want the
    fuller look).
  - Colour-coded by tier (client / firm leadership / discipline) using the same
    proposal theme palette the dividers use, so it matches the rest of the pack.
  - A slot with no name assigned yet is drawn greyed with "[to be assigned]",
    so an incomplete chart is obvious rather than silently blank.

Never raises: returns PNG bytes, or None on any failure, so a caller can fall
back to a placeholder rather than crash the export.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_CACHE: dict = {}

# Reuse the divider palette so the chart matches the rest of the pack. primary =
# firm leadership boxes, accent = discipline boxes, client box is near-black.
from modules.divider_designer import THEME_COLOURS, _DEFAULT_THEME

CLIENT_BOX = (28, 28, 30)          # near-black, like the client box in the example
UNASSIGNED_BOX = (176, 176, 178)   # grey when no name is set yet
LINE = (150, 150, 150)
WHITE = (255, 255, 255)
PAGE_BG = (250, 250, 251)          # faint off-white canvas instead of flat white
SHADOW = (0, 0, 0)                 # composited at low opacity for a soft drop shadow
SHADOW_OFFSET = (0, 5)
SHADOW_ALPHA = 55
BOX_RADIUS = 14
BORDER_ALPHA = 90                  # thin light border drawn on top of each box for crispness


def render_org_chart(
    assignments: list,
    theme_name: str = _DEFAULT_THEME,
    project_title: str | None = None,
    font_paths: dict | None = None,
    width: int = 2200,
) -> bytes | None:
    """
    Render the org chart from a list of resourcing.ResourceAssignment objects
    (or any objects/dicts exposing slot, slot_kind, person_name, is_lead,
    custom_title). Returns PNG bytes, or None on failure.

    A discipline can carry a lead plus any number of support members added
    under them (see resourcing.ResourceAssignment.custom_title) -- these are
    grouped into ONE box per discipline (_group_disciplines), with the
    support members' names and titles listed under the lead's, in the same
    box, exactly like the client/leadership boxes. Discipline boxes size to
    fit however many support members they carry, so a lead with three people
    under them draws taller than one with none; all boxes in the same row
    still share that row's tallest height, so the row stays visually aligned.

    `font_paths` (optional) lets the caller override the fonts, e.g. to render
    in Arial when the user has picked it in Graphics & Design -- a dict like
    {"regular": "/path/Arial.ttf", "bold": "/path/Arial-Bold.ttf"}. Falls back
    to the bundled DejaVu fonts if not given or if a path can't be loaded.
    """
    try:
        colours = THEME_COLOURS.get(theme_name, THEME_COLOURS[_DEFAULT_THEME])
        firm_colour = colours["primary"]
        disc_colour = colours["accent"]
        line_colour = colours["accent"]  # accent-toned connectors instead of flat grey

        client, leadership, disc_groups = _split_assignments(assignments)

        # Layout metrics -- a touch more generous than a bare utility diagram, so the
        # chart reads as a designed piece of the pack rather than a debug drawing.
        margin = 70
        mgmt_box_h = 138
        v_gap = 100
        title_h = 130 if project_title else 30

        # Discipline boxes wrap across rows of up to `per_row`.
        per_row = max(1, min(5, len(disc_groups) or 1))
        disc_rows = _chunk(disc_groups, per_row)

        img_probe = Image.new("RGB", (10, 10))
        probe_draw = ImageDraw.Draw(img_probe)

        # Total canvas height depends on how many tiers/rows we have, and each
        # discipline row's own height (taller when a box in it carries nested
        # support members) rather than one fixed height for every row.
        rows = 0
        if client:
            rows += 1
        if leadership:
            rows += 1
        row_heights = [mgmt_box_h] * rows
        disc_row_heights = []
        for row in disc_rows:
            box_w = _row_box_width(width - margin * 2, len(row))
            disc_row_heights.append(max(mgmt_box_h, max(
                _group_content_height(g, probe_draw, font_paths, box_w) for g in row
            )))
        row_heights += disc_row_heights
        total_rows = len(row_heights)
        shadow_pad = SHADOW_OFFSET[1] + 6
        height = margin * 2 + title_h + sum(row_heights) + max(0, total_rows - 1) * v_gap + shadow_pad

        img = Image.new("RGB", (width, height), PAGE_BG)
        draw = ImageDraw.Draw(img)

        y = margin
        if project_title:
            title_font = _font(font_paths, bold=True, size=48)
            _draw_text_center(draw, project_title, width // 2, y + 34, title_font, (32, 32, 34))
            _draw_text_center(draw, "Project Organisation Chart", width // 2, y + 74,
                              _font(font_paths, bold=False, size=24), (110, 110, 114))
            bar_w = 160
            bar_y = y + 100
            draw.rounded_rectangle(
                [width // 2 - bar_w // 2, bar_y, width // 2 + bar_w // 2, bar_y + 5],
                radius=3, fill=colours["accent"],
            )
            y += title_h
        else:
            y += 10

        content_w = width - margin * 2
        centres_by_tier = []  # remember box centre points to draw connectors

        # Tier 1: client PM (single centred box).
        if client:
            cx = width // 2
            box_w = min(760, content_w // 2)
            _draw_box(draw, cx - box_w // 2, y, box_w, mgmt_box_h,
                      CLIENT_BOX if _has_name(client) else UNASSIGNED_BOX,
                      {"lead": client, "supports": []}, font_paths)
            centres_by_tier.append([(cx, y, y + mgmt_box_h)])
            y += mgmt_box_h + v_gap

        # Tier 2: firm leadership row.
        if leadership:
            centres = _draw_row(draw, [{"lead": a, "supports": []} for a in leadership],
                                 margin, y, content_w, mgmt_box_h, firm_colour, font_paths)
            centres_by_tier.append([(cx, y, y + mgmt_box_h) for cx in centres])
            y += mgmt_box_h + v_gap

        # Tier 3+: discipline rows, one box per discipline (lead + any nested
        # support members), each row sized to its tallest box.
        disc_tier_centres = []
        for row, row_h in zip(disc_rows, disc_row_heights):
            centres = _draw_row(draw, row, margin, y, content_w, row_h, disc_colour, font_paths)
            disc_tier_centres.append([(cx, y, y + row_h) for cx in centres])
            y += row_h + v_gap

        _draw_connectors(draw, centres_by_tier, disc_tier_centres, width, line_colour)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Assignment handling
# ---------------------------------------------------------------------------

def _get(a, key, default=""):
    if isinstance(a, dict):
        return a.get(key, default)
    return getattr(a, key, default)


def _split_assignments(assignments: list):
    """Return (client_pm_or_None, [leadership], [discipline_groups]) from the
    plan. Each discipline group is {"lead": assignment | None, "supports":
    [assignment, ...]} -- one group per discipline slot, in first-appearance
    order, so a lead and anyone added under them (see
    resourcing.ResourceAssignment.custom_title) become a single box rather
    than one box per row of the plan."""
    client = None
    leadership = []
    groups: dict[str, dict] = {}
    order: list[str] = []
    for a in assignments or []:
        kind = _get(a, "slot_kind", "discipline")
        slot = _get(a, "slot", "")
        if kind == "management":
            if slot == "Client Project Manager":
                client = a
            else:
                leadership.append(a)
            continue
        if slot not in groups:
            groups[slot] = {"lead": None, "supports": []}
            order.append(slot)
        if _get(a, "is_lead", True) and groups[slot]["lead"] is None:
            groups[slot]["lead"] = a
        else:
            groups[slot]["supports"].append(a)
    return client, leadership, [groups[s] for s in order]


def _has_name(a) -> bool:
    return a is not None and bool((_get(a, "person_name", "") or "").strip())


def _role_label(a) -> str:
    """Display title for one assignment -- a support member's own custom
    title if they have one (see resourcing.role_label, mirrored here so this
    module stays decoupled from resourcing.py's imports), falling back to the
    slot for a lead or an untitled support member."""
    if not _get(a, "is_lead", True) and (_get(a, "custom_title", "") or "").strip():
        return (_get(a, "custom_title", "") or "").strip()
    return _get(a, "slot", "")


def _row_box_width(content_w: int, n: int, gap: int = 40) -> int:
    return (content_w - gap * (n - 1)) // max(1, n)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

# Fixed per-line heights (not adaptive-shrink like a single-assignment box
# could get away with) -- a box now sizes ITSELF to fit its content (see
# _group_content_height), so text never needs to be squeezed smaller than
# these to fit; a lead with several support members underneath just gets a
# taller box, and the rest of that row matches it.
_ROLE_LINE_H = 36
_NAME_LINE_H = 32
_SUPPORT_LINE_H = 28
_SPACER_H = 20


def _group_content(group: dict, draw, font_paths, box_w: int):
    """Wrapped text + fonts for one discipline box: the lead's role/name, plus
    one wrapped line per support member ("Name -- Title"). `group["lead"]` may
    be None (support members whose lead row is somehow missing) -- the role
    line then falls back to the first support's own slot so the box is never
    unlabelled."""
    lead = group.get("lead")
    supports = group.get("supports") or []
    role = _get(lead, "slot", "") if lead is not None else (_get(supports[0], "slot", "") if supports else "")
    role_font = _font(font_paths, bold=True, size=30)
    name_font = _font(font_paths, bold=False, size=28)
    support_font = _font(font_paths, bold=False, size=23)

    role_wrapped = _wrap(draw, role, role_font, box_w - 30)
    lead_name = (_get(lead, "person_name", "") or "").strip() if lead is not None else ""
    name_wrapped = _wrap(draw, lead_name or "[to be assigned]", name_font, box_w - 30)

    support_wrapped: list[str] = []
    for s in supports:
        sname = (_get(s, "person_name", "") or "").strip() or "[to be assigned]"
        stitle = _role_label(s) or "Team member"
        support_wrapped.extend(_wrap(draw, f"{sname} — {stitle}", support_font, box_w - 30))

    return role_wrapped, name_wrapped, support_wrapped, role_font, name_font, support_font


def _group_content_height(group: dict, draw, font_paths, box_w: int) -> int:
    """The box height needed to fit `group`'s content at the fixed per-line
    heights above, plus top/bottom padding."""
    role_wrapped, name_wrapped, support_wrapped, *_ = _group_content(group, draw, font_paths, box_w)
    total = len(role_wrapped) * _ROLE_LINE_H + _SPACER_H + len(name_wrapped) * _NAME_LINE_H
    if support_wrapped:
        total += _SPACER_H // 2 + len(support_wrapped) * _SUPPORT_LINE_H
    return total + 40  # top + bottom padding


def _draw_row(draw, groups, left, y, content_w, box_h, colour, font_paths) -> list[int]:
    """Draw a horizontal row of equally-spaced boxes, one per discipline
    group (or per single-assignment group for the client/leadership tiers);
    return their centre-x."""
    n = len(groups)
    gap = 40
    box_w = _row_box_width(content_w, n, gap)
    centres = []
    x = left
    for group in groups:
        fill = colour if _has_name(group.get("lead")) else UNASSIGNED_BOX
        _draw_box(draw, x, y, box_w, box_h, fill, group, font_paths)
        centres.append(x + box_w // 2)
        x += box_w + gap
    return centres


def _draw_box(draw, x, y, w, h, fill, group, font_paths):
    # Soft drop shadow first (a slightly darker, offset duplicate of the box shape),
    # then the real box on top with a thin light border for a crisper, less flat edge.
    sx, sy = SHADOW_OFFSET
    shadow_colour = (205, 205, 209)
    draw.rounded_rectangle([x + sx, y + sy, x + w + sx, y + h + sy], radius=BOX_RADIUS, fill=shadow_colour)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=BOX_RADIUS, fill=fill)
    border_colour = tuple(min(255, c + 28) for c in fill)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=BOX_RADIUS, outline=border_colour, width=2)

    role_wrapped, name_wrapped, support_wrapped, role_font, name_font, support_font = \
        _group_content(group, draw, font_paths, w)

    cx = x + w // 2
    total_h = (len(role_wrapped) * _ROLE_LINE_H + _SPACER_H + len(name_wrapped) * _NAME_LINE_H)
    if support_wrapped:
        total_h += _SPACER_H // 2 + len(support_wrapped) * _SUPPORT_LINE_H
    ty = y + max(10, (h - total_h) // 2)

    for ln in role_wrapped:
        _draw_text_center(draw, ln, cx, ty + _ROLE_LINE_H // 2, role_font, WHITE)
        ty += _ROLE_LINE_H
    ty += _SPACER_H
    for ln in name_wrapped:
        _draw_text_center(draw, ln, cx, ty + _NAME_LINE_H // 2, name_font, WHITE)
        ty += _NAME_LINE_H
    if support_wrapped:
        ty += _SPACER_H // 2
        for ln in support_wrapped:
            _draw_text_center(draw, ln, cx, ty + _SUPPORT_LINE_H // 2, support_font, (232, 232, 236))
            ty += _SUPPORT_LINE_H


def _draw_connectors(draw, top_tiers: list, disc_tiers: list, width: int, line_colour=LINE):
    """Draw simple elbow connectors: client -> leadership -> a horizontal bus ->
    each discipline box, with a small filled node dot at every junction so the
    chart reads as a deliberate diagram rather than loose lines. Kept schematic;
    exact routing isn't important, clarity is."""
    # client -> leadership
    if len(top_tiers) >= 2:
        client_c = top_tiers[0][0]
        end_y = top_tiers[1][0][1] if top_tiers[1] else client_c[2]
        _v_line(draw, client_c[0], client_c[2], end_y, line_colour)
        _node(draw, client_c[0], client_c[2], line_colour)
    # leadership -> discipline bus
    if top_tiers:
        anchor = top_tiers[-1]
        # bottom centre of the middle leadership box (or the single client box)
        mid = anchor[len(anchor) // 2]
        anchor_x, _, anchor_bottom = mid
        if disc_tiers and disc_tiers[0]:
            first_row = disc_tiers[0]
            bus_y = first_row[0][1] - 40
            _v_line(draw, anchor_x, anchor_bottom, bus_y, line_colour)
            xs = [c[0] for c in first_row]
            draw.line([(min(xs), bus_y), (max(xs), bus_y)], fill=line_colour, width=4)
            for cx, top, _ in first_row:
                _v_line(draw, cx, bus_y, top, line_colour)
                _node(draw, cx, bus_y, line_colour)


def _node(draw, x, y, colour, r=6):
    draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)


def _v_line(draw, x, y1, y2, colour=LINE):
    draw.line([(x, y1), (x, y2)], fill=colour, width=4)


def _draw_text_center(draw, text, cx, cy, font, colour):
    w = draw.textlength(text, font=font)
    try:
        ascent, descent = font.getmetrics()
        h = ascent + descent
    except Exception:
        h = font.size if hasattr(font, "size") else 20
    draw.text((cx - w / 2, cy - h / 2), text, font=font, fill=colour)


def _wrap(draw, text, font, max_width) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)] if items else []


def _font(font_paths: dict | None, bold: bool = False, size: int = 30):
    key = (bool(font_paths), bold, size)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    path = None
    if font_paths:
        path = font_paths.get("bold" if bold else "regular")
    if not path:
        path = str(_FONT_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"))
    try:
        font = ImageFont.truetype(path, size=size)
    except Exception:
        try:
            font = ImageFont.truetype(str(_FONT_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")), size=size)
        except Exception:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font
