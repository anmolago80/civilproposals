"""
graphics_engine.py

Identifies the graphics that should go in the pack and produces clear
placeholders for the ones this prototype can't actually generate. This is
deliberately deterministic (no AI call) -- it works off the section list
already assembled by proposal_structure.py.

Several graphics are now generated for real by the app -- the evaluation
weighting bar chart here, plus the org chart (org_chart.py /
org_chart_pptx.py), the methodology stage table (methodology_pptx.py), the
delivery program (program_pptx.py), the fee distribution pies below, and
the cover/divider banners (divider_designer.py). Those are reported as
Generated, with a pointer to where the user gets them. What remains a
placeholder is genuinely not generated anywhere: icon sets, brand
callouts, experience matrices, and anything needing a graphic designer.

Keeping this list honest matters more than it looks: it is printed into
the exported pack under "Graphics for this section", so a stale entry
tells a user to go and hand-build something the app already made for
them.

Divider/cover image sourcing priority, per the product brief: user-uploaded
project photos first, then a company project image library, then a stock/
royalty-free placeholder, then (in a future version) an AI-generated
conceptual image.
"""

from __future__ import annotations

import io

from pydantic import BaseModel

from modules.proposal_structure import ProposalSection
from modules.weighting_engine import WeightedCriterion

GRAPHIC_STATUSES = ["Generated", "Placeholder", "User Input Required"]


class GraphicRecommendation(BaseModel):
    graphic_title: str
    graphic_type: str
    purpose: str
    suggested_placement: str
    source_data_required: str
    status: str
    placeholder_text: str = ""


def recommend_graphics(
    sections: list[ProposalSection],
    has_project_photos: bool = False,
    has_company_image_library: bool = False,
    divider_image_sections: set[str] | None = None,
    cover_generated: bool = False,
    project_type: str | None = None,
) -> list[GraphicRecommendation]:
    """
    divider_image_sections: titles of sections that already have a REAL generated
    divider banner (see divider_designer.py / app.py's Graphics & Design tab) so this
    list reports them as Generated rather than still-outstanding placeholders.
    cover_generated: same idea for the cover page hero image/banner.
    project_type: this project's type from Project Setup, used for the divider
    image subject hint -- without it the hint falls back to a generic one
    rather than naming a project type this brief may have nothing to do with.
    """
    recs: list[GraphicRecommendation] = []
    divider_image_sections = divider_image_sections or set()

    image_source, image_status = _divider_image_source(has_project_photos, has_company_image_library)
    recs.append(GraphicRecommendation(
        graphic_title="Cover page hero image", graphic_type="Cover Image",
        purpose="Sets first impression; should visually reference the actual project/site.",
        suggested_placement="Cover page",
        source_data_required="Generated in the Graphics & Design tab" if cover_generated else image_source,
        status="Generated" if cover_generated else image_status,
        placeholder_text="" if cover_generated else f"[COVER IMAGE PLACEHOLDER: {image_source.upper()}]",
    ))

    for section in sections:
        is_generated = section.title in divider_image_sections
        recs.append(GraphicRecommendation(
            graphic_title=f"{section.title} -- section divider image",
            graphic_type="Section Divider Image",
            purpose="Visual section break, reinforces project relevance.",
            suggested_placement=section.title,
            source_data_required="Generated in the Graphics & Design tab" if is_generated else image_source,
            status="Generated" if is_generated else image_status,
            placeholder_text="" if is_generated else f"[DIVIDER IMAGE PLACEHOLDER: {_project_type_hint(project_type)}]",
        ))
        for graphic_name in section.recommended_graphics:
            source = _infer_source_data(graphic_name)
            generated_by = _generated_by(graphic_name)
            recs.append(GraphicRecommendation(
                graphic_title=graphic_name,
                graphic_type=_infer_graphic_type(graphic_name),
                purpose=_infer_purpose(graphic_name),
                suggested_placement=section.title,
                source_data_required=generated_by or source,
                status="Generated" if generated_by or source == "app-generated" else "User Input Required",
                # A generated graphic gets no red "go and make this" text --
                # that instruction is the whole problem this fixes.
                placeholder_text="" if generated_by else f"[{graphic_name.upper()} PLACEHOLDER]",
            ))

    recs.append(GraphicRecommendation(
        graphic_title="Evaluation weighting dashboard", graphic_type="Chart",
        purpose="Shows at a glance how weighting has been applied across the proposal structure.",
        suggested_placement="Tender Summary / Page Allocation Plan",
        source_data_required="app-generated", status="Generated",
    ))
    recs.append(GraphicRecommendation(
        graphic_title="Icons and callout boxes", graphic_type="Icon/Callout",
        purpose="Break up dense text, highlight key commitments/differentiators.",
        suggested_placement="Throughout document", source_data_required="Firm brand icon set",
        status="Placeholder", placeholder_text="[ICON/CALLOUT PLACEHOLDER]",
    ))
    return recs


