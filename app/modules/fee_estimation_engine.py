"""
fee_estimation_engine.py

Produces an INDICATIVE, INTERNAL-ONLY fee split by discipline -- a sanity
check for the bid team before committing hours to a pursuit, never a number
to submit. See README.md for the full reasoning; the short version:

- Primary source is a bundled reference table of typical industry fee-split
  patterns by project type (sample_data/fee_benchmarks.json). Fast, works
  offline, and is honestly labelled as a rule-of-thumb rather than a
  researched figure.
- An optional "AI-modelled benchmarks" action asks the configured AI provider
  for its knowledge of published fee benchmarks. It was called "refresh from
  web" and it never touched the web -- none of the base provider APIs wired
  up in ai_interface.py browse the internet -- so the name was a claim the
  feature could not back. It is now named for what it does, and every figure
  it produces is labelled AI-modelled, carries a range rather than a single
  false-precision number, and states its own basis.
- Three labelled tiers, in descending order of how much they should be
  trusted: the firm's own history (see modules/fee_history.py), the bundled
  rule-of-thumb table, and AI-modelled benchmarks. Every estimate says which
  tier it came from.
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
    # The plausible band around fee_percentage, where the source gave one.
    # A single number implies a precision none of these tiers has; the AI
    # tier in particular returned one significant figure dressed up as three.
    # None means "this source gave a point estimate", not "the range is zero".
    pct_low: float | None = None
    pct_high: float | None = None

    @property
    def range_text(self) -> str:
        """"12.0-18.0%" where a range is known, "15.0%" where it isn't."""
        if self.pct_low is None or self.pct_high is None:
            return f"{self.fee_percentage:.1f}%"
        return f"{self.pct_low:.1f}-{self.pct_high:.1f}%"


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


AI_BENCHMARK_LABEL = "AI-modelled benchmarks"

_AI_BENCHMARK_SYSTEM = """You are advising an Australian civil engineering consultancy on how a \
design fee typically divides between disciplines. Work from published fee-scale guidance, \
industry association fee guides and typical Australian market practice for this kind of \
commission. You have no live access to the web and must not imply that you do: say what your \
figure is based on, and give a plausible RANGE rather than a single number, because a single \
number implies a precision this kind of estimate does not have."""

_AI_BENCHMARK_PROMPT = """PROJECT TYPE: {project_type}
CONTEXT: Australian civil engineering consulting commission.

PROJECT SCOPE AS STATED IN THE BRIEF:
{project_scope}

SCOPE ITEMS THE BRIEF LISTS:
{scope_items}

DISCIPLINES TO SPLIT THE FEE ACROSS (return one entry for EACH, using the exact text given):
{disciplines}

FEE CAP / BUDGET CEILING STATED IN THE BRIEF: {fee_cap}

Weight the split towards what THIS job actually involves, as described above, rather than the \
average job of this type. Where the scope barely touches a discipline, say so with a low range.

Return a JSON object:
{{
  "estimates": [
    {{"discipline": string (exactly as given above),
      "pct_low": number, "pct_high": number, "pct_typical": number,
      "basis": string (one short sentence -- what this figure is based on),
      "confidence": "High"|"Medium"|"Low"}}
  ]
}}
The pct_typical values across all disciplines should sum to approximately 100."""


def _format_scope_items(analysis) -> str:
    items = getattr(analysis, "scope_items", None) or [] if analysis is not None else []
    lines = []
    for item in items:
        title = (getattr(item, "title", "") or "").strip()
        if title:
            lines.append(f"- {title}")
    return "\n".join(lines) or "- (none extracted)"


