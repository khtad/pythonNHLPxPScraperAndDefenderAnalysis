import sqlite3

import pytest

from database import (
    _GAME_CONTEXT_SCHEMA_VERSION,
    _VENUE_BIAS_Z_SCORE_THRESHOLD,
    create_core_dimension_tables,
    create_game_context_table,
    create_venue_bias_corrections_table,
    create_venue_bias_diagnostics_table,
    create_shot_events_table,
    ensure_xg_schema,
    upsert_game_metadata,
    upsert_team,
    game_has_metadata,
    game_has_context,
    populate_game_context,
    compute_venue_season_stats,
    compute_league_season_stats,
    populate_venue_diagnostics,
    populate_venue_bias_corrections,
    load_game_shots_with_venue_correction,
    validate_game_context_quality,
    _migrate_games_add_venue_columns,
    _stddev,
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    create_core_dimension_tables(connection)
    create_shot_events_table(connection)
    create_game_context_table(connection)
    create_venue_bias_diagnostics_table(connection)
    create_venue_bias_corrections_table(connection)
    yield connection
    connection.close()


# ── Constants ────────────────────────────────────────────────────────


def test_game_context_schema_version_is_string():
    assert isinstance(_GAME_CONTEXT_SCHEMA_VERSION, str)
    assert len(_GAME_CONTEXT_SCHEMA_VERSION) > 0


def test_venue_bias_z_score_threshold_is_positive():
    assert _VENUE_BIAS_Z_SCORE_THRESHOLD > 0


# ── upsert_team ─────────────────────────────────────────────────────


def test_upsert_team_inserts(conn):
    upsert_team(conn, 10, "TOR", "Toronto")
    cur = conn.cursor()
    cur.execute("SELECT team_abbrev, team_name FROM teams WHERE team_id = 10")
    row = cur.fetchone()
    assert row == ("TOR", "Toronto")


def test_upsert_team_updates(conn):
    upsert_team(conn, 10, "TOR", "Toronto")
    upsert_team(conn, 10, "TOR", "Toronto Maple Leafs")
    cur = conn.cursor()
    cur.execute("SELECT team_name FROM teams WHERE team_id = 10")
    assert cur.fetchone()[0] == "Toronto Maple Leafs"


# ── upsert_game_metadata ────────────────────────────────────────────


def test_upsert_game_metadata_inserts(conn):
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    cur = conn.cursor()
    cur.execute("SELECT game_date, season, home_team_id, away_team_id FROM games WHERE game_id = 2024020001")
    row = cur.fetchone()
    assert row == ("2024-10-08", "20242025", 10, 8)


def test_upsert_game_metadata_updates(conn):
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    upsert_game_metadata(conn, 2024020001, "2024-10-09", 20242025, 10, 8)
    cur = conn.cursor()
    cur.execute("SELECT game_date FROM games WHERE game_id = 2024020001")
    assert cur.fetchone()[0] == "2024-10-09"


def test_upsert_game_metadata_with_venue(conn):
    upsert_game_metadata(
        conn, 2024020001, "2024-10-08", 20242025, 10, 8,
        venue_name="Scotiabank Arena", venue_city="Toronto",
        venue_utc_offset="-05:00",
    )
    cur = conn.cursor()
    cur.execute("SELECT venue_name, venue_city, venue_utc_offset FROM games WHERE game_id = 2024020001")
    row = cur.fetchone()
    assert row == ("Scotiabank Arena", "Toronto", "-05:00")


# ── game_has_metadata ───────────────────────────────────────────────


def test_game_has_metadata_false_when_empty(conn):
    assert game_has_metadata(conn, 9999) is False


def test_game_has_metadata_true_when_present(conn):
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    assert game_has_metadata(conn, 2024020001) is True


# ── game_context table DDL ──────────────────────────────────────────


def test_create_game_context_table_creates_table(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='game_context'")
    assert cur.fetchone() is not None


def test_create_game_context_table_has_expected_columns(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(game_context)")
    cols = {row[1] for row in cur.fetchall()}
    expected = {
        "game_id", "home_rest_days", "away_rest_days", "rest_advantage",
        "home_is_back_to_back", "away_is_back_to_back",
        "travel_distance_km", "timezone_delta", "context_schema_version",
    }
    assert expected.issubset(cols)


def test_create_game_context_table_is_idempotent(conn):
    create_game_context_table(conn)  # already created in fixture
    create_game_context_table(conn)


# ── populate_game_context ───────────────────────────────────────────


def test_populate_game_context_basic(conn):
    # Insert two games for the home team to compute rest days
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    upsert_game_metadata(conn, 2024020002, "2024-10-10", 20242025, 10, 6)

    populate_game_context(conn, 2024020002)

    cur = conn.cursor()
    cur.execute("SELECT home_rest_days, home_is_back_to_back FROM game_context WHERE game_id = 2024020002")
    row = cur.fetchone()
    assert row[0] == 2  # 2 days rest
    assert row[1] == 0  # not back to back


def test_populate_game_context_back_to_back(conn):
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    upsert_game_metadata(conn, 2024020002, "2024-10-09", 20242025, 10, 6)

    populate_game_context(conn, 2024020002)

    cur = conn.cursor()
    cur.execute("SELECT home_rest_days, home_is_back_to_back FROM game_context WHERE game_id = 2024020002")
    row = cur.fetchone()
    assert row[0] == 1
    assert row[1] == 1


def test_populate_game_context_no_previous_game(conn):
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)

    populate_game_context(conn, 2024020001)

    cur = conn.cursor()
    cur.execute("SELECT home_rest_days, away_rest_days FROM game_context WHERE game_id = 2024020001")
    row = cur.fetchone()
    assert row[0] is None  # no previous game
    assert row[1] is None


def test_populate_game_context_idempotent(conn):
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    populate_game_context(conn, 2024020001)
    populate_game_context(conn, 2024020001)  # should not raise

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM game_context WHERE game_id = 2024020001")
    assert cur.fetchone()[0] == 1


def test_populate_game_context_missing_game(conn):
    populate_game_context(conn, 9999)  # no games row, should not raise

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM game_context")
    assert cur.fetchone()[0] == 0


def test_populate_game_context_travel_distance(conn):
    # TOR (team 10) vs BOS (team 6) — known teams in arena_reference
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 6)

    populate_game_context(conn, 2024020001)

    cur = conn.cursor()
    cur.execute("SELECT travel_distance_km FROM game_context WHERE game_id = 2024020001")
    row = cur.fetchone()
    assert row[0] is not None
    assert row[0] > 0


def test_populate_game_context_rest_advantage(conn):
    # Home team (10) played yesterday, away team (8) played 3 days ago
    upsert_game_metadata(conn, 2024020001, "2024-10-07", 20242025, 10, 6)  # home prev
    upsert_game_metadata(conn, 2024020003, "2024-10-05", 20242025, 5, 8)   # away prev
    upsert_game_metadata(conn, 2024020002, "2024-10-08", 20242025, 10, 8)

    populate_game_context(conn, 2024020002)

    cur = conn.cursor()
    cur.execute("SELECT home_rest_days, away_rest_days, rest_advantage FROM game_context WHERE game_id = 2024020002")
    row = cur.fetchone()
    assert row[0] == 1  # home: 1 day rest
    assert row[1] == 3  # away: 3 days rest
    assert row[2] == -2  # home has 2 fewer rest days


# ── games table venue migration ─────────────────────────────────────


def test_migrate_games_add_venue_columns_idempotent(conn):
    _migrate_games_add_venue_columns(conn)  # already has them from DDL
    _migrate_games_add_venue_columns(conn)  # should not raise


def test_games_table_has_venue_columns(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(games)")
    cols = {row[1] for row in cur.fetchall()}
    assert "venue_name" in cols
    assert "venue_city" in cols
    assert "venue_utc_offset" in cols


# ── venue_bias_diagnostics table DDL ────────────────────────────────


def test_create_venue_bias_diagnostics_table(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='venue_bias_diagnostics'")
    assert cur.fetchone() is not None


def test_venue_bias_diagnostics_has_expected_columns(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(venue_bias_diagnostics)")
    cols = {row[1] for row in cur.fetchall()}
    expected = {
        "venue_name", "season", "total_shots", "avg_distance",
        "x_coord_mean", "x_coord_stddev", "y_coord_mean", "y_coord_stddev",
        "shot_count_z_score", "distance_z_score", "bias_flag",
    }
    assert expected.issubset(cols)


def test_create_venue_bias_corrections_table(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='venue_bias_corrections'")
    assert cur.fetchone() is not None


# ── _stddev ─────────────────────────────────────────────────────────


def test_stddev_uniform():
    assert _stddev([5, 5, 5], 5.0) == 0.0


def test_stddev_known():
    import math
    # values: [1, 2, 3], mean=2, variance = (1+0+1)/3 = 2/3
    result = _stddev([1, 2, 3], 2.0)
    assert abs(result - math.sqrt(2.0 / 3.0)) < 0.001


def test_stddev_empty():
    assert _stddev([], 0.0) == 0.0


def test_stddev_single():
    assert _stddev([5], 5.0) == 0.0


# ── compute_venue_season_stats ──────────────────────────────────────


def _insert_shot_for_venue(conn, game_id, event_idx, x, y, distance):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO shot_events
           (game_id, event_idx, period, time_in_period,
            time_remaining_seconds, shot_type, is_goal,
            shooting_team_id, x_coord, y_coord, distance_to_goal,
            event_schema_version)
           VALUES (?, ?, 1, '10:00', 600, 'wrist', 0, 10, ?, ?, ?, 'v2')""",
        (game_id, event_idx, x, y, distance),
    )
    conn.commit()


def test_compute_venue_season_stats_empty(conn):
    stats = compute_venue_season_stats(conn, "Test Arena", "20242025")
    assert stats["total_shots"] == 0
    assert stats["avg_distance"] is None


def test_compute_venue_season_stats_with_data(conn):
    upsert_game_metadata(
        conn, 1, "2024-10-08", "20242025", 10, 8,
        venue_name="Test Arena",
    )
    _insert_shot_for_venue(conn, 1, 1, 70.0, 10.0, 30.0)
    _insert_shot_for_venue(conn, 1, 2, 80.0, 5.0, 20.0)

    stats = compute_venue_season_stats(conn, "Test Arena", "20242025")
    assert stats["total_shots"] == 2
    assert abs(stats["avg_distance"] - 25.0) < 0.01
    assert abs(stats["x_coord_mean"] - 75.0) < 0.01


# ── compute_league_season_stats ─────────────────────────────────────


def test_compute_league_season_stats_empty(conn):
    stats = compute_league_season_stats(conn, "20242025")
    assert stats["total_shots"] == 0


def test_compute_league_season_stats_with_data(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    upsert_game_metadata(conn, 2, "2024-10-09", "20242025", 6, 5, venue_name="Arena B")
    _insert_shot_for_venue(conn, 1, 1, 70.0, 10.0, 30.0)
    _insert_shot_for_venue(conn, 1, 2, 80.0, 5.0, 20.0)
    _insert_shot_for_venue(conn, 2, 3, 75.0, -5.0, 25.0)

    stats = compute_league_season_stats(conn, "20242025")
    assert stats["total_shots"] == 3
    assert stats["venue_shot_count_mean"] is not None
    assert stats["venue_shot_count_stddev"] is not None


# ── populate_venue_diagnostics ──────────────────────────────────────


def test_populate_venue_diagnostics_empty(conn):
    populate_venue_diagnostics(conn, "20242025")  # should not raise
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM venue_bias_diagnostics")
    assert cur.fetchone()[0] == 0


def test_populate_venue_diagnostics_with_data(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    upsert_game_metadata(conn, 2, "2024-10-09", "20242025", 6, 5, venue_name="Arena B")
    _insert_shot_for_venue(conn, 1, 1, 70.0, 10.0, 30.0)
    _insert_shot_for_venue(conn, 1, 2, 80.0, 5.0, 20.0)
    _insert_shot_for_venue(conn, 2, 3, 75.0, -5.0, 25.0)

    populate_venue_diagnostics(conn, "20242025")

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM venue_bias_diagnostics")
    assert cur.fetchone()[0] == 2  # two venues


def test_populate_venue_diagnostics_idempotent(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    _insert_shot_for_venue(conn, 1, 1, 70.0, 10.0, 30.0)

    populate_venue_diagnostics(conn, "20242025")
    populate_venue_diagnostics(conn, "20242025")  # OR REPLACE, should not raise

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM venue_bias_diagnostics WHERE season = '20242025'")
    assert cur.fetchone()[0] == 1


def test_populate_venue_bias_corrections_skips_small_samples(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    _insert_shot_for_venue(conn, 1, 1, 70.0, 10.0, 30.0)
    populate_venue_diagnostics(conn, "20242025")

    inserted = populate_venue_bias_corrections(conn, "20242025")
    assert inserted == 0


def test_populate_venue_bias_corrections_inserts_rows(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    upsert_game_metadata(conn, 2, "2024-10-09", "20242025", 6, 5, venue_name="Arena B")
    for event_idx in range(1, 501):
        _insert_shot_for_venue(conn, 1, event_idx, 72.0, 3.0, 22.0)
    for event_idx in range(501, 1001):
        _insert_shot_for_venue(conn, 2, event_idx, 73.0, -2.0, 33.0)
    populate_venue_diagnostics(conn, "20242025")

    inserted = populate_venue_bias_corrections(conn, "20242025")
    assert inserted == 2
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM venue_bias_corrections "
        "WHERE season = ?",
        ("20242025",),
    )
    assert cur.fetchone()[0] == 2


def test_populate_venue_bias_corrections_replaces_stale_rows(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    upsert_game_metadata(conn, 2, "2024-10-09", "20242025", 6, 5, venue_name="Arena B")
    for event_idx in range(1, 501):
        _insert_shot_for_venue(conn, 1, event_idx, 72.0, 3.0, 22.0)
    for event_idx in range(501, 1001):
        _insert_shot_for_venue(conn, 2, event_idx, 73.0, -2.0, 33.0)
    populate_venue_diagnostics(conn, "20242025")
    inserted = populate_venue_bias_corrections(conn, "20242025")
    assert inserted == 2

    cur = conn.cursor()
    cur.execute("DELETE FROM venue_bias_diagnostics WHERE venue_name = ?", ("Arena B",))
    conn.commit()

    inserted = populate_venue_bias_corrections(conn, "20242025")
    assert inserted == 1
    cur.execute(
        "SELECT COUNT(*) FROM venue_bias_corrections WHERE season = ?",
        ("20242025",),
    )
    assert cur.fetchone()[0] == 1


def test_populate_venue_bias_corrections_autofills_missing_diagnostics(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    upsert_game_metadata(conn, 2, "2024-10-09", "20242025", 6, 5, venue_name="Arena B")
    for event_idx in range(1, 501):
        _insert_shot_for_venue(conn, 1, event_idx, 72.0, 3.0, 22.0)
    for event_idx in range(501, 1001):
        _insert_shot_for_venue(conn, 2, event_idx, 73.0, -2.0, 33.0)

    inserted = populate_venue_bias_corrections(conn, "20242025")
    assert inserted == 2


def test_load_game_shots_with_venue_correction_adds_corrected_distance(conn):
    upsert_game_metadata(conn, 1, "2024-10-08", "20242025", 10, 8, venue_name="Arena A")
    upsert_game_metadata(conn, 2, "2024-10-09", "20242025", 6, 5, venue_name="Arena B")
    for event_idx in range(1, 501):
        _insert_shot_for_venue(conn, 1, event_idx, 72.0, 3.0, 22.0)
    for event_idx in range(501, 1001):
        _insert_shot_for_venue(conn, 2, event_idx, 73.0, -2.0, 33.0)
    populate_venue_diagnostics(conn, "20242025")
    populate_venue_bias_corrections(conn, "20242025")

    rows = load_game_shots_with_venue_correction(conn, 1)
    assert rows
    assert "distance_to_goal_corrected" in rows[0]
    assert rows[0]["distance_to_goal_corrected"] != rows[0]["distance_to_goal"]


# ── ensure_xg_schema integration ────────────────────────────────────


def test_ensure_xg_schema_creates_all_phase2_tables():
    connection = sqlite3.connect(":memory:")
    create_core_dimension_tables(connection)
    ensure_xg_schema(connection)

    cur = connection.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cur.fetchall()}
    assert "game_context" in tables
    assert "venue_bias_diagnostics" in tables
    connection.close()


# ── validate_game_context_quality ───────────────────────────────────


def test_validate_game_context_quality_empty(conn):
    result = validate_game_context_quality(conn)
    assert result["total_rows"] == 0
    assert result["orphan_game_rows"] == 0
    for key in result:
        if key.startswith("null_"):
            assert result[key] == 0


def _seed_two_game_series(conn):
    upsert_team(conn, 10, "TOR", "Toronto")
    upsert_team(conn, 8, "MTL", "Montreal")
    upsert_team(conn, 20, "NYR", "New York Rangers")
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    upsert_game_metadata(conn, 2024020050, "2024-10-15", 20242025, 10, 20)
    populate_game_context(conn, 2024020001)
    populate_game_context(conn, 2024020050)


def test_validate_game_context_quality_flags_first_game_as_structural(conn):
    _seed_two_game_series(conn)
    result = validate_game_context_quality(conn)
    assert result["total_rows"] == 2
    assert result["orphan_game_rows"] == 0
    # Game 1 (TOR vs MTL): both teams first-ever game → both rest cols null.
    # Game 2 (TOR vs NYR): TOR has prior history, NYR first game → away rest null.
    # Both rows are structural because at least one rest column is null by design.
    assert result["structural_null_rest_rows"] == 2
    assert result["null_home_rest_days_rows"] >= 1
    assert result["null_away_rest_days_rows"] >= 2


def test_validate_game_context_quality_counts_partial_structural_null(conn):
    """Row with one team having history and one team debuting must count
    as structural — the predicate must not require *both* teams to lack
    prior games."""
    upsert_team(conn, 10, "TOR", "Toronto")
    upsert_team(conn, 8, "MTL", "Montreal")
    upsert_team(conn, 20, "NYR", "New York Rangers")
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 8)
    upsert_game_metadata(conn, 2024020099, "2024-10-20", 20242025, 8, 20)
    populate_game_context(conn, 2024020001)
    populate_game_context(conn, 2024020099)

    result = validate_game_context_quality(conn)
    assert result["total_rows"] == 2
    assert result["structural_null_rest_rows"] == 2
    assert result["null_home_rest_days_rows"] == 1
    assert result["null_away_rest_days_rows"] == 2


def test_validate_game_context_quality_detects_orphans(conn):
    _seed_two_game_series(conn)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO game_context
           (game_id, home_rest_days, away_rest_days, rest_advantage,
            home_is_back_to_back, away_is_back_to_back,
            travel_distance_km, timezone_delta, context_schema_version)
           VALUES (9999999999, 2, 1, 1, 0, 0, 500.0, 0.0, ?)""",
        (_GAME_CONTEXT_SCHEMA_VERSION,),
    )
    conn.commit()
    result = validate_game_context_quality(conn)
    assert result["orphan_game_rows"] == 1


def test_validate_game_context_quality_counts_travel_nulls(conn):
    upsert_team(conn, 10, "TOR", "Toronto")
    upsert_team(conn, 99, "ZZZ", "No Arena Team")
    upsert_game_metadata(conn, 2024020001, "2024-10-08", 20242025, 10, 99)
    populate_game_context(conn, 2024020001)
    result = validate_game_context_quality(conn)
    assert result["null_travel_distance_km_rows"] == 1
    assert result["null_timezone_delta_rows"] == 1
