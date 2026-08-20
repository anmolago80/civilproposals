"""
org_chart_render.py

The project organisation chart's shared data model, and four PNG renderers --
one per user-selectable presentation style.

WHY ONE MODEL AND FOUR RENDERERS
--------------------------------
Exactly the arrangement program_render.py uses for the delivery program, and
for the same reason: the chart has to appear in the UI preview, the pack's
Key Personnel section, and the companion PowerPoint. build_model() normalises
the resourcing plan ONCE -- leadership, disciplines with their leads and
support members, assurance roles, quals lines -- and every renderer, in every
output, consumes that one object, so a preview and an export cannot drift
apart.

WHAT IS AND ISN'T INVENTED
--------------------------
Everything here comes from the resourcing plan the user filled in. An
unassigned lead is drawn as a dashed red TBC, never quietly omitted and never
given a plausible name. A missing qualification line is omitted, never
guessed. An assurance/reviewer entry appears ONLY where the plan actually
holds such a slot -- this module never adds one, so a project with no
reviewer simply has no assurance band and no QA badge.

A role the user REMOVED (see resourcing.OPTIONAL_MANAGEMENT_ROLES) is a
different thing from a role left unfilled: it is absent from the plan, so it
is absent from the chart, with no TBC. Deliberate absence is not a gap.

STYLE VOCABULARY (shared by all four)
-------------------------------------
Rounded white cards on a near-white page. A near-black client box. Thin light
connectors. Uppercase muted captions. Red dashed TBC. Discipline identity is
carried by the discipline NAME, which is always printed -- colour only ever
reinforces it, so the chart still reads in monochrome.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

STYLES = ("cards", "columns", "bands", "tree")
DEFAULT_STYLE = "cards"

STYLE_LABELS = {
    "cards": "Executive cards",
    "columns": "Discipline columns",
    "bands": "Governance bands",
    "tree": "Classic tree",
}

STYLE_DESCRIPTIONS = {
    "cards": "Avatar initials, quals line, QA/Review badge (modern)",
    "columns": "Colour-banded lanes, leads + support stacked",
    "bands": "Client → leadership → delivery team → assurance",
    "tree": "Monochrome boxes and rules, single accent (traditional)",
}

# Fixed and colourblind-validated, the same four as program_render.STAGE_COLOURS.
# Do not substitute hues: these are distinguishable under deuteranopia and
# protanopia, which a "nicer" set picked by eye generally is not. Past four
# disciplines the colours cycle as tints -- which is safe precisely because
# the discipline NAME is always printed, so identity is never colour-alone.
DISCIPLINE_COLOURS = ["#1D4ED8", "#0D9488", "#F97316", "#6D28D9"]

INK = "#111827"
MUTED = "#7A8598"
SUBTLE = "#9AA3B2"
CLIENT_DARK = "#131A2A"
CARD_WHITE = "#FFFFFF"
CARD_EDGE = "#E4E8EF"
PAGE_BG = "#FFFFFF"
LINE = "#C9CFDA"
TBC_RED = "#DC2626"
TBC_FILL = "#FEF2F2"
ASSURANCE_AMBER = "#B45309"
ASSURANCE_FILL = "#FFF7ED"

# Which slots count as assurance. Deliberately narrow: this decides whether a
# whole band appears, and inferring one from a loosely-matching discipline
# name would be inventing a reviewer the project doesn't have.
_ASSURANCE_MARKERS = ("independent review", "peer review", "design review",
                      "reviewer", "assurance", "quality assurance")


@dataclass
class Person:
    name: str = ""            # "" means the slot exists but nobody is in it
    role: str = ""
    quals: str = ""           # "" means unknown -- the line is omitted, never guessed
    discipline: str = ""      # the group this person sits under, where relevant
    is_lead: bool = True      # a discipline's lead, or any single-person role
    group_index: int = 0      # which discipline colour this person belongs to
    role_is_placeholder: bool = False   # the role line is a red fill-me, not a title

    @property
    def is_tbc(self) -> bool:
        return not (self.name or "").strip()

    @property
    def initials(self) -> str:
        words = [w for w in (self.name or "").split() if w[:1].isalpha()]
        if not words:
            return "?"
        return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


@dataclass
class DisciplineGroup:
    name: str
    lead: Person | None = None
    supports: list[Person] = field(default_factory=list)

    @property
    def people(self) -> list[Person]:
        return ([self.lead] if self.lead is not None else []) + list(self.supports)


@dataclass
class OrgModel:
    client_name: str = ""
    project_name: str = ""
    tender_name: str = ""
    client_role: str = "Client"
    leadership: list[Person] = field(default_factory=list)
    disciplines: list[DisciplineGroup] = field(default_factory=list)
    assurance: list[Person] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.leadership and not self.disciplines

    @property
    def has_assurance(self) -> bool:
        return bool(self.assurance)

    @property
    def heading(self) -> str:
        parts = [p for p in ((self.project_name or "").strip(),
                             (self.tender_name or "").strip()) if p]
        return " — ".join(parts)


CONFIRM_TITLE = "[CONFIRM TITLE]"

EMPTY_NOTE = ("[NO TEAM ASSIGNED -- add the management roles and discipline leads in the "
              "Team & Resourcing tab, then re-generate this]")


def _quals_line(assignment) -> str:
    """The small grey line under a person's role. Built only from what the
    user entered -- a blank qualification and a blank RPEQ give a blank line,
    which the renderers omit rather than filling in."""
    parts = [
        (getattr(assignment, "qualification", "") or "").strip(),
        (getattr(assignment, "rpeq_status", "") or "").strip(),
    ]
    return " ".join(p for p in parts if p).strip()


def _is_assurance(slot: str) -> bool:
    lowered = (slot or "").strip().lower()
    return any(marker in lowered for marker in _ASSURANCE_MARKERS)


def build_model(resource_plan: list | None, client_name: str = "", project_name: str = "",
                tender_name: str = "") -> OrgModel:
    """Normalise the resourcing plan into the one object all four renderers
    read. Pure derivation -- see the module note on what is never invented."""
    from modules import resourcing

    model = OrgModel(client_name=(client_name or "").strip(),
                     project_name=(project_name or "").strip(),
                     tender_name=(tender_name or "").strip())

    groups: dict[str, DisciplineGroup] = {}
    order: list[str] = []
    for assignment in (resource_plan or []):
        slot = (getattr(assignment, "slot", "") or "").strip()
        if not slot:
            continue
        kind = getattr(assignment, "slot_kind", "discipline")
        is_lead = bool(getattr(assignment, "is_lead", True))
        role = resourcing.role_label(assignment)
        role_is_placeholder = False
        if kind != "management" and not is_lead and not (
                getattr(assignment, "custom_title", "") or "").strip():
            # A support member's position on this job is theirs, not the
            # discipline's. Falling back to the discipline name here would
            # read as a real, deliberate title -- the one place this module
            # would be filling a blank in rather than marking it.
            role = CONFIRM_TITLE
            role_is_placeholder = True
        elif kind != "management" and is_lead and not _is_assurance(slot):
            # "Structural Lead" rather than bare "Structural": the app has
            # always called this row the discipline's Lead (it was the literal
            # word on the old chart's sub-row), and the bare discipline name
            # reads as a department rather than a person's position.
            role = f"{role} Lead"
        person = Person(
            name=(getattr(assignment, "person_name", "") or "").strip(),
            role=role,
            quals=_quals_line(assignment),
            discipline=slot,
            is_lead=is_lead,
            role_is_placeholder=role_is_placeholder,
        )
        if kind == "management":
            if slot == resourcing.CLIENT_ROLE:
                # The client's own PM is the client's staff, not the firm's --
                # it names the box at the top rather than joining leadership.
                if person.name:
                    model.client_role = f"Client · {person.name}"
                continue
            # A reviewer entered as a management row is still assurance.
            (model.assurance if _is_assurance(slot) else model.leadership).append(person)
            continue

        if _is_assurance(slot):
            model.assurance.append(person)
            continue

        if slot not in groups:
            groups[slot] = DisciplineGroup(name=slot)
            order.append(slot)
        group = groups[slot]
        if is_lead and group.lead is None:
            group.lead = person
        else:
            person.is_lead = False
            group.supports.append(person)

    model.disciplines = [groups[slot] for slot in order]
    for index, group in enumerate(model.disciplines):
        for person in group.people:
            person.group_index = index
    return model


def effective_style(model: OrgModel, style: str) -> str:
    """The style that will actually be drawn. All four cope with any plan, so
    this only normalises an unknown value -- it exists so callers can ask the
    same question they ask program_render, rather than special-casing one of
    the two."""
    return style if style in STYLES else DEFAULT_STYLE


def render_png(model: OrgModel, style: str = DEFAULT_STYLE,
               theme_accent: str | None = None) -> bytes | None:
    """The org chart as a PNG, in the requested style.

    Returns None on any failure -- the callers all fall back to something that
    still communicates the team, never to nothing.
    """
    style = effective_style(model, style)
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        renderer = {
            "cards": _render_cards,
            "columns": _render_columns,
            "bands": _render_bands,
            "tree": _render_tree,
        }[style]
        figure = renderer(model, theme_accent or DISCIPLINE_COLOURS[0])
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=170, bbox_inches="tight",
                       facecolor=PAGE_BG, edgecolor="none")
        plt.close(figure)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Shared drawing helpers
# ---------------------------------------------------------------------------

# Inches of figure per 1.0 of vertical data space. Fixed so card heights, text
# sizes and gaps stay identical whatever the team size -- the figure grows,
# the drawing does not rescale. Same approach as program_render._finalise.
_V_SCALE = 9.0
_TOP = 1.06
_WIDTH = 12.0


def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _tint(colour: str, towards_white: float) -> tuple:
    return tuple(c + (1 - c) * towards_white for c in _hex_to_rgb(colour))


def _discipline_colour(index: int) -> str:
    return DISCIPLINE_COLOURS[index % len(DISCIPLINE_COLOURS)]


def _new_figure(height: float):
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(_WIDTH, height))
    axes.set_axis_off()
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    return figure, axes


def _finalise(figure, axes, lowest: float):
    """Crop the canvas to the content and size the figure to match, so a
    four-person chart isn't padded out with half a page of white."""
    lowest = min(lowest, _TOP - 0.12)
    axes.set_ylim(lowest, _TOP)
    figure.set_size_inches(_WIDTH, max(1.8, (_TOP - lowest) * _V_SCALE))
    return figure


