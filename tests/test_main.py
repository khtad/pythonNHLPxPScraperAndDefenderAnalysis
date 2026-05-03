import datetime
import sqlite3
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

import main
from database import (
    create_connection, create_collection_log_table,
    mark_date_collected, ensure_xg_schema,
    ensure_player_database_schema,
    create_table, insert_data,
)


class _UnclosableConn:
    """Wrapper that delegates everything to a real connection but ignores close()."""

    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _in_memory_conn():
    conn = _UnclosableConn(sqlite3.connect(":memory:"))
    create_collection_log_table(conn)
    ensure_player_database_schema(conn)
    ensure_xg_schema(conn)
    return conn


@pytest.fixture(autouse=True)
def _disable_shift_population(monkeypatch):
    monkeypatch.setattr(
        main,
        "populate_shift_data_for_game",
        lambda connection, game_id: SimpleNamespace(games_populated=0),
    )


def _simple_full_pbp(game_id, home_id=10, away_id=20):
    """Minimal full play-by-play JSON with one faceoff and one shot."""
    return {
        "id": game_id,
        "homeTeam": {"id": home_id},
        "awayTeam": {"id": away_id},
        "plays": [
            {
                "eventId": 1,
                "typeDescKey": "faceoff",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "00:00",
                "timeRemaining": "20:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {"zoneCode": "N"},
            },
            {
                "eventId": 2,
                "typeDescKey": "shot-on-goal",
                "periodDescriptor": {"number": 1},
                "timeInPeriod": "01:00",
                "timeRemaining": "19:00",
                "situationCode": "1551",
                "homeTeamDefendingSide": "left",
                "details": {
                    "xCoord": 70,
                    "yCoord": 10,
                    "shotType": "wrist",
                    "shootingPlayerId": 100,
                    "goalieInNetId": 200,
                    "eventOwnerTeamId": home_id,
                },
            },
        ],
    }


