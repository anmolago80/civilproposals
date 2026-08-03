"""
tender_analyser.py

Turns raw tender-brief text (+ any annotations the user made while reading it)
into a structured, validated TenderAnalysis object: scope, objectives,
mandatory requirements, evaluation criteria (with weightings, page limits,
and formatting rules where the brief states them), page limits, deliverables,
required forms/schedules, risks, assumptions, and a stated fee cap if any.

For long documents this does a light map-reduce: each chunk gets a compact
extraction pass first, then a final structured pass turns the combined notes
into the JSON schema below. For short documents (most tender briefs) it's a
single pass.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai, call_ai_json
from modules.document_processor import clean_extracted_text, split_text_into_chunks


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class EvaluationCriterion(BaseModel):
    name: str
    criterion_code: str | None = None          # e.g. "SC1", or None if the brief uses a plain table
    description: str = ""
    detected_weighting: float | None = None    # percentage, e.g. 20.0 for "20%"
    is_mandatory_gate: bool = False             # pass/fail item, e.g. "Compliance with the ITO"
    page_limit: str | None = None               # free text, e.g. "2 single-sided A4 pages"
    format_requirements: str | None = None      # e.g. "Arial 11pt, minimum 15pt line spacing"
    returnable_schedule_ref: str | None = None  # e.g. "Returnable Schedule 5"


class ScopeItem(BaseModel):
    """A discrete piece of work the brief describes -- 'Project Inception', 'Site Inspections',
    'Detailed Design', whatever the actual brief calls for. This is deliberately generic: the
    same shape captures a four-boat-ramp condition assessment or a balanced cantilever bridge
    design, because it's built entirely from what the brief itself says, never a template of
    "typical" tasks for a project type. Used to drive Scope of Work sections, fee-per-item
    tables, and program/schedule tables in any proposal format."""
    title: str
    tasks: list[str] = Field(default_factory=list)


class TenderAnalysis(BaseModel):
    project_scope: str = ""
    client_objectives: list[str] = Field(default_factory=list)
    submission_date: str | None = None
    mandatory_requirements: list[str] = Field(default_factory=list)
    evaluation_criteria: list[EvaluationCriterion] = Field(default_factory=list)
    uses_named_selection_criteria: bool = False   # True if brief defines SC1/SC2-style criteria
    total_page_limit: int | None = None
    section_page_limits: dict[str, str] = Field(default_factory=dict)
    deliverables: list[str] = Field(default_factory=list)
    scope_items: list[ScopeItem] = Field(default_factory=list)
    required_forms: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    fee_cap: str | None = None                    # e.g. "$1,500,000 ex GST"
    disciplines_involved: list[str] = Field(default_factory=list)
    submission_format_notes: list[str] = Field(default_factory=list)
    user_flagged_items: list[dict] = Field(default_factory=list)
    analysis_warnings: list[str] = Field(default_factory=list)


SYSTEM_MESSAGE = """You are assisting a proposals team at an engineering/infrastructure \
consultancy to read a brief -- this could be a formal tender or EOI document with pages of \
conditions, or it could be a short email or one-paragraph scope request asking for a fee \
proposal. You must be precise and conservative: extract only what the brief actually states. \
Never invent a weighting, page limit, date, requirement, or task that isn't in the text. If \
something is ambiguous or not stated, leave it null or say so explicitly rather than \
guessing. Government and council tenders vary a lot in format -- some list a simple weighted \
"Evaluation Criteria" table, others define named, numbered "Selection Criteria" (SC1, SC2...) \
each with its own page limit and font/spacing rules that are enforced as a compliance \
requirement, not just a suggestion. Detect which style this brief uses. Stay completely \
agnostic to the subject matter -- treat a bus shelter, a boat ramp, and a balanced cantilever \
bridge identically: read what THIS brief actually asks for and describe that, never a \
"typical" scope for the project type."""