def _text_width_frac(figure, artist) -> float:
    """A text artist's width as a fraction of the AXES width.

    Against the axes and not the figure, because every width it is compared
    with is an x-coordinate in the axes' own 0..1 space -- see the same note
    in program_render, where measuring against the figure made every label
    look about a quarter narrower than it really was."""
    try:
        renderer = figure.canvas.get_renderer()
    except Exception:
        figure.canvas.draw()
        renderer = figure.canvas.get_renderer()
    bbox = artist.get_window_extent(renderer=renderer)
    axes = getattr(artist, "axes", None)
    reference = axes.get_window_extent(renderer=renderer).width if axes is not None else figure.bbox.width
    return bbox.width / max(1.0, reference)


def _fit(figure, artist, max_frac: float, min_size: float = 5.0) -> None:
    """Shrink a label to fit its card, then ellipsize if it still will not.
    Shrinking first keeps the whole label readable; an ellipsis is at least
    visibly an ellipsis, unlike a name that runs off the side of its card."""
    size = artist.get_fontsize()
    while size > min_size and _text_width_frac(figure, artist) > max_frac:
        size -= 0.2
        artist.set_fontsize(size)
    text = artist.get_text()
    while len(text) > 4 and _text_width_frac(figure, artist) > max_frac:
        text = text[:-2]
        artist.set_text(text.rstrip() + "…")


