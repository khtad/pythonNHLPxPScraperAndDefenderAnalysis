"""Temporal train/validation/test splits for xG model training.

All splits are season-based to prevent future-data leakage.
The training window always precedes validation, which precedes testing.
"""

_TRAIN_FRAC_DEFAULT = 0.70
_VAL_FRAC_DEFAULT = 0.15
# Test fraction is the remainder: 1 - _TRAIN_FRAC_DEFAULT - _VAL_FRAC_DEFAULT
_MIN_SEASONS_FOR_SPLIT = 3


def get_distinct_seasons(conn):
    """Return sorted list of unique season values from the games table.

    Seasons are returned in ascending order (oldest first) so that
    callers can rely on positional order for temporal splits.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT season FROM games WHERE season IS NOT NULL ORDER BY season"
    )
    return [row[0] for row in cursor.fetchall()]


def split_seasons_temporal(seasons,
                           train_frac=_TRAIN_FRAC_DEFAULT,
                           val_frac=_VAL_FRAC_DEFAULT):
    """Split a sorted season list into (train, val, test) temporal partitions.

    The split respects chronological order: train seasons are the oldest,
    val seasons come next, and test seasons are the most recent.
    Each partition is guaranteed to contain at least one season.

    Args:
        seasons: Sorted list of season identifiers (oldest first).
        train_frac: Approximate fraction of seasons for training.
        val_frac: Approximate fraction of seasons for validation.

    Returns:
        Tuple (train_seasons, val_seasons, test_seasons) as lists.

    Raises:
        ValueError: If len(seasons) < _MIN_SEASONS_FOR_SPLIT.
    """
    n = len(seasons)
    if n < _MIN_SEASONS_FOR_SPLIT:
        raise ValueError(
            f"Need at least {_MIN_SEASONS_FOR_SPLIT} seasons to split; got {n}"
        )

    train_n = max(1, int(n * train_frac))
    val_n = max(1, int(n * val_frac))
    test_n = n - train_n - val_n

    # If rounding leaves test empty, reduce train by the shortfall
    if test_n < 1:
        train_n -= (1 - test_n)
        train_n = max(1, train_n)
        test_n = n - train_n - val_n

    return (
        seasons[:train_n],
        seasons[train_n:train_n + val_n],
        seasons[train_n + val_n:],
    )


def get_shot_events_by_seasons(conn, season_list):
    """Fetch shot events for a list of seasons, joined with game season info.

    Returns a list of dicts, each containing all shot_events columns plus
    a 'season' field from the games table. Rows are ordered by season,
    game_id, then event_idx so temporal order is preserved within each split.

    Args:
        conn: SQLite connection.
        season_list: List of season identifiers to include.

    Returns:
        List of dicts. Empty list if season_list is empty.
    """
    if not season_list:
        return []
    placeholders = ", ".join(["?"] * len(season_list))
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT se.*, g.season AS season
            FROM shot_events se
            JOIN games g ON se.game_id = g.game_id
            WHERE g.season IN ({placeholders})
            ORDER BY g.season, se.game_id, se.event_idx""",
        list(season_list),
    )
    cols = [desc[0] for desc in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]
