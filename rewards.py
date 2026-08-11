"""Pure, DB-free business logic for Hourglass.

Every function here takes plain numbers/lists and returns plain values so it
can be unit-tested without a live Supabase connection.
"""

PRODUCTIVITY_THRESHOLD = 0.35

TREE_STAGES = ["seed", "sprout", "sapling", "tree", "blooming tree"]
TREE_EMOJI = {
    "seed": "\U0001F330",
    "sprout": "\U0001F331",
    "sapling": "\U0001F33F",
    "tree": "\U0001F333",
    "blooming tree": "\U0001F338",
}


def compute_productivity(logs):
    """logs: list of {"hours": float, "is_productive": bool}.

    Returns (total_hours, productive_hours, productive_pct).
    productive_pct is 0.0 when total_hours is 0.
    """
    total_hours = sum(log["hours"] for log in logs)
    productive_hours = sum(log["hours"] for log in logs if log["is_productive"])
    productive_pct = productive_hours / total_hours if total_hours > 0 else 0.0
    return total_hours, productive_hours, productive_pct


def meets_threshold(total_hours, productive_hours):
    """Whether a day's logs qualify for a token, per PRODUCTIVITY_THRESHOLD."""
    if total_hours <= 0:
        return False
    return (productive_hours / total_hours) >= PRODUCTIVITY_THRESHOLD


def should_award_token(total_hours, productive_hours, already_awarded):
    """Decide whether to award a token for a user+day.

    already_awarded: True if a tokens row already exists for this user+day.
    Awarding is idempotent -- never award twice for the same day.
    """
    if already_awarded:
        return False
    return meets_threshold(total_hours, productive_hours)


def tree_stage_from_redemptions(redemption_count):
    """Map a total redemption count to a tree growth stage name."""
    if redemption_count < 0:
        redemption_count = 0
    index = min(redemption_count, len(TREE_STAGES) - 1)
    return TREE_STAGES[index]


def tree_emoji_from_redemptions(redemption_count):
    return TREE_EMOJI[tree_stage_from_redemptions(redemption_count)]
