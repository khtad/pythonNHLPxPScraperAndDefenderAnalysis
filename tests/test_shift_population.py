import sqlite3

from database import (
    ensure_player_database_schema,
    ensure_xg_schema,
    insert_shift_records,
    insert_shot_events,
    replace_game_on_ice_intervals,
    upsert_game_metadata,
)
from shift_population import populate_shift_data_for_game, select_shift_backfill_game_ids


def _conn():
    connection = sqlite3.connect(":memory:")
    ensure_player_database_schema(connection)
    ensure_xg_schema(connection)
    return connection


def _shot(game_id, event_idx=1):
    return {
        "game_id": game_id,
        "event_idx": event_idx,
        "shot_event_type": "shot-on-goal",
        "period": 1,
        "time_in_period": "00:20",
        "time_remaining_seconds": 1180,
        "shot_type": "wrist",
        "x_coord": 70,
        "y_coord": 10,
        "distance_to_goal": 22.36,
        "angle_to_goal": 26.56,
        "is_goal": 0,
        "shooting_team_id": 22,
        "goalie_id": 40,
        "shooter_id": 1,
        "score_state": "tied",
        "manpower_state": "5v5",
    }


def _seed_game(connection, game_id):
    upsert_game_metadata(
        connection,
        game_id,
        game_date="2025-10-01",
        season="20252026",
        home_team_id=22,
        away_team_id=10,
    )
    insert_shot_events(connection, [_shot(game_id)])


def _full_shift_payload(game_id):
    rows = []
    for player_id, position in [(1, "C"), (2, "L"), (3, "R"), (4, "D"), (5, "D"), (30, "G")]:
        rows.append({
            "gameId": game_id,
            "playerId": player_id,
            "teamId": 22,
            "period": 1,
            "startTime": "00:00",
            "endTime": "00:40",
            "positionCode": position,
        })
    for player_id, position in [(11, "C"), (12, "L"), (13, "R"), (14, "D"), (15, "D"), (40, "G")]:
        rows.append({
            "gameId": game_id,
            "playerId": player_id,
            "teamId": 10,
            "period": 1,
            "startTime": "00:00",
            "endTime": "00:40",
            "positionCode": position,
        })
    return rows


def test_populate_shift_data_for_game_persists_intervals_and_updates_shots():
    connection = _conn()
    game_id = 2025020001
    _seed_game(connection, game_id)

    result = populate_shift_data_for_game(
        connection,
        game_id,
        fetch_fn=lambda shifted_game_id: _full_shift_payload(shifted_game_id),
    )

    assert result.games_scanned == 1
    assert result.games_populated == 1
    assert result.shift_rows_inserted == 12
    assert result.interval_rows_inserted == 1
    assert result.shot_rows_updated == 1

    cur = connection.cursor()
    cur.execute("SELECT COUNT(*) FROM shifts WHERE game_id = ?", (game_id,))
    assert cur.fetchone()[0] == 12
    cur.execute("SELECT COUNT(*) FROM on_ice_intervals WHERE game_id = ?", (game_id,))
    assert cur.fetchone()[0] == 1
    cur.execute(
        """SELECT home_on_ice_1_player_id,
                  home_on_ice_6_player_id,
                  away_on_ice_1_player_id,
                  away_on_ice_6_player_id
           FROM shot_events
           WHERE game_id = ?""",
        (game_id,),
    )
    assert cur.fetchone() == (1, 30, 11, 40)

    second_result = populate_shift_data_for_game(
        connection,
        game_id,
        fetch_fn=lambda shifted_game_id: (_ for _ in ()).throw(AssertionError()),
    )

    assert second_result.games_skipped == 1
    cur.execute("SELECT COUNT(*) FROM shifts WHERE game_id = ?", (game_id,))
    assert cur.fetchone()[0] == 12


def test_select_shift_backfill_game_ids_respects_game_id_and_limit():
    connection = _conn()
    first_game_id = 2025020001
    second_game_id = 2025020002
    _seed_game(connection, first_game_id)
    _seed_game(connection, second_game_id)
    insert_shift_records(connection, [{
        "game_id": first_game_id,
        "player_id": 1,
        "team_id": 22,
        "team_side": "home",
        "position": "C",
        "period": 1,
        "start_seconds": 0,
        "end_seconds": 40,
    }])
    replace_game_on_ice_intervals(connection, first_game_id, [{
        "game_id": first_game_id,
        "period": 1,
        "start_s": 0,
        "end_s": 40,
        "home_skaters_json": "[1]",
        "away_skaters_json": "[]",
        "home_goalie_player_id": None,
        "away_goalie_player_id": None,
        "strength_state": "1v0",
    }])

    assert select_shift_backfill_game_ids(connection, game_id=first_game_id) == [first_game_id]
    assert select_shift_backfill_game_ids(connection, all_games=True, limit=1) == [second_game_id]
