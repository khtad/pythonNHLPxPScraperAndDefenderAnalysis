import sqlite3
from datetime import date

import pytest

from database import (
    _XG_EVENT_SCHEMA_VERSION,
    _quote_identifier,
    PlayerMetadataNotFound,
    backfill_player_metadata,
    create_core_dimension_tables,
    create_collection_log_table,
    create_player_game_features_table,
    create_player_game_stats_table,
    create_player_metadata_unavailable_table,
    create_on_ice_intervals_table,
    create_shot_events_table,
    create_shifts_table,
    create_table,
    ensure_player_database_schema,
    deduplicate_existing_tables,
    fix_incomplete_collection_log,
    get_last_collected_date,
    get_missing_player_ids,
    get_random_game_id,
    insert_data,
    delete_game_shot_events,
    insert_shot_events,
    is_date_range_collected,
    is_game_collected,
    load_game_shots,
    load_training_shot_events,
    mark_date_collected,
    mark_players_metadata_unavailable,
    populate_player_game_stats,
    upsert_game_metadata,
    upsert_player,
    upsert_players,
    validate_player_game_stats_quality,
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def test_quote_identifier_accepts_valid_names():
    assert _quote_identifier("game_2023020001") == '"game_2023020001"'
    assert _quote_identifier("abc_123") == '"abc_123"'


@pytest.mark.parametrize("bad_name", ["", "game 1", "game;DROP", 'game"name'])
def test_quote_identifier_rejects_invalid_names(bad_name):
    with pytest.raises(ValueError):
        _quote_identifier(bad_name)


def test_create_table_is_idempotent_and_has_unique_constraint(conn):
    create_table(conn, "2023020001")
    create_table(conn, "2023020001")

    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='game_2023020001'"
    )
    assert cur.fetchone() is not None

    cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='game_2023020001'"
    )
    schema = cur.fetchone()[0]
    assert "UNIQUE(period, time, event, description)" in schema


def test_insert_data_inserts_rows_and_ignores_duplicates(conn):
    create_table(conn, "2023020002")
    rows = [
        {"period": 1, "time": "10:00", "event": "SHOT", "description": "One"},
        {"period": 1, "time": "10:00", "event": "SHOT", "description": "One"},
    ]

    insert_data(conn, "2023020002", rows)

    cur = conn.cursor()
    cur.execute("SELECT period, time, event, description FROM game_2023020002")
    fetched = cur.fetchall()
    assert fetched == [(1, "10:00", "SHOT", "One")]


def test_create_collection_log_table_creates_expected_columns(conn):
    create_collection_log_table(conn)

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(collection_log)")
    cols = [row[1] for row in cur.fetchall()]
    assert cols == ["date", "games_found", "games_collected", "completed_at"]


def test_is_game_collected_false_when_table_missing(conn):
    assert is_game_collected(conn, 2023020999) is False


def test_is_game_collected_false_when_table_empty(conn):
    create_table(conn, "2023020003")
    assert is_game_collected(conn, 2023020003) is False


def test_is_game_collected_true_when_table_has_rows(conn):
    create_table(conn, "2023020004")
    insert_data(
        conn,
        "2023020004",
        [{"period": 2, "time": "05:12", "event": "GOAL", "description": "Scored"}],
    )
    assert is_game_collected(conn, 2023020004) is True


def test_mark_date_collected_replaces_existing_row(conn):
    create_collection_log_table(conn)

    mark_date_collected(conn, "2024-01-01", 10, 8)
    mark_date_collected(conn, "2024-01-01", 12, 12)

    cur = conn.cursor()
    cur.execute(
        "SELECT date, games_found, games_collected, completed_at FROM collection_log WHERE date='2024-01-01'"
    )
    row = cur.fetchone()
    assert row[0] == "2024-01-01"
    assert row[1] == 12
    assert row[2] == 12
    assert row[3] is not None


