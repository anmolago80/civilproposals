"""
fee_history.py

The firm's OWN fee history, and the benchmarks derived from it.

WHY
---
The fee build-up opened at zeros, and the only "benchmark" on offer was a
bundled table of published industry averages for a project type. A firm that
has priced eleven bridge duplications knows far more about how its own splits
land than any published average does -- and the tool was throwing that away
every time a pack was exported.

Every exported/archived pack now leaves a snapshot behind: per discipline,
the hours, the rate, the amount and its share of the total. Two or more
snapshots of the same project type and the Fee tab can offer the firm's own
median split, ranked ABOVE the bundled table and labelled as what it is.

WHAT IS AND ISN'T CLAIMED
-------------------------
The median of a firm's own past splits is a fact about that firm's past
pricing, and it is labelled exactly that way -- "your firm's history (median
of N bids)" with the per-discipline range shown, never as a recommendation or
a market rate. Below two bids there is no median worth the name, so nothing
is offered at all rather than presenting a single past job as a benchmark.

Snapshots are strictly per user (see db.FeeSnapshot.user_id) -- one firm's
pricing must never surface in another firm's benchmark, which is also why
every function here takes a user_id and none of them has a global fallback.

Never raises. Everything here is an optional accuracy improvement layered on
top of a fee sheet that already works, so a database hiccup degrades to "no
history available" rather than to a traceback mid-bid.
"""

from __future__ import annotations

import json
import statistics
import sys

from modules import db

# Below this, "median of N bids" is not a median, it is one job with extra
# steps. Two is the smallest number for which a range means anything.
MIN_BIDS_FOR_BENCHMARK = 2

SOURCE_HISTORY = "your firm's history"
SOURCE_BUNDLED = "bundled rule-of-thumb"
SOURCE_AI = "AI-modelled"


def _lines_payload(fee_lines: list | None) -> tuple[list[dict], float]:
    """Normalise resourcing.DisciplineFeeLine rows into the stored shape.

    An unpriced row (no hours or no rate) is DROPPED rather than stored as a
    0% discipline: it means "not priced yet", and averaging it in as a zero
    would drag every future benchmark down by however many rows the user
    hadn't got to."""
    rows = []
    total = 0.0
    for line in (fee_lines or []):
        discipline = (getattr(line, "discipline", "") or "").strip()
        amount = float(getattr(line, "fee_amount", 0.0) or 0.0)
        if not discipline or amount <= 0:
            continue
        rows.append({
            "discipline": discipline,
            "hours": float(getattr(line, "total_hours", 0.0) or 0.0),
            "rate": float(getattr(line, "rate_per_hour", 0.0) or 0.0),
            "amount": amount,
        })
        total += amount
    for row in rows:
        row["pct_of_total"] = round(row["amount"] / total * 100, 2) if total else 0.0
    return rows, total


def record_snapshot(user_id: str | None, project_key: str, project_type: str,
                    fee_lines: list | None, project_name: str = "") -> bool:
    """Store (or refresh) this project's fee split. Returns True if something
    was written.

    Upsert on (user_id, project_key) rather than insert: this is called every
    time a pack is generated as well as when one is archived, and a user who
    regenerates five times has still only bid once."""
    if not user_id or not (project_key or "").strip():
        return False
    rows, total = _lines_payload(fee_lines)
    if not rows:
        # Nothing priced yet. Storing an empty split would count as a bid in
        # the "median of N bids" line without contributing anything to it.
        return False
    try:
        with db.get_session() as session:
            existing = session.query(db.FeeSnapshot).filter(
                db.FeeSnapshot.user_id == user_id,
                db.FeeSnapshot.project_key == project_key,
            ).first()
            if existing is None:
                existing = db.FeeSnapshot(user_id=user_id, project_key=project_key)
                session.add(existing)
            existing.project_name = project_name or ""
            existing.project_type = (project_type or "").strip() or "Unspecified"
            existing.total_amount = total
            existing.lines_json = json.dumps(rows)
            session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 -- never lose an export over bookkeeping
        print(f"[fee history] couldn't record snapshot: {exc}", file=sys.stderr)
        return False


def snapshot_count(user_id: str | None, project_type: str | None = None) -> int:
    if not user_id:
        return 0
    try:
        with db.get_session() as session:
            query = session.query(db.FeeSnapshot).filter(db.FeeSnapshot.user_id == user_id)
            if project_type:
                query = query.filter(db.FeeSnapshot.project_type == project_type)
            return query.count()
    except Exception as exc:  # noqa: BLE001
        print(f"[fee history] couldn't count snapshots: {exc}", file=sys.stderr)
        return 0