def refresh_estimate_from_ai(
    project_type: str,
    disciplines_involved: list[str] | None = None,
    fee_cap_text: str | None = None,
    config: dict | None = None,
    scope_summary: str = "",
    analysis=None,
    capture_prompt: list | None = None,
) -> tuple[list[DisciplineFeeEstimate], str]:
    """
    Ask the configured AI provider how a fee of this kind typically divides,
    given THIS brief's scope, scope items, discipline list and fee cap.

    Explicitly not a live web fetch, and no longer named as though it were --
    see the module docstring. Returns (estimates, error). On failure the
    estimates list is EMPTY and the error explains why: the previous version
    fell back to the bundled table, so a user who pressed the button got the
    bundled numbers back with nothing on screen disagreeing with them, and
    would reasonably read unchanged figures as a second source confirming the
    first. Two tiers must never be able to impersonate each other.

    `capture_prompt`, if given, has the prompt appended to it -- the tests
    assert on the real prompt rather than on a re-derivation of it, which is
    the only way to catch context quietly failing to reach the model.
    """
    disciplines = [d for d in (disciplines_involved or []) if (d or "").strip()]
    prompt = _AI_BENCHMARK_PROMPT.format(
        project_type=(project_type or "").strip() or "(not specified)",
        project_scope=(scope_summary or "").strip()[:1500] or "(not extracted)",
        scope_items=_format_scope_items(analysis),
        disciplines="\n".join(f"- {d}" for d in disciplines)
                    or "- (not specified -- use the disciplines typical for this project type)",
        fee_cap=(fee_cap_text or "").strip() or "(none stated in the brief)",
    )
    if capture_prompt is not None:
        capture_prompt.append(prompt)

    try:
        data = call_ai_json(prompt, system_message=_AI_BENCHMARK_SYSTEM, config=config,
                            max_tokens=2000)
        raw_estimates = (data or {}).get("estimates") or []
        if not raw_estimates:
            raise ValueError("the AI returned no estimates")
        total_amount = _parse_currency(fee_cap_text) if fee_cap_text else None
        estimates = []
        for item in raw_estimates:
            low = _as_float(item.get("pct_low"))
            high = _as_float(item.get("pct_high"))
            typical = _as_float(item.get("pct_typical"))
            if typical is None and low is not None and high is not None:
                typical = (low + high) / 2
            if typical is None:
                continue
            if low is not None and high is not None and low > high:
                low, high = high, low
            basis = (item.get("basis") or "").strip() or "no basis given"
            estimates.append(DisciplineFeeEstimate(
                discipline=(item.get("discipline") or "Unspecified").strip(),
                fee_percentage=round(typical, 1),
                pct_low=round(low, 1) if low is not None else None,
                pct_high=round(high, 1) if high is not None else None,
                fee_amount=round(total_amount * typical / 100, 0) if total_amount else None,
                source=f"{AI_BENCHMARK_LABEL} (no live lookup) -- {basis} Verify independently.",
                confidence=(item.get("confidence") or "Low").strip(),
            ))
        if not estimates:
            raise ValueError("no usable percentages in the AI's response")
        estimates.sort(key=lambda e: -e.fee_percentage)
        return estimates, ""
    except Exception as exc:
        return [], (
            f"Couldn't get {AI_BENCHMARK_LABEL} ({str(exc)[:140]}). Nothing on the table below "
            f"has changed -- these are still whatever figures were already there, not a fresh "
            f"estimate."
        )


def keep_range_if_unedited(estimate: DisciplineFeeEstimate,
                           prior: DisciplineFeeEstimate | None) -> DisciplineFeeEstimate:
    """Carry a benchmark's typical range onto a rebuilt row, but only while
    the percentage is still the benchmark's.

    The fee tables rebuild every DisciplineFeeEstimate from their editor's
    rows on each apply, which drops anything the editor doesn't hold -- and
    the range is deliberately not editable, so it was being lost. Carrying it
    unconditionally would be worse: a range is a statement about where the
    SOURCE puts this discipline, and once the user types their own percentage
    it no longer describes the number beside it. Leaving it there would dress
    a pricing decision up as a benchmarked one.
    """
    if prior is None or prior.pct_low is None:
        return estimate
    if abs((prior.fee_percentage or 0) - (estimate.fee_percentage or 0)) > 0.001:
        return estimate
    estimate.pct_low = prior.pct_low
    estimate.pct_high = prior.pct_high
    return estimate


def _as_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


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