MAP_PROMPT_TEMPLATE = """Read this excerpt from a brief (part {part} of {total}) -- it may be \
a formal tender/EOI document or a short email/scope request -- and produce compact \
bullet-point notes capturing anything relevant to: project scope and objectives, submission \
date/closing time, mandatory requirements, evaluation or selection criteria (names, codes \
like SC1, descriptions, weightings, page limits, font/spacing rules), total page limits, \
deliverables, the discrete pieces of work described (e.g. "kick-off meeting", "site \
inspections", "detailed design", "concept report" -- whatever this specific brief actually \
asks for, with the concrete tasks under each), required forms/returnable schedules, risks, \
assumptions, any stated fee cap or budget ceiling, and engineering disciplines mentioned \
(structural, geotechnical, hydraulics/hydrology, road/civil, environmental, traffic, cost \
estimating, project management, etc). Skip boilerplate legal clauses (privacy, IP, governing \
law) unless they impose a concrete formatting or submission requirement. Be concise -- this \
is an intermediate note, not a final answer.

--- EXCERPT ---
{chunk}
--- END EXCERPT ---"""

REDUCE_PROMPT_TEMPLATE = """Using the material below, produce a single JSON object with \
exactly these fields:

{{
  "project_scope": string,
  "client_objectives": [string],
  "submission_date": string or null,
  "mandatory_requirements": [string],
  "evaluation_criteria": [
    {{
      "name": string,
      "criterion_code": string or null,
      "description": string,
      "detected_weighting": number or null,
      "is_mandatory_gate": boolean,
      "page_limit": string or null,
      "format_requirements": string or null,
      "returnable_schedule_ref": string or null
    }}
  ],
  "uses_named_selection_criteria": boolean,
  "total_page_limit": number or null,
  "section_page_limits": {{"section name": "limit as stated"}},
  "deliverables": [string],
  "scope_items": [
    {{"title": string, "tasks": [string]}}
  ],
  "required_forms": [string],
  "risks": [string],
  "assumptions": [string],
  "fee_cap": string or null,
  "disciplines_involved": [string],
  "submission_format_notes": [string],
  "analysis_warnings": [string]
}}

Rules:
- "uses_named_selection_criteria" is true only if the brief itself labels criteria with \
codes like SC1/SC2/etc (or similar numbered scheme) rather than a plain unlabelled table.
- "detected_weighting" is a plain percentage number (20 for "20%"), or null if not stated \
for that criterion.
- "is_mandatory_gate" is true for pass/fail compliance items (e.g. "Compliance with this \
ITO" marked "Mandatory" rather than given a %).
- "analysis_warnings" should flag anything ambiguous, contradictory, or that you could not \
confidently extract -- be honest here rather than silently guessing.
- "scope_items" should break the actual work described in THIS brief into discrete items in \
the order the brief presents them (e.g. for a formal RFT this might mirror its work-breakdown \
or methodology section; for a short email/fee-proposal brief it's whatever discrete pieces of \
work are implied, like "Site Inspections" or "Detailed Design"). Each item's "tasks" are the \
concrete bullet-point actions under it. Do not invent items or tasks the brief doesn't imply -- \
if the brief is too sparse to break down, return a single item with the overall scope as one task.
- If the user has flagged specific passages with their own comments (shown below under \
USER ANNOTATIONS), treat those as high-priority signals: whatever they highlighted and \
asked about should be reflected in mandatory_requirements, risks, or analysis_warnings as \
appropriate, and referenced in relevant descriptions.

--- BRIEF MATERIAL ---
{source_material}
--- END BRIEF MATERIAL ---

{annotation_block}"""


def analyse_tender(
    document_text: str,
    annotations: list[dict] | None = None,
    config: dict | None = None,
    progress_callback=None,
) -> TenderAnalysis:
    """
    Run the full extraction pipeline on tender brief text and return a
    validated TenderAnalysis. Raises on total AI failure; callers should
    surface `analysis_warnings` to the user rather than treat this as a
    black box.
    """
    cleaned = clean_extracted_text(document_text)
    chunks = split_text_into_chunks(cleaned, chunk_size=12000, overlap=300)

    if len(chunks) <= 1:
        source_material = cleaned
    else:
        notes = []
        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i, len(chunks))
            note = call_ai(
                MAP_PROMPT_TEMPLATE.format(part=i + 1, total=len(chunks), chunk=chunk),
                system_message=SYSTEM_MESSAGE,
                config=config,
                max_tokens=1200,
            )
            notes.append(f"--- Notes from part {i + 1}/{len(chunks)} ---\n{note}")
        source_material = "\n\n".join(notes)

    annotation_block = _format_annotations(annotations)
    prompt = REDUCE_PROMPT_TEMPLATE.format(
        source_material=source_material, annotation_block=annotation_block
    )
    raw = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=4000)

    analysis = TenderAnalysis.model_validate(raw)
    analysis.user_flagged_items = _flagged_items_from_annotations(annotations)
    return analysis


