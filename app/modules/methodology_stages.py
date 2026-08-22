"""
methodology_stages.py

The delivery stages that fill the methodology table -- one row per stage,
each with its key tasks, engagement activities, outcome and deliverables.

WHY THIS EXISTS
---------------
methodology_pptx.populate_methodology() used to read exactly one field of
the analysis (scope_items) and fill exactly one of its sixteen content
cells. The other eleven were hardcoded red placeholders, and the four stage
names were hardcoded too -- so a brief that named its own stages ("30% /
70% / 100% design") still exported a table headed "15% design stage". All
of that was placeholder-by-default, in the artefact the product is
demonstrated on.

The app already held what those cells need: the brief's deliverables (which
were extracted and then never used anywhere), its objectives and mandatory
requirements, the drafted methodology text, and the week-by-week delivery
program. What was missing was the assignment step -- deciding which scope
item and which deliverable belong to which stage. That is a judgement, it
is reviewable, and it is exactly the kind of thing an AI step should do
under a strict contract.

THE CONTRACT
------------
This step ASSIGNS and REPHRASES. It never authors. Every task, activity,
deliverable and date it emits must already be present in its inputs; where
the inputs don't support a cell, it emits the literal string "TBC" and the
renderer shows that in red. The prompt says so in those words, and
_scrub_stages() enforces the shape of the result independently of whether
the model complied.

The user then reviews and edits the whole grid before anything is exported
-- see the Draft Responses tab. Nothing here reaches a document without
passing under a human's eyes first.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai_json
from modules.export_i18n import canonical_marker_instruction

# The literal a cell carries when the inputs don't support it. Rendered red
# by both the PPTX and the DOCX image, same convention as every other
# unknown in this tool.
TBC = "TBC"

# Used only when the brief names no stages of its own. Deliberately generic
# and few: inventing a five-stage process a brief never described would be
# exactly the failure this module exists to avoid.
DEFAULT_STAGE_NAMES = [
    "Project initiation",
    "Concept design",
    "Detailed design",
    "Finalisation and handover",
]

# Input caps. A brief with 60 scope items would otherwise blow the context
# budget on a single call; the prompt is told when a list was cut so the
# model doesn't silently treat a truncated list as complete.
MAX_SCOPE_ITEMS = 25
MAX_TASKS_PER_ITEM = 8
MAX_DELIVERABLES = 30
MAX_OBJECTIVES = 12
MAX_REQUIREMENTS = 15
MAX_METHODOLOGY_CHARS = 6000


class MethodologyStage(BaseModel):
    """One column of the methodology table.

    week_start/week_end are 1-based indices into the delivery program's week
    list, or None when the program doesn't place this stage. They are
    indices rather than dates so that setting a program start date later
    (see program_schedule.week_labels) relabels the table without anything
    needing to be regenerated."""
    name: str = ""
    week_start: int | None = None
    week_end: int | None = None
    key_tasks: list[str] = Field(default_factory=list)
    engagement_activities: list[str] = Field(default_factory=list)
    outcome: str = ""
    deliverables: list[str] = Field(default_factory=list)


SYSTEM_MESSAGE = """You are assembling the delivery-stage table for an \
engineering/infrastructure proposal, from material that has already been extracted from the \
client's own brief. This is a FIRST PASS for a human proposal writer to review and edit, not \
submission-ready text.

Your job is ASSIGNMENT and REPHRASING ONLY. Specifically:

- Assign each scope item, and each deliverable, from the inputs to EXACTLY ONE stage. Every \
scope item and every deliverable you are given must appear under exactly one stage -- do not \
drop any, and do not repeat any across stages.
- Use the brief's OWN stage names when the inputs state them (e.g. "30% design", "Concept", \
"IFC"). Only if the inputs name no stages at all, use the four standard stages you are given.
- Rephrase for brevity and consistent voice. Do not add.
- NEVER add a task, activity, deliverable, date, hold point, review, workshop, meeting or \
milestone that is not present in the inputs. Not one that is "standard practice", not one that \
is "obviously required", not one that would make the table look more complete.
- Output the literal string "TBC" for any cell the inputs do not support. A table with several \
TBCs is CORRECT when the brief is thin. A table filled with plausible invented content is the \
single worst thing you can produce here -- it goes into a legal offer document.

Engagement activities in particular: only list a meeting, workshop, review or hold point if the \
brief's own material mentions it. If it mentions none, every engagement cell is "TBC".

Stay agnostic to subject matter -- read what THIS brief asks for, never a typical scope for the \
project type."""

PROMPT_TEMPLATE = """Assemble the delivery-stage table for this project.

