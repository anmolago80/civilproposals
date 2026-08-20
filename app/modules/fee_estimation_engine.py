"""
fee_estimation_engine.py

Produces an INDICATIVE, INTERNAL-ONLY fee split by discipline -- a sanity
check for the bid team before committing hours to a pursuit, never a number
to submit. See README.md for the full reasoning; the short version:

- Primary source is a bundled reference table of typical industry fee-split
  patterns by project type (sample_data/fee_benchmarks.json). Fast, works
  offline, and is honestly labelled as a rule-of-thumb rather than a
  researched figure.
- An optional "refresh from web" action asks the configured AI provider for
  its knowledge of published fee benchmarks. This is NOT a live web fetch --
  none of the base provider APIs wired up in ai_interface.py browse the
  internet by default -- so results are clearly labelled as AI-recalled
  knowledge, not researched fact, with a confidence flag.
- Where the brief states a real fee cap/budget ceiling, the split is
  anchored to that actual number instead of guessing a project value.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel

from modules.ai_interface import call_ai_json

_BENCHMARKS_PATH = Path(__file__).resolve().parent.parent / "sample_data" / "fee_benchmarks.json"

INDICATIVE_NOTE = (
    "INDICATIVE FEE SPLIT -- INTERNAL PLANNING ONLY, NOT FOR SUBMISSION. "
    "This is a rough sanity check for the bid team, not a priced offer. It must be reviewed "
    "and re-priced by whoever owns commercial sign-off before any number here is used "
    "anywhere near an actual submission."
)


class DisciplineFeeEstimate(BaseModel):
    discipline: str
    fee_percentage: float
    fee_amount: float | None = None
    source: str
    confidence: str  # High | Medium | Low


def estimate_fee_split(
    project_type: str,
    fee_cap_text: str | None = None,
) -> list[DisciplineFeeEstimate]:
    """Default, fast path: bundled reference table, optionally anchored to a stated fee cap."""
    benchmarks = _load_benchmarks()
    entry = benchmarks.get(project_type, benchmarks["Default"])
    total_amount = _parse_currency(fee_cap_text) if fee_cap_text else None

    estimates = []
    for discipline, pct in entry["fee_split"].items():
        estimates.append(DisciplineFeeEstimate(
            discipline=discipline,
            fee_percentage=pct,
            fee_amount=round(total_amount * pct / 100, 0) if total_amount else None,
            source=entry["source"],
            confidence=entry["confidence"],
        ))
    estimates.sort(key=lambda e: -e.fee_percentage)
    return estimates


def refresh_estimate_from_web(
    project_type: str,
    disciplines_involved: list[str] | None = None,
    fee_cap_text: str | None = None,
    config: dict | None = None,
    scope_summary: str = "",
) -> tuple[list[DisciplineFeeEstimate], str]:
    """
    Ask the configured AI provider for a fee-split estimate drawing on its general
    knowledge of published industry fee benchmarks. Explicitly NOT a live web fetch --
    see module docstring.

    Returns (estimates, warning). A failure falls back to the bundled table
    AND says so in the warning: this used to fall back silently, so a user
    who pressed "refresh from web" got the same bundled numbers back with no
    indication that the refresh hadn't happened, and would reasonably read
    the unchanged figures as confirmation rather than as a failure.
    """
    disciplines_hint = ", ".join(disciplines_involved) if disciplines_involved else "(not specified -- infer typical disciplines for this project type)"
    scope_block = (
        f"\n\nTHIS PROJECT'S ACTUAL SCOPE (weight the split towards what this job really "
        f"involves, not the average job of this type):\n{scope_summary.strip()[:1500]}"
        if (scope_summary or "").strip() else ""
    )
    cap_block = (
        f"\n\nSTATED FEE CAP / BUDGET CEILING FOR THIS JOB: {fee_cap_text}"
        if (fee_cap_text or "").strip() else ""
    )
    prompt = f"""You are asked for an INDICATIVE fee split by engineering discipline for a \
"{project_type}" project, covering disciplines: {disciplines_hint}.{scope_block}{cap_block}

Draw on your knowledge of published fee-scale guidance, industry association fee guides, \
and typical market practice for this project type. Be honest that this is general knowledge, \
not a live lookup, and mark your confidence accordingly -- "High" only if you're recalling a \
specific named published source, "Low" if this is a general rule-of-thumb.