DISCIPLINE_DETECTION_SYSTEM = (
    "You are a bid manager at a multidisciplinary engineering consultancy reading a brief to "
    "decide which technical disciplines the job needs staffed. Be thorough and practical: "
    "include a discipline if the scope of work plainly requires it, even when the brief never "
    "names it as a 'discipline' -- e.g. any road/bridge job implies constructability review and "
    "usually survey; works near waterways or with drainage imply hydraulics/hydrology and often "
    "environmental and cultural heritage; level-crossing or rail-corridor works imply rail. Do "
    "NOT invent disciplines with no basis in the scope, and do not pad the list with things the "
    "job clearly doesn't touch."
)

DISCIPLINE_DETECTION_PROMPT = """From the brief below, list every engineering/technical \
discipline this job needs. Consider (non-exhaustively): Project Management, Structural, \
Bridges, Geotechnical, Road & Civil, Pavement, Hydraulics & Hydrology, Drainage, Traffic \
Engineering, Environmental, Cultural Heritage, Ecology, Survey, Rail, Utilities & Services, \
Electrical, Mechanical, Landscaping, Constructability, Stakeholder Engagement, Cost Estimating, \
Sustainability. Include one only if the scope genuinely calls for it.

Return a JSON object:
{{
  "disciplines": [string]
}}
Use short, standard discipline names. Include EVERYTHING the scope implies; don't stop short.

--- BRIEF ---
{brief}
--- END BRIEF ---"""


def detect_disciplines_from_text(brief_text: str, config: dict | None = None,
                                 max_chars: int = 30000) -> list[str]:
    """
    Focused discipline detection: read the brief and return the disciplines the
    job needs, inferring from the scope (not just the ones the brief names
    explicitly). This is deliberately separate from the big analyse_tender()
    pass -- a single narrow question the model answers far more reliably than as
    one field among twenty. Returns a de-duplicated list of raw discipline
    names (the caller canonicalises). Returns [] on failure rather than raising.
    """
    material = (brief_text or "").strip()
    if not material:
        return []
    if len(material) > max_chars:
        material = material[:max_chars] + "\n\n[...truncated for length...]"
    try:
        data = call_ai_json(
            DISCIPLINE_DETECTION_PROMPT.format(brief=material),
            system_message=DISCIPLINE_DETECTION_SYSTEM, config=config, max_tokens=800,
        )
    except Exception:
        return []
    raw = data.get("disciplines", []) if isinstance(data, dict) else []
    out: list[str] = []
    seen = set()
    for d in raw:
        name = (d if isinstance(d, str) else "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out


def _format_annotations(annotations: list[dict] | None) -> str:
    if not annotations:
        return ""
    lines = ["USER ANNOTATIONS (highlights/comments the user already made on the brief):"]
    for a in annotations:
        page = a.get("page", "?")
        comment = a.get("comment", "").strip()
        highlighted = a.get("highlighted_text", "").strip()
        if comment and highlighted:
            lines.append(f'- p.{page}: highlighted "{highlighted[:200]}" -- comment: "{comment}"')
        elif comment:
            lines.append(f'- p.{page}: comment: "{comment}"')
        elif highlighted:
            lines.append(f'- p.{page}: highlighted "{highlighted[:200]}"')
    return "\n".join(lines)


def _flagged_items_from_annotations(annotations: list[dict] | None) -> list[dict]:
    if not annotations:
        return []
    return [
        {
            "page": a.get("page"),
            "note": a.get("comment") or "(highlight, no comment text)",
            "context": a.get("highlighted_text", ""),
        }
        for a in annotations
        if a.get("comment") or a.get("highlighted_text")
    ]