PROJECT: {project_name}
CLIENT: {client_name}

SCOPE ITEMS FROM THE BRIEF (assign every one of these to exactly one stage):
{scope_items}

DELIVERABLES FROM THE BRIEF (assign every one of these to exactly one stage):
{deliverables}

CLIENT OBJECTIVES (context for the "outcome" cells -- an outcome must still come from the \
scope/deliverables you were given, not from an objective on its own):
{objectives}

MANDATORY REQUIREMENTS (context only -- do not turn these into tasks unless they already \
describe work in the scope items):
{requirements}

THE DRAFTED METHODOLOGY TEXT (the writer's own words about how the work will be delivered -- \
this is the best source for stage names, engagement activities and hold points; rephrase from \
it, never beyond it):
{methodology_text}

DELIVERY PROGRAM ({week_count} weeks, week 1 to week {week_count}):
{program}

For each stage return:
- "name": the stage's name, from the brief's own naming where it states one.
- "week_start" / "week_end": 1-based week numbers from the delivery program above, ONLY where \
the program actually places that stage's scope items. Use null for both if it does not.
- "key_tasks": the assigned scope items' tasks, rephrased short.
- "engagement_activities": client/stakeholder engagement for this stage, ONLY where the inputs \
mention it -- otherwise ["TBC"].
- "outcome": one short sentence on what the stage produces, from its own assigned scope and \
deliverables -- otherwise "TBC".
- "deliverables": the deliverables assigned to this stage -- otherwise ["TBC"].

If the inputs name no stages of their own, use exactly these: {default_stages}

Return a JSON object:
{{
  "stages": [
    {{
      "name": string,
      "week_start": integer or null,
      "week_end": integer or null,
      "key_tasks": [string, ...],
      "engagement_activities": [string, ...],
      "outcome": string,
      "deliverables": [string, ...]
    }}, ...
  ]
}}"""


def _bullets(values, limit: int, empty: str = "(none extracted)") -> str:
    values = [str(v).strip() for v in (values or []) if str(v or "").strip()]
    if not values:
        return f"- {empty}"
    shown = values[:limit]
    out = "\n".join(f"- {v}" for v in shown)
    if len(values) > limit:
        # Say so explicitly: a model handed a silently-truncated list will
        # treat it as the complete set and "assign every one" of a subset.
        out += f"\n- (...and {len(values) - limit} more, not shown -- do not assume the list above is complete)"
    return out


def _format_scope_items(scope_items) -> str:
    lines = []
    for item in (scope_items or [])[:MAX_SCOPE_ITEMS]:
        title = (getattr(item, "title", "") or "").strip()
        if not title:
            continue
        lines.append(f"- {title}")
        for task in (getattr(item, "tasks", None) or [])[:MAX_TASKS_PER_ITEM]:
            task = str(task or "").strip()
            if task:
                lines.append(f"    - {task}")
    return "\n".join(lines) or "- (none extracted)"


def _format_program(program_schedule: dict | None, week_labels: list | None) -> str:
    """Which weeks each scope item runs in, so the model can put a stage's
    week range where its own assigned scope items actually sit."""
    if not program_schedule or not week_labels:
        return "(no delivery program entered -- return null for every week_start/week_end)"
    lines = []
    for title, weeks in list(program_schedule.items())[:MAX_SCOPE_ITEMS]:
        active = [i + 1 for i, on in enumerate(weeks or []) if on]
        if active:
            lines.append(f"- {title}: weeks {active[0]} to {active[-1]}")
        else:
            lines.append(f"- {title}: not programmed")
    return "\n".join(lines)


def _clean_list(values, allow_tbc: bool = True) -> list[str]:
    out = []
    for value in (values or []):
        text = str(value or "").strip()
        if not text:
            continue
        if text.upper() == TBC:
            text = TBC
        if text not in out:
            out.append(text)
    if not out and allow_tbc:
        return [TBC]
    return out


def _clean_week(value, week_count: int) -> int | None:
    """A week index the program can actually contain, or None.

    Guards against the model returning week 14 of a 12-week program, or a
    date string, or 0 -- any of which would render a nonsense chevron on a
    client-facing table."""
    try:
        week = int(value)
    except (TypeError, ValueError):
        return None
    if week_count <= 0 or week < 1 or week > week_count:
        return None
    return week


def _scrub_stages(raw_stages, week_count: int) -> list[MethodologyStage]:
    """Force the model's output into the shape the renderer requires.

    Deliberately independent of whether the model followed the contract: an
    empty cell must become a visible TBC rather than a blank the reader
    reads as "nothing needed here", and an out-of-range week must become no
    week at all rather than a fabricated date."""
    stages: list[MethodologyStage] = []
    for raw in (raw_stages or []):
        if not isinstance(raw, dict):
            continue
        start = _clean_week(raw.get("week_start"), week_count)
        end = _clean_week(raw.get("week_end"), week_count)
        if start and end and end < start:
            start, end = end, start
        stages.append(MethodologyStage(
            name=(str(raw.get("name") or "").strip() or TBC),
            week_start=start,
            week_end=end,
            key_tasks=_clean_list(raw.get("key_tasks")),
            engagement_activities=_clean_list(raw.get("engagement_activities")),
            outcome=(str(raw.get("outcome") or "").strip() or TBC),
            deliverables=_clean_list(raw.get("deliverables")),
        ))
    return stages


def blank_stages(names: list[str] | None = None) -> list[MethodologyStage]:
    """An empty grid the user can fill in by hand -- used when there's no AI
    key, when the call fails, or when someone would rather type it than
    generate it. Every cell starts as TBC so an untouched grid exports as
    visibly incomplete rather than as blank cells."""
    return [
        MethodologyStage(name=name, key_tasks=[TBC], engagement_activities=[TBC],
                         outcome=TBC, deliverables=[TBC])
        for name in (names or DEFAULT_STAGE_NAMES)
    ]


def draft_methodology_stages(
    analysis,
    methodology_draft_text: str = "",
    program_schedule: dict | None = None,
    program_week_labels: list | None = None,
    project_info: dict | None = None,
    config: dict | None = None,
    output_language: str = "en",
) -> list[MethodologyStage]:
    """One AI call producing the reviewable stage grid. Raises whatever
    call_ai_json raises (AIConfigError) -- the caller shows it verbatim and
    offers the blank grid instead.

    `output_language`: language for the narrative/prose fields ("name",
    "key_tasks", "engagement_activities", "outcome", "deliverables") -- "en"
    (default) or "es". Independent of the app's own UI language; see
    modules/i18n.py's module docstring."""
    project_info = project_info or {}
    week_count = len(program_week_labels or [])

    methodology_text = (methodology_draft_text or "").strip()
    if len(methodology_text) > MAX_METHODOLOGY_CHARS:
        methodology_text = methodology_text[:MAX_METHODOLOGY_CHARS] + "\n(...truncated)"

    prompt = PROMPT_TEMPLATE.format(
        project_name=project_info.get("project_name") or "(not supplied)",
        client_name=project_info.get("client_name") or "(not supplied)",
        scope_items=_format_scope_items(getattr(analysis, "scope_items", None)),
        deliverables=_bullets(getattr(analysis, "deliverables", None), MAX_DELIVERABLES),
        objectives=_bullets(getattr(analysis, "client_objectives", None), MAX_OBJECTIVES),
        requirements=_bullets(getattr(analysis, "mandatory_requirements", None), MAX_REQUIREMENTS),
        methodology_text=methodology_text or "(no methodology drafted yet)",
        program=_format_program(program_schedule, program_week_labels),
        week_count=week_count or 0,
        default_stages=", ".join(DEFAULT_STAGE_NAMES),
    )
    if output_language == "es":
        # Round 3, Part 1c: canonical-marker instruction shared via
        # export_i18n.canonical_marker_instruction() -- see its docstring.
        # The existing "keep TBC as TBC" sentence stays -- that is a
        # SEPARATE, deliberately language-invariant marker (same convention
        # as risk_register.py), not part of the bracket-prefix family the
        # shared helper governs.
        prompt += (
            "\n\nWrite the narrative/prose string VALUES in your JSON response (\"name\", the "
            "entries of \"key_tasks\", \"engagement_activities\", \"outcome\", and the entries of "
            "\"deliverables\") in Spanish (Español). Keep the JSON field names above exactly as "
            "given, in English, and keep the literal marker \"TBC\" exactly as \"TBC\" -- do not "
            "translate it, it is a structural placeholder the rest of the app matches on. "
            "Translate only the language, not the substance -- do not invent, omit, or alter any "
            "task, deliverable, date, or fact because of this instruction."
            + canonical_marker_instruction(output_language)
        )

    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=4000)
    return _scrub_stages(data.get("stages"), week_count)


