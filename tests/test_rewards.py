import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rewards import (
    compute_productivity,
    meets_threshold,
    should_award_token,
    tree_stage_from_redemptions,
    tree_emoji_from_redemptions,
)


def test_compute_productivity_no_logs():
    total, productive, pct = compute_productivity([])
    assert total == 0
    assert productive == 0
    assert pct == 0.0


def test_compute_productivity_mixed():
    logs = [
        {"hours": 3, "is_productive": True},
        {"hours": 2, "is_productive": False},
    ]
    total, productive, pct = compute_productivity(logs)
    assert total == 5
    assert productive == 3
    assert pct == 0.6


def test_meets_threshold_zero_total_hours():
    assert meets_threshold(0, 0) is False


def test_meets_threshold_exactly_35_percent():
    assert meets_threshold(total_hours=20, productive_hours=7) is True  # 0.35 exactly


def test_meets_threshold_below():
    assert meets_threshold(total_hours=20, productive_hours=6.9) is False


def test_meets_threshold_above():
    assert meets_threshold(total_hours=10, productive_hours=5) is True


def test_should_award_token_first_time_meets_threshold():
    assert should_award_token(total_hours=10, productive_hours=4, already_awarded=False) is True


def test_should_award_token_first_time_below_threshold():
    assert should_award_token(total_hours=10, productive_hours=2, already_awarded=False) is False


def test_should_award_token_idempotent_even_if_more_logged():
    # Already awarded earlier today -- must not award again even though
    # productive hours now comfortably clear the threshold.
    assert should_award_token(total_hours=20, productive_hours=15, already_awarded=True) is False


def test_should_award_token_zero_hours():
    assert should_award_token(total_hours=0, productive_hours=0, already_awarded=False) is False


def test_tree_stage_progression():
    assert tree_stage_from_redemptions(0) == "seed"
    assert tree_stage_from_redemptions(1) == "sprout"
    assert tree_stage_from_redemptions(2) == "sapling"
    assert tree_stage_from_redemptions(3) == "tree"
    assert tree_stage_from_redemptions(4) == "blooming tree"


def test_tree_stage_caps_at_final_stage():
    assert tree_stage_from_redemptions(5) == "blooming tree"
    assert tree_stage_from_redemptions(1000) == "blooming tree"


def test_tree_stage_negative_treated_as_zero():
    assert tree_stage_from_redemptions(-3) == "seed"


def test_tree_emoji_matches_stage_count():
    from rewards import TREE_STAGES, TREE_EMOJI

    for stage in TREE_STAGES:
        assert stage in TREE_EMOJI


def test_tree_emoji_from_redemptions_smoke():
    assert tree_emoji_from_redemptions(0) == "\U0001F330"
    assert tree_emoji_from_redemptions(4) == "\U0001F338"
