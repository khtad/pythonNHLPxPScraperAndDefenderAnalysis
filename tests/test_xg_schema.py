import sqlite3

import pytest

from database import (
    _XG_EVENT_SCHEMA_VERSION,
    _XG_FEATURE_SCHEMA_VERSION,
    VALID_SHOT_TYPES,
    VALID_MANPOWER_STATES,
    VALID_SCORE_STATES,
    NORMALIZED_X_COORD_MIN,
    NORMALIZED_X_COORD_MAX,
    NORMALIZED_Y_COORD_MIN,
    NORMALIZED_Y_COORD_MAX,
    create_shot_events_table,
    create_core_dimension_tables,
    validate_shot_events_quality,
    ensure_xg_schema,
    insert_shot_events,
    game_has_shot_events,
    game_has_current_shot_events,
    delete_game_shot_events,
    _migrate_shot_events_v1_to_v2,
    _migrate_shot_events_v4_to_v5,
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    create_core_dimension_tables(connection)
    yield connection
    connection.close()


# ── Phase 0: schema version constants ────────────────────────────────


def test_xg_event_schema_version_is_string():
    assert isinstance(_XG_EVENT_SCHEMA_VERSION, str)
    assert len(_XG_EVENT_SCHEMA_VERSION) > 0


def test_xg_feature_schema_version_is_string():
    assert isinstance(_XG_FEATURE_SCHEMA_VERSION, str)
    assert len(_XG_FEATURE_SCHEMA_VERSION) > 0


# ── Phase 0: data-contract constants ─────────────────────────────────


def test_valid_shot_types_is_nonempty_tuple_of_strings():
    assert isinstance(VALID_SHOT_TYPES, tuple)
    assert len(VALID_SHOT_TYPES) > 0
    assert all(isinstance(s, str) for s in VALID_SHOT_TYPES)


def test_valid_manpower_states_contains_common_states():
    required = {"5v5", "5v4", "4v5", "5v3", "3v5", "4v4"}
    assert required.issubset(set(VALID_MANPOWER_STATES))


def test_valid_score_states_contains_common_states():
    required = {"tied", "up1", "up2", "up3plus", "down1", "down2", "down3plus"}
    assert required.issubset(set(VALID_SCORE_STATES))


def test_coordinate_range_constants_are_numeric():
    assert NORMALIZED_X_COORD_MIN < NORMALIZED_X_COORD_MAX
    assert NORMALIZED_Y_COORD_MIN < NORMALIZED_Y_COORD_MAX


# ── Phase 0: shot_events table DDL ───────────────────────────────────


def test_create_shot_events_table_creates_table(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='shot_events'"
    )
    assert cur.fetchone() is not None


def test_create_shot_events_table_is_idempotent(conn):
    create_shot_events_table(conn)
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='shot_events'"
    )
    assert cur.fetchone()[0] == 1


def test_shot_events_table_has_expected_columns(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(shot_events)")
    cols = {row[1] for row in cur.fetchall()}
    expected = {
        "shot_event_id",
        "game_id",
        "event_idx",
        "shot_event_type",
        "period",
        "time_in_period",
        "time_remaining_seconds",
        "shot_type",
        "x_coord",
        "y_coord",
        "distance_to_goal",
        "angle_to_goal",
        "is_goal",
        "shooting_team_id",
        "goalie_id",
        "shooter_id",
        "score_state",
        "manpower_state",
        "event_schema_version",
    }
    assert expected.issubset(cols)


def test_shot_events_table_unique_on_game_id_event_idx(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO shot_events (
            game_id, event_idx, period, time_in_period,
            time_remaining_seconds, shot_type, is_goal,
            shooting_team_id, event_schema_version
        ) VALUES (2023020001, 42, 1, '10:00', 600, 'wrist', 0, 10, ?)
        """,
        (_XG_EVENT_SCHEMA_VERSION,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute(
            """
            INSERT INTO shot_events (
                game_id, event_idx, period, time_in_period,
                time_remaining_seconds, shot_type, is_goal,
                shooting_team_id, event_schema_version
            ) VALUES (2023020001, 42, 1, '10:00', 600, 'slap', 1, 10, ?)
            """,
            (_XG_EVENT_SCHEMA_VERSION,),
        )


def test_shot_events_table_has_game_id_index(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute("PRAGMA index_list(shot_events)")
    index_names = {row[1] for row in cur.fetchall()}
    assert "idx_shot_events_game_id" in index_names


# ── Phase 0: validate_shot_events_quality ─────────────────────────────


def _insert_shot(cur, overrides=None, version=None):
    """Insert a valid baseline shot event, with optional column overrides."""
    defaults = {
        "game_id": 2023020001,
        "event_idx": 1,
        "shot_event_type": "shot-on-goal",
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "x_coord": 70.0,
        "y_coord": 10.0,
        "distance_to_goal": 30.0,
        "angle_to_goal": 18.4,
        "is_goal": 0,
        "shooting_team_id": 10,
        "goalie_id": 8471111,
        "shooter_id": 8478402,
        "score_state": "tied",
        "manpower_state": "5v5",
        "event_schema_version": version or _XG_EVENT_SCHEMA_VERSION,
    }
    if overrides:
        defaults.update(overrides)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join(["?"] * len(defaults))
    cur.execute(
        f"INSERT INTO shot_events ({cols}) VALUES ({placeholders})",
        tuple(defaults.values()),
    )


def test_validate_shot_events_quality_clean_data_returns_no_errors(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"event_idx": 1})
    _insert_shot(cur, {"event_idx": 2, "game_id": 2023020002})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["invalid_shot_event_type_rows"] == 0
    assert report["invalid_shot_type_rows"] == 0
    assert report["invalid_manpower_state_rows"] == 0
    assert report["invalid_score_state_rows"] == 0
    assert report["x_coord_out_of_range_rows"] == 0
    assert report["y_coord_out_of_range_rows"] == 0
    assert report["invalid_is_goal_rows"] == 0
    assert report["negative_time_remaining_rows"] == 0
    assert report["duplicate_game_event_rows"] == 0


def test_validate_shot_events_quality_detects_invalid_shot_type(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"shot_type": "INVALID_TYPE"})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["invalid_shot_type_rows"] == 1


def test_validate_shot_events_quality_detects_invalid_manpower_state(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"manpower_state": "6v6"})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["invalid_manpower_state_rows"] == 1


def test_validate_shot_events_quality_detects_invalid_score_state(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"score_state": "winning_big"})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["invalid_score_state_rows"] == 1


def test_validate_shot_events_quality_detects_x_coord_out_of_range(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"event_idx": 1, "x_coord": -110.0})
    _insert_shot(
        cur, {"event_idx": 2, "game_id": 2023020002, "x_coord": 110.0}
    )
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["x_coord_out_of_range_rows"] == 2


def test_validate_shot_events_quality_detects_y_coord_out_of_range(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"y_coord": -50.0})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["y_coord_out_of_range_rows"] == 1


def test_validate_shot_events_quality_detects_invalid_is_goal(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"is_goal": 2})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["invalid_is_goal_rows"] == 1


def test_validate_shot_events_quality_detects_negative_time_remaining(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"time_remaining_seconds": -1})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["negative_time_remaining_rows"] == 1


def test_validate_shot_events_quality_null_coords_are_not_flagged(conn):
    """NULL coordinates are allowed (some events may lack tracking data)."""
    create_shot_events_table(conn)
    cur = conn.cursor()
    _insert_shot(cur, {"x_coord": None, "y_coord": None})
    conn.commit()

    report = validate_shot_events_quality(conn)
    assert report["x_coord_out_of_range_rows"] == 0
    assert report["y_coord_out_of_range_rows"] == 0


# ── Phase 0: ensure_xg_schema orchestrator ────────────────────────────


def test_ensure_xg_schema_creates_shot_events_table(conn):
    ensure_xg_schema(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='shot_events'"
    )
    assert cur.fetchone() is not None


def test_ensure_xg_schema_is_idempotent(conn):
    ensure_xg_schema(conn)
    ensure_xg_schema(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='shot_events'"
    )
    assert cur.fetchone()[0] == 1


# ── Phase 1: new columns ──────────────────────────────────────────────


def test_shot_events_table_has_faceoff_columns(conn):
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(shot_events)")
    cols = {row[1] for row in cur.fetchall()}
    assert "seconds_since_faceoff" in cols
    assert "faceoff_zone_code" in cols


def test_valid_manpower_states_contains_pulled_goalie_states():
    required = {"6v5", "5v6", "6v4", "4v6", "6v3", "3v6"}
    assert required.issubset(set(VALID_MANPOWER_STATES))


def test_xg_event_schema_version_is_v5():
    assert _XG_EVENT_SCHEMA_VERSION == "v5"


# ── Phase 1: migration ────────────────────────────────────────────────


def test_migrate_shot_events_v1_to_v2_adds_columns(conn):
    """Migration adds new columns to a v1 table that lacks them."""
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE shot_events (
            shot_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            event_idx INTEGER NOT NULL,
            period INTEGER NOT NULL,
            time_in_period TEXT NOT NULL,
            time_remaining_seconds INTEGER NOT NULL,
            shot_type TEXT NOT NULL,
            x_coord REAL,
            y_coord REAL,
            distance_to_goal REAL,
            angle_to_goal REAL,
            is_goal INTEGER NOT NULL DEFAULT 0,
            shooting_team_id INTEGER NOT NULL,
            goalie_id INTEGER,
            shooter_id INTEGER,
            score_state TEXT,
            manpower_state TEXT,
            event_schema_version TEXT NOT NULL DEFAULT 'v1',
            UNIQUE(game_id, event_idx)
        )
    """)
    conn.commit()

    _migrate_shot_events_v1_to_v2(conn)

    cur.execute("PRAGMA table_info(shot_events)")
    cols = {row[1] for row in cur.fetchall()}
    assert "seconds_since_faceoff" in cols
    assert "faceoff_zone_code" in cols


def test_migrate_shot_events_v1_to_v2_is_idempotent(conn):
    """Running migration twice does not raise."""
    create_shot_events_table(conn)
    _migrate_shot_events_v1_to_v2(conn)
    _migrate_shot_events_v1_to_v2(conn)


def test_migrate_shot_events_v4_to_v5_reconstructs_event_types(conn):
    """v4 rows can be promoted when raw non-blocked events match in order."""
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE game_2023020001 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period INTEGER,
            time TEXT,
            event TEXT,
            description TEXT
        )
    """)
    cur.executemany(
        """INSERT INTO game_2023020001 (period, time, event, description)
           VALUES (?, ?, ?, ?)""",
        [
            (1, "00:10", "shot-on-goal", "shot-on-goal"),
            (1, "00:15", "blocked-shot", "blocked-shot"),
            (1, "00:30", "missed-shot", "missed-shot"),
            (1, "00:35", "goal", "goal"),
        ],
    )
    for event_idx, time_remaining in [(10, 1190), (30, 1170), (35, 1165)]:
        _insert_shot(
            cur,
            {
                "game_id": 2023020001,
                "event_idx": event_idx,
                "time_remaining_seconds": time_remaining,
                "shot_event_type": None,
            },
            version="v4",
        )
    conn.commit()

    _migrate_shot_events_v4_to_v5(conn)

    cur.execute(
        """SELECT shot_event_type, event_schema_version
           FROM shot_events
           ORDER BY event_idx"""
    )
    assert cur.fetchall() == [
        ("shot-on-goal", _XG_EVENT_SCHEMA_VERSION),
        ("missed-shot", _XG_EVENT_SCHEMA_VERSION),
        ("goal", _XG_EVENT_SCHEMA_VERSION),
    ]


def test_migrate_shot_events_v4_to_v5_leaves_mismatched_games_stale(conn):
    """Mismatched raw and derived sequences stay stale for API backfill."""
    create_shot_events_table(conn)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE game_2023020002 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period INTEGER,
            time TEXT,
            event TEXT,
            description TEXT
        )
    """)
    cur.execute(
        """INSERT INTO game_2023020002 (period, time, event, description)
           VALUES (1, '00:10', 'shot-on-goal', 'shot-on-goal')"""
    )
    _insert_shot(
        cur,
        {
            "game_id": 2023020002,
            "event_idx": 10,
            "time_remaining_seconds": 1190,
            "shot_event_type": None,
        },
        version="v4",
    )
    _insert_shot(
        cur,
        {
            "game_id": 2023020002,
            "event_idx": 20,
            "time_remaining_seconds": 1180,
            "shot_event_type": None,
        },
        version="v4",
    )
    conn.commit()

    _migrate_shot_events_v4_to_v5(conn)

    cur.execute(
        """SELECT shot_event_type, event_schema_version
           FROM shot_events
           ORDER BY event_idx"""
    )
    assert cur.fetchall() == [(None, "v4"), (None, "v4")]


# ── Phase 1: insert_shot_events ───────────────────────────────────────


def test_insert_shot_events_inserts_rows(conn):
    ensure_xg_schema(conn)
    events = [
        {
            "game_id": 2023020001,
            "event_idx": 1,
            "period": 1,
            "time_in_period": "10:00",
            "time_remaining_seconds": 600,
            "shot_type": "wrist",
            "x_coord": 70.0,
            "y_coord": 10.0,
            "distance_to_goal": 30.0,
            "angle_to_goal": 18.4,
            "is_goal": 0,
            "shooting_team_id": 10,
            "goalie_id": 8471111,
            "shooter_id": 8478402,
            "score_state": "tied",
            "manpower_state": "5v5",
            "seconds_since_faceoff": 30,
            "faceoff_zone_code": "N",
        },
    ]
    insert_shot_events(conn, events)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shot_events")
    assert cur.fetchone()[0] == 1


def test_insert_shot_events_auto_populates_schema_version(conn):
    ensure_xg_schema(conn)
    events = [
        {
            "game_id": 2023020001,
            "event_idx": 1,
            "period": 1,
            "time_in_period": "10:00",
            "time_remaining_seconds": 600,
            "shot_type": "wrist",
            "is_goal": 0,
            "shooting_team_id": 10,
        },
    ]
    insert_shot_events(conn, events)
    cur = conn.cursor()
    cur.execute("SELECT event_schema_version FROM shot_events")
    assert cur.fetchone()[0] == _XG_EVENT_SCHEMA_VERSION