def _patch_datetime(end_date):
    """Return a mock datetime module that delegates real operations to datetime."""
    mock_dt = MagicMock()
    mock_dt.date.today.return_value = end_date
    mock_dt.date.side_effect = lambda *args, **kw: datetime.date(*args, **kw)
    mock_dt.date.fromisoformat = datetime.date.fromisoformat
    mock_dt.timedelta = datetime.timedelta
    return mock_dt


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_uses_weekly_schedule_instead_of_daily(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """main() should call get_weekly_schedule, not get_game_ids_for_date."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {"2007-10-03": [2007020001]},
        None,
    )
    mock_full_pbp.return_value = _simple_full_pbp(2007020001)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    mock_weekly.assert_called()
    mock_full_pbp.assert_called_once_with(2007020001)


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_advances_by_next_start_date(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """main() should paginate using nextStartDate from the API."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.side_effect = [
        ({"2007-10-03": [1], "2007-10-04": [2]}, "2007-10-08"),
        ({"2007-10-08": [3]}, None),
    ]
    mock_full_pbp.return_value = _simple_full_pbp(1)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 10))):
        main.main()

    assert mock_weekly.call_count == 2
    assert mock_full_pbp.call_count == 3


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_skips_dates_outside_range(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """Dates in gameWeek that fall outside start_date..end_date should be skipped."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-03": [1],
            "2007-10-04": [2],
            "2007-10-05": [3],  # past end_date
        },
        None,
    )
    mock_full_pbp.return_value = _simple_full_pbp(1)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 4))):
        main.main()

    assert mock_full_pbp.call_count == 2


@patch("main.mark_date_collected")
@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_marks_each_date_collected(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp, mock_mark,
):
    """Each date in the week should get its own collection log entry."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-03": [1, 2],
            "2007-10-04": [3],
        },
        None,
    )
    mock_full_pbp.return_value = _simple_full_pbp(1)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    marked_dates = [call_args[0][1] for call_args in mock_mark.call_args_list]
    assert "2007-10-03" in marked_dates
    assert "2007-10-04" in marked_dates
    assert len(marked_dates) == 2


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_stops_when_next_start_date_is_none(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """When the API returns no nextStartDate, the loop should end."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = ({"2007-10-03": []}, None)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 10))):
        main.main()

    assert mock_weekly.call_count == 1
    mock_full_pbp.assert_not_called()


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_resumes_from_last_collected_date(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """When resuming, the first weekly schedule call should start after the last collected date."""
    conn = _in_memory_conn()
    mark_date_collected(conn, "2007-10-03", 2, 2)
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-04": [10],
            "2007-10-05": [11],
        },
        None,
    )
    mock_full_pbp.return_value = _simple_full_pbp(1)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 6))):
        main.main()

    called_date = mock_weekly.call_args[0][0]
    assert str(called_date) == "2007-10-04"


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_resumes_from_incomplete_date(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """When an incomplete date exists, main() should resume from that date."""
    conn = _in_memory_conn()
    mark_date_collected(conn, "2007-10-03", 2, 2)  # complete
    mark_date_collected(conn, "2007-10-04", 2, 1)  # incomplete
    mark_date_collected(conn, "2007-10-05", 1, 1)  # complete
    mock_conn.return_value = conn

    mock_weekly.return_value = (
        {
            "2007-10-04": [20, 21],
            "2007-10-05": [22],
        },
        None,
    )
    mock_full_pbp.return_value = _simple_full_pbp(1)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 6))):
        main.main()

    called_date = mock_weekly.call_args[0][0]
    assert str(called_date) == "2007-10-04"


# ── Phase 1: shot event extraction integration ────────────────────────


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_extracts_and_inserts_shot_events(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """main() should extract shot events from full play-by-play data."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = ({"2007-10-03": [2007020001]}, None)
    mock_full_pbp.return_value = _simple_full_pbp(2007020001)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shot_events")
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT game_id, shot_type, is_goal FROM shot_events")
    row = cur.fetchone()
    assert row[0] == 2007020001
    assert row[1] == "wrist"
    assert row[2] == 0


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_counts_null_api_response_as_collected(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """Games where get_full_play_by_play returns None should still count
    toward games_collected so the date is marked complete."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = ({"2007-10-03": [1, 2]}, None)
    mock_full_pbp.return_value = None  # API returns nothing for both games

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    cur = conn.cursor()
    cur.execute(
        "SELECT games_found, games_collected, completed_at IS NOT NULL "
        "FROM collection_log WHERE date = '2007-10-03'"
    )
    row = cur.fetchone()
    assert row[0] == 2, "games_found should be 2"
    assert row[1] == 2, "games_collected should count null responses"
    assert row[2] == 1, "date should be marked complete"


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_skips_shot_extraction_when_already_processed(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """Shot events should not be re-inserted on a second run."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    mock_weekly.return_value = ({"2007-10-03": [2007020001]}, None)
    mock_full_pbp.return_value = _simple_full_pbp(2007020001)

    # First run inserts shot events
    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    # Second run — game is already collected, so get_full_play_by_play won't be called
    mock_full_pbp.reset_mock()
    mock_weekly.return_value = ({"2007-10-03": [2007020001]}, None)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    mock_full_pbp.assert_not_called()

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shot_events")
    assert cur.fetchone()[0] == 1


@patch("main.get_full_play_by_play")
@patch("main.get_weekly_schedule")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_main_backfills_shot_events_for_existing_raw_game(
    mock_conn, mock_dedup, mock_weekly, mock_full_pbp,
):
    """Existing raw tables should not prevent shot-event backfill."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    game_id = 2007020001
    create_table(conn, game_id)
    insert_data(conn, game_id, [{
        "period": 1,
        "time": "01:00",
        "event": "shot-on-goal",
        "description": "shot-on-goal",
    }])

    mock_weekly.return_value = ({"2007-10-03": [game_id]}, None)
    mock_full_pbp.return_value = _simple_full_pbp(game_id)

    with patch("main.datetime", _patch_datetime(datetime.date(2007, 10, 5))):
        main.main()

    mock_full_pbp.assert_called_once_with(game_id)


@patch("main.get_full_play_by_play")
def test_process_game_populates_shift_data_after_shot_events(mock_full_pbp, monkeypatch):
    conn = _in_memory_conn()
    game_id = 2007020001
    shift_calls = []

    def fake_shift_population(connection, shifted_game_id):
        assert connection is conn
        shift_calls.append(shifted_game_id)
        return SimpleNamespace(games_populated=0)

    mock_full_pbp.return_value = _simple_full_pbp(game_id)
    monkeypatch.setattr(main, "populate_shift_data_for_game", fake_shift_population)

    assert main._process_game(conn, game_id)

    assert shift_calls == [game_id]

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shot_events WHERE game_id = ?", (game_id,))
    assert cur.fetchone()[0] == 1


@patch("main.get_full_play_by_play")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_backfill_missing_game_data_processes_existing_raw_games(
    mock_conn, mock_dedup, mock_full_pbp,
):
    """Explicit backfill should repair old databases with raw-only games."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    game_id = 2007020001
    create_table(conn, game_id)
    insert_data(conn, game_id, [{
        "period": 1,
        "time": "01:00",
        "event": "shot-on-goal",
        "description": "shot-on-goal",
    }])

    mock_full_pbp.return_value = _simple_full_pbp(game_id)

    processed_games = main.backfill_missing_game_data(limit=1)

    assert processed_games == 1
    mock_full_pbp.assert_called_once_with(game_id)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shot_events WHERE game_id = ?", (game_id,))
    assert cur.fetchone()[0] == 1


@patch("main.get_full_play_by_play")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_backfill_missing_game_data_is_idempotent(
    mock_conn, mock_dedup, mock_full_pbp,
):
    """A second backfill run should do no work for already-repaired games."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    game_id = 2007020001
    create_table(conn, game_id)
    insert_data(conn, game_id, [{
        "period": 1,
        "time": "01:00",
        "event": "shot-on-goal",
        "description": "shot-on-goal",
    }])

    mock_full_pbp.return_value = _simple_full_pbp(game_id)

    first_processed_games = main.backfill_missing_game_data(limit=1)
    second_processed_games = main.backfill_missing_game_data(limit=1)

    assert first_processed_games == 1
    assert second_processed_games == 0
    mock_full_pbp.assert_called_once_with(game_id)

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shot_events WHERE game_id = ?", (game_id,))
    assert cur.fetchone()[0] == 1

    cur.execute("SELECT COUNT(*) FROM games WHERE game_id = ?", (game_id,))
    assert cur.fetchone()[0] == 1


@patch("main.get_full_play_by_play")
@patch("main.deduplicate_existing_tables")
@patch("main.create_connection")
def test_backfill_missing_game_data_skips_fully_processed_games(
    mock_conn, mock_dedup, mock_full_pbp,
):
    """Explicit backfill should not refetch games that already have derived rows."""
    conn = _in_memory_conn()
    mock_conn.return_value = conn

    game_id = 2007020001
    create_table(conn, game_id)
    insert_data(conn, game_id, [{
        "period": 1,
        "time": "01:00",
        "event": "shot-on-goal",
        "description": "shot-on-goal",
    }])

    mock_full_pbp.return_value = _simple_full_pbp(game_id)
    assert main.backfill_missing_game_data(limit=1) == 1

    mock_full_pbp.reset_mock()

    processed_games = main.backfill_missing_game_data(limit=1)

    assert processed_games == 0
    mock_full_pbp.assert_not_called()


@patch("main.populate_player_game_features")
@patch("main.populate_player_game_stats")
@patch("main.backfill_player_metadata")
def test_refresh_player_tables_runs_stats_then_features(
    mock_backfill_metadata, mock_populate_stats, mock_populate_features,
):
    conn = _in_memory_conn()
    call_order = []

    def fake_backfill(connection, fetch_fn):
        assert connection is conn
        assert fetch_fn is main.get_player_metadata
        call_order.append("metadata")
        return 3, 2, 1

    def fake_populate_stats(connection):
        assert connection is conn
        call_order.append("stats")
        return 10

    def fake_populate_features(connection):
        assert connection is conn
        call_order.append("features")
        return 10

    mock_backfill_metadata.side_effect = fake_backfill
    mock_populate_stats.side_effect = fake_populate_stats
    mock_populate_features.side_effect = fake_populate_features

    result = main.refresh_player_tables(conn)

    assert call_order == ["metadata", "stats", "features"]
    assert result == {
        "metadata_attempted": 3,
        "metadata_upserted": 2,
        "metadata_unavailable": 1,
        "player_game_stats_rows": 10,
        "player_game_features_rows": 10,
    }


@patch("main.backfill_missing_game_data")
@patch("main.main")
def test_run_scraper_and_backfill_calls_main_then_backfill(
    mock_main_fn, mock_backfill,
):
    """The public wrapper should update the database, then backfill it."""
    mock_backfill.return_value = 123

    processed_games = main.run_scraper_and_backfill(backfill_limit=7)

    mock_main_fn.assert_called_once_with()
    mock_backfill.assert_called_once_with(limit=7)
    assert processed_games == 123


def test_finalize_season_diagnostics_runs_per_season():
    from database import upsert_team, upsert_game_metadata
    conn = _in_memory_conn()
    upsert_team(conn, 10, "TOR", "Toronto")
    upsert_team(conn, 20, "MTL", "Montreal")
    upsert_game_metadata(
        conn, 2024020001, "2024-10-08", "20242025", 10, 20,
        venue_name="Scotiabank Arena",
    )
    upsert_game_metadata(
        conn, 2023020999, "2023-10-10", "20232024", 10, 20,
        venue_name="Scotiabank Arena",
    )

    populated_seasons = main.finalize_season_diagnostics(conn)
    assert populated_seasons == 2


def test_finalize_season_diagnostics_idempotent():
    from database import upsert_team, upsert_game_metadata
    conn = _in_memory_conn()
    upsert_team(conn, 10, "TOR", "Toronto")
    upsert_team(conn, 20, "MTL", "Montreal")
    upsert_game_metadata(
        conn, 2024020001, "2024-10-08", "20242025", 10, 20,
        venue_name="Scotiabank Arena",
    )

    main.finalize_season_diagnostics(conn)
    main.finalize_season_diagnostics(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM venue_bias_diagnostics")
    # INSERT OR REPLACE keyed on (venue_name, season) — no duplication.
    assert cursor.fetchone()[0] <= 1