Return a JSON object:
{{
  "estimates": [
    {{"discipline": string, "fee_percentage": number, "source": string, "confidence": "High"|"Medium"|"Low"}}
  ]
}}
Percentages across all disciplines should sum to approximately 100."""

    try:
        data = call_ai_json(prompt, config=config, max_tokens=1500)
        raw_estimates = data.get("estimates", [])
        if not raw_estimates:
            raise ValueError("empty estimate list")
        total_amount = _parse_currency(fee_cap_text) if fee_cap_text else None
        estimates = []
        for item in raw_estimates:
            pct = float(item.get("fee_percentage", 0))
            estimates.append(DisciplineFeeEstimate(
                discipline=item.get("discipline", "Unspecified"),
                fee_percentage=pct,
                fee_amount=round(total_amount * pct / 100, 0) if total_amount else None,
                source=f"AI-recalled industry benchmark (not a live web fetch) -- {item.get('source', 'no source given')}. Verify independently.",
                confidence=item.get("confidence", "Low"),
            ))
        estimates.sort(key=lambda e: -e.fee_percentage)
        return estimates, ""
    except Exception as exc:
        # Still falls back to the reliable bundled table -- but says so. A
        # silent fallback returns numbers that look like a successful refresh.
        return estimate_fee_split(project_type, fee_cap_text), (
            f"Couldn't refresh the benchmark split ({str(exc)[:120]}). The figures below are "
            f"the bundled reference table, unchanged -- not a fresh estimate."
        )


def fee_estimates_to_excel(
    estimates: list[DisciplineFeeEstimate],
    indicative_amounts: dict[str, float] | None = None,
    theme_name: str | None = None,
    project_info: dict | None = None,
) -> bytes | None:
    """
    Build a downloadable .xlsx of the indicative benchmark % split table.
    indicative_amounts, if given, overrides each estimate's stored fee_amount
    with a live-recomputed one (e.g. from a manually-entered total project
    fee) keyed by discipline, so the export matches exactly what's on screen
    rather than whatever was baked in when the split was last generated.
    Returns None if openpyxl isn't installed.
    """
    from modules.excel_export import build_fee_workbook
    from modules.resourcing import UNPRICED_NOTE, fee_export_meta

    indicative_amounts = indicative_amounts or {}
    rows = []
    total_amount = 0.0
    total_pct = 0.0
    any_amount = False
    any_unpriced = False
    for e in estimates:
        amount = indicative_amounts.get(e.discipline, e.fee_amount)
        total_pct += e.fee_percentage or 0.0
        if amount:
            total_amount += amount
            any_amount = True
        else:
            any_unpriced = True
        # A blank $ column means "no total project fee entered to apply this
        # percentage to" -- exporting 0 there reads as a priced-at-nothing
        # discipline, which is the opposite of what it means.
        rows.append([e.discipline, e.fee_percentage or None, amount or None,
                     e.confidence, e.source])

    # The Fee % total cell was left empty, so the one number that tells you
    # whether the split adds up to 100% was the one number missing.
    summary_rows = [["Total", total_pct or None, total_amount if any_amount else None, "", ""]]
    notes = []
    if any_unpriced:
        notes.append(
            "A blank Indicative $ cell means no total project fee has been entered to apply "
            "that percentage to -- it is not a zero-value discipline."
        )
    if abs(total_pct - 100.0) > 0.05 and total_pct:
        notes.append(f"The percentages total {total_pct:.1f}%, not 100% -- check the split before using it.")
    return build_fee_workbook(
        sheet_title="Indicative fee split",
        headers=["Discipline", "Fee %", "Indicative $", "Confidence", "Source"],
        rows=rows,
        column_formats={2: '0.0"%"', 3: "$#,##0"},
        summary_rows=summary_rows,
        theme_name=theme_name,
        title="Indicative fee split by discipline",
        meta=fee_export_meta(project_info),
        notes=notes or None,
    )


SCOPE_FEE_SEED_NOTE = (
    "SEEDED STARTING POINT ONLY -- NOT A PRICED OFFER. Every row below is a rough split of "
    "your entered ballpark project value across scope items, weighted only by how many tasks "
    "each item lists. It is not based on real effort estimation and must be replaced with "
    "actual priced figures before this goes anywhere near a client."
)


class ScopeItemFee(BaseModel):
    item_title: str
    fee_amount: float = 0.0
    notes: str = ""


def seed_scope_item_fees(scope_items: list, total_estimate: float | None = None) -> list[ScopeItemFee]:
    """
    Starting point ONLY for the real, priced fee table a letter proposal needs (see
    modules/proposal_structure.py's letter-proposal branch and app.py's Fees editor).

    Unlike estimate_fee_split() (a discipline-of-a-known-total split backed by industry
    benchmark data), there's no benchmark table for "how much does a scope item cost" --
    that depends entirely on real effort estimation the tool has no way to do honestly.
    So this just distributes a ballpark total the user enters across scope items, weighted
    by how many tasks each one lists as a rough effort proxy, purely so the user has a
    starting table to edit rather than a blank one. If no total is given, every item seeds
    at $0.00 and the user fills in real numbers directly.
    """
    if not scope_items:
        return []
    if not total_estimate or total_estimate <= 0:
        return [
            ScopeItemFee(item_title=item.title, fee_amount=0.0, notes="Enter fee -- no estimate seeded")
            for item in scope_items
        ]

    weights = [1 + len(item.tasks) for item in scope_items]
    total_weight = sum(weights) or 1
    fees = []
    for item, weight in zip(scope_items, weights):
        amount = round(total_estimate * weight / total_weight / 50) * 50  # round to nearest $50
        fees.append(ScopeItemFee(
            item_title=item.title, fee_amount=float(amount),
            notes="Seeded from ballpark total -- verify against real effort estimate",
        ))
    return fees


# Project Management is always included as a fixed line item in the
# scope-item / deliverable fee tables, in addition to whatever deliverables
# Tender Analysis extracts -- mirrors resourcing.ALWAYS_INCLUDED_DISCIPLINE /
# resourcing.ensure_project_management_present() for the discipline fee
# build-up table, applied here to the deliverable/scope-item fee table instead.
ALWAYS_INCLUDED_ITEM = "Project Management"


def ensure_project_management_present(fees: list[ScopeItemFee]) -> list[ScopeItemFee]:
    """
    Guarantee a "Project Management" row is present in a scope-item/deliverable
    fee list, appending one (at $0, to be priced) if it's missing -- whether
    because the list hasn't been seeded with it yet, or because the user
    deleted it via the editor. Matching is case-insensitive on item_title.
    """
    if any(f.item_title.strip().lower() == ALWAYS_INCLUDED_ITEM.lower() for f in fees):
        return fees
    return fees + [ScopeItemFee(item_title=ALWAYS_INCLUDED_ITEM, fee_amount=0.0,
                                 notes="Fixed line item -- always included in addition to deliverables")]


def _load_benchmarks() -> dict:
    with open(_BENCHMARKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_currency(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None