def fee_history_benchmarks(user_id: str | None, project_type: str | None) -> dict:
    """The firm's own median split for this project type.

    Returns {"bids": int, "disciplines": [{discipline, median_pct, low_pct,
    high_pct, bids}]} sorted by median share, or {"bids": 0, "disciplines":
    []} when there isn't enough history to say anything.

    `bids` counts the PROJECTS behind the benchmark; each discipline also
    carries its own `bids`, because a discipline that appeared on two of five
    jobs is a weaker signal than one that appeared on all five, and the tab
    shows both rather than flattening them together.
    """
    empty = {"bids": 0, "disciplines": []}
    if not user_id:
        return empty
    try:
        with db.get_session() as session:
            query = session.query(db.FeeSnapshot).filter(db.FeeSnapshot.user_id == user_id)
            if project_type:
                query = query.filter(db.FeeSnapshot.project_type == project_type)
            snapshots = query.all()
            payloads = [snapshot.lines_json for snapshot in snapshots]
    except Exception as exc:  # noqa: BLE001
        print(f"[fee history] couldn't read snapshots: {exc}", file=sys.stderr)
        return empty

    by_discipline: dict[str, list[float]] = {}
    counted = 0
    for payload in payloads:
        try:
            rows = json.loads(payload or "[]")
        except (TypeError, ValueError):
            continue
        if not rows:
            continue
        counted += 1
        for row in rows:
            discipline = (row.get("discipline") or "").strip()
            pct = float(row.get("pct_of_total") or 0.0)
            if discipline and pct > 0:
                by_discipline.setdefault(discipline, []).append(pct)

    if counted < MIN_BIDS_FOR_BENCHMARK or not by_discipline:
        return empty

    disciplines = [
        {
            "discipline": discipline,
            "median_pct": round(statistics.median(values), 1),
            "low_pct": round(min(values), 1),
            "high_pct": round(max(values), 1),
            "bids": len(values),
        }
        for discipline, values in by_discipline.items()
    ]
    disciplines.sort(key=lambda entry: -entry["median_pct"])
    return {"bids": counted, "disciplines": disciplines}


def best_available_split(user_id: str | None, project_type: str | None,
                         disciplines: list[str] | None) -> tuple[dict, str]:
    """The best percentage split available for `disciplines`, and which of the
    three labelled tiers it came from.

    The firm's own history first, the bundled rule-of-thumb table second.
    Returns ({discipline: pct}, source_label); the percentages are
    renormalised across exactly the disciplines asked for, so a split that
    covered a discipline this project doesn't have doesn't leave the total
    short.
    """
    wanted = [d for d in (disciplines or []) if (d or "").strip()]
    if not wanted:
        return {}, ""

    history = fee_history_benchmarks(user_id, project_type)
    lookup = {entry["discipline"].strip().lower(): entry["median_pct"]
              for entry in history["disciplines"]}
    matched = {d: lookup[d.strip().lower()] for d in wanted if d.strip().lower() in lookup}
    # A history that covers only one of six disciplines isn't a split, it is a
    # single data point being stretched across a sheet.
    if matched and len(matched) >= max(2, len(wanted) // 2):
        return _renormalise(matched, wanted), SOURCE_HISTORY

    try:
        from modules.fee_estimation_engine import estimate_fee_split

        bundled = {e.discipline.strip().lower(): e.fee_percentage
                   for e in estimate_fee_split(project_type or "")}
    except Exception as exc:  # noqa: BLE001
        print(f"[fee history] couldn't load bundled benchmarks: {exc}", file=sys.stderr)
        return {}, ""
    matched = {d: bundled[d.strip().lower()] for d in wanted if d.strip().lower() in bundled}
    if not matched:
        # Nothing recognised the disciplines this brief actually names, so an
        # even split is the only honest answer -- and it is labelled as coming
        # from the bundled tier, which is where the fallback lives.
        return {d: round(100 / len(wanted), 2) for d in wanted}, SOURCE_BUNDLED
    return _renormalise(matched, wanted), SOURCE_BUNDLED


def _renormalise(matched: dict, wanted: list[str]) -> dict:
    """Spread the matched percentages over every wanted discipline so they sum
    to 100. Unmatched disciplines share whatever is left over evenly -- they
    are real disciplines on this job and giving them 0% would read as a
    decision not to price them."""
    unmatched = [d for d in wanted if d not in matched]
    matched_total = sum(matched.values()) or 1.0
    if not unmatched:
        return {d: round(pct / matched_total * 100, 2) for d, pct in matched.items()}
    # Keep the matched disciplines' relative shares, and reserve a slice for
    # the unmatched ones proportional to how many of them there are.
    reserved = min(45.0, 100.0 * len(unmatched) / len(wanted))
    result = {d: round(pct / matched_total * (100 - reserved), 2) for d, pct in matched.items()}
    for discipline in unmatched:
        result[discipline] = round(reserved / len(unmatched), 2)
    return result