def test_insert_shot_events_rejects_invalid_keys(conn):
    ensure_xg_schema(conn)
    events = [{"game_id": 1, "bad_key": "value"}]
    with pytest.raises(ValueError, match="Invalid shot event keys"):
        insert_shot_events(conn, events)


def test_insert_shot_events_ignores_duplicates(conn):
    ensure_xg_schema(conn)
    event = {
        "game_id": 2023020001,
        "event_idx": 1,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "is_goal": 0,
        "shooting_team_id": 10,
    }
    insert_shot_events(conn, [event])
    insert_shot_events(conn, [event])
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shot_events")
    assert cur.fetchone()[0] == 1


def test_insert_shot_events_empty_list(conn):
    ensure_xg_schema(conn)
    insert_shot_events(conn, [])  # should not raise


# ── Phase 1: game_has_shot_events ─────────────────────────────────────


def test_game_has_shot_events_false_when_empty(conn):
    ensure_xg_schema(conn)
    assert game_has_shot_events(conn, 2023020001) is False


def test_game_has_shot_events_true_when_present(conn):
    ensure_xg_schema(conn)
    event = {
        "game_id": 2023020001,
        "event_idx": 1,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "is_goal": 0,
        "shooting_team_id": 10,
    }
    insert_shot_events(conn, [event])
    assert game_has_shot_events(conn, 2023020001) is True
    assert game_has_shot_events(conn, 9999999) is False


# ── Phase 1: game_has_current_shot_events ─────────────────────────────


def test_game_has_current_shot_events_true_for_current_version(conn):
    ensure_xg_schema(conn)
    event = {
        "game_id": 2023020001,
        "event_idx": 1,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "is_goal": 0,
        "shooting_team_id": 10,
    }
    insert_shot_events(conn, [event])
    assert game_has_current_shot_events(conn, 2023020001) is True


def test_game_has_current_shot_events_false_for_stale_version(conn):
    ensure_xg_schema(conn)
    event = {
        "game_id": 2023020001,
        "event_idx": 1,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "is_goal": 0,
        "shooting_team_id": 10,
    }
    insert_shot_events(conn, [event])
    # Manually downgrade the version to simulate stale data
    conn.execute(
        "UPDATE shot_events SET event_schema_version = 'v1' WHERE game_id = ?",
        (2023020001,),
    )
    conn.commit()
    assert game_has_current_shot_events(conn, 2023020001) is False
    # But game_has_shot_events still returns True (rows exist)
    assert game_has_shot_events(conn, 2023020001) is True


def test_game_has_current_shot_events_false_when_empty(conn):
    ensure_xg_schema(conn)
    assert game_has_current_shot_events(conn, 2023020001) is False


# ── Phase 1: delete_game_shot_events ──────────────────────────────────


def test_delete_game_shot_events_removes_rows(conn):
    ensure_xg_schema(conn)
    events = [
        {
            "game_id": 2023020001,
            "event_idx": i,
            "period": 1,
            "time_in_period": "10:00",
            "time_remaining_seconds": 600,
            "shot_type": "wrist",
            "is_goal": 0,
            "shooting_team_id": 10,
        }
        for i in range(3)
    ]
    insert_shot_events(conn, events)
    assert game_has_shot_events(conn, 2023020001) is True

    delete_game_shot_events(conn, 2023020001)
    assert game_has_shot_events(conn, 2023020001) is False


def test_delete_game_shot_events_only_deletes_target_game(conn):
    ensure_xg_schema(conn)
    event_a = {
        "game_id": 2023020001,
        "event_idx": 1,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "is_goal": 0,
        "shooting_team_id": 10,
    }
    event_b = {
        "game_id": 2023020002,
        "event_idx": 1,
        "period": 1,
        "time_in_period": "10:00",
        "time_remaining_seconds": 600,
        "shot_type": "wrist",
        "is_goal": 0,
        "shooting_team_id": 10,
    }
    insert_shot_events(conn, [event_a, event_b])

    delete_game_shot_events(conn, 2023020001)
    assert game_has_shot_events(conn, 2023020001) is False
    assert game_has_shot_events(conn, 2023020002) is True
