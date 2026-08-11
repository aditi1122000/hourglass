import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from insights import (
    aggregate_hours,
    fold_to_top_groups,
    daily_productive_series,
    build_daily_threshold_flags,
    current_streak,
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