def _wrap_columns(count: int, min_w: float, gap: float, max_w: float):
    """How to lay `count` columns across the page without squeezing any of
    them below a legible width.

    Past a handful of disciplines a single row makes every card too narrow to
    hold a name -- an eight-discipline chart came out reading "Lead Pe…" in
    every column. Wrap to further rows instead, balanced so the last row
    isn't a lonely single card. Returns (columns_per_row, column_width)."""
    count = max(1, count)
    per_row = max(1, int((1.0 + gap) // (min_w + gap)))
    rows = -(-count // per_row)          # ceil
    per_row = -(-count // rows)          # ceil, balanced across rows
    width = min(max_w, (1.0 - (per_row - 1) * gap) / per_row)
    return per_row, width


def _card(axes, x, y, w, h, facecolor=CARD_WHITE, edgecolor=CARD_EDGE,
          radius=0.012, linewidth=0.9, linestyle="solid", zorder=2):
    from matplotlib.patches import FancyBboxPatch

    patch = FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=facecolor, edgecolor=edgecolor, linewidth=linewidth,
        linestyle=linestyle, mutation_aspect=1, zorder=zorder,
    )
    axes.add_patch(patch)
    return patch


def _accent_bar(axes, x, y, w, colour, height=0.006):
    """The thin coloured rule along the top of a card. Drawn as its own
    rounded patch so the card underneath keeps its white body."""
    _card(axes, x, y, w, height, facecolor=colour, edgecolor=colour,
          radius=height / 2, linewidth=0, zorder=3)


def _line(axes, x0, y0, x1, y1, colour=LINE, width=0.9, zorder=1):
    axes.plot([x0, x1], [y0, y1], color=colour, linewidth=width, zorder=zorder,
              solid_capstyle="butt")


def _title(axes, model: OrgModel, subtitle: str = ""):
    axes.text(0.0, 1.0, "Project organisation", fontsize=16, fontweight="bold",
              color=INK, ha="left", va="top")
    if subtitle:
        axes.text(0.0, 0.965, subtitle, fontsize=6.6, color=SUBTLE, ha="left", va="top")
    if model.heading:
        axes.text(1.0, 1.0, model.heading, fontsize=8.4, fontweight="bold",
                  color="#6B7280", ha="right", va="top")


def _empty_figure(model: OrgModel):
    figure, axes = _new_figure(2.4)
    _title(axes, model)
    axes.text(0.5, 0.88, EMPTY_NOTE, fontsize=8, color="#C00000", style="italic",
              ha="center", va="center", wrap=True)
    return _finalise(figure, axes, 0.82)


def _person_lines(person: Person, role_colour: str | None = None) -> list[tuple[str, float, bool, str]]:
    """(text, size, bold, colour) for a person's stacked lines. The quals line
    is dropped when unknown rather than printed empty or invented."""
    if person.is_tbc:
        lines = [("TBC", 7.6, True, TBC_RED), (person.role or "", 6.6, True, TBC_RED)]
        lines.append(("to be confirmed", 6.0, False, MUTED))
    else:
        lines = [(person.name, 7.6, True, INK)]
        if person.role:
            # A lead's role carries the accent, a support member's is grey:
            # the chart should say at a glance who runs a discipline without
            # the reader having to compare card positions. An un-entered
            # title stays red, like every other unknown in this tool.
            if person.role_is_placeholder:
                colour = TBC_RED
            else:
                colour = (role_colour or INK) if person.is_lead else MUTED
            lines.append((person.role, 6.6, True, colour))
        if person.quals:
            lines.append((person.quals, 6.0, False, MUTED))
    return [line for line in lines if line[0]]


# ---------------------------------------------------------------------------
# A. Executive cards
# ---------------------------------------------------------------------------

_CARD_W = 0.19
_CARD_GAP = 0.022


def _avatar_card(figure, axes, x, y, w, h, person: Person, accent: str,
                 badge: str = ""):
    """A white card with a top accent rule, a circular initials avatar, and
    the person's stacked lines. A TBC card is dashed and red throughout --
    the same convention every other unknown in this tool uses."""
    tbc = person.is_tbc
    _card(axes, x, y, w, h,
          facecolor=TBC_FILL if tbc else CARD_WHITE,
          edgecolor=TBC_RED if tbc else CARD_EDGE,
          linewidth=0.9, linestyle=(0, (2.4, 1.8)) if tbc else "solid")
    # Only a lead's card carries the top rule. A support member's card sitting
    # under it with the same bar made the two read as peers.
    if not tbc and person.is_lead:
        _accent_bar(axes, x, y + h - 0.006, w, accent)
    if badge and not tbc:
        _card(axes, x + w * 0.52, y + h - 0.004, w * 0.48, 0.017,
              facecolor=ASSURANCE_FILL, edgecolor=ASSURANCE_AMBER, radius=0.004,
              linewidth=0.7, zorder=4)
        axes.text(x + w * 0.76, y + h + 0.0045, badge.upper(), fontsize=5.2,
                  fontweight="bold", color=ASSURANCE_AMBER, ha="center", va="center",
                  zorder=5)

    avatar_r = min(h * 0.24, 0.019)
    avatar_cx = x + 0.026
    avatar_cy = y + h / 2
    from matplotlib.patches import Circle

    axes.add_patch(Circle((avatar_cx, avatar_cy), avatar_r,
                          facecolor=TBC_FILL if tbc else _tint(accent, 0.88),
                          edgecolor="none", zorder=3,
                          transform=axes.transData))
    axes.text(avatar_cx, avatar_cy, person.initials, fontsize=6.4, fontweight="bold",
              color=TBC_RED if tbc else accent, ha="center", va="center", zorder=4)

    lines = _person_lines(person, role_colour=accent)
    text_x = x + 0.049
    max_frac = w - 0.058
    step = 0.0155
    first_y = y + h / 2 + (len(lines) - 1) * step / 2 - 0.001
    labels = []
    for index, (text, size, bold, colour) in enumerate(lines):
        artist = axes.text(text_x, first_y - index * step, text, fontsize=size,
                           fontweight="bold" if bold else "normal", color=colour,
                           ha="left", va="center", zorder=4)
        labels.append((artist, max_frac))
    return labels


def _render_cards(model: OrgModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)

    figure, axes = _new_figure(6.0)
    _title(axes, model)
    labels: list[tuple[object, float]] = []

    centre = 0.5
    y = 0.90

    # Client box -- near-black, the client's side of the table.
    client_w, client_h = 0.20, 0.042
    _card(axes, centre - client_w / 2, y - client_h, client_w, client_h,
          facecolor=CLIENT_DARK, edgecolor=CLIENT_DARK)
    labels.append((axes.text(centre, y - client_h * 0.38,
                             model.client_name or "[CLIENT NAME]", fontsize=8,
                             fontweight="bold",
                             color="#FFFFFF" if model.client_name else "#FCA5A5",
                             ha="center", va="center", zorder=4), client_w - 0.02))
    axes.text(centre, y - client_h * 0.75, model.client_role, fontsize=5.8,
              fontweight="bold", color="#9CA3AF", ha="center", va="center", zorder=4)
    y -= client_h

    card_h = 0.062
    # Leadership: the first role centred under the client, the rest spread on
    # a second rank alongside any assurance card.
    lead_people = list(model.leadership)
    top_person = lead_people.pop(0) if lead_people else None
    if top_person is not None:
        _line(axes, centre, y, centre, y - 0.022)
        y -= 0.022
        labels += _avatar_card(figure, axes, centre - _CARD_W / 2, y - card_h,
                               _CARD_W, card_h, top_person, accent)
        y -= card_h

    rank = [(person, "") for person in lead_people]
    rank += [(person, "QA / Review") for person in model.assurance]
    if rank:
        _line(axes, centre, y, centre, y - 0.024)
        y -= 0.024
        total = len(rank) * _CARD_W + (len(rank) - 1) * _CARD_GAP
        x = centre - total / 2
        for person, badge in rank:
            labels += _avatar_card(figure, axes, x, y - card_h, _CARD_W, card_h,
                                   person, ASSURANCE_AMBER if badge else accent,
                                   badge=badge)
            x += _CARD_W + _CARD_GAP
        y -= card_h

    # Discipline columns, each with an uppercase caption and its lead plus
    # however many support members the plan carries.
    if model.disciplines:
        per_row, col_w = _wrap_columns(len(model.disciplines), 0.165, _CARD_GAP, _CARD_W)
        chunks = [model.disciplines[i:i + per_row]
                  for i in range(0, len(model.disciplines), per_row)]
        for chunk_index, chunk in enumerate(chunks):
            bus_y = y - 0.026
            if chunk_index == 0:
                _line(axes, centre, y, centre, bus_y)
            total = len(chunk) * col_w + (len(chunk) - 1) * _CARD_GAP
            x = max(0.0, 0.5 - total / 2)
            centres = []
            row_bottom = bus_y
            for group in chunk:
                centres.append(x + col_w / 2)
                # The Executive-cards style is single-accent by design (the
                # fixed discipline palette belongs to the column style): the
                # uppercase caption already names each discipline, so
                # colouring them differently here only adds noise.
                axes.text(x + col_w / 2, bus_y - 0.018, group.name.upper(), fontsize=6.0,
                          fontweight="bold", color=MUTED, ha="center", va="center")
                card_y = bus_y - 0.030
                for person in group.people:
                    labels += _avatar_card(figure, axes, x, card_y - card_h, col_w,
                                           card_h, person, accent)
                    card_y -= card_h + 0.010
                row_bottom = min(row_bottom, card_y)
                x += col_w + _CARD_GAP
            if len(centres) > 1:
                _line(axes, centres[0], bus_y, centres[-1], bus_y)
            for column_centre in centres:
                _line(axes, column_centre, bus_y, column_centre, bus_y - 0.012)
            y = row_bottom - 0.014

    figure = _finalise(figure, axes, y - 0.02)
    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure


# ---------------------------------------------------------------------------
# B. Discipline columns
# ---------------------------------------------------------------------------

def _pill(axes, x, y, w, h, facecolor, label, sub="", label_colour="#FFFFFF",
          sub_colour="#D7DEEA", label_size=8.0):
    _card(axes, x, y, w, h, facecolor=facecolor, edgecolor=facecolor, radius=0.008)
    if sub:
        artist = axes.text(x + w / 2, y + h * 0.62, label, fontsize=label_size,
                           fontweight="bold", color=label_colour, ha="center",
                           va="center", zorder=4)
        axes.text(x + w / 2, y + h * 0.28, sub, fontsize=6.2, fontweight="bold",
                  color=sub_colour, ha="center", va="center", zorder=4)
    else:
        artist = axes.text(x + w / 2, y + h / 2, label, fontsize=label_size,
                           fontweight="bold", color=label_colour, ha="center",
                           va="center", zorder=4)
    return artist


def _render_columns(model: OrgModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)

    figure, axes = _new_figure(6.0)
    _title(axes, model)
    labels: list[tuple[object, float]] = []

    centre = 0.5
    y = 0.90
    pill_h = 0.040

    client_w = 0.26
    labels.append((_pill(axes, centre - client_w / 2, y - pill_h, client_w, pill_h,
                         CLIENT_DARK,
                         f"{model.client_name or '[CLIENT NAME]'} — Client",
                         label_colour="#FFFFFF" if model.client_name else "#FCA5A5"),
                   client_w - 0.02))
    y -= pill_h

    for index, person in enumerate(model.leadership):
        _line(axes, centre, y, centre, y - 0.020)
        y -= 0.020
        # The first leadership pill carries the quals line, the rest sit
        # slightly narrower beneath it -- the reference look's tapering chain.
        width = 0.24 if index == 0 else 0.19
        label = person.name or "TBC"
        sub = person.role + (f" · {person.quals}" if person.quals else "")
        colour = accent if index == 0 else _rgb_hex(_tint(accent, 0.18))
        labels.append((_pill(axes, centre - width / 2, y - pill_h, width, pill_h,
                             colour if not person.is_tbc else TBC_FILL, label, sub,
                             label_colour="#FFFFFF" if not person.is_tbc else TBC_RED,
                             sub_colour="#D7DEEA" if not person.is_tbc else TBC_RED),
                       width - 0.02))
        y -= pill_h

    if model.disciplines:
        y -= 0.028
        gap = 0.016
        per_row, lane_w = _wrap_columns(len(model.disciplines), 0.175, gap, 0.24)
        chunks = [model.disciplines[i:i + per_row]
                  for i in range(0, len(model.disciplines), per_row)]
        row_h = 0.046
        x = 0.0
        for chunk in chunks:
            total = len(chunk) * lane_w + (len(chunk) - 1) * gap
            x = max(0.0, 0.5 - total / 2)
            # Every lane in a row is the same height, so the row reads as a
            # row rather than a ragged skyline.
            tallest = max(len(g.people) for g in chunk)
            lane_h = 0.030 + tallest * (row_h + 0.008) + 0.008
            for group in chunk:
                colour = _discipline_colour(group.people[0].group_index if group.people
                                            else model.disciplines.index(group))
                _card(axes, x, y - lane_h, lane_w, lane_h, facecolor="#F7F9FC",
                      edgecolor="#EDF1F6", radius=0.010, zorder=1)
                _accent_bar(axes, x, y - 0.006, lane_w, colour)
                labels.append((axes.text(x + lane_w / 2, y - 0.020, group.name.upper(),
                                         fontsize=6.6, fontweight="bold", color=colour,
                                         ha="center", va="center", zorder=4),
                               lane_w - 0.02))
                card_y = y - 0.030
                for person in group.people:
                    tbc = person.is_tbc
                    _card(axes, x + 0.008, card_y - row_h, lane_w - 0.016, row_h,
                          facecolor=TBC_FILL if tbc else CARD_WHITE,
                          edgecolor=TBC_RED if tbc else CARD_EDGE,
                          linestyle=(0, (2.4, 1.8)) if tbc else "solid", radius=0.008)
                    lines = _person_lines(person, role_colour=colour)
                    step = 0.0135
                    first = card_y - row_h / 2 + (len(lines) - 1) * step / 2
                    for line_index, (text, size, bold, line_colour) in enumerate(lines):
                        labels.append((axes.text(x + lane_w / 2, first - line_index * step,
                                                 text, fontsize=size,
                                                 fontweight="bold" if bold else "normal",
                                                 color=line_colour, ha="center", va="center",
                                                 zorder=4), lane_w - 0.028))
                    card_y -= row_h + 0.008
                x += lane_w + gap
            y -= lane_h + 0.016

    # The amber independent-review strip, ONLY when the plan holds such a slot.
    if model.assurance:
        y -= 0.026
        strip_h = 0.036
        strip_w = 0.44
        _card(axes, centre - strip_w / 2, y - strip_h, strip_w, strip_h,
              facecolor=ASSURANCE_FILL, edgecolor="#FBBF24", radius=0.010)
        text = " · ".join(
            f"{p.name or 'TBC'} — {p.role}" + (f" ({p.quals})" if p.quals else "")
            for p in model.assurance)
        labels.append((axes.text(centre, y - strip_h / 2, f"★ Independent review: {text}",
                                 fontsize=6.6, fontweight="bold", color=ASSURANCE_AMBER,
                                 ha="center", va="center", zorder=4), strip_w - 0.02))
        y -= strip_h

    figure = _finalise(figure, axes, y - 0.02)
    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure


def _rgb_hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb)


# ---------------------------------------------------------------------------
# C. Governance bands
# ---------------------------------------------------------------------------

def _render_bands(model: OrgModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)

    figure, axes = _new_figure(6.0)
    _title(axes, model)
    labels: list[tuple[object, float]] = []

    label_x, band_x, band_right = 0.145, 0.16, 1.0
    y = 0.90
    chip_h = 0.050
    chip_gap = 0.010

    def band(title: str, chips: list[tuple[str, str, str, bool, str]], fill,
             chip_edge=CARD_EDGE):
        """chips: (name, role, quals, is_tbc, role_colour)."""
        nonlocal y
        if not chips:
            return
        pad = 0.010
        # Chips flow left to right and wrap, so a 12-person delivery band grows
        # downwards rather than off the right-hand edge.
        widths = [min(0.20, max(0.11, 0.030 + 0.0088 * max(len(name), len(role))))
                  for name, role, *_rest in chips]
        rows: list[list[int]] = [[]]
        used = 0.0
        for index, width in enumerate(widths):
            if rows[-1] and used + width + chip_gap > (band_right - band_x - 2 * pad):
                rows.append([])
                used = 0.0
            rows[-1].append(index)
            used += width + chip_gap
        band_h = pad * 2 + len(rows) * chip_h + (len(rows) - 1) * chip_gap
        _card(axes, band_x, y - band_h, band_right - band_x, band_h,
              facecolor=fill, edgecolor="none", radius=0.008, linewidth=0, zorder=1)
        axes.text(label_x, y - band_h / 2, title.upper(), fontsize=6.4, fontweight="bold",
                  color=MUTED, ha="right", va="center")
        chip_y = y - pad
        for row in rows:
            x = band_x + pad
            for index in row:
                name, role, quals, tbc, role_colour = chips[index]
                width = widths[index]
                _card(axes, x, chip_y - chip_h, width, chip_h,
                      facecolor=TBC_FILL if tbc else CARD_WHITE,
                      edgecolor=TBC_RED if tbc else chip_edge,
                      linestyle=(0, (2.4, 1.8)) if tbc else "solid", radius=0.008, zorder=2)
                lines = [(name, 7.2, True, TBC_RED if tbc else INK),
                         (role, 6.4, True, TBC_RED if tbc else role_colour)]
                if quals:
                    lines.append((quals, 6.0, False, MUTED))
                lines = [line for line in lines if line[0]]
                step = 0.0135
                first = chip_y - chip_h / 2 + (len(lines) - 1) * step / 2
                for line_index, (text, size, bold, colour) in enumerate(lines):
                    labels.append((axes.text(x + 0.008, first - line_index * step, text,
                                             fontsize=size,
                                             fontweight="bold" if bold else "normal",
                                             color=colour, ha="left", va="center", zorder=3),
                                   width - 0.014))
                x += width + chip_gap
            chip_y -= chip_h + chip_gap
        y -= band_h + 0.014

    band("Client",
         [(model.client_name or "[CLIENT NAME]", model.client_role, "", False, MUTED)],
         CLIENT_DARK, chip_edge=CLIENT_DARK)
    band("Leadership",
         [(p.name or "TBC", p.role, p.quals, p.is_tbc, accent) for p in model.leadership],
         _tint(accent, 0.94))
    delivery = []
    for group in model.disciplines:
        colour = _discipline_colour(group.people[0].group_index if group.people else 0)
        for person in group.people:
            role = (person.role if person.role.startswith(group.name)
                    else f"{person.role} · {group.name}")
            delivery.append((person.name or "TBC", role, person.quals, person.is_tbc,
                             colour if person.is_lead else MUTED))
    band("Delivery team", delivery, _tint(DISCIPLINE_COLOURS[1], 0.95))
    # No assurance band at all when the plan holds no reviewer -- an empty
    # band labelled ASSURANCE reads as a missing answer rather than an
    # absent role.
    band("Assurance",
         [(p.name or "TBC", p.role, p.quals, p.is_tbc, ASSURANCE_AMBER)
          for p in model.assurance],
         _tint(ASSURANCE_AMBER, 0.93))

    axes.text(0.0, y - 0.006,
              "Solid reporting lines run top-down; the assurance band reviews independently "
              "of the delivery team." if model.has_assurance else
              "Solid reporting lines run top-down.",
              fontsize=6.2, fontweight="bold", color=SUBTLE, ha="left", va="top")

    figure = _finalise(figure, axes, y - 0.030)
    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure


# ---------------------------------------------------------------------------
# D. Classic tree
# ---------------------------------------------------------------------------

def _tree_box(axes, x, y, w, h, person_lines, accent=None, tbc=False):
    _card(axes, x, y, w, h, facecolor=CARD_WHITE,
          edgecolor=TBC_RED if tbc else (accent or INK),
          linewidth=1.4 if accent or tbc else 1.0,
          linestyle=(0, (2.6, 2.0)) if tbc else "solid", radius=0.006)
    step = 0.0145
    first = y + h / 2 + (len(person_lines) - 1) * step / 2
    out = []
    for index, (text, size, bold, colour) in enumerate(person_lines):
        out.append((axes.text(x + w / 2, first - index * step, text, fontsize=size,
                              fontweight="bold" if bold else "normal", color=colour,
                              ha="center", va="center", zorder=4), w - 0.014))
    return out


def _render_tree(model: OrgModel, accent: str):
    if model.is_empty:
        return _empty_figure(model)

    figure, axes = _new_figure(6.0)
    _title(axes, model)
    labels: list[tuple[object, float]] = []

    centre = 0.5
    y = 0.90
    box_w, box_h = 0.20, 0.056

    labels += _tree_box(axes, centre - box_w / 2, y - box_h, box_w, box_h, [
        (model.client_name or "[CLIENT NAME]", 8.0, True,
         INK if model.client_name else TBC_RED),
        (model.client_role, 6.4, True, MUTED),
    ])
    y -= box_h

    lead_people = list(model.leadership)
    top_person = lead_people.pop(0) if lead_people else None
    if top_person is not None:
        _line(axes, centre, y, centre, y - 0.024, colour=INK, width=1.0)
        y -= 0.024
        labels += _tree_box(axes, centre - box_w / 2, y - box_h, box_w, box_h,
                            _person_lines(top_person, role_colour=INK),
                            accent=accent, tbc=top_person.is_tbc)
        y -= box_h

    rank = lead_people + model.assurance
    if rank:
        _line(axes, centre, y, centre, y - 0.026, colour=INK, width=1.0)
        y -= 0.026
        gap = 0.024
        total = len(rank) * box_w + (len(rank) - 1) * gap
        x = centre - total / 2
        for person in rank:
            labels += _tree_box(axes, x, y - box_h, box_w, box_h,
                                _person_lines(person, role_colour=INK),
                                tbc=person.is_tbc)
            x += box_w + gap
        y -= box_h

    if model.disciplines:
        gap = 0.020
        per_row, col_w = _wrap_columns(len(model.disciplines), 0.165, gap, box_w)
        chunks = [model.disciplines[i:i + per_row]
                  for i in range(0, len(model.disciplines), per_row)]
        for chunk_index, chunk in enumerate(chunks):
            bus_y = y - 0.026
            if chunk_index == 0:
                _line(axes, centre, y, centre, bus_y, colour=INK, width=1.0)
            total = len(chunk) * col_w + (len(chunk) - 1) * gap
            x = max(0.0, 0.5 - total / 2)
            centres = []
            lowest = bus_y
            for group in chunk:
                centres.append(x + col_w / 2)
                box_y = bus_y - 0.024
                for person in group.people:
                    labels += _tree_box(axes, x, box_y - box_h, col_w, box_h,
                                        _person_lines(person, role_colour=INK),
                                        tbc=person.is_tbc)
                    box_y -= box_h + 0.012
                lowest = min(lowest, box_y)
                x += col_w + gap
            if len(centres) > 1:
                _line(axes, min(centres), bus_y, max(centres), bus_y, colour=INK, width=1.2)
            for column_centre in centres:
                _line(axes, column_centre, bus_y, column_centre, bus_y - 0.024,
                      colour=INK, width=1.0)
            y = lowest - 0.010

    figure = _finalise(figure, axes, y - 0.02)
    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure
