"""
risk_register.py

A first-pass risk / impact / mitigation table, derived from the risks the
brief itself raises and the gaps the analysis found.

WHY
---
`analysis.risks` was extracted from the brief and then dumped into the pack
as raw bullets -- the brief's own sentences, repeated back to the client
who wrote them, with nothing said about what any of it means for delivery
or what this firm would do about it. A risk section that only restates the
client's risks scores nothing, because it demonstrates nothing.

THE CONTRACT
------------
Same as every other AI step here, and it matters more than usual: a
mitigation is a COMMITMENT. Inventing one puts the firm on the hook for
something nobody agreed to do.

So this step rephrases and structures ONLY. The risk text must come from
the brief's own risk list or the gap analysis. The impact must follow from
that risk and the project's stated scope. The mitigation must be either
something the brief or the inputs already describe, or the literal string
"TBC" for the bid team to fill in. It is told, in those words, that a table
of TBC mitigations is a correct output for a thin brief.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from modules.ai_interface import call_ai_json

TBC = "TBC"

MAX_RISKS = 15


class RiskEntry(BaseModel):
    risk: str = ""
    impact: str = TBC
    mitigation: str = TBC
    # "Brief" | "Gap analysis" -- where this risk came from, so a reviewer can
    # tell a client-stated risk from one the app inferred.
    source: str = ""


class RiskRegister(BaseModel):
    entries: list[RiskEntry] = Field(default_factory=list)


SYSTEM_MESSAGE = """You are structuring a risk register for an engineering/infrastructure \
proposal, from risks that have already been extracted from the client's own brief. This is a \
FIRST PASS for a human bid team to review and finish.

Your job is REPHRASING and STRUCTURING ONLY.

- Every risk you output must correspond to one you were given. Do not add risks. Not ones that \
are "standard for this kind of project", not ones that would make the register look more \
thorough.
- An impact must follow from that risk and the project's stated scope. If you cannot state one \
without speculating, output "TBC".
- A MITIGATION IS A COMMITMENT THE FIRM WILL BE HELD TO. Only state a mitigation the inputs \
already describe. If the inputs do not describe one, output the literal string "TBC" -- the bid \
team will decide what they are actually willing to commit to. A register whose mitigations are \
mostly "TBC" is a CORRECT output for a brief that does not discuss mitigation; a register full \
of plausible invented commitments is the worst thing you can produce, because someone will \
submit it and then be bound by it.
- Merge duplicates. The same risk stated twice in different words is one row."""

PROMPT_TEMPLATE = """Structure the risk register for this project.

PROJECT SCOPE (context for stating impacts):
{project_scope}

RISKS THE BRIEF ITSELF RAISES:
{risks}

GAPS THE ANALYSIS FOUND (things missing or unresolved in this bid -- include one only where it \
is genuinely a delivery risk, not merely an incomplete form):
{gaps}

MITIGATION MATERIAL PRESENT IN THE INPUTS (the brief's own words about how risks are to be \
managed, if any -- this is the ONLY source a mitigation may come from):
{mitigation_material}

Return a JSON object:
{{
  "entries": [
    {{"risk": string, "impact": string, "mitigation": string, "source": "Brief"|"Gap analysis"}},
    ...
  ]
}}"""


def _bullets(values, empty: str = "(none)") -> str:
    values = [str(v).strip() for v in (values or []) if str(v or "").strip()]
    return "\n".join(f"- {v}" for v in values[:MAX_RISKS]) or f"- {empty}"


def draft_risk_register(analysis, gap_items: list | None = None,
                        config: dict | None = None) -> RiskRegister:
    """One AI call. Raises whatever call_ai_json raises; the caller decides
    whether to surface it or fall back to the raw bullets."""
    risks = list(getattr(analysis, "risks", None) or [])
    gaps = [
        (getattr(item, "issue", "") or "").strip()
        for item in (gap_items or [])
    ]
    if not risks and not any(gaps):
        return RiskRegister()

    prompt = PROMPT_TEMPLATE.format(
        project_scope=(getattr(analysis, "project_scope", "") or "").strip() or "(not extracted)",
        risks=_bullets(risks, "(none extracted from the brief)"),
        gaps=_bullets(gaps, "(none)"),
        # The brief's assumptions are the closest thing to stated mitigation
        # material most briefs carry. Anything beyond this is the bid team's
        # to write.
        mitigation_material=_bullets(
            getattr(analysis, "assumptions", None),
            "(the brief states no mitigation approach -- every mitigation must be TBC)",
        ),
    )
    data = call_ai_json(prompt, system_message=SYSTEM_MESSAGE, config=config, max_tokens=2500)

    entries = []
    seen = set()
    for raw in (data.get("entries") or []):
        if not isinstance(raw, dict):
            continue
        risk = str(raw.get("risk") or "").strip()
        if not risk:
            continue
        key = risk.lower()
        if key in seen:
            continue
        seen.add(key)
        entries.append(RiskEntry(
            risk=risk,
            # Blank must become a visible TBC, not an empty cell a reader
            # takes for "no impact" or "nothing needed".
            impact=str(raw.get("impact") or "").strip() or TBC,
            mitigation=str(raw.get("mitigation") or "").strip() or TBC,
            source=str(raw.get("source") or "").strip() or "Brief",
        ))
    return RiskRegister(entries=entries[:MAX_RISKS])


def format_for_prompt(register) -> str:
    """The register as prompt context for the Risk/Safety/Quality section
    draft, so that section argues from the structured table rather than
    re-deriving it from the same raw bullets."""
    entries = getattr(register, "entries", None) or []
    if not entries:
        return ""
    lines = []
    for entry in entries:
        lines.append(f"- Risk: {entry.risk}")
        lines.append(f"  Impact: {entry.impact}")
        lines.append(f"  Mitigation: {entry.mitigation}")
    return (
        "--- REVIEWED RISK REGISTER (risk / impact / mitigation, already checked by the bid "
        "team -- use these, and treat any 'TBC' as still open rather than writing one in) ---\n"
        + "\n".join(lines)
    )
