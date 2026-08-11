import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from insights import (
    aggregate_hours,
    fold_to_top_groups,
    group_totals,
    category_share_takeaway,
    daily_productive_series,
    build_daily_threshold_flags,
    current_streak,
    streak_flame,
    build_calendar_heatmap_rows,
    OTHER_LABEL,
)


D1 = date(2026, 1, 1)
D2 = date(2026, 1, 2)
D3 = date(2026, 1, 3)


def test_aggregate_hours_sums_same_date_and_group():
    rows = [
        {"log_date": D1, "category": "Work", "hours": 2},
        {"log_date": D1, "category": "Work", "hours": 1.5},
        {"log_date": D1, "category": "Fun", "hours": 1},
    ]
    result = aggregate_hours(rows, "category")
    assert result == [
        {"log_date": D1, "category": "Fun", "hours": 1},
        {"log_date": D1, "category": "Work", "hours": 3.5},
    ]


def test_aggregate_hours_sorted_by_date_then_group():
    rows = [
        {"log_date": D2, "category": "Work", "hours": 1},
        {"log_date": D1, "category": "Fun", "hours": 1},
        {"log_date": D1, "category": "Work", "hours": 1},
    ]
    result = aggregate_hours(rows, "category")
    assert [ (r["log_date"], r["category"]) for r in result ] == [
        (D1, "Fun"), (D1, "Work"), (D2, "Work")
    ]


def test_aggregate_hours_empty():
    assert aggregate_hours([], "category") == []


def test_fold_to_top_groups_no_folding_needed():
    rows = [
        {"log_date": D1, "category": "Work", "hours": 2},
        {"log_date": D1, "category": "Fun", "hours": 1},
    ]
    result = fold_to_top_groups(rows, "category", max_groups=8)
    assert {r["category"] for r in result} == {"Work", "Fun"}


def test_fold_to_top_groups_folds_extras_and_sums_other():
    rows = [
        {"log_date": D1, "category": "A", "hours": 10},
        {"log_date": D1, "category": "B", "hours": 9},
        {"log_date": D1, "category": "C", "hours": 3},
        {"log_date": D1, "category": "D", "hours": 2},
    ]
    result = fold_to_top_groups(rows, "category", max_groups=2)
    by_group = {r["category"]: r["hours"] for r in result}
    assert by_group["A"] == 10
    assert by_group["B"] == 9
    assert by_group[OTHER_LABEL] == 5  # C(3) + D(2)
    assert len(result) == 3


def test_fold_to_top_groups_exactly_at_max_no_folding():
    rows = [
        {"log_date": D1, "category": "A", "hours": 1},
        {"log_date": D1, "category": "B", "hours": 1},
    ]
    result = fold_to_top_groups(rows, "category", max_groups=2)
    assert {r["category"] for r in result} == {"A", "B"}


def test_daily_productive_series_basic():
    logs = [
        {"log_date": D1, "hours": 3, "is_productive": True},
        {"log_date": D1, "hours": 2, "is_productive": False},
        {"log_date": D2, "hours": 4, "is_productive": True},
    ]
    result = daily_productive_series(logs)
    assert result == [
        {"log_date": D1, "total_hours": 5, "productive_hours": 3, "pct": 0.6},
        {"log_date": D2, "total_hours": 4, "productive_hours": 4, "pct": 1.0},
    ]


def test_daily_productive_series_all_nonproductive_gives_zero_pct():
    logs = [{"log_date": D1, "hours": 2, "is_productive": False}]
    result = daily_productive_series(logs)
    assert result[0]["pct"] == 0.0


def test_daily_productive_series_empty():
    assert daily_productive_series([]) == []


def test_build_daily_threshold_flags_fills_gaps_as_false():
    daily_rows = [
        {"log_date": D1, "pct": 0.5},
        {"log_date": D3, "pct": 0.4},
    ]
    flags = build_daily_threshold_flags(daily_rows, D1, D3)
    assert flags == [True, False, True]  # D2 has no logs -> False


def test_build_daily_threshold_flags_exact_threshold_counts_as_met():
    daily_rows = [{"log_date": D1, "pct": 0.35}]
    flags = build_daily_threshold_flags(daily_rows, D1, D1)
    assert flags == [True]


