import sqlite3
from datetime import date

import pytest

from database import (
    _quote_identifier,
    create_core_dimension_tables,
    create_collection_log_table,
    create_player_game_features_table,
    create_player_game_stats_table,
    create_table,
    ensure_player_database_schema,
    deduplicate_existing_tables,
    get_last_collected_date,
    insert_data,
    is_date_range_collected,
    is_game_collected,
    mark_date_collected,
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