def test_get_last_collected_date_returns_none_when_empty(conn):
    create_collection_log_table(conn)
    assert get_last_collected_date(conn) is None


def test_get_last_collected_date_returns_latest_date(conn):
    create_collection_log_table(conn)
    mark_date_collected(conn, "2024-01-01", 1, 1)
    mark_date_collected(conn, "2024-01-03", 2, 2)
    mark_date_collected(conn, "2024-01-02", 2, 2)

    assert get_last_collected_date(conn) == date(2024, 1, 3)


def test_is_date_range_collected_true_when_all_dates_present(conn):
    create_collection_log_table(conn)
    for d in ["2024-01-01", "2024-01-02", "2024-01-03"]:
        mark_date_collected(conn, d, 1, 1)

    assert is_date_range_collected(conn, date(2024, 1, 1), date(2024, 1, 3)) is True


def test_is_date_range_collected_false_when_any_date_missing(conn):
    create_collection_log_table(conn)
    mark_date_collected(conn, "2024-01-01", 1, 1)
    mark_date_collected(conn, "2024-01-03", 1, 1)

    assert is_date_range_collected(conn, date(2024, 1, 1), date(2024, 1, 3)) is False


def test_deduplicate_existing_tables_removes_duplicates_and_adds_unique_constraint(conn):
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE game_2023020005 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period INTEGER,
            time TEXT,
            event TEXT,
            description TEXT
        )
        """
    )
    cur.executemany(
        "INSERT INTO game_2023020005 (period, time, event, description) VALUES (?, ?, ?, ?)",
        [
            (1, "01:00", "SHOT", "Dup"),
            (1, "01:00", "SHOT", "Dup"),
            (2, "02:00", "GOAL", "Unique"),
        ],
    )
    conn.commit()

    deduplicate_existing_tables(conn)

    cur.execute("SELECT COUNT(*) FROM game_2023020005")
    assert cur.fetchone()[0] == 2

    cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='game_2023020005'"
    )
    schema = cur.fetchone()[0]
    assert "UNIQUE(period, time, event, description)" in schema


def test_deduplicate_existing_tables_leaves_already_unique_tables_untouched(conn):
    create_table(conn, "2023020006")
    insert_data(
        conn,
        "2023020006",
        [{"period": 1, "time": "01:00", "event": "SHOT", "description": "Once"}],
    )

    deduplicate_existing_tables(conn)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM game_2023020006")
    assert cur.fetchone()[0] == 1


def test_deduplicate_existing_tables_ignores_games_dimension_table(conn):
    create_core_dimension_tables(conn)

    deduplicate_existing_tables(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='games'"
    )
    assert cur.fetchone()[0] == "games"


def test_phase_2_create_core_dimension_tables_creates_players_games_teams(conn):
    create_core_dimension_tables(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('players', 'games', 'teams')"
    )
    existing = {row[0] for row in cur.fetchall()}

    assert existing == {"players", "games", "teams"}


def test_phase_2_players_table_has_expected_primary_key(conn):
    create_core_dimension_tables(conn)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(players)")
    table_info = {row[1]: row for row in cur.fetchall()}

    assert table_info["player_id"][5] == 1


def test_phase_3_create_player_game_stats_table_and_indexes(conn):
    create_player_game_stats_table(conn)
    cur = conn.cursor()

    cur.execute("PRAGMA index_list(player_game_stats)")
    index_names = {row[1] for row in cur.fetchall()}

    assert "idx_player_game_stats_game_id" in index_names
    assert "idx_player_game_stats_position_group_game_id" in index_names


def test_phase_3_player_game_stats_unique_on_player_game(conn):
    create_player_game_stats_table(conn)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO player_game_stats (
            player_id, game_id, team_id, position_group, toi_seconds
        ) VALUES (8478402, 2023020001, 10, 'F', 600)
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            """
            INSERT INTO player_game_stats (
                player_id, game_id, team_id, position_group, toi_seconds
            ) VALUES (8478402, 2023020001, 10, 'F', 610)
            """
        )


def test_phase_4_create_player_game_features_table(conn):
    create_player_game_features_table(conn)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info(player_game_features)")
    cols = {row[1] for row in cur.fetchall()}

    assert {
        "player_id",
        "game_id",
        "season",
        "game_number_for_player",
        "toi_rank_pos_5g",
        "toi_rank_pos_10g",
        "toi_rolling_mean_5g",
        "points_rolling_10g",
        "feature_set_version",
    }.issubset(cols)


def test_phase_5_validate_player_game_stats_quality_reports_errors(conn):
    create_player_game_stats_table(conn)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO player_game_stats (
            player_id, game_id, team_id, position_group, toi_seconds
        ) VALUES
            (1, 2023021001, 10, 'F', -1),
            (2, 2023021001, 10, 'X', 4500)
        """
    )
    conn.commit()

    report = validate_player_game_stats_quality(conn)

    assert report["invalid_position_group_rows"] == 1
    assert report["negative_toi_rows"] == 1
    assert report["toi_above_max_rows"] == 1


