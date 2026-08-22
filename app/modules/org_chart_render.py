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

WHAT A CARD SHOWS
------------------
Every person on the chart renders exactly two lines: their name, and their
role/title. Nothing else -- in particular, qualifications (BEng, RPEQ, years
of experience, ...) are never drawn here. That data still exists on the
resourcing plan and still drives the Word pack's Key Personnel profiles; a
chart is read at a glance from across a room, and a card carrying a full CV
sentence overflowed its own box and collided with the caption above it. An
unfilled slot is a red "TBC" plus its role -- also two lines, never a third
"to be confirmed" line underneath.

PEER REVIEW
-----------
Every one of the four styles carries a Peer Review element: one row per
discipline in the plan, showing that discipline's nominated peer reviewer
(ResourceAssignment.peer_reviewer, set on the discipline's lead row) or a red
"TBC" where none has been entered yet. Unlike the assurance band above, this
element is unconditional -- it appears whenever the plan has at least one
discipline, whether or not any reviewer has been named, because every
discipline's work needs a reviewer eventually and a chart that only shows the
question once someone has answered it isn't useful during the time it's
actually needed.

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

from modules import export_i18n

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
    # ResourceAssignment.peer_reviewer off this discipline's LEAD row -- "" means
    # not yet confirmed, rendered as a red TBC by the Peer Review element, never
    # invented or inferred from anywhere else.
    peer_reviewer: str = ""

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
                tender_name: str = "", language: str | None = None) -> OrgModel:
    """Normalise the resourcing plan into the one object all four renderers
    read. Pure derivation -- see the module note on what is never invented.

    `language`: None (the default -- every PNG-live-preview caller, Part 4b's
    own territory) keeps the English fallbacks below (CONFIRM_TITLE, the
    " Lead" suffix, the "Client" role label) as plain English; a real
    language (org_chart_pptx.py's PPTX caller passes output_language)
    resolves all of them through export_i18n instead -- Round 3, Part 2,
    since an untitled support member, a discipline lead, and the client's
    own box are all everyday, not edge-case, states."""
    from modules import resourcing

    model = OrgModel(client_name=(client_name or "").strip(),
                     project_name=(project_name or "").strip(),
                     tender_name=(tender_name or "").strip())
    if language is not None:
        model.client_role = export_i18n.export_t("pptx_org_band_client", language)

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
            role = (export_i18n.export_t("pptx_confirm_title", language) if language is not None
                   else CONFIRM_TITLE)
            role_is_placeholder = True
        elif kind != "management" and is_lead and not _is_assurance(slot):
            # "Structural Lead" rather than bare "Structural": the app has
            # always called this row the discipline's Lead (it was the literal
            # word on the old chart's sub-row), and the bare discipline name
            # reads as a department rather than a person's position.
            role = (export_i18n.export_t("pptx_role_lead_label", language, role=role) if language is not None
                   else f"{role} Lead")
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
                    model.client_role = (
                        export_i18n.export_t("pptx_client_role_with_name", language, name=person.name)
                        if language is not None else f"Client · {person.name}")
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
            group.peer_reviewer = (getattr(assignment, "peer_reviewer", "") or "").strip()
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
               theme_accent: str | None = None, language: str | None = None) -> bytes | None:
    """The org chart as a PNG, in the requested style.

    `language` defaults to None, which preserves the exact original
    English-only behaviour for any caller not yet updated to pass a real
    language -- see the module-level note on the language opt-in pattern.

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
        figure = renderer(model, theme_accent or DISCIPLINE_COLOURS[0], language=language)
        buffer = io.BytesIO()
        # No bbox_inches="tight": that crops the saved PNG back down to the
        # drawn content's bounding box, silently undoing the fixed A4-landscape
        # page this module now deliberately renders -- the whole point of the
        # scale-to-fill rework is that the OUTPUT PAGE is a constant size and
        # the content is what scales, not the other way round.
        figure.savefig(buffer, format="png", dpi=170,
                       facecolor=PAGE_BG, edgecolor="none")
        plt.close(figure)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Shared drawing helpers -- fixed A4-landscape page, scaled-to-fill layout
# ---------------------------------------------------------------------------
#
# FIX BRIEF: "org chart must FILL the A4 landscape page." The chart used to
# live on an auto-cropped canvas of fixed-size cards -- a four-person chart
# got a short, thin figure; an eight-person one got a tall one -- so however
# many people were on the plan, the CARDS never changed size and the PAGE
# just grew or shrank around them. That is backwards for a document meant to
# occupy a fixed A4 landscape sheet: pasted or printed, a small team read as
# a small diagram lost on a big page.
#
# The figure is now fixed at A4 landscape size. Every style instead computes
# a SCALE FACTOR from the current team's row/column counts -- how much the
# reference (scale=1.0) card sizes, gaps and fonts need to grow or shrink so
# the content exactly fills the page within margins -- and derives every
# box, gap, line weight and font size from that one factor. `_Flow` (below)
# is the shared engine every style's vertical sequence renders through: it
# takes the natural (reference-scale) height of each block and gap in the
# sequence, and once a scale is chosen, spreads whatever page height is left
# over EVENLY across every gap -- never letting slack collect into one dead
# band, and never assuming a fixed pixel/EMU offset that only suited one
# particular team size.

# Same precise A4 dimensions modules/program_pptx.py and
# modules/methodology_pptx.py already use for their own slides (297mm x
# 210mm), so the on-screen/DOCX chart and the companion PowerPoint
# (org_chart_pptx.py) are the same physical page as every other generated
# artefact in this pack, not merely close to it.
PAGE_W_IN = 11.6929
PAGE_H_IN = 8.2677
_MARGIN_IN = 0.35
_TITLE_BAND_IN = 0.62

# Drawable-area geometry, in axes-fraction (0..1 maps onto the fixed
# PAGE_W_IN x PAGE_H_IN figure) -- every style's content lives inside this
# box, never past it.
CONTENT_LEFT = _MARGIN_IN / PAGE_W_IN
CONTENT_RIGHT = 1.0 - _MARGIN_IN / PAGE_W_IN
PAGE_TOP = 1.0 - _MARGIN_IN / PAGE_H_IN
CONTENT_BOTTOM = _MARGIN_IN / PAGE_H_IN
CONTENT_TOP = PAGE_TOP - _TITLE_BAND_IN / PAGE_H_IN

AVAIL_W_IN = (CONTENT_RIGHT - CONTENT_LEFT) * PAGE_W_IN
AVAIL_H_IN = (CONTENT_TOP - CONTENT_BOTTOM) * PAGE_H_IN

# The scale factor is clamped to this range: MIN keeps a very large team
# (more rows than any sane wrap can fully compensate for) legible rather
# than illegibly tiny; MAX keeps a very small team (e.g. one discipline)
# from blowing cards up to a cartoonish size just because the page is empty.
# 1.35 is chosen so a typical 4-discipline chart -- which the fix brief calls
# out by name -- lands name text in the requested ~16-20pt band rather than
# ballooning past it.
MIN_SCALE = 0.55
MAX_SCALE = 1.35


def _x_in(inches: float) -> float:
    """Inches -> axes x-fraction, against the FIXED page width."""
    return inches / PAGE_W_IN


def _y_in(inches: float) -> float:
    """Inches -> axes y-fraction, against the FIXED page height."""
    return inches / PAGE_H_IN


def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _tint(colour: str, towards_white: float) -> tuple:
    return tuple(c + (1 - c) * towards_white for c in _hex_to_rgb(colour))


def _discipline_colour(index: int) -> str:
    return DISCIPLINE_COLOURS[index % len(DISCIPLINE_COLOURS)]


def _new_figure():
    """A fixed A4-landscape figure whose axes fill the ENTIRE physical page --
    add_axes([0, 0, 1, 1]) rather than plt.subplots()'s default inset, so
    axes-fraction (0, 0)..(1, 1) maps exactly onto the fixed PAGE_W_IN x
    PAGE_H_IN page with no hidden matplotlib margin eating into it. Paired
    with render_png() no longer passing bbox_inches="tight" -- otherwise the
    saved PNG is cropped back down to the drawn content regardless of what
    figsize says, which is exactly how the chart used to escape its page."""
    import matplotlib.pyplot as plt

    figure = plt.figure(figsize=(PAGE_W_IN, PAGE_H_IN))
    axes = figure.add_axes((0.0, 0.0, 1.0, 1.0))
    axes.set_axis_off()
    axes.set_xlim(0, 1)
    axes.set_ylim(0, 1)
    return figure, axes


class _Flow:
    """A vertical sequence of blocks (drawable content, fixed reference size)
    and gaps (spacing that STRETCHES to absorb leftover page height), each
    given a reference height in INCHES at scale=1.0.

    render() replays the sequence top-down: every height is multiplied by
    the chosen scale, and any page height left over after that is spread
    EVENLY across every gap in the sequence -- so a short chart's extra room
    becomes breathing space at every seam, not one dead band. A connector
    (a line between two boxes) is a gap too, via connector() below, so it
    lengthens along with the space it crosses rather than leaving a floating
    stub with blank page beneath it -- an early version kept connectors as
    non-stretching blocks and it reliably produced exactly one oversized gap
    (the single remaining stretch point) instead of even spacing throughout.
    Every draw(y_top, y_bottom, scale) callback -- block or gap alike --
    receives its own already-scaled-and-positioned axes-fraction span, plus
    the scale itself for anything that needs it directly (font sizes, line
    weights)."""

    def __init__(self):
        self._items: list[dict] = []

    def block(self, height_in: float, draw) -> None:
        self._items.append({"kind": "block", "h": max(0.0, height_in), "draw": draw})

    def gap(self, height_in: float, draw=None) -> None:
        self._items.append({"kind": "gap", "h": max(0.0, height_in), "draw": draw})

    def connector(self, height_in: float, draw) -> None:
        """A stretchable gap that also draws (typically a line spanning its
        own, possibly-lengthened, span) -- see the class docstring."""
        self.gap(height_in, draw=draw)

    def natural_height_in(self) -> float:
        return sum(it["h"] for it in self._items)

    def render(self, top_frac: float, scale: float, avail_h_in: float = AVAIL_H_IN) -> float:
        """Draws every block and returns the final bottom y (axes-fraction)."""
        n_gaps = sum(1 for it in self._items if it["kind"] == "gap")
        used_in = self.natural_height_in() * scale
        leftover_in = max(0.0, avail_h_in - used_in)
        extra_per_gap_in = (leftover_in / n_gaps) if n_gaps else 0.0
        y = top_frac
        for it in self._items:
            h_in = it["h"] * scale + (extra_per_gap_in if it["kind"] == "gap" else 0.0)
            y_bottom = y - _y_in(h_in)
            if it["draw"] is not None:
                it["draw"](y, y_bottom, scale)
            y = y_bottom
        return y


def _solve_scale(build_flow, per_row_candidates,
                 avail_w_in: float = AVAIL_W_IN, avail_h_in: float = AVAIL_H_IN):
    """Try every candidate discipline-columns-per-row wrap, measure the
    resulting flow WITHOUT drawing anything, and keep whichever wrap yields
    the largest resulting scale -- i.e. the best-fitting page. This is the
    "beyond [min font sizes], wrap to a second row of discipline columns
    instead of shrinking further" rule: a wrap that lets everything render
    bigger wins over a single row that would have to shrink past legibility.
    Ties (including the common case of only one candidate, when there's
    nothing to wrap) favour fewer rows -- less visual clutter.

    `build_flow(per_row)` -> (flow: _Flow, row_width_in: float) for one wrap
    choice; row_width_in is that choice's natural (scale=1.0) width, used
    for the width-fit half of scale = min(width_fit, height_fit).

    Returns (flow, scale, per_row) for the winning candidate."""
    best = None
    for per_row in per_row_candidates:
        flow, row_width_in = build_flow(per_row)
        natural_h = flow.natural_height_in()
        height_fit = (avail_h_in / natural_h) if natural_h > 0 else MAX_SCALE
        width_fit = (avail_w_in / row_width_in) if row_width_in > 0 else MAX_SCALE
        scale = max(MIN_SCALE, min(MAX_SCALE, min(height_fit, width_fit)))
        # Candidates are tried fewest-rows-first (see _row_candidates), so a
        # later, more-wrapped candidate only takes over on a MEANINGFUL scale
        # gain (>6%) -- without this margin, a three-column row that just
        # barely misses the clamp (scale 1.345) loses to a 2+1 wrap that just
        # barely reaches it (1.35 exactly), trading a clean single row for a
        # lopsided one over a difference nobody would notice.
        if best is None or scale > best[1] * 1.06:
            best = (flow, scale, per_row)
    return best


def _row_candidates(count: int) -> list[int]:
    """Per-row candidates worth trying for `count` columns: every row count
    from 1 (a single row) up to `count` (one column per row), each turned
    into a per-row value via ceil-division so rows stay balanced (the same
    balancing _wrap_columns used to do). Small counts have few candidates
    to try, so this stays cheap even though _solve_scale tries all of them."""
    if count <= 0:
        return [1]
    seen = []
    for rows in range(1, count + 1):
        per_row = -(-count // rows)  # ceil
        if per_row not in seen:
            seen.append(per_row)
    return seen


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


def _balanced_wrap(count: int, max_per_row: int) -> int:
    """Simple balanced row-wrap for small multi-item rows (a leadership rank
    row, a badge row) that aren't part of the discipline-column scale search
    in _solve_scale -- ceil-balanced across rows so the last row isn't a
    lonely single item. Returns columns-per-row."""
    if count <= 0:
        return 1
    per_row = min(count, max_per_row)
    rows = -(-count // per_row)          # ceil
    return -(-count // rows)             # ceil, balanced across rows


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


def _title(axes, model: OrgModel, subtitle: str = "", language: str | None = None):
    """Page furniture, not content -- drawn at a constant size regardless of
    team size, anchored to the fixed margin/title band rather than the old
    bare (0, 1)/(1, 1) corners, since the axes now really do span the whole
    physical page (see _new_figure) and (0, 1) would sit flush on the paper
    edge.

    `language`: None (the default -- render_png() has always been called
    with no language, see its own docstring) keeps the plain English title;
    a real language resolves it through export_i18n -- Round 3, Part 4b."""
    title_text = (export_i18n.export_t("pptx_org_chart_title", language) if language is not None
                 else "Project organisation")
    x, y = CONTENT_LEFT, PAGE_TOP
    axes.text(x, y, title_text, fontsize=16, fontweight="bold",
              color=INK, ha="left", va="top")
    if subtitle:
        axes.text(x, y - _y_in(0.22), subtitle, fontsize=6.6, color=SUBTLE, ha="left", va="top")
    if model.heading:
        axes.text(CONTENT_RIGHT, y, model.heading, fontsize=8.4, fontweight="bold",
                  color="#6B7280", ha="right", va="top")


def _empty_figure(model: OrgModel, language: str | None = None):
    figure, axes = _new_figure()
    _title(axes, model, language=language)
    note = (export_i18n.export_t("org_chart_preview_empty_note", language) if language is not None
           else EMPTY_NOTE)
    axes.text(0.5, (CONTENT_TOP + CONTENT_BOTTOM) / 2, note, fontsize=11,
              color="#C00000", style="italic", ha="center", va="center", wrap=True)
    return figure


# Reference (scale=1.0) font sizes for a person's two stacked lines. Boosted
# well past the chart's old fixed 7.6pt/6.6pt -- which never changed no
# matter how few people were on the plan -- so that a typical small team,
# scaled up by _solve_scale, actually lands in the fix brief's requested
# ~16-20pt name / ~12-14pt role band rather than merely being less tiny.
# Floors stop a very large, heavily-wrapped team from shrinking past
# legibility; _fit() (per-card, per-name) is still the final safety net for
# any one unusually long label.
_NAME_PT_REF = 14.5
_ROLE_PT_REF = 10.5
_NAME_PT_MIN = 8.0
_ROLE_PT_MIN = 6.5


def _person_lines(person: Person, role_colour: str | None = None,
                  scale: float = 1.0) -> list[tuple[str, float, bool, str]]:
    """(text, size, bold, colour) for a person's stacked lines -- ALWAYS
    exactly two: name (or "TBC"), then role/title. Qualifications are
    deliberately never drawn here (see the module docstring) -- a chart is
    read at a glance, and a full CV sentence on a card overflowed the card
    and collided with whatever sits above it."""
    name_pt = max(_NAME_PT_MIN, _NAME_PT_REF * scale)
    role_pt = max(_ROLE_PT_MIN, _ROLE_PT_REF * scale)
    if person.is_tbc:
        lines = [("TBC", name_pt, True, TBC_RED), (person.role or "", role_pt, True, TBC_RED)]
    else:
        lines = [(person.name, name_pt, True, INK)]
        if person.role:
            # A lead's role carries the accent, a support member's is grey:
            # the chart should say at a glance who runs a discipline without
            # the reader having to compare card positions. An un-entered
            # title stays red, like every other unknown in this tool.
            if person.role_is_placeholder:
                colour = TBC_RED
            else:
                colour = (role_colour or INK) if person.is_lead else MUTED
            lines.append((person.role, role_pt, True, colour))
    return [line for line in lines if line[0]]



def _rgb_hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in rgb)


# ---------------------------------------------------------------------------
# Peer Review panel -- shared by the cards, columns and tree styles (bands
# folds the same information into its "Assurance" band instead, see below).
# Unconditional whenever the plan has at least one discipline (see the
# module docstring): one row per discipline against its nominated reviewer,
# red TBC until one is entered.
# ---------------------------------------------------------------------------

_PANEL_HEADER_IN = 0.30
_PANEL_ROW_IN = 0.28
_PANEL_W_IN = 3.1


def _draw_peer_review_panel(axes, model: OrgModel, scale: float, labels: list,
                            x_frac: float, top_frac: float, w_in_ref: float,
                            language: str | None = None) -> float:
    """Draws the panel anchored at its top-left corner (x_frac, top_frac) and
    returns its bottom y (axes-fraction), so a caller that needs to clear it
    knows exactly how far down it reaches."""
    n = len(model.disciplines)
    if not n:
        return top_frac
    w = _x_in(w_in_ref * scale)
    header_h = _y_in(_PANEL_HEADER_IN * scale)
    row_h = _y_in(_PANEL_ROW_IN * scale)
    total_h = header_h + row_h * n
    _card(axes, x_frac, top_frac - total_h, w, total_h,
          facecolor=ASSURANCE_FILL, edgecolor=ASSURANCE_AMBER,
          radius=min(w, total_h) * 0.05, linewidth=max(0.7, 1.0 * scale))
    panel_heading = (export_i18n.export_t("pptx_peer_review_heading", language) if language is not None
                    else "PEER REVIEW")
    axes.text(x_frac + w / 2, top_frac - header_h / 2, panel_heading,
              fontsize=max(6.0, 7.4 * scale), fontweight="bold", color=ASSURANCE_AMBER,
              ha="center", va="center", zorder=4)
    pad = w * 0.06
    row_y = top_frac - header_h
    for group in model.disciplines:
        reviewer = (group.peer_reviewer or "").strip()
        tbc = not reviewer
        labels.append((axes.text(x_frac + pad, row_y - row_h / 2, group.name,
                                 fontsize=max(5.5, 7.0 * scale), fontweight="bold", color=INK,
                                 ha="left", va="center", zorder=4), w * 0.55))
        labels.append((axes.text(x_frac + w - pad, row_y - row_h / 2, reviewer or "TBC",
                                 fontsize=max(5.5, 7.0 * scale), fontweight="bold",
                                 color=TBC_RED if tbc else ASSURANCE_AMBER,
                                 ha="right", va="center", zorder=4), w * 0.42))
        row_y -= row_h
    return top_frac - total_h


# ---------------------------------------------------------------------------
# A. Executive cards
# ---------------------------------------------------------------------------
#
# Vertical sequence: client box -> connector -> top leadership card ->
# connector -> a wrapped "rank" row of any remaining co-leads/reviewers ->
# a gap that also reserves room for the Peer Review panel beside it ->
# discipline columns, wrapped into further rows past a handful of
# disciplines. Built as one _Flow so the whole sequence shares a single
# scale factor and a single pool of distributable vertical slack.

_CARDS_CLIENT_W_IN = 3.0
_CARDS_CLIENT_H_IN = 0.55
_CARDS_CARD_W_IN = 2.55
_CARDS_CARD_H_IN = 0.66
_CARDS_COL_GAP_IN = 0.26
_CARDS_ROW_GAP_IN = 0.14
_CARDS_CONNECTOR_IN = 0.22
_CARDS_CAPTION_IN = 0.26
_CARDS_SECTION_GAP_IN = 0.24
_CARDS_ROW_TO_ROW_IN = 0.22


def _avatar_card(figure, axes, x, y, w, h, person: Person, accent: str, scale: float,
                 badge: str = ""):
    """A white card with a top accent rule, a circular initials avatar, and
    the person's stacked lines. A TBC card is dashed and red throughout --
    the same convention every other unknown in this tool uses. Every size on
    the card is either a fraction of its own (already-scaled) w/h, or takes
    `scale` directly for the few things that aren't -- so the card grows and
    shrinks as one coherent unit rather than each piece separately."""
    tbc = person.is_tbc
    lw = max(0.7, min(1.3, 0.9 * scale))
    _card(axes, x, y, w, h,
          facecolor=TBC_FILL if tbc else CARD_WHITE,
          edgecolor=TBC_RED if tbc else CARD_EDGE,
          linewidth=lw, linestyle=(0, (2.4, 1.8)) if tbc else "solid")
    # Only a lead's card carries the top rule. A support member's card sitting
    # under it with the same bar made the two read as peers.
    if not tbc and person.is_lead:
        bar_h = h * 0.09
        _accent_bar(axes, x, y + h - bar_h, w, accent, height=bar_h)
    badge_artist = None
    if badge and not tbc:
        badge_w, badge_h = w * 0.46, h * 0.30
        bx = x + w - badge_w - w * 0.02
        by = y + h - badge_h * 0.55
        _card(axes, bx, by, badge_w, badge_h, facecolor=ASSURANCE_FILL,
              edgecolor=ASSURANCE_AMBER, radius=badge_h / 3, linewidth=0.7, zorder=4)
        badge_artist = axes.text(bx + badge_w / 2, by + badge_h / 2, badge.upper(),
                                 fontsize=max(5.0, 5.8 * scale), fontweight="bold",
                                 color=ASSURANCE_AMBER, ha="center", va="center", zorder=5)

    # An Ellipse, not a Circle: the axes aren't equal-aspect (the page itself
    # isn't square), so a patch with an equal x/y data radius would draw as a
    # slight oval. Correcting the x radius by the page's own aspect ratio is
    # what actually makes the avatar look round in the rendered PNG.
    from matplotlib.patches import Ellipse

    r_y = h * 0.30
    r_x = r_y * (PAGE_H_IN / PAGE_W_IN)
    cx, cy = x + w * 0.15, y + h / 2
    axes.add_patch(Ellipse((cx, cy), r_x * 2, r_y * 2,
                           facecolor=TBC_FILL if tbc else _tint(accent, 0.88),
                           edgecolor="none", zorder=3))
    axes.text(cx, cy, person.initials, fontsize=max(6.5, 7.6 * scale), fontweight="bold",
              color=TBC_RED if tbc else accent, ha="center", va="center", zorder=4)

    lines = _person_lines(person, role_colour=accent, scale=scale)
    text_x = x + w * 0.28
    max_frac = w - w * 0.32
    step = h * 0.30
    first_y = y + h / 2 + (len(lines) - 1) * step / 2
    labels = []
    if badge_artist is not None:
        labels.append((badge_artist, badge_w - _x_in(0.04)))
    for index, (text, size, bold, colour) in enumerate(lines):
        artist = axes.text(text_x, first_y - index * step, text, fontsize=size,
                           fontweight="bold" if bold else "normal", color=colour,
                           ha="left", va="center", zorder=4)
        labels.append((artist, max_frac))
    return labels


def _render_cards(model: OrgModel, accent: str, language: str | None = None):
    if model.is_empty:
        return _empty_figure(model, language=language)

    figure, axes = _new_figure()
    _title(axes, model, language=language)
    labels: list[tuple[object, float]] = []
    centre = (CONTENT_LEFT + CONTENT_RIGHT) / 2
    # The Peer Review panel floats beside the leadership section (client/
    # top-person/rank) but the discipline rows always sit BELOW the panel,
    # never beside it (panel_extra_in below pushes them down whenever the
    # panel is taller than the leadership section) -- so only the leadership
    # rows need to make room for it horizontally. Centring leadership on the
    # panel-reduced width (lead_centre), while the discipline rows keep the
    # full-width centre, means the panel's width is reserved once, not
    # mirrored on both sides of the page centre for content that never sits
    # next to it.
    _panel_reserve_in = _PANEL_W_IN * MAX_SCALE if model.disciplines else 0.0
    lead_centre = (CONTENT_LEFT + _x_in(AVAIL_W_IN - _panel_reserve_in) / 2
                  if model.disciplines else centre)

    lead_people = list(model.leadership)
    top_person = lead_people[0] if lead_people else None
    qa_badge = (export_i18n.export_t("pptx_qa_review_badge", language) if language is not None
               else "QA / Review")
    rank = [(p, "") for p in lead_people[1:]] + [(p, qa_badge) for p in model.assurance]
    rank_per_row = _balanced_wrap(len(rank), 4) if rank else 0
    rank_rows = -(-len(rank) // rank_per_row) if rank else 0
    rank_h_in = (rank_rows * _CARDS_CARD_H_IN + max(0, rank_rows - 1) * _CARDS_ROW_GAP_IN) if rank else 0.0

    # How tall the leadership section (everything above the disciplines) is
    # at reference scale -- used only to make sure the Peer Review panel,
    # which floats beside it rather than flowing through it, always has
    # somewhere to fit without overlapping the leadership cards above it.
    leadership_h_in = _CARDS_CLIENT_H_IN
    if top_person is not None:
        leadership_h_in += _CARDS_CONNECTOR_IN + _CARDS_CARD_H_IN
    if rank:
        leadership_h_in += _CARDS_CONNECTOR_IN + rank_h_in
    panel_h_in = (_PANEL_HEADER_IN + len(model.disciplines) * _PANEL_ROW_IN) if model.disciplines else 0.0
    panel_extra_in = max(0.0, panel_h_in - leadership_h_in)

    def build_flow(per_row):
        disciplines = model.disciplines
        chunks = ([disciplines[i:i + per_row] for i in range(0, len(disciplines), per_row)]
                 if disciplines else [])
        row_infos = []
        disc_width_in = 0.0
        for chunk in chunks:
            tallest = max(len(g.people) for g in chunk)
            row_h_in = (_CARDS_CAPTION_IN + tallest * _CARDS_CARD_H_IN
                       + max(0, tallest - 1) * _CARDS_ROW_GAP_IN)
            row_infos.append((chunk, row_h_in))
            width = len(chunk) * _CARDS_CARD_W_IN + (len(chunk) - 1) * _CARDS_COL_GAP_IN
            disc_width_in = max(disc_width_in, width)
        rank_width_in = ((rank_per_row * _CARDS_CARD_W_IN + max(0, rank_per_row - 1) * _CARDS_COL_GAP_IN)
                         if rank else 0.0)
        leadership_width_in = max(_CARDS_CLIENT_W_IN, _CARDS_CARD_W_IN, rank_width_in)
        # The Peer Review panel sits beside the (separately-centred)
        # leadership section but always below the discipline rows -- so each
        # needs its own fit check against the width it actually has (the
        # leadership section's width excludes the panel's reserved slice,
        # the discipline rows' doesn't). Both are expressed as a fraction of
        # their own available width, and the larger (more binding) fraction
        # is converted back into an equivalent row_width_in against the FULL
        # available width, so the existing width_fit = AVAIL_W_IN /
        # row_width_in in _solve_scale still picks up whichever one binds.
        lead_avail_in = (AVAIL_W_IN - _panel_reserve_in) if disciplines else AVAIL_W_IN
        lead_ratio = (leadership_width_in / lead_avail_in) if lead_avail_in > 0 else 1.0
        disc_ratio = (disc_width_in / AVAIL_W_IN) if disc_width_in > 0 else 0.0
        row_width_in = max(lead_ratio, disc_ratio) * AVAIL_W_IN

        flow = _Flow()

        def draw_client(y_top, y_bottom, scale):
            w = _x_in(_CARDS_CLIENT_W_IN * scale)
            h = y_top - y_bottom
            x = lead_centre - w / 2
            _card(axes, x, y_bottom, w, h, facecolor=CLIENT_DARK, edgecolor=CLIENT_DARK)
            client_placeholder = (export_i18n.export_t("export_client_name_placeholder", language)
                                 if language is not None else "[CLIENT NAME]")
            labels.append((axes.text(lead_centre, y_bottom + h * 0.62,
                                     model.client_name or client_placeholder,
                                     fontsize=max(8.5, 11.0 * scale), fontweight="bold",
                                     color="#FFFFFF" if model.client_name else "#FCA5A5",
                                     ha="center", va="center", zorder=4), w - _x_in(0.14)))
            axes.text(lead_centre, y_bottom + h * 0.26, model.client_role,
                      fontsize=max(6.0, 8.0 * scale), fontweight="bold", color="#9CA3AF",
                      ha="center", va="center", zorder=4)
        flow.block(_CARDS_CLIENT_H_IN, draw_client)

        if top_person is not None:
            def draw_conn1(y_top, y_bottom, scale):
                _line(axes, lead_centre, y_top, lead_centre, y_bottom, width=max(0.7, 0.9 * scale))
            flow.connector(_CARDS_CONNECTOR_IN, draw_conn1)

            def draw_top(y_top, y_bottom, scale):
                w = _x_in(_CARDS_CARD_W_IN * scale)
                h = y_top - y_bottom
                x = lead_centre - w / 2
                labels.extend(_avatar_card(figure, axes, x, y_bottom, w, h, top_person, accent, scale))
            flow.block(_CARDS_CARD_H_IN, draw_top)

        if rank:
            def draw_conn2(y_top, y_bottom, scale):
                _line(axes, lead_centre, y_top, lead_centre, y_bottom, width=max(0.7, 0.9 * scale))
            flow.connector(_CARDS_CONNECTOR_IN, draw_conn2)

            def draw_rank(y_top, y_bottom, scale):
                row_h = _y_in(_CARDS_CARD_H_IN * scale)
                row_gap = _y_in(_CARDS_ROW_GAP_IN * scale)
                col_gap = _x_in(_CARDS_COL_GAP_IN * scale)
                col_w = _x_in(_CARDS_CARD_W_IN * scale)
                row_chunks = [rank[i:i + rank_per_row] for i in range(0, len(rank), rank_per_row)]
                ry = y_top
                for row_chunk in row_chunks:
                    total = len(row_chunk) * col_w + (len(row_chunk) - 1) * col_gap
                    rx = lead_centre - total / 2
                    for person, badge in row_chunk:
                        labels.extend(_avatar_card(figure, axes, rx, ry - row_h, col_w, row_h,
                                                   person, ASSURANCE_AMBER if badge else accent,
                                                   scale, badge=badge))
                        rx += col_w + col_gap
                    ry -= row_h + row_gap
            flow.block(rank_h_in, draw_rank)

        if disciplines:
            def draw_elbow(y_top, y_bottom, scale):
                # The leadership trunk runs down lead_centre (shifted left to
                # leave the panel clear); the discipline rows fan out from
                # the full-page centre instead, since they always sit below
                # the panel and have no reason to give up that width. This
                # jog reconciles the two centrelines within the (usually
                # generously stretched) gap between them, rather than
                # leaving a visibly kinked single line or silently
                # mismatched brackets.
                if abs(lead_centre - centre) > 1e-6:
                    y_mid = (y_top + y_bottom) / 2
                    _line(axes, lead_centre, y_top, lead_centre, y_mid, width=max(0.7, 0.9 * scale))
                    _line(axes, lead_centre, y_mid, centre, y_mid, width=max(0.7, 0.9 * scale))
                    _line(axes, centre, y_mid, centre, y_bottom, width=max(0.7, 0.9 * scale))
                else:
                    _line(axes, centre, y_top, centre, y_bottom, width=max(0.7, 0.9 * scale))
            flow.connector(_CARDS_SECTION_GAP_IN + panel_extra_in, draw_elbow)

            def draw_stub(y_top, y_bottom, scale):
                _line(axes, centre, y_top, centre, y_bottom, width=max(0.7, 0.9 * scale))
            flow.connector(_CARDS_CONNECTOR_IN, draw_stub)

            for row_index, (chunk, row_h_in) in enumerate(row_infos):
                def draw_row(y_top, y_bottom, scale, chunk=chunk):
                    bus_y = y_top
                    col_w = _x_in(_CARDS_CARD_W_IN * scale)
                    col_gap = _x_in(_CARDS_COL_GAP_IN * scale)
                    total = len(chunk) * col_w + (len(chunk) - 1) * col_gap
                    x0 = centre - total / 2
                    centres = [x0 + col_w / 2 + i * (col_w + col_gap) for i in range(len(chunk))]
                    if len(centres) > 1:
                        _line(axes, centres[0], bus_y, centres[-1], bus_y, width=max(0.7, 0.9 * scale))
                    caption_h = _y_in(_CARDS_CAPTION_IN * scale)
                    card_h = _y_in(_CARDS_CARD_H_IN * scale)
                    row_gap = _y_in(_CARDS_ROW_GAP_IN * scale)
                    for i, group in enumerate(chunk):
                        cx = centres[i]
                        _line(axes, cx, bus_y, cx, bus_y - caption_h * 0.35, width=max(0.7, 0.9 * scale))
                        axes.text(cx, bus_y - caption_h * 0.68, group.name.upper(),
                                  fontsize=max(6.0, 7.6 * scale), fontweight="bold", color=MUTED,
                                  ha="center", va="center")
                        card_y = bus_y - caption_h
                        gx = x0 + i * (col_w + col_gap)
                        for person in group.people:
                            labels.extend(_avatar_card(figure, axes, gx, card_y - card_h, col_w,
                                                       card_h, person, accent, scale))
                            card_y -= card_h + row_gap
                flow.block(row_h_in, draw_row)
                if row_index < len(row_infos) - 1:
                    flow.gap(_CARDS_ROW_TO_ROW_IN)

        return flow, row_width_in

    per_row_candidates = _row_candidates(len(model.disciplines)) if model.disciplines else [1]
    flow, scale, per_row = _solve_scale(build_flow, per_row_candidates)
    flow.render(CONTENT_TOP, scale)

    if model.disciplines:
        panel_w = _x_in(_PANEL_W_IN * scale)
        panel_x = CONTENT_RIGHT - panel_w
        _draw_peer_review_panel(axes, model, scale, labels, panel_x, CONTENT_TOP, _PANEL_W_IN, language)

    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure


# ---------------------------------------------------------------------------
# B. Discipline columns
# ---------------------------------------------------------------------------

_COLUMNS_PILL_H_IN = 0.55
_COLUMNS_CLIENT_W_IN = 3.4
_COLUMNS_LEAD_W1_IN = 3.0
_COLUMNS_LEAD_W2_IN = 2.5
_COLUMNS_CONNECTOR_IN = 0.20
_COLUMNS_LANE_W_IN = 2.75
_COLUMNS_LANE_GAP_IN = 0.24
_COLUMNS_ROW_H_IN = 0.62
_COLUMNS_CAPTION_IN = 0.32
_COLUMNS_ROW_GAP_IN = 0.12
_COLUMNS_LANE_PAD_IN = 0.10
_COLUMNS_SECTION_GAP_IN = 0.26
_COLUMNS_ROW_TO_ROW_IN = 0.22
_COLUMNS_STRIP_H_IN = 0.55
_COLUMNS_STRIP_W_IN = 7.5


def _pill(axes, x, y, w, h, facecolor, label, sub, label_colour, sub_colour, scale):
    _card(axes, x, y, w, h, facecolor=facecolor, edgecolor=facecolor, radius=min(w, h) * 0.16)
    if sub:
        artist = axes.text(x + w / 2, y + h * 0.62, label, fontsize=max(8.5, 11.5 * scale),
                           fontweight="bold", color=label_colour, ha="center", va="center", zorder=4)
        axes.text(x + w / 2, y + h * 0.26, sub, fontsize=max(6.0, 8.5 * scale), fontweight="bold",
                  color=sub_colour, ha="center", va="center", zorder=4)
    else:
        artist = axes.text(x + w / 2, y + h / 2, label, fontsize=max(8.5, 11.5 * scale),
                           fontweight="bold", color=label_colour, ha="center", va="center", zorder=4)
    return artist


def _render_columns(model: OrgModel, accent: str, language: str | None = None):
    if model.is_empty:
        return _empty_figure(model, language=language)

    figure, axes = _new_figure()
    _title(axes, model, language=language)
    labels: list[tuple[object, float]] = []
    centre = (CONTENT_LEFT + CONTENT_RIGHT) / 2

    def build_flow(per_row):
        disciplines = model.disciplines
        chunks = ([disciplines[i:i + per_row] for i in range(0, len(disciplines), per_row)]
                 if disciplines else [])
        row_infos = []
        row_width_in = _COLUMNS_CLIENT_W_IN
        for chunk in chunks:
            tallest = max(len(g.people) for g in chunk)
            row_h_in = (_COLUMNS_CAPTION_IN + tallest * _COLUMNS_ROW_H_IN
                       + max(0, tallest - 1) * _COLUMNS_ROW_GAP_IN + 2 * _COLUMNS_LANE_PAD_IN)
            row_infos.append((chunk, row_h_in))
            width = len(chunk) * _COLUMNS_LANE_W_IN + (len(chunk) - 1) * _COLUMNS_LANE_GAP_IN
            row_width_in = max(row_width_in, width)

        flow = _Flow()

        def draw_client(y_top, y_bottom, scale):
            w = _x_in(_COLUMNS_CLIENT_W_IN * scale)
            h = y_top - y_bottom
            x = centre - w / 2
            if language is not None:
                client_placeholder = export_i18n.export_t("export_client_name_placeholder", language)
                label = export_i18n.export_t("pptx_client_suffix_label", language,
                                              label=(model.client_name or client_placeholder))
            else:
                label = f"{model.client_name or '[CLIENT NAME]'} — Client"
            colour = "#FFFFFF" if model.client_name else "#FCA5A5"
            labels.append((_pill(axes, x, y_bottom, w, h, CLIENT_DARK, label, "", colour, colour,
                                 scale), w - _x_in(0.15)))
        flow.block(_COLUMNS_PILL_H_IN, draw_client)

        for index, person in enumerate(model.leadership):
            def draw_conn(y_top, y_bottom, scale):
                _line(axes, centre, y_top, centre, y_bottom, width=max(0.7, 0.9 * scale))
            flow.connector(_COLUMNS_CONNECTOR_IN, draw_conn)

            def draw_lead(y_top, y_bottom, scale, person=person, index=index):
                width_in = _COLUMNS_LEAD_W1_IN if index == 0 else _COLUMNS_LEAD_W2_IN
                w = _x_in(width_in * scale)
                h = y_top - y_bottom
                x = centre - w / 2
                tbc = person.is_tbc
                fill = accent if index == 0 else _rgb_hex(_tint(accent, 0.18))
                fc = TBC_FILL if tbc else fill
                label_colour = TBC_RED if tbc else "#FFFFFF"
                sub_colour = TBC_RED if tbc else "#D7DEEA"
                labels.append((_pill(axes, x, y_bottom, w, h, fc, person.name or "TBC", person.role,
                                     label_colour, sub_colour, scale), w - _x_in(0.15)))
            flow.block(_COLUMNS_PILL_H_IN, draw_lead)

        if disciplines:
            flow.gap(_COLUMNS_SECTION_GAP_IN)
            for row_index, (chunk, row_h_in) in enumerate(row_infos):
                def draw_row(y_top, y_bottom, scale, chunk=chunk):
                    lane_w = _x_in(_COLUMNS_LANE_W_IN * scale)
                    lane_gap = _x_in(_COLUMNS_LANE_GAP_IN * scale)
                    total = len(chunk) * lane_w + (len(chunk) - 1) * lane_gap
                    x0 = centre - total / 2
                    lane_h = y_top - y_bottom
                    for i, group in enumerate(chunk):
                        colour_hex = _discipline_colour(
                            group.people[0].group_index if group.people else disciplines.index(group))
                        lx = x0 + i * (lane_w + lane_gap)
                        _card(axes, lx, y_bottom, lane_w, lane_h, facecolor="#F7F9FC",
                              edgecolor="#EDF1F6", radius=lane_w * 0.03, zorder=1)
                        bar_h = _y_in(0.07 * scale)
                        _accent_bar(axes, lx, y_top - bar_h, lane_w, colour_hex, height=bar_h)
                        caption_h = _y_in(_COLUMNS_CAPTION_IN * scale)
                        labels.append((axes.text(lx + lane_w / 2, y_top - caption_h * 0.6,
                                                 group.name.upper(), fontsize=max(7.0, 9.2 * scale),
                                                 fontweight="bold", color=colour_hex, ha="center",
                                                 va="center", zorder=4), lane_w - _x_in(0.14)))
                        pad = _x_in(_COLUMNS_LANE_PAD_IN * scale)
                        row_h = _y_in(_COLUMNS_ROW_H_IN * scale)
                        row_gap = _y_in(_COLUMNS_ROW_GAP_IN * scale)
                        card_y = y_top - caption_h
                        for person in group.people:
                            tbc = person.is_tbc
                            _card(axes, lx + pad, card_y - row_h, lane_w - 2 * pad, row_h,
                                  facecolor=TBC_FILL if tbc else CARD_WHITE,
                                  edgecolor=TBC_RED if tbc else CARD_EDGE,
                                  linestyle=(0, (2.4, 1.8)) if tbc else "solid", radius=row_h * 0.12)
                            lines = _person_lines(person, role_colour=colour_hex, scale=scale)
                            step = row_h * 0.42
                            first = card_y - row_h / 2 + (len(lines) - 1) * step / 2
                            for li, (text, size, bold, lc) in enumerate(lines):
                                labels.append((axes.text(lx + lane_w / 2, first - li * step, text,
                                                         fontsize=size,
                                                         fontweight="bold" if bold else "normal",
                                                         color=lc, ha="center", va="center", zorder=4),
                                              lane_w - _x_in(0.2)))
                            card_y -= row_h + row_gap
                flow.block(row_h_in, draw_row)
                if row_index < len(row_infos) - 1:
                    flow.gap(_COLUMNS_ROW_TO_ROW_IN)

        if model.assurance:
            flow.gap(_COLUMNS_SECTION_GAP_IN)

            def draw_strip(y_top, y_bottom, scale):
                w = _x_in(_COLUMNS_STRIP_W_IN * scale)
                h = y_top - y_bottom
                x = centre - w / 2
                _card(axes, x, y_bottom, w, h, facecolor=ASSURANCE_FILL,
                      edgecolor="#FBBF24", radius=h * 0.2)
                text = " · ".join(f"{p.name or 'TBC'} — {p.role}" for p in model.assurance)
                strip_text = (export_i18n.export_t("pptx_independent_review_prefix", language, text=text)
                             if language is not None else f"★ Independent review: {text}")
                labels.append((axes.text(centre, y_bottom + h / 2, strip_text,
                                         fontsize=max(7.0, 9.2 * scale), fontweight="bold",
                                         color=ASSURANCE_AMBER, ha="center", va="center", zorder=4),
                              w - _x_in(0.2)))
            flow.block(_COLUMNS_STRIP_H_IN, draw_strip)

        if disciplines:
            flow.gap(_COLUMNS_SECTION_GAP_IN)
            panel_h_in = _PANEL_HEADER_IN + len(disciplines) * _PANEL_ROW_IN

            def draw_panel(y_top, y_bottom, scale):
                w = _x_in(_PANEL_W_IN * scale)
                x = centre - w / 2
                _draw_peer_review_panel(axes, model, scale, labels, x, y_top, _PANEL_W_IN, language)
            flow.block(panel_h_in, draw_panel)

        return flow, row_width_in

    per_row_candidates = _row_candidates(len(model.disciplines)) if model.disciplines else [1]
    flow, scale, per_row = _solve_scale(build_flow, per_row_candidates)
    flow.render(CONTENT_TOP, scale)

    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure


# ---------------------------------------------------------------------------
# C. Governance bands
# ---------------------------------------------------------------------------
#
# Bands are full content-width by design -- unlike the column-based styles,
# there's no "row of N boxes" whose count trades off against width, so this
# style isn't part of the _solve_scale per-row search. Only band/chip HEIGHT
# and font sizes scale; each chip's WIDTH and which row it wraps onto are
# decided once, at reference sizing, purely from the fixed page width and
# the chips' own text lengths -- keeping width fixed is what guarantees a
# scaled-up band never runs its chips past the page margin.

_BANDS_LABEL_W_IN = 1.6
_BANDS_CHIP_H_IN = 0.62
_BANDS_CHIP_GAP_IN = 0.16
_BANDS_PAD_IN = 0.14
_BANDS_SECTION_GAP_IN = 0.20


def _render_bands(model: OrgModel, accent: str, language: str | None = None):
    if model.is_empty:
        return _empty_figure(model, language=language)

    figure, axes = _new_figure()
    _title(axes, model, language=language)
    labels: list[tuple[object, float]] = []

    band_left = CONTENT_LEFT + _x_in(_BANDS_LABEL_W_IN)
    band_right = CONTENT_RIGHT
    avail_in = (band_right - band_left) * PAGE_W_IN

    def chip_rows(chips):
        """Which row each chip wraps onto, and each chip's WIDTH in inches --
        both fixed regardless of scale (see the note above)."""
        widths_in = [min(2.6, max(1.35, 0.30 + 0.078 * max(len(name), len(role))))
                    for name, role, *_rest in chips]
        rows, used = [[]], 0.0
        for index, w in enumerate(widths_in):
            if rows[-1] and used + w + _BANDS_CHIP_GAP_IN > avail_in - 2 * _BANDS_PAD_IN:
                rows.append([])
                used = 0.0
            rows[-1].append(index)
            used += w + _BANDS_CHIP_GAP_IN
        return rows, widths_in

    flow = _Flow()

    def make_band(title, chips, fill, chip_edge=CARD_EDGE):
        if not chips:
            return
        rows, widths_in = chip_rows(chips)
        band_h_in = (2 * _BANDS_PAD_IN + len(rows) * _BANDS_CHIP_H_IN
                    + max(0, len(rows) - 1) * _BANDS_CHIP_GAP_IN)

        def draw(y_top, y_bottom, scale, title=title, chips=chips, fill=fill, chip_edge=chip_edge,
                 rows=rows, widths_in=widths_in):
            h = y_top - y_bottom
            _card(axes, band_left, y_bottom, band_right - band_left, h, facecolor=fill,
                  edgecolor="none", radius=_y_in(0.08 * scale), linewidth=0, zorder=1)
            axes.text(band_left - _x_in(0.06), y_bottom + h / 2, title.upper(),
                      fontsize=max(6.5, 8.0 * scale), fontweight="bold", color=MUTED,
                      ha="right", va="center")
            chip_gap = _x_in(_BANDS_CHIP_GAP_IN * scale)
            chip_h = _y_in(_BANDS_CHIP_H_IN * scale)
            chip_y = y_top - _y_in(_BANDS_PAD_IN * scale)
            for row in rows:
                x = band_left + _x_in(_BANDS_PAD_IN)
                for index in row:
                    name, role, tbc, role_colour = chips[index]
                    w = _x_in(widths_in[index])
                    _card(axes, x, chip_y - chip_h, w, chip_h,
                          facecolor=TBC_FILL if tbc else CARD_WHITE,
                          edgecolor=TBC_RED if tbc else chip_edge,
                          linestyle=(0, (2.4, 1.8)) if tbc else "solid", radius=chip_h * 0.12, zorder=2)
                    lines = [(name, max(8.0, 11.0 * scale), True, TBC_RED if tbc else INK),
                             (role, max(6.0, 8.2 * scale), True, TBC_RED if tbc else role_colour)]
                    lines = [line for line in lines if line[0]]
                    step = chip_h * 0.34
                    first = chip_y - chip_h / 2 + (len(lines) - 1) * step / 2
                    for li, (text, size, bold, colour) in enumerate(lines):
                        labels.append((axes.text(x + _x_in(0.08), first - li * step, text,
                                                 fontsize=size, fontweight="bold" if bold else "normal",
                                                 color=colour, ha="left", va="center", zorder=3),
                                      w - _x_in(0.16)))
                    x += w + chip_gap
                chip_y -= chip_h + chip_gap

        flow.block(band_h_in, draw)
        flow.gap(_BANDS_SECTION_GAP_IN)

    if language is not None:
        client_band_title = export_i18n.export_t("pptx_org_band_client", language)
        leadership_band_title = export_i18n.export_t("pptx_org_band_leadership", language)
        delivery_band_title = export_i18n.export_t("pptx_org_band_delivery_team", language)
        assurance_band_title = export_i18n.export_t("pptx_org_band_assurance", language)
        client_placeholder = export_i18n.export_t("export_client_name_placeholder", language)
    else:
        client_band_title = "Client"
        leadership_band_title = "Leadership"
        delivery_band_title = "Delivery team"
        assurance_band_title = "Assurance"
        client_placeholder = "[CLIENT NAME]"

    make_band(client_band_title,
             [(model.client_name or client_placeholder, model.client_role, False, MUTED)],
              CLIENT_DARK, chip_edge=CLIENT_DARK)
    make_band(leadership_band_title,
             [(p.name or "TBC", p.role, p.is_tbc, accent) for p in model.leadership],
             _tint(accent, 0.94))
    delivery = []
    for group in model.disciplines:
        colour = _discipline_colour(group.people[0].group_index if group.people else 0)
        for person in group.people:
            role = (person.role if person.role.startswith(group.name)
                   else f"{person.role} · {group.name}")
            delivery.append((person.name or "TBC", role, person.is_tbc,
                            colour if person.is_lead else MUTED))
    make_band(delivery_band_title, delivery, _tint(DISCIPLINE_COLOURS[1], 0.95))
    # The Assurance band now ALWAYS carries the Peer Review element -- one
    # row per discipline, red TBC until a reviewer is entered -- alongside
    # any dedicated reviewer role the plan holds, so the band appears
    # whenever there is at least one discipline rather than only once a
    # reviewer slot exists.
    assurance_chips = [(p.name or "TBC", p.role, p.is_tbc, ASSURANCE_AMBER) for p in model.assurance]
    assurance_chips += [
        (group.peer_reviewer or "TBC",
         (export_i18n.export_t("pptx_org_peer_review", language, name=group.name)
          if language is not None else f"Peer review — {group.name}"),
         not bool((group.peer_reviewer or "").strip()), ASSURANCE_AMBER)
        for group in model.disciplines
    ]
    make_band(assurance_band_title, assurance_chips, _tint(ASSURANCE_AMBER, 0.93))

    def draw_footnote(y_top, y_bottom, scale):
        if language is not None:
            footnote_key = ("pptx_org_footnote_with_assurance" if (model.has_assurance or model.disciplines)
                            else "pptx_org_footnote_plain")
            text = export_i18n.export_t(footnote_key, language)
        else:
            text = (("Solid reporting lines run top-down; the assurance band reviews independently "
                    "of the delivery team.") if (model.has_assurance or model.disciplines) else
                   "Solid reporting lines run top-down.")
        axes.text(band_left, y_top, text, fontsize=max(6.5, 8.0 * scale), fontweight="bold",
                  color=SUBTLE, ha="left", va="top")
    flow.block(0.22, draw_footnote)

    natural_h = flow.natural_height_in()
    scale = max(MIN_SCALE, min(MAX_SCALE, AVAIL_H_IN / natural_h if natural_h > 0 else MAX_SCALE))
    flow.render(CONTENT_TOP, scale)

    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure


# ---------------------------------------------------------------------------
# D. Classic tree
# ---------------------------------------------------------------------------

_TREE_BOX_W_IN = 2.6
_TREE_BOX_H_IN = 0.62
_TREE_COL_GAP_IN = 0.26
_TREE_ROW_GAP_IN = 0.14
_TREE_CONNECTOR_IN = 0.22
_TREE_SECTION_GAP_IN = 0.22
_TREE_ROW_TO_ROW_IN = 0.20


def _tree_box(axes, x, y, w, h, person_lines, scale, accent=None, tbc=False):
    linewidth = max(0.8, min(1.6, 1.4 * scale)) if (accent or tbc) else max(0.7, min(1.3, 1.0 * scale))
    _card(axes, x, y, w, h, facecolor=CARD_WHITE,
          edgecolor=TBC_RED if tbc else (accent or INK), linewidth=linewidth,
          linestyle=(0, (2.6, 2.0)) if tbc else "solid", radius=h * 0.05)
    step = h * 0.30
    first = y + h / 2 + (len(person_lines) - 1) * step / 2
    out = []
    for index, (text, size, bold, colour) in enumerate(person_lines):
        artist = axes.text(x + w / 2, first - index * step, text, fontsize=size,
                           fontweight="bold" if bold else "normal", color=colour,
                           ha="center", va="center", zorder=4)
        out.append((artist, w - _x_in(0.10)))
    return out


def _render_tree(model: OrgModel, accent: str, language: str | None = None):
    if model.is_empty:
        return _empty_figure(model, language=language)

    figure, axes = _new_figure()
    _title(axes, model, language=language)
    labels: list[tuple[object, float]] = []
    panel_anchor: dict = {}
    centre = (CONTENT_LEFT + CONTENT_RIGHT) / 2
    # Same split as the cards style: the director level sits beside the
    # panel and gives up width for it; the discipline rows always sit below
    # the panel (panel_extra_in below pushes them down whenever the panel is
    # taller than the director level) and keep the full-width centre.
    _panel_reserve_in = _PANEL_W_IN * MAX_SCALE if model.disciplines else 0.0
    lead_centre = (CONTENT_LEFT + _x_in(AVAIL_W_IN - _panel_reserve_in) / 2
                  if model.disciplines else centre)

    lead_people = list(model.leadership)
    top_person = lead_people[0] if lead_people else None
    rank = lead_people[1:] + model.assurance
    rank_per_row = _balanced_wrap(len(rank), 4) if rank else 0
    rank_rows = -(-len(rank) // rank_per_row) if rank else 0
    rank_h_in = (rank_rows * _TREE_BOX_H_IN + max(0, rank_rows - 1) * _TREE_ROW_GAP_IN) if rank else 0.0

    # The director level -- client box, then (if present) the top leadership
    # box -- is where the Peer Review panel is anchored, level with the top
    # box rather than the flowing cursor below it (see org_chart_pptx's
    # identical convention). Tracked here so both the panel's own top
    # position AND the flow's reserved room for it agree with each other.
    director_h_in = _TREE_BOX_H_IN + (_TREE_CONNECTOR_IN if top_person is not None else 0.0)
    leadership_h_in = _TREE_BOX_H_IN
    if top_person is not None:
        leadership_h_in += _TREE_CONNECTOR_IN + _TREE_BOX_H_IN
    if rank:
        leadership_h_in += _TREE_CONNECTOR_IN + rank_h_in
    panel_h_in = (_PANEL_HEADER_IN + len(model.disciplines) * _PANEL_ROW_IN) if model.disciplines else 0.0
    panel_extra_in = max(0.0, director_h_in + panel_h_in - leadership_h_in)

    def build_flow(per_row):
        disciplines = model.disciplines
        chunks = ([disciplines[i:i + per_row] for i in range(0, len(disciplines), per_row)]
                 if disciplines else [])
        row_infos = []
        disc_width_in = 0.0
        for chunk in chunks:
            tallest = max(len(g.people) for g in chunk)
            row_h_in = (_TREE_CONNECTOR_IN + tallest * _TREE_BOX_H_IN
                       + max(0, tallest - 1) * _TREE_ROW_GAP_IN)
            row_infos.append((chunk, row_h_in))
            width = len(chunk) * _TREE_BOX_W_IN + (len(chunk) - 1) * _TREE_COL_GAP_IN
            disc_width_in = max(disc_width_in, width)
        rank_width_in = ((rank_per_row * _TREE_BOX_W_IN + max(0, rank_per_row - 1) * _TREE_COL_GAP_IN)
                         if rank else 0.0)
        leadership_width_in = max(_TREE_BOX_W_IN, rank_width_in)
        # Same split fit as the cards style -- see the comment above
        # lead_centre: the director level's own available width excludes the
        # panel's reserved slice, the discipline rows' doesn't, so each gets
        # its own fraction and the larger (more binding) one wins.
        lead_avail_in = (AVAIL_W_IN - _panel_reserve_in) if disciplines else AVAIL_W_IN
        lead_ratio = (leadership_width_in / lead_avail_in) if lead_avail_in > 0 else 1.0
        disc_ratio = (disc_width_in / AVAIL_W_IN) if disc_width_in > 0 else 0.0
        row_width_in = max(lead_ratio, disc_ratio) * AVAIL_W_IN

        flow = _Flow()

        def draw_client(y_top, y_bottom, scale):
            w = _x_in(_TREE_BOX_W_IN * scale)
            h = y_top - y_bottom
            x = lead_centre - w / 2
            client_placeholder = (export_i18n.export_t("export_client_name_placeholder", language)
                                  if language is not None else "[CLIENT NAME]")
            labels.extend(_tree_box(axes, x, y_bottom, w, h, [
                (model.client_name or client_placeholder, max(8.5, 11.0 * scale), True,
                 INK if model.client_name else TBC_RED),
                (model.client_role, max(6.0, 8.5 * scale), True, MUTED),
            ], scale))
            if top_person is None:
                panel_anchor["y"] = y_bottom
        flow.block(_TREE_BOX_H_IN, draw_client)

        if top_person is not None:
            def draw_conn1(y_top, y_bottom, scale):
                _line(axes, lead_centre, y_top, lead_centre, y_bottom, colour=INK, width=max(0.7, 1.0 * scale))
            flow.connector(_TREE_CONNECTOR_IN, draw_conn1)

            def draw_top(y_top, y_bottom, scale):
                w = _x_in(_TREE_BOX_W_IN * scale)
                h = y_top - y_bottom
                x = lead_centre - w / 2
                labels.extend(_tree_box(axes, x, y_bottom, w, h,
                                        _person_lines(top_person, role_colour=INK, scale=scale),
                                        scale, accent=accent, tbc=top_person.is_tbc))
                # Where the panel beside this row actually anchors -- recorded
                # here (the ACTUAL drawn position) rather than recomputed from
                # reference heights, since the connector above this box can
                # itself stretch to absorb leftover page height, and a purely
                # analytical estimate would drift out of alignment with it.
                panel_anchor["y"] = y_top
            flow.block(_TREE_BOX_H_IN, draw_top)

        if rank:
            def draw_conn2(y_top, y_bottom, scale):
                _line(axes, lead_centre, y_top, lead_centre, y_bottom, colour=INK, width=max(0.7, 1.0 * scale))
            flow.connector(_TREE_CONNECTOR_IN, draw_conn2)

            def draw_rank(y_top, y_bottom, scale):
                row_h = _y_in(_TREE_BOX_H_IN * scale)
                row_gap = _y_in(_TREE_ROW_GAP_IN * scale)
                col_gap = _x_in(_TREE_COL_GAP_IN * scale)
                col_w = _x_in(_TREE_BOX_W_IN * scale)
                row_chunks = [rank[i:i + rank_per_row] for i in range(0, len(rank), rank_per_row)]
                ry = y_top
                for row_chunk in row_chunks:
                    total = len(row_chunk) * col_w + (len(row_chunk) - 1) * col_gap
                    rx = lead_centre - total / 2
                    for person in row_chunk:
                        labels.extend(_tree_box(axes, rx, ry - row_h, col_w, row_h,
                                                _person_lines(person, role_colour=INK, scale=scale),
                                                scale, tbc=person.is_tbc))
                        rx += col_w + col_gap
                    ry -= row_h + row_gap
            flow.block(rank_h_in, draw_rank)

        if disciplines:
            def draw_elbow(y_top, y_bottom, scale):
                # Reconciles the director level's lead_centre with the
                # discipline rows' full-width centre -- see the identical
                # comment in _render_cards.
                if abs(lead_centre - centre) > 1e-6:
                    y_mid = (y_top + y_bottom) / 2
                    _line(axes, lead_centre, y_top, lead_centre, y_mid, colour=INK, width=max(0.7, 1.0 * scale))
                    _line(axes, lead_centre, y_mid, centre, y_mid, colour=INK, width=max(0.7, 1.0 * scale))
                    _line(axes, centre, y_mid, centre, y_bottom, colour=INK, width=max(0.7, 1.0 * scale))
            flow.connector(_TREE_SECTION_GAP_IN + panel_extra_in, draw_elbow)

            for row_index, (chunk, row_h_in) in enumerate(row_infos):
                def draw_row(y_top, y_bottom, scale, chunk=chunk):
                    col_w = _x_in(_TREE_BOX_W_IN * scale)
                    col_gap = _x_in(_TREE_COL_GAP_IN * scale)
                    total = len(chunk) * col_w + (len(chunk) - 1) * col_gap
                    x0 = centre - total / 2
                    centres = [x0 + col_w / 2 + i * (col_w + col_gap) for i in range(len(chunk))]
                    bus_y = y_top - _y_in(_TREE_CONNECTOR_IN * scale * 0.4)
                    _line(axes, centre, y_top, centre, bus_y, colour=INK, width=max(0.7, 1.0 * scale))
                    if len(centres) > 1:
                        _line(axes, centres[0], bus_y, centres[-1], bus_y, colour=INK,
                              width=max(0.8, 1.2 * scale))
                    box_h = _y_in(_TREE_BOX_H_IN * scale)
                    row_gap = _y_in(_TREE_ROW_GAP_IN * scale)
                    box_top = bus_y - _y_in(_TREE_CONNECTOR_IN * scale * 0.6)
                    for i, group in enumerate(chunk):
                        cx = centres[i]
                        _line(axes, cx, bus_y, cx, box_top, colour=INK, width=max(0.7, 1.0 * scale))
                        by = box_top
                        for person in group.people:
                            labels.extend(_tree_box(axes, cx - col_w / 2, by - box_h, col_w, box_h,
                                                    _person_lines(person, role_colour=INK, scale=scale),
                                                    scale, tbc=person.is_tbc))
                            by -= box_h + row_gap
                flow.block(row_h_in, draw_row)
                if row_index < len(row_infos) - 1:
                    flow.gap(_TREE_ROW_TO_ROW_IN)

        return flow, row_width_in

    per_row_candidates = _row_candidates(len(model.disciplines)) if model.disciplines else [1]
    flow, scale, per_row = _solve_scale(build_flow, per_row_candidates)
    flow.render(CONTENT_TOP, scale)

    if model.disciplines:
        panel_w = _x_in(_PANEL_W_IN * scale)
        panel_top = panel_anchor.get("y", CONTENT_TOP - _y_in(director_h_in * scale))
        panel_x = CONTENT_RIGHT - panel_w
        _draw_peer_review_panel(axes, model, scale, labels, panel_x, panel_top, _PANEL_W_IN, language)

    for artist, max_frac in labels:
        _fit(figure, artist, max_frac)
    return figure
