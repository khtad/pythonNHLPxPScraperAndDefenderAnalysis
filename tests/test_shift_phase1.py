import json

from on_ice_builder import attach_on_ice_slots_to_shots, build_on_ice_intervals
from shifts import ShiftRecord, parse_shift_rows, validate_shift_records


def test_parse_shift_rows_normalizes_clock_strings():
    raw_rows = [
        {
            "player_id": "101",
            "period": "1",
            "start_seconds": "00:10",
            "end_seconds": "00:35",
        }
    ]

    records = parse_shift_rows(game_id=2025020001, raw_rows=raw_rows)

    assert records == [
        ShiftRecord(
            game_id=2025020001,
            player_id=101,
            period=1,
            start_seconds=10,
            end_seconds=35,
        )
    ]


def test_validate_shift_records_reports_invalid_rows():
    records = [
        ShiftRecord(game_id=1, player_id=10, period=1, start_seconds=1, end_seconds=2),
        ShiftRecord(game_id=1, player_id=11, period=0, start_seconds=1, end_seconds=2),
        ShiftRecord(game_id=1, player_id=12, period=2, start_seconds=9, end_seconds=8),
    ]

    quality = validate_shift_records(records)

    assert quality["total_records"] == 3
    assert quality["invalid_period_rows"] == 1
    assert quality["invalid_duration_rows"] == 1


def test_build_on_ice_intervals_and_attach_to_shots():
    shift_rows = [
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 1, "team_side": "home", "position": "C"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 2, "team_side": "home", "position": "LW"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 3, "team_side": "home", "position": "RW"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 4, "team_side": "home", "position": "LD"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 5, "team_side": "home", "position": "RD"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 30, "team_side": "home", "position": "G"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 11, "team_side": "away", "position": "C"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 12, "team_side": "away", "position": "LW"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 13, "team_side": "away", "position": "RW"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 14, "team_side": "away", "position": "LD"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 15, "team_side": "away", "position": "RD"},
        {"game_id": 77, "period": 1, "start_seconds": 0, "end_seconds": 40, "player_id": 40, "team_side": "away", "position": "G"},
    ]

    intervals = build_on_ice_intervals(game_id=77, shift_rows=shift_rows)

    assert len(intervals) == 1
    assert json.loads(intervals[0].home_skaters_json) == [1, 2, 3, 4, 5]
    assert json.loads(intervals[0].away_skaters_json) == [11, 12, 13, 14, 15]
    assert intervals[0].home_goalie_player_id == 30
    assert intervals[0].away_goalie_player_id == 40
    assert intervals[0].strength_state == "5v5"

    shots = [{"game_id": 77, "period": 1, "time_in_period": 20, "event_idx": 1}]
    enriched = attach_on_ice_slots_to_shots(shots, intervals)

    assert enriched[0]["home_on_ice_1_player_id"] == 1
    assert enriched[0]["home_on_ice_5_player_id"] == 5
    assert enriched[0]["home_on_ice_6_player_id"] == 30
    assert enriched[0]["away_on_ice_1_player_id"] == 11
    assert enriched[0]["away_on_ice_5_player_id"] == 15
    assert enriched[0]["away_on_ice_6_player_id"] == 40