def test_phase_5_validate_player_game_stats_quality_no_errors_on_valid_data(conn):
    create_player_game_stats_table(conn)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO player_game_stats (
            player_id, game_id, team_id, position_group, toi_seconds
        ) VALUES
            (1, 2023021002, 10, 'F', 900),
            (2, 2023021002, 10, 'D', 1200),
            (3, 2023021002, 10, 'G', 3600)
        """
    )
    conn.commit()

    report = validate_player_game_stats_quality(conn)

    assert report == {
        "duplicate_player_game_rows": 0,
        "negative_toi_rows": 0,
        "toi_above_max_rows": 0,
        "invalid_position_group_rows": 0,
    }


def test_ensure_player_database_schema_is_idempotent(conn):
    ensure_player_database_schema(conn)
    ensure_player_database_schema(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='player_game_features'"
    )
    assert cur.fetchone() is not None


def test_mark_date_collected_sets_null_completed_at_when_incomplete(conn):
    create_collection_log_table(conn)
    mark_date_collected(conn, "2024-02-01", 5, 3)

    cur = conn.cursor()
    cur.execute("SELECT completed_at FROM collection_log WHERE date='2024-02-01'")
    assert cur.fetchone()[0] is None


def test_mark_date_collected_sets_completed_at_when_all_games_collected(conn):
    create_collection_log_table(conn)
    mark_date_collected(conn, "2024-02-01", 5, 5)

    cur = conn.cursor()
    cur.execute("SELECT completed_at FROM collection_log WHERE date='2024-02-01'")
    assert cur.fetchone()[0] is not None


def test_get_last_collected_date_returns_day_before_earliest_incomplete(conn):
    create_collection_log_table(conn)
    mark_date_collected(conn, "2024-01-01", 2, 2)  # complete
    mark_date_collected(conn, "2024-01-02", 3, 1)  # incomplete
    mark_date_collected(conn, "2024-01-03", 2, 2)  # complete

    assert get_last_collected_date(conn) == date(2024, 1, 1)


def test_get_last_collected_date_falls_back_when_no_incomplete(conn):
    create_collection_log_table(conn)
    mark_date_collected(conn, "2024-01-01", 2, 2)
    mark_date_collected(conn, "2024-01-02", 3, 3)

    assert get_last_collected_date(conn) == date(2024, 1, 2)


def test_mark_date_collected_incomplete_then_complete_sets_completed_at(conn):
    create_collection_log_table(conn)
    mark_date_collected(conn, "2024-02-01", 5, 3)

    cur = conn.cursor()
    cur.execute("SELECT completed_at FROM collection_log WHERE date='2024-02-01'")
    assert cur.fetchone()[0] is None

    mark_date_collected(conn, "2024-02-01", 5, 5)
    cur.execute("SELECT completed_at FROM collection_log WHERE date='2024-02-01'")
    assert cur.fetchone()[0] is not None


def test_fix_incomplete_collection_log_clears_bad_completed_at(conn):
    create_collection_log_table(conn)
    cur = conn.cursor()
    # Simulate old buggy data: incomplete date with completed_at set
    cur.execute(
        "INSERT INTO collection_log (date, games_found, games_collected, completed_at) "
        "VALUES (?, ?, ?, ?)",
        ("2024-03-01", 5, 3, "2024-03-01T12:00:00"),
    )
    # Complete date should be left alone
    cur.execute(
        "INSERT INTO collection_log (date, games_found, games_collected, completed_at) "
        "VALUES (?, ?, ?, ?)",
        ("2024-03-02", 4, 4, "2024-03-02T12:00:00"),
    )
    conn.commit()

    fix_incomplete_collection_log(conn)

    cur.execute("SELECT completed_at FROM collection_log WHERE date='2024-03-01'")
    assert cur.fetchone()[0] is None

    cur.execute("SELECT completed_at FROM collection_log WHERE date='2024-03-02'")
    assert cur.fetchone()[0] is not None


# ── get_random_game_id / load_game_shots fixtures ────────────────────────────


def _shot_dict(game_id, event_idx, version=None, **overrides):
    base = {
        "game_id": game_id,
        "event_idx": event_idx,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 1200,
        "shot_type": "wrist",
        "x_coord": 60.0,
        "y_coord": 5.0,
        "distance_to_goal": 30.0,
        "angle_to_goal": 10.0,
        "is_goal": 0,
        "shooting_team_id": 1,
    }
    base.update(overrides)
    if version is not None:
        base["event_schema_version"] = version
    return base


def _seed_game(conn, game_id, season, n_shots, version=None, event_idx_start=0):
    upsert_game_metadata(
        conn, game_id, game_date=f"{season[:4]}-10-15", season=season,
        home_team_id=1, away_team_id=2, venue_name=f"Arena_{game_id}",
    )
    shots = [
        _shot_dict(game_id, event_idx_start + i, version=version)
        for i in range(n_shots)
    ]
    insert_shot_events(conn, shots)


def _seed_game_env(conn):
    create_core_dimension_tables(conn)
    create_shot_events_table(conn)


def test_get_random_game_id_returns_none_when_empty(conn):
    _seed_game_env(conn)
    assert get_random_game_id(conn) is None


def test_get_random_game_id_respects_min_shots(conn):
    _seed_game_env(conn)
    _seed_game(conn, 100, "20232024", n_shots=1)
    _seed_game(conn, 200, "20232024", n_shots=10)
    for seed in range(5):
        assert get_random_game_id(conn, min_shots=5, seed=seed) == 200


def test_get_random_game_id_respects_season(conn):
    _seed_game_env(conn)
    _seed_game(conn, 300, "20222023", n_shots=10)
    _seed_game(conn, 400, "20232024", n_shots=10)
    for seed in range(5):
        assert get_random_game_id(conn, season="20232024", seed=seed) == 400


def test_get_random_game_id_is_reproducible_with_seed(conn):
    _seed_game_env(conn)
    for gid in range(500, 510):
        _seed_game(conn, gid, "20232024", n_shots=5)
    first = get_random_game_id(conn, seed=42)
    second = get_random_game_id(conn, seed=42)
    assert first == second
    assert first is not None


def test_get_random_game_id_requires_current_schema_version(conn):
    _seed_game_env(conn)
    _seed_game(conn, 600, "20232024", n_shots=10, version="v2")
    assert get_random_game_id(conn) is None
    # Sanity: a current-version game IS returned.
    _seed_game(conn, 601, "20232024", n_shots=10)
    assert get_random_game_id(conn) == 601


def test_get_random_game_id_season_accepts_int(conn):
    _seed_game_env(conn)
    _seed_game(conn, 700, "20232024", n_shots=5)
    assert get_random_game_id(conn, season=20232024, seed=0) == 700


def test_load_game_shots_returns_rows_ordered_by_event_idx(conn):
    _seed_game_env(conn)
    upsert_game_metadata(
        conn, 800, game_date="2023-10-15", season="20232024",
        home_team_id=1, away_team_id=2, venue_name="TestArena",
    )
    insert_shot_events(conn, [
        _shot_dict(800, 5),
        _shot_dict(800, 1),
        _shot_dict(800, 3),
    ])
    shots = load_game_shots(conn, 800)
    assert [s["event_idx"] for s in shots] == [1, 3, 5]


def test_load_game_shots_joins_game_metadata(conn):
    _seed_game_env(conn)
    upsert_game_metadata(
        conn, 801, game_date="2023-10-15", season="20232024",
        home_team_id=10, away_team_id=20, venue_name="VerifyArena",
    )
    insert_shot_events(conn, [_shot_dict(801, 1)])
    shots = load_game_shots(conn, 801)
    assert len(shots) == 1
    row = shots[0]
    assert row["game_date"] == "2023-10-15"
    assert row["season"] == "20232024"
    assert row["home_team_id"] == 10
    assert row["away_team_id"] == 20
    assert row["venue_name"] == "VerifyArena"


def test_load_game_shots_empty_game(conn):
    _seed_game_env(conn)
    upsert_game_metadata(
        conn, 802, game_date="2023-10-15", season="20232024",
        home_team_id=1, away_team_id=2,
    )
    assert load_game_shots(conn, 802) == []


def test_load_training_shot_events_excludes_pre_2009_seasons(conn):
    _seed_game_env(conn)
    _seed_game(conn, 810, "20082009", n_shots=1)
    _seed_game(conn, 811, "20092010", n_shots=1)

    rows = load_training_shot_events(conn)

    assert [(r["game_id"], r["season"]) for r in rows] == [(811, "20092010")]


def test_load_training_shot_events_excludes_null_distance_rows(conn):
    _seed_game_env(conn)
    _seed_game(conn, 812, "20092010", n_shots=1)
    insert_shot_events(conn, [_shot_dict(812, 99, distance_to_goal=None)])

    rows = load_training_shot_events(conn)

    assert all(r["distance_to_goal"] is not None for r in rows)
    assert [r["event_idx"] for r in rows] == [0]


def test_create_shifts_table_creates_expected_columns(conn):
    create_shifts_table(conn)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(shifts)")
    cols = [row[1] for row in cur.fetchall()]
    assert "shift_schema_version" in cols


def test_create_on_ice_intervals_table_creates_expected_columns(conn):
    create_on_ice_intervals_table(conn)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(on_ice_intervals)")
    cols = [row[1] for row in cur.fetchall()]
    assert "home_skaters_json" in cols
    assert "away_skaters_json" in cols


# ── Phase 2.5.1: players upsert / backfill / populate_player_game_stats ─────


def _player_row(player_id, position="C", team_id=22, shoots="L"):
    return {
        "player_id": player_id,
        "first_name": f"First{player_id}",
        "last_name": f"Last{player_id}",
        "shoots_catches": shoots,
        "position": position,
        "team_id": team_id,
    }


def _fetch_player_rows(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, first_name, last_name, shoots_catches, position, team_id "
        "FROM players ORDER BY player_id"
    )
    return cur.fetchall()


def test_upsert_player_inserts_new_row(conn):
    ensure_player_database_schema(conn)
    upsert_player(conn, _player_row(10))
    assert _fetch_player_rows(conn) == [
        (10, "First10", "Last10", "L", "C", 22),
    ]


def test_upsert_player_updates_existing_row(conn):
    ensure_player_database_schema(conn)
    upsert_player(conn, _player_row(10, position="C", team_id=22))
    upsert_player(conn, _player_row(10, position="L", team_id=30, shoots="R"))
    rows = _fetch_player_rows(conn)
    assert rows == [(10, "First10", "Last10", "R", "L", 30)]


def test_upsert_player_rejects_unknown_keys(conn):
    ensure_player_database_schema(conn)
    with pytest.raises(ValueError):
        upsert_player(conn, {"player_id": 1, "nickname": "Gretz"})


def test_upsert_player_requires_player_id(conn):
    ensure_player_database_schema(conn)
    with pytest.raises(ValueError):
        upsert_player(conn, {"player_id": None, "position": "C"})


def test_upsert_players_batch_insert_and_update(conn):
    ensure_player_database_schema(conn)
    upsert_players(conn, [_player_row(1), _player_row(2), _player_row(3)])
    assert len(_fetch_player_rows(conn)) == 3

    upsert_players(conn, [
        _player_row(2, position="D", team_id=50),
        _player_row(4, position="G", team_id=11),
    ])
    rows = dict((r[0], r) for r in _fetch_player_rows(conn))
    assert rows[2][4] == "D" and rows[2][5] == 50
    assert rows[4][4] == "G"
    assert len(rows) == 4


def test_upsert_players_empty_list_is_noop(conn):
    ensure_player_database_schema(conn)
    upsert_players(conn, [])
    assert _fetch_player_rows(conn) == []


def _seed_shot(conn, game_id, event_idx, shooter_id, goalie_id,
               shooting_team_id=1, is_goal=0):
    insert_shot_events(conn, [
        {
            "game_id": game_id,
            "event_idx": event_idx,
            "period": 1,
            "time_in_period": "10:00",
            "time_remaining_seconds": 600,
            "shot_type": "wrist",
            "x_coord": 50.0,
            "y_coord": 0.0,
            "distance_to_goal": 40.0,
            "angle_to_goal": 5.0,
            "is_goal": is_goal,
            "shooting_team_id": shooting_team_id,
            "shooter_id": shooter_id,
            "goalie_id": goalie_id,
        },
    ])


def test_get_missing_player_ids_unions_shooters_and_goalies(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 900, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 900, 1, shooter_id=101, goalie_id=201)
    _seed_shot(conn, 900, 2, shooter_id=102, goalie_id=201)

    upsert_player(conn, _player_row(101))

    missing = get_missing_player_ids(conn)
    assert missing == [102, 201]


def test_get_missing_player_ids_filters_nulls(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 901, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 901, 1, shooter_id=101, goalie_id=None)
    _seed_shot(conn, 901, 2, shooter_id=None, goalie_id=201)

    assert get_missing_player_ids(conn) == [101, 201]


def test_backfill_player_metadata_upserts_every_missing_id(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 902, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 902, 1, shooter_id=101, goalie_id=201)
    _seed_shot(conn, 902, 2, shooter_id=102, goalie_id=201)

    fetch_calls = []

    def fake_fetch(player_id):
        fetch_calls.append(player_id)
        return _player_row(player_id)

    attempted, upserted, unavailable = backfill_player_metadata(
        conn, fake_fetch, batch_size=2
    )
    assert attempted == 3
    assert upserted == 3
    assert unavailable == 0
    assert sorted(fetch_calls) == [101, 102, 201]
    assert {r[0] for r in _fetch_player_rows(conn)} == {101, 102, 201}


def test_backfill_player_metadata_is_idempotent_on_second_run(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 903, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 903, 1, shooter_id=101, goalie_id=201)

    def fake_fetch(player_id):
        return _player_row(player_id)

    backfill_player_metadata(conn, fake_fetch)
    attempted, upserted, unavailable = backfill_player_metadata(conn, fake_fetch)
    assert attempted == 0
    assert upserted == 0
    assert unavailable == 0


def test_backfill_player_metadata_skips_when_fetch_returns_none(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 904, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 904, 1, shooter_id=101, goalie_id=201)

    def fake_fetch(player_id):
        return None if player_id == 201 else _player_row(player_id)

    attempted, upserted, unavailable = backfill_player_metadata(conn, fake_fetch)
    assert attempted == 2
    assert upserted == 1
    assert unavailable == 0
    assert {r[0] for r in _fetch_player_rows(conn)} == {101}


def test_backfill_player_metadata_marks_unavailable_on_not_found(conn):
    """Fetches that raise PlayerMetadataNotFound must be cached in
    player_metadata_unavailable so subsequent runs skip the id.
    """
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 905, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 905, 1, shooter_id=101, goalie_id=201)

    def fake_fetch(player_id):
        if player_id == 201:
            raise PlayerMetadataNotFound(player_id)
        return _player_row(player_id)

    attempted, upserted, unavailable = backfill_player_metadata(
        conn, fake_fetch, batch_size=1
    )
    assert attempted == 2
    assert upserted == 1
    assert unavailable == 1

    cur = conn.cursor()
    cur.execute("SELECT player_id FROM player_metadata_unavailable ORDER BY player_id")
    assert [r[0] for r in cur.fetchall()] == [201]


def test_backfill_player_metadata_skips_unavailable_ids_on_rerun(conn):
    """A second run must not re-fetch ids already recorded as unavailable."""
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 906, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 906, 1, shooter_id=101, goalie_id=201)

    call_counts = {"total": 0}

    def fake_fetch(player_id):
        call_counts["total"] += 1
        if player_id == 201:
            raise PlayerMetadataNotFound(player_id)
        return _player_row(player_id)

    backfill_player_metadata(conn, fake_fetch)
    attempted, upserted, unavailable = backfill_player_metadata(conn, fake_fetch)
    assert attempted == 0
    assert upserted == 0
    assert unavailable == 0
    assert call_counts["total"] == 2


def test_get_missing_player_ids_excludes_unavailable_rows(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 907, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 907, 1, shooter_id=101, goalie_id=201)

    mark_players_metadata_unavailable(conn, [201])
    assert get_missing_player_ids(conn) == [101]


def test_mark_players_metadata_unavailable_is_idempotent(conn):
    create_player_metadata_unavailable_table(conn)
    mark_players_metadata_unavailable(conn, [101, 102])
    mark_players_metadata_unavailable(conn, [101, 103])

    cur = conn.cursor()
    cur.execute(
        "SELECT player_id FROM player_metadata_unavailable ORDER BY player_id"
    )
    assert [r[0] for r in cur.fetchall()] == [101, 102, 103]


def test_populate_player_game_stats_counts_shots_and_goals(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 910, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    upsert_player(conn, _player_row(101, position="C", team_id=1))
    upsert_player(conn, _player_row(201, position="G", team_id=2))

    _seed_shot(conn, 910, 1, shooter_id=101, goalie_id=201, shooting_team_id=1, is_goal=0)
    _seed_shot(conn, 910, 2, shooter_id=101, goalie_id=201, shooting_team_id=1, is_goal=1)
    _seed_shot(conn, 910, 3, shooter_id=101, goalie_id=201, shooting_team_id=1, is_goal=0)

    populate_player_game_stats(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, team_id, position_group, shots, goals "
        "FROM player_game_stats ORDER BY player_id"
    )
    rows = cur.fetchall()
    assert rows == [
        (101, 1, "F", 3, 1),
        (201, 2, "G", 0, 0),
    ]

    issues = validate_player_game_stats_quality(conn)
    assert all(v == 0 for v in issues.values()), issues


def test_populate_player_game_stats_derives_goalie_team_id_from_games(conn):
    """Goalie rows use the opponent of shooting_team_id in the games table."""
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 911, game_date="2023-10-15", season="20232024",
                         home_team_id=7, away_team_id=8)
    upsert_player(conn, _player_row(301, position="G", team_id=None))

    _seed_shot(conn, 911, 1, shooter_id=999, goalie_id=301, shooting_team_id=7)
    _seed_shot(conn, 911, 2, shooter_id=999, goalie_id=301, shooting_team_id=7)

    populate_player_game_stats(conn)

    cur = conn.cursor()
    cur.execute("SELECT team_id FROM player_game_stats WHERE player_id = 301")
    assert cur.fetchone()[0] == 8


def test_populate_player_game_stats_is_idempotent(conn):
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 912, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    upsert_player(conn, _player_row(101, position="C", team_id=1))
    upsert_player(conn, _player_row(201, position="G", team_id=2))
    _seed_shot(conn, 912, 1, shooter_id=101, goalie_id=201, shooting_team_id=1, is_goal=1)

    populate_player_game_stats(conn)
    populate_player_game_stats(conn)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM player_game_stats")
    assert cur.fetchone()[0] == 2


def test_populate_player_game_stats_defaults_unknown_position_group(conn):
    """If a shooter has no players-table row, default to F; goalies default to G."""
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 913, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    _seed_shot(conn, 913, 1, shooter_id=101, goalie_id=201, shooting_team_id=1)

    populate_player_game_stats(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, position_group FROM player_game_stats ORDER BY player_id"
    )
    assert cur.fetchall() == [(101, "F"), (201, "G")]


def test_populate_player_game_stats_merges_goalie_shooter_same_game(conn):
    """A goalie who also registers a shot in the same game (e.g., empty-net
    goal) must retain their shot and goal counts; the goalie aggregate's
    zero-totals row must not overwrite the shooter aggregate.
    """
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 914, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    upsert_player(conn, _player_row(401, position="G", team_id=1))
    upsert_player(conn, _player_row(501, position="C", team_id=2))

    _seed_shot(conn, 914, 1, shooter_id=501, goalie_id=401, shooting_team_id=2, is_goal=0)
    _seed_shot(conn, 914, 2, shooter_id=501, goalie_id=401, shooting_team_id=2, is_goal=0)
    _seed_shot(conn, 914, 3, shooter_id=401, goalie_id=None, shooting_team_id=1, is_goal=1)

    populate_player_game_stats(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, team_id, position_group, shots, goals "
        "FROM player_game_stats WHERE player_id = 401"
    )
    assert cur.fetchone() == (401, 1, "G", 1, 1)


def test_populate_player_game_stats_clears_stale_rows_after_reprocess(conn):
    """Reprocessing a game (delete + reinsert shot_events) must drop
    player_game_stats rows for players who are no longer in the refreshed
    events, so downstream features never see stale aggregates.
    """
    ensure_player_database_schema(conn)
    create_shot_events_table(conn)
    upsert_game_metadata(conn, 915, game_date="2023-10-15", season="20232024",
                         home_team_id=1, away_team_id=2)
    upsert_player(conn, _player_row(101, position="C", team_id=1))
    upsert_player(conn, _player_row(102, position="C", team_id=1))
    upsert_player(conn, _player_row(201, position="G", team_id=2))

    _seed_shot(conn, 915, 1, shooter_id=101, goalie_id=201, shooting_team_id=1)
    _seed_shot(conn, 915, 2, shooter_id=102, goalie_id=201, shooting_team_id=1)
    populate_player_game_stats(conn)

    cur = conn.cursor()
    cur.execute(
        "SELECT player_id FROM player_game_stats "
        "WHERE game_id = 915 ORDER BY player_id"
    )
    assert [r[0] for r in cur.fetchall()] == [101, 102, 201]

    delete_game_shot_events(conn, 915)
    _seed_shot(conn, 915, 1, shooter_id=101, goalie_id=201, shooting_team_id=1)
    populate_player_game_stats(conn)

    cur.execute(
        "SELECT player_id FROM player_game_stats "
        "WHERE game_id = 915 ORDER BY player_id"
    )
    assert [r[0] for r in cur.fetchall()] == [101, 201]
