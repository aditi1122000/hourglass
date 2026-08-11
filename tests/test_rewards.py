import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rewards import (
    compute_productivity,
    meets_threshold,
    should_award_token,
    tree_stage_from_redemptions,
    tree_emoji_from_redemptions,
    forest_history,
    redemptions_until_full_tree,
    FOREST_CYCLE,
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


def test_forest_cycle_matches_stage_count():
    assert FOREST_CYCLE == 4


def test_forest_history_fresh_start():
    past, stage, emoji = forest_history(0)
    assert past == []
    assert stage == "seed"
    assert emoji == "\U0001F330"


def test_forest_history_mid_first_tree():
    past, stage, emoji = forest_history(3)
    assert past == []
    assert stage == "tree"
    assert emoji == "\U0001F333"


def test_forest_history_one_tree_completed_starts_new_seed():
    past, stage, emoji = forest_history(4)
    assert past == ["\U0001F338"]
    assert stage == "seed"
    assert emoji == "\U0001F330"


def test_forest_history_second_tree_in_progress():
    past, stage, emoji = forest_history(5)
    assert past == ["\U0001F338"]
    assert stage == "sprout"


def test_forest_history_two_trees_completed():
    past, stage, emoji = forest_history(8)
    assert past == ["\U0001F338", "\U0001F338"]
    assert stage == "seed"


def test_forest_history_negative_treated_as_zero():
    past, stage, emoji = forest_history(-5)
    assert past == []
    assert stage == "seed"


def test_redemptions_until_full_tree_fresh_start():
    assert redemptions_until_full_tree(0) == 4


def test_redemptions_until_full_tree_partway():
    assert redemptions_until_full_tree(1) == 3
    assert redemptions_until_full_tree(3) == 1


def test_redemptions_until_full_tree_resets_after_completion():
    assert redemptions_until_full_tree(4) == 4
    assert redemptions_until_full_tree(8) == 4


def test_redemptions_until_full_tree_negative_treated_as_zero():
    assert redemptions_until_full_tree(-10) == 4