def generate_weighting_chart(weighted_criteria: list[WeightedCriterion]) -> bytes | None:
    """Render a simple horizontal bar chart of applied weightings. Returns PNG bytes, or None on failure."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        scored = [c for c in weighted_criteria if not c.is_mandatory_gate and c.applied_weighting > 0]
        scored.sort(key=lambda c: c.applied_weighting)
        if not scored:
            return None

        labels = [c.mapped_section for c in scored]
        values = [c.applied_weighting for c in scored]

        fig, ax = plt.subplots(figsize=(7, max(2, 0.45 * len(scored))))
        bars = ax.barh(labels, values, color="#2c5f8a")
        for bar, value in zip(bars, values):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                     f"{value:.0f}%", va="center", fontsize=9)
        ax.set_xlabel("Applied weighting (%)")
        ax.set_title("Evaluation weighting by section")
        ax.set_xlim(0, max(values) * 1.2 if values else 100)
        fig.tight_layout()

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=150)
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


def generate_fee_distribution_pie(items: list[tuple[str, float]], title: str, value_fmt=None,
                                   show_pct_share: bool = True, legend_value: str = "raw") -> bytes | None:
    """
    Render a pie chart showing each discipline's share of a fee total -- used
    for both fee tables in the Fee Estimate tab (the hours x rate build-up,
    and the AI benchmark % split). Returns PNG bytes, or None if there's
    nothing worth charting (no items, or every value is zero).

    Colors are assigned in a FIXED order from a validated categorical palette
    (blue/orange/aqua/yellow/magenta/green/violet/red -- see the dataviz
    skill's reference palette), never cycled or re-sorted by value, so a
    discipline keeps the same color across reruns as the numbers change.
    Caps at 6 individually-coloured slices -- the point past which adjacent
    pie wedges start to blur -- and folds anything beyond that into a single
    grey "Other" slice rather than stretching the palette past what it can
    carry.

    show_pct_share adds each slice's share of THIS chart's total in brackets
    after the formatted value, e.g. "Structural -- $45,000 (17%)". Ignored
    when legend_value="share".

    legend_value picks what number the legend shows next to each label:
    "raw" (default) formats the value passed in via value_fmt, e.g. a dollar
    amount. "share" instead formats each slice's share of THIS chart's total
    (value / sum of shown values) -- use this when items are already
    percentages with no dollar total to anchor to, so the legend always
    matches the wedge's own on-slice percentage exactly. Folding several
    small slices into "Other" renormalises the chart's total, which would
    otherwise make a raw input percentage and its wedge size visibly
    disagree.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        value_fmt = value_fmt or (lambda v: f"${v:,.0f}")

        cleaned = [(str(label), float(value)) for label, value in (items or []) if value and float(value) > 0]
        if not cleaned:
            return None
        cleaned.sort(key=lambda x: -x[1])

        max_slices = 6
        if len(cleaned) > max_slices:
            shown = cleaned[:max_slices]
            other_total = sum(v for _, v in cleaned[max_slices:])
            other_count = len(cleaned) - max_slices
            shown.append((f"Other ({other_count} discipline{'s' if other_count != 1 else ''})", other_total))
        else:
            shown = cleaned

        # Fixed-order validated categorical palette -- never cycled/re-sorted,
        # so a given discipline's color stays stable as data changes.
        palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
        other_grey = "#898781"
        colors = [palette[i % len(palette)] for i in range(len(shown))]
        if shown[-1][0].startswith("Other ("):
            colors[-1] = other_grey

        labels = [label for label, _ in shown]
        values = [value for _, value in shown]
        total = sum(values)

        fig, ax = plt.subplots(figsize=(7.5, 5.0))
        wedges, _texts, _autotexts = ax.pie(
            values,
            colors=colors,
            autopct=lambda pct: f"{pct:.0f}%" if pct >= 4 else "",
            pctdistance=0.75,
            startangle=90,
            counterclock=False,
            radius=1.15,
            wedgeprops=dict(edgecolor="white", linewidth=2),
            textprops=dict(color="white", fontsize=10, fontweight="bold"),
        )
        ax.set_title(title, fontsize=13, fontweight="bold", color="#0b0b0b", pad=10)
        ax.axis("equal")

        if legend_value == "share":
            legend_labels = [f"{label}  --  {value_fmt(value / total * 100)}" for label, value in shown]
        elif show_pct_share:
            legend_labels = [f"{label}  --  {value_fmt(value)}  ({value / total * 100:.0f}%)" for label, value in shown]
        else:
            legend_labels = [f"{label}  --  {value_fmt(value)}" for label, value in shown]
        ax.legend(
            wedges, legend_labels, loc="center left", bbox_to_anchor=(1.0, 0.5),
            frameon=False, fontsize=9.5, labelspacing=1.1,
        )
        fig.subplots_adjust(top=0.90, bottom=0.05)

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None


def _divider_image_source(has_project_photos: bool, has_company_image_library: bool) -> tuple[str, str]:
    if has_project_photos:
        return "user-uploaded project photo", "User Input Required"
    if has_company_image_library:
        return "company project image library", "User Input Required"
    return "stock/royalty-free placeholder (none uploaded)", "Placeholder"


# Graphics the app now builds itself, keyed by a phrase that appears in the
# recommended-graphic name, with where the user actually gets each one. The
# app used to tell users to hand-produce all four.
_GENERATED_GRAPHICS = [
    (("organisation chart", "organization chart", "org chart"),
     "Generated by the app -- download 'Org Chart (PPTX)' on the Export Pack tab"),
    # Any methodology graphic: the generated stage table is what a
    # "methodology process diagram" recommendation is asking for.
    (("methodology",),
     "Generated by the app -- download 'Methodology Table (PPTX)' on the Export Pack tab"),
    (("programme timeline", "program timeline", "programme chart", "program chart",
      "delivery programme", "delivery program", "gantt"),
     "Generated by the app -- set the delivery program on the Fees & Program tab, "
     "then download 'Program (PPTX)' on the Export Pack tab"),
    (("fee chart", "fee breakdown chart", "fee distribution", "fee pie"),
     "Generated by the app -- see the fee charts on the Fees & Program tab"),
]


def _generated_by(name: str) -> str:
    """Where this graphic comes from, if the app generates it. Empty string
    means it genuinely still needs a human."""
    lowered = (name or "").lower()
    for phrases, where in _GENERATED_GRAPHICS:
        if any(phrase in lowered for phrase in phrases):
            return where
    return ""


def _project_type_hint(project_type: str | None) -> str:
    """Subject hint printed inside a divider-image placeholder.

    This was hardcoded to "BRIDGE / ROAD / INFRASTRUCTURE" for every project,
    which is a confident, wrong instruction on a coastal, environmental or
    surveying job -- the tool telling the user to find a photo of the wrong
    kind of work."""
    project_type = (project_type or "").strip()
    return project_type.upper() if project_type else "PROJECT-RELEVANT IMAGE"


def _infer_graphic_type(name: str) -> str:
    lowered = name.lower()
    if "diagram" in lowered:
        return "Diagram"
    if "chart" in lowered or "dashboard" in lowered:
        return "Chart"
    if "matrix" in lowered or "table" in lowered:
        return "Table/Matrix"
    if "timeline" in lowered or "programme" in lowered or "program" in lowered:
        return "Timeline"
    if "organisation" in lowered or "org chart" in lowered:
        return "Organisation Chart"
    return "Graphic"


def _infer_purpose(name: str) -> str:
    lowered = name.lower()
    if "methodology" in lowered:
        return "Visualises the delivery approach and key process stages."
    if "programme" in lowered or "timeline" in lowered:
        return "Shows key milestones and delivery sequencing."
    if "risk" in lowered:
        return "Summarises key risks and how they'll be managed."
    if "organisation" in lowered:
        return "Shows team structure, reporting lines, and role coverage."
    if "experience matrix" in lowered:
        return "Cross-references past projects against the brief's requirements."
    if "fee" in lowered:
        return "Summarises the priced offer at a glance."
    return "Supports and reinforces the section's written content."


def _infer_source_data(name: str) -> str:
    lowered = name.lower()
    if "organisation" in lowered:
        return "Project team names/roles (from CV library or manual entry)"
    if "experience matrix" in lowered:
        return "Project references (from uploaded past proposals/references)"
    if "fee" in lowered:
        return "Priced schedule (commercial team input)"
    return "Firm template / graphic designer input"