def stage_week_label(stage: MethodologyStage, week_labels: list | None) -> str:
    """The date chevron's text for one stage.

    Uses the program's own week labels, so it says "Wk 1 - Wk 3" with no
    start date set and "6 Oct - 20 Oct" once one is (see
    program_schedule.week_labels). Never invents a range."""
    labels = week_labels or []
    if not stage.week_start or not labels:
        return TBC
    start_index = stage.week_start - 1
    end_index = (stage.week_end or stage.week_start) - 1
    if start_index >= len(labels):
        return TBC
    end_index = min(end_index, len(labels) - 1)
    start = str(labels[start_index])
    end = str(labels[end_index])
    return start if start == end else f"{start} - {end}"


# ---------------------------------------------------------------------------
# First-pass image for the DOCX
# ---------------------------------------------------------------------------

def render_stages_png(stages: list, week_labels: list | None = None,
                      theme_name: str | None = None, wvr_confirmed: bool = False) -> bytes | None:
    """Render the reviewed stage grid as a PNG for the Word pack.

    The DOCX has always carried a red "[INSERT METHODOLOGY TABLE HERE]" note
    and nothing else, even for a user who had already generated the
    PowerPoint version -- the same gap the org chart had. This is the
    first-pass image that goes above that note; the note stays, because the
    PowerPoint is still the artefact you finish and paste in.

    Themed from divider_designer.THEME_COLOURS so it matches the rest of the
    pack. Returns None on any failure -- an image is a nice-to-have and must
    never take an export down.
    """
    if not stages:
        return None
    try:
        import io as _io

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        from modules.divider_designer import THEME_COLOURS

        palette = THEME_COLOURS.get(theme_name or "", THEME_COLOURS["Corporate"])
        primary = tuple(c / 255 for c in palette["primary"])
        accent = tuple(c / 255 for c in palette["accent"])
        header_text = "white" if sum(palette["primary"]) / 3 < 150 else "#222222"
        red = "#C00000"

        def _cell(values) -> str:
            if isinstance(values, str):
                return values
            return "\n".join(f"– {v}" for v in values) or TBC

        row_labels = ["Timing", "Key tasks", "Engagement", "Outcome", "Deliverables"]
        body = [
            [stage_week_label(s, week_labels) for s in stages],
            [_cell(s.key_tasks) for s in stages],
            [_cell(s.engagement_activities) for s in stages],
            [_cell(s.outcome) for s in stages],
            [_cell(s.deliverables) for s in stages],
        ]

        # Row heights follow their own content. matplotlib gives every row
        # the same height by default, which clipped any cell with more than
        # one line -- the exact failure mode the PowerPoint version had.
        header_lines = max((len(str(s.name or TBC)) // 22) + 1 for s in stages)
        row_lines = [max(len(str(cell).split("\n")) for cell in row) for row in body]
        total_lines = header_lines + sum(row_lines)

        line_in = 0.26           # inches per text line, at 7.5pt with padding
        fig_h = max(2.4, total_lines * line_in + 0.5)
        fig_w = max(7.0, 2.9 * len(stages))
        fig, ax = plt.subplots(figsize=(fig_w, fig_h))
        ax.axis("off")

        table = ax.table(
            cellText=body,
            rowLabels=row_labels,
            colLabels=[s.name or TBC for s in stages],
            cellLoc="left", rowLoc="right", loc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(7.5)

        unit = 1.0 / max(total_lines, 1)
        for (row, col), cell in table.get_celld().items():
            lines = header_lines if row == 0 else row_lines[row - 1]
            cell.set_height(unit * lines)

        for (row, col), cell in table.get_celld().items():
            cell.set_edgecolor("#D9D9D9")
            cell.set_linewidth(0.6)
            cell.get_text().set_verticalalignment("top")
            if row == 0:  # stage headers
                cell.set_facecolor(primary)
                cell.get_text().set_color(header_text)
                cell.get_text().set_fontweight("bold")
                cell.get_text().set_horizontalalignment("center")
            elif col == -1:  # row labels
                cell.set_facecolor(accent)
                cell.get_text().set_color("white")
                cell.get_text().set_fontweight("bold")
            else:
                text = body[row - 1][col]
                # A TBC in the image has to look like a TBC in the document.
                if str(text).strip().upper() == TBC or str(text).strip().startswith(TBC):
                    cell.get_text().set_color(red)
                    cell.get_text().set_style("italic")

        note = (
            "All design deliverables will be issued with completed Work Verification Records (WVRs)"
            if wvr_confirmed else
            "[CONFIRM WVR / QA STATEMENT FOR THIS FIRM]"
        )
        fig.text(0.01, 0.01, note, fontsize=6.5, style="italic",
                 color="#333333" if wvr_confirmed else red)

        buffer = _io.BytesIO()
        fig.savefig(buffer, format="png", dpi=170, bbox_inches="tight")
        plt.close(fig)
        buffer.seek(0)
        return buffer.read()
    except Exception:
        return None
