"""Tests for temporal train/val/test split functions (Component 05, step 1)."""
import sqlite3

import pytest

from database import (
    create_core_dimension_tables,
    ensure_xg_schema,
    insert_shot_events,
    upsert_game_metadata,
)
from model_validation import (
    _MIN_SEASONS_FOR_SPLIT,
    _TRAIN_FRAC_DEFAULT,
    _VAL_FRAC_DEFAULT,
    get_distinct_seasons,
    get_shot_events_by_seasons,
    split_seasons_temporal,
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    create_core_dimension_tables(connection)
    ensure_xg_schema(connection)
    yield connection
    connection.close()


def _insert_game(conn, game_id, season):
    """Insert a minimal games row for the given season."""
    upsert_game_metadata(
        conn, game_id=game_id, game_date="2024-01-01",
        season=season, home_team_id=1, away_team_id=2,
    )


def _insert_shot(conn, game_id, event_idx):
    """Insert a minimal shot event for the given game."""
    insert_shot_events(conn, [{
        "game_id": game_id,
        "event_idx": event_idx,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "is_goal": 0,
        "shooting_team_id": 1,
    }])


# ── get_distinct_seasons ───────────────────────────────────────────────


def test_get_distinct_seasons_empty(conn):
    assert get_distinct_seasons(conn) == []


def test_get_distinct_seasons_single(conn):
    _insert_game(conn, 1, "20232024")
    assert get_distinct_seasons(conn) == ["20232024"]


def test_get_distinct_seasons_sorted(conn):
    for i, season in enumerate(["20242025", "20212022", "20222023", "20232024"]):
        _insert_game(conn, i + 1, season)
    result = get_distinct_seasons(conn)
    assert result == ["20212022", "20222023", "20232024", "20242025"]


def test_get_distinct_seasons_deduplicates(conn):
    _insert_game(conn, 1, "20232024")
    _insert_game(conn, 2, "20232024")
    _insert_game(conn, 3, "20242025")
    assert get_distinct_seasons(conn) == ["20232024", "20242025"]


def test_get_distinct_seasons_excludes_null(conn):
    # Insert a game with NULL season via direct SQL
    conn.execute(
        "INSERT INTO games (game_id, game_date, season, home_team_id, away_team_id)"
        " VALUES (99, '2024-01-01', NULL, 1, 2)"
    )
    conn.commit()
    _insert_game(conn, 1, "20232024")
    assert get_distinct_seasons(conn) == ["20232024"]


# ── split_seasons_temporal ─────────────────────────────────────────────


def test_split_seasons_temporal_too_few_raises():
    with pytest.raises(ValueError, match=str(_MIN_SEASONS_FOR_SPLIT)):
        split_seasons_temporal([1, 2])


def test_split_seasons_temporal_empty_raises():
    with pytest.raises(ValueError):
        split_seasons_temporal([])


def test_split_seasons_temporal_minimum_three():
    seasons = [2019, 2020, 2021]
    train, val, test = split_seasons_temporal(seasons)
    assert len(train) >= 1
    assert len(val) >= 1
    assert len(test) >= 1
    assert train + val + test == seasons


def test_split_seasons_temporal_covers_all_seasons():
    seasons = list(range(2007, 2025))  # 18 seasons
    train, val, test = split_seasons_temporal(seasons)
    assert sorted(train + val + test) == sorted(seasons)


def test_split_seasons_temporal_no_overlap():
    seasons = list(range(2007, 2025))
    train, val, test = split_seasons_temporal(seasons)
    train_set = set(train)
    val_set = set(val)
    test_set = set(test)
    assert train_set.isdisjoint(val_set)
    assert train_set.isdisjoint(test_set)
    assert val_set.isdisjoint(test_set)


def test_split_seasons_temporal_preserves_order():
    """Train seasons must all precede val seasons, which precede test seasons."""
    seasons = list(range(2007, 2025))
    train, val, test = split_seasons_temporal(seasons)
    assert max(train) < min(val)
    assert max(val) < min(test)


def test_split_seasons_temporal_respects_fractions_approximately():
    seasons = list(range(2000, 2020))  # 20 seasons
    train, val, test = split_seasons_temporal(
        seasons, train_frac=_TRAIN_FRAC_DEFAULT, val_frac=_VAL_FRAC_DEFAULT
    )
    # Train should be roughly 70%
    assert len(train) >= 12
    assert len(train) <= 16
    # Val should be roughly 15%
    assert len(val) >= 1
    # Test should have at least 1 season
    assert len(test) >= 1


def test_split_seasons_temporal_each_partition_nonempty():
    # Stress test: check that all partition sizes >= 1 for various n
    for n in range(3, 25):
        seasons = list(range(n))
        train, val, test = split_seasons_temporal(seasons)
        assert len(train) >= 1, f"train empty for n={n}"
        assert len(val) >= 1, f"val empty for n={n}"
        assert len(test) >= 1, f"test empty for n={n}"
        assert len(train) + len(val) + len(test) == n


# ── get_shot_events_by_seasons ─────────────────────────────────────────


def test_get_shot_events_by_seasons_empty_list(conn):
    assert get_shot_events_by_seasons(conn, []) == []


def test_get_shot_events_by_seasons_no_matching_data(conn):
    assert get_shot_events_by_seasons(conn, [20232024]) == []


def test_get_shot_events_by_seasons_returns_rows(conn):
    _insert_game(conn, 2023020001, "20232024")
    _insert_shot(conn, 2023020001, 1)
    rows = get_shot_events_by_seasons(conn, ["20232024"])
    assert len(rows) == 1
    assert rows[0]["game_id"] == 2023020001
    assert rows[0]["season"] == "20232024"


def test_get_shot_events_by_seasons_filters_by_season(conn):
    _insert_game(conn, 2023020001, "20232024")
    _insert_game(conn, 2024020001, "20242025")
    _insert_shot(conn, 2023020001, 1)
    _insert_shot(conn, 2024020001, 1)

    rows = get_shot_events_by_seasons(conn, ["20232024"])
    assert all(r["season"] == "20232024" for r in rows)
    assert len(rows) == 1


def test_get_shot_events_by_seasons_includes_multiple_seasons(conn):
    for i, season in enumerate(["20212022", "20222023", "20232024"]):
        game_id = 2020000000 + i
        _insert_game(conn, game_id, season)
        _insert_shot(conn, game_id, 1)

    rows = get_shot_events_by_seasons(conn, ["20212022", "20232024"])
    seasons_found = {r["season"] for r in rows}
    assert seasons_found == {"20212022", "20232024"}
    assert len(rows) == 2


def test_get_shot_events_by_seasons_ordered_by_season_game_event(conn):
    _insert_game(conn, 2023020002, "20232024")
    _insert_game(conn, 2023020001, "20232024")
    _insert_shot(conn, 2023020002, 1)
    _insert_shot(conn, 2023020001, 1)
    _insert_shot(conn, 2023020001, 2)

    rows = get_shot_events_by_seasons(conn, ["20232024"])
    assert len(rows) == 3
    game_ids = [r["game_id"] for r in rows]
    assert game_ids == [2023020001, 2023020001, 2023020002]
    assert rows[0]["event_idx"] == 1
    assert rows[1]["event_idx"] == 2


def test_get_shot_events_by_seasons_returns_dicts_with_shot_columns(conn):
    _insert_game(conn, 2023020001, "20232024")
    _insert_shot(conn, 2023020001, 1)

    rows = get_shot_events_by_seasons(conn, ["20232024"])
    assert len(rows) == 1
    row = rows[0]
    assert "shot_type" in row
    assert "is_goal" in row
    assert "x_coord" in row
    assert "season" in row