def test_build_daily_threshold_flags_below_threshold():
    daily_rows = [{"log_date": D1, "pct": 0.34}]
    flags = build_daily_threshold_flags(daily_rows, D1, D1)
    assert flags == [False]


def test_current_streak_empty():
    assert current_streak([]) == 0


def test_current_streak_all_true():
    assert current_streak([True, True, True]) == 3


def test_current_streak_trailing_false_resets_to_zero():
    assert current_streak([True, True, False]) == 0


def test_current_streak_counts_only_trailing_run():
    assert current_streak([False, True, False, True, True]) == 2


def test_current_streak_single_day():
    assert current_streak([True]) == 1
    assert current_streak([False]) == 0


def test_group_totals_sums_across_dates():
    rows = [
        {"log_date": D1, "category": "Work", "hours": 2},
        {"log_date": D2, "category": "Work", "hours": 3},
        {"log_date": D1, "category": "Fun", "hours": 1},
    ]
    assert group_totals(rows, "category") == {"Work": 5, "Fun": 1}


def test_group_totals_empty():
    assert group_totals([], "category") == {}


def test_category_share_takeaway_names_top_group_and_share():
    rows = [
        {"log_date": D1, "category": "Work", "hours": 6},
        {"log_date": D1, "category": "Fun", "hours": 4},
    ]
    takeaway = category_share_takeaway(rows, "category")
    assert takeaway == "Work took up 60% of your logged time in this range."


def test_category_share_takeaway_empty_returns_none():
    assert category_share_takeaway([], "category") is None


def test_category_share_takeaway_zero_hours_returns_none():
    rows = [{"log_date": D1, "category": "Work", "hours": 0}]
    assert category_share_takeaway(rows, "category") is None


def test_streak_flame_dormant_at_zero():
    assert streak_flame(0) == "\U0001F4A4"


def test_streak_flame_spark_below_three():
    assert streak_flame(1) == "✨"
    assert streak_flame(2) == "✨"


def test_streak_flame_single_flame_at_three():
    assert streak_flame(3) == "\U0001F525"
    assert streak_flame(6) == "\U0001F525"


def test_streak_flame_double_flame_at_seven():
    assert streak_flame(7) == "\U0001F525\U0001F525"
    assert streak_flame(13) == "\U0001F525\U0001F525"


def test_streak_flame_triple_flame_at_fourteen():
    assert streak_flame(14) == "\U0001F525\U0001F525\U0001F525"
    assert streak_flame(100) == "\U0001F525\U0001F525\U0001F525"


def test_build_calendar_heatmap_rows_covers_every_day_inclusive():
    rows = build_calendar_heatmap_rows([], D1, D3)
    assert [r["date"] for r in rows] == [D1, D2, D3]


def test_build_calendar_heatmap_rows_no_data_when_no_logs():
    rows = build_calendar_heatmap_rows([], D1, D1)
    assert rows[0]["status"] == "no_data"
    assert rows[0]["pct"] is None


def test_build_calendar_heatmap_rows_met_and_missed():
    daily_rows = [{"log_date": D1, "pct": 0.5}, {"log_date": D2, "pct": 0.1}]
    rows = build_calendar_heatmap_rows(daily_rows, D1, D2)
    assert rows[0]["status"] == "met"
    assert rows[1]["status"] == "missed"


def test_build_calendar_heatmap_rows_exact_threshold_counts_as_met():
    daily_rows = [{"log_date": D1, "pct": 0.35}]
    rows = build_calendar_heatmap_rows(daily_rows, D1, D1, threshold=0.35)
    assert rows[0]["status"] == "met"


def test_build_calendar_heatmap_rows_week_start_is_preceding_sunday():
    # Walk every weekday once and confirm week_start always lands on Sunday
    # and is within 6 days before (or equal to) the day itself.
    monday = date(2026, 1, 5)  # a known Monday
    for offset in range(7):
        day = monday + timedelta(days=offset)
        rows = build_calendar_heatmap_rows([], day, day)
        week_start = rows[0]["week_start"]
        assert week_start.weekday() == 6  # Sunday
        assert 0 <= (day - week_start).days <= 6


def test_build_calendar_heatmap_rows_weekday_label_matches_python_weekday():
    monday = date(2026, 1, 5)
    rows = build_calendar_heatmap_rows([], monday, monday)
    assert rows[0]["weekday_label"] == "Mon"
