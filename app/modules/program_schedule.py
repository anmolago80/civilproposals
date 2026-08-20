"""
program_schedule.py

Builds a starting-point delivery program (a week-by-scope-item Gantt-style
grid) for a letter proposal, the way the shaded week table in a real fee
proposal letter works. Purely deterministic -- no AI call, since a delivery
schedule is a planning decision for the bid team, not something to infer
from a brief. The default spread is a reasonable starting guess (each item
gets a duration proportional to how many tasks it lists, with a one-week
overlap into the next item, which is how real programs usually look); the
app then lets the user tick/untick weeks per item before export.
"""

from __future__ import annotations

from datetime import date, timedelta


def week_labels(num_weeks: int, start_date: "date | None" = None) -> list[str]:
    """Column headers for the program grid.

    Without a start date these are "Wk 1", "Wk 2", ... -- which is all the app
    could say, because nobody had ever been asked when the work starts. With
    one, each header carries the real calendar week beginning ("Wk 1 - 6 Oct"),
    which is what a client actually reads a program against, and it flows
    through to the letter pack's program table and the program PowerPoint
    without either of them needing to know a date was involved.

    The date is the user's own anticipated start, never derived from the
    brief's submission date or an award assumption: those would be guesses,
    and a guessed date in a program table is exactly the kind of invented fact
    this tool refuses to produce.
    """
    num_weeks = max(0, int(num_weeks))
    if not start_date:
        return [f"Wk {i + 1}" for i in range(num_weeks)]
    labels = []
    for i in range(num_weeks):
        week_start = start_date + timedelta(weeks=i)
        # Built by hand rather than with %-d/%#d, which differ between
        # platforms -- this runs on Linux in production and Windows locally.
        labels.append(f"Wk {i + 1} - {week_start.day} {week_start.strftime('%b')}")
    return labels


def build_default_program(scope_items: list, num_weeks: int) -> dict[str, list[bool]]:
    """
    Returns {item_title: [week_1_active, week_2_active, ...]} of length num_weeks.
    Items are spread sequentially across the available weeks, sized by task count,
    with a one-week overlap into the next item where there's room -- a reasonable
    starting point, not a real schedule. The user adjusts it in-app afterwards.
    """
    num_weeks = max(1, int(num_weeks))
    if not scope_items:
        return {}

    weights = [max(1, len(item.tasks)) for item in scope_items]
    total_weight = sum(weights) or 1

    # Proportional duration per item (at least 1 week each), then lay them out
    # sequentially with a 1-week overlap where there's room.
    durations = []
    for w in weights:
        raw = round(num_weeks * w / total_weight)
        durations.append(max(1, min(num_weeks, raw)))

    schedule: dict[str, list[bool]] = {}
    cursor = 0
    for item, duration in zip(scope_items, durations):
        start = min(cursor, num_weeks - 1)
        end = min(start + duration, num_weeks)
        row = [False] * num_weeks
        for w in range(start, end):
            row[w] = True
        schedule[item.title] = row
        cursor = max(start + 1, end - 1)  # advance, allowing a 1-week overlap with the next item

    return schedule
