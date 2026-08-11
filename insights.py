"""Pure, DB-free data-shaping for the Insights page.

Same pattern as rewards.py: plain lists/dicts in, plain lists/dicts out, so
this is fully unit-testable without a live Supabase connection.
"""

from datetime import timedelta

from rewards import PRODUCTIVITY_THRESHOLD

OTHER_LABEL = "Other"
MAX_CHART_GROUPS = 8

# Sunday-first order, matching GitHub's contribution graph convention.
WEEKDAY_LABELS_MON_FIRST = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
CALENDAR_WEEKDAY_ORDER = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def aggregate_hours(rows, group_field):
    """rows: list of {"log_date": ..., group_field: ..., "hours": number}.

    Sums hours for matching (log_date, group) pairs and returns one row per
    pair, sorted by date then group name.
    """
    totals = {}
    for row in rows:
        key = (row["log_date"], row[group_field])
        totals[key] = totals.get(key, 0) + row["hours"]

    result = [
        {"log_date": key[0], group_field: key[1], "hours": hours}
        for key, hours in totals.items()
    ]
    result.sort(key=lambda r: (r["log_date"], r[group_field]))
    return result


def group_totals(rows, group_field):
    """rows: list of {group_field: ..., "hours": number}.

    Returns {group_name: total_hours} across all rows, regardless of date.
    """
    totals = {}
    for row in rows:
        totals[row[group_field]] = totals.get(row[group_field], 0) + row["hours"]
    return totals


def category_share_takeaway(rows, group_field):
    """A one-line, plain-Python takeaway about the biggest group's share of
    total hours, e.g. "Work took up 62% of your logged time in this range."
    Returns None when there's nothing to summarize.
    """
    totals = group_totals(rows, group_field)
    total_hours = sum(totals.values())
    if total_hours <= 0:
        return None
    top_group, top_hours = max(totals.items(), key=lambda kv: kv[1])
    share_pct = top_hours / total_hours * 100
    return f"{top_group} took up {share_pct:.0f}% of your logged time in this range."


def fold_to_top_groups(rows, group_field, max_groups=MAX_CHART_GROUPS, other_label=OTHER_LABEL):
    """Cap the number of distinct groups a chart has to render.

    Groups outside the top `max_groups` (by total hours across all rows) are
    relabeled to `other_label` and re-summed, so a chart never has to render
    an unbounded number of series.
    """
    totals = group_totals(rows, group_field)

    if len(totals) <= max_groups:
        return aggregate_hours(rows, group_field)

    top_groups = set(sorted(totals, key=lambda g: totals[g], reverse=True)[:max_groups])
    folded = [
        {**row, group_field: row[group_field] if row[group_field] in top_groups else other_label}
        for row in rows
    ]
    return aggregate_hours(folded, group_field)


def daily_productive_series(logs):
    """logs: list of {"log_date": ..., "hours": number, "is_productive": bool}.

    Returns one row per day that has at least one log, sorted by date:
    {"log_date", "total_hours", "productive_hours", "pct"}.
    """
    per_day = {}
    for log in logs:
        entry = per_day.setdefault(log["log_date"], {"total": 0.0, "productive": 0.0})
        entry["total"] += log["hours"]
        if log["is_productive"]:
            entry["productive"] += log["hours"]

    rows = []
    for day in sorted(per_day):
        total = per_day[day]["total"]
        productive = per_day[day]["productive"]
        pct = productive / total if total > 0 else 0.0
        rows.append(
            {"log_date": day, "total_hours": total, "productive_hours": productive, "pct": pct}
        )
    return rows


def build_daily_threshold_flags(daily_rows, start_date, end_date, threshold=PRODUCTIVITY_THRESHOLD):
    """Expand daily_productive_series() output into one bool per calendar day
    from start_date to end_date (inclusive) -- True if that day's productive
    % cleared `threshold`. Days with no logs at all count as False.
    """
    pct_by_date = {row["log_date"]: row["pct"] for row in daily_rows}
    flags = []
    day = start_date
    while day <= end_date:
        flags.append(pct_by_date.get(day, 0.0) >= threshold)
        day += timedelta(days=1)
    return flags


def current_streak(day_flags):
    """day_flags: chronological list of bool, oldest first.

    Returns the number of consecutive True values trailing the end of the
    list -- i.e. the current in-progress streak.
    """
    streak = 0
    for met in reversed(day_flags):
        if not met:
            break
        streak += 1
    return streak


def streak_flame(streak):
    """Map a day-streak length to a Duolingo-style flame intensity emoji --
    escalating visual weight rewards a longer streak instead of just showing
    a bare number."""
    if streak >= 14:
        return "\U0001F525\U0001F525\U0001F525"
    if streak >= 7:
        return "\U0001F525\U0001F525"
    if streak >= 3:
        return "\U0001F525"
    if streak >= 1:
        return "✨"
    return "\U0001F4A4"


def build_calendar_heatmap_rows(daily_rows, start_date, end_date, threshold=PRODUCTIVITY_THRESHOLD):
    """One row per calendar day in [start_date, end_date], shaped for a
    GitHub-style contribution heatmap: which Sunday-starting week it falls
    in, its weekday abbreviation, and whether that day met/missed the
    productivity threshold (or has no logged data at all).
    """
    pct_by_date = {row["log_date"]: row["pct"] for row in daily_rows}
    rows = []
    current = start_date
    while current <= end_date:
        weekday_index = current.weekday()  # Mon=0 .. Sun=6
        days_since_sunday = (weekday_index + 1) % 7
        week_start = current - timedelta(days=days_since_sunday)
        pct = pct_by_date.get(current)
        if pct is None:
            status = "no_data"
        elif pct >= threshold:
            status = "met"
        else:
            status = "missed"
        rows.append(
            {
                "date": current,
                "week_start": week_start,
                "weekday_label": WEEKDAY_LABELS_MON_FIRST[weekday_index],
                "pct": pct,
                "status": status,
            }
        )
        current += timedelta(days=1)
    return rows
