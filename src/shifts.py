"""Shift chart ingestion utilities for roster-change decomposition program."""

from dataclasses import dataclass
from typing import Iterable, List

from database import _SHIFT_SCHEMA_VERSION
from nhl_api import _api_get, _NHL_API_BASE_URL

SHIFT_TIME_DRIFT_TOLERANCE_SECONDS = 1
SHIFT_SCHEMA_VERSION = _SHIFT_SCHEMA_VERSION
_PLAYER_ID_KEYS = ("player_id", "playerId")
_TEAM_ID_KEYS = ("team_id", "teamId")
_TEAM_SIDE_KEYS = ("team_side", "side")
_POSITION_KEYS = ("position", "position_code", "positionCode", "playerPositionCode")
_START_TIME_KEYS = ("start_seconds", "startSeconds", "startTime")
_END_TIME_KEYS = ("end_seconds", "endSeconds", "endTime")
_DURATION_KEYS = ("duration_seconds", "durationSeconds", "duration")
_HOME_TEAM_SIDE = "home"
_AWAY_TEAM_SIDE = "away"


@dataclass(frozen=True)
class ShiftRecord:
    game_id: int
    player_id: int
    period: int
    start_seconds: int
    end_seconds: int
    team_id: int | None = None
    team_side: str | None = None
    position: str | None = None
    shift_schema_version: str = SHIFT_SCHEMA_VERSION


def _first_present(row: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def clock_to_seconds(clock_value: int | str) -> int:
    """Normalize period clock values to elapsed-seconds integers."""
    if isinstance(clock_value, int):
        return clock_value

    if ":" not in clock_value:
        return int(clock_value)

    minutes_str, seconds_str = clock_value.split(":", maxsplit=1)
    return int(minutes_str) * 60 + int(seconds_str)


def _normalize_position(position_value):
    if position_value is None:
        return None
    if isinstance(position_value, dict):
        position_value = position_value.get("code") or position_value.get("default")
    return str(position_value).upper()


def _team_side(team_id, home_team_id, away_team_id, raw_side):
    if raw_side is not None:
        normalized_side = str(raw_side).lower()
        if normalized_side in (_HOME_TEAM_SIDE, _AWAY_TEAM_SIDE):
            return normalized_side
    if team_id is None:
        return None
    if home_team_id is not None and int(team_id) == int(home_team_id):
        return _HOME_TEAM_SIDE
    if away_team_id is not None and int(team_id) == int(away_team_id):
        return _AWAY_TEAM_SIDE
    return None


def _normalized_shift_dict(
    game_id: int,
    row: dict,
    home_team_id=None,
    away_team_id=None,
    player_positions=None,
):
    player_positions = player_positions or {}
    player_id = _first_present(row, _PLAYER_ID_KEYS)
    period = row.get("period")
    start_value = _first_present(row, _START_TIME_KEYS)
    end_value = _first_present(row, _END_TIME_KEYS)
    duration_value = _first_present(row, _DURATION_KEYS)
    if player_id is None or period is None or start_value is None:
        return None

    try:
        normalized_player_id = int(player_id)
        start_seconds = clock_to_seconds(start_value)
        if end_value is None and duration_value is not None:
            end_seconds = start_seconds + clock_to_seconds(duration_value)
        else:
            end_seconds = clock_to_seconds(end_value)
        team_id = _first_present(row, _TEAM_ID_KEYS)
        normalized_team_id = int(team_id) if team_id is not None else None
        position = _normalize_position(_first_present(row, _POSITION_KEYS))
        if position is None:
            position = _normalize_position(player_positions.get(normalized_player_id))
        return {
            "game_id": int(row.get("game_id", game_id)),
            "player_id": normalized_player_id,
            "team_id": normalized_team_id,
            "team_side": _team_side(
                normalized_team_id,
                home_team_id,
                away_team_id,
                _first_present(row, _TEAM_SIDE_KEYS),
            ),
            "position": position,
            "period": int(period),
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "shift_schema_version": SHIFT_SCHEMA_VERSION,
        }
    except (TypeError, ValueError):
        return None


def extract_shift_player_ids(raw_rows: Iterable[dict]) -> set[int]:
    """Return player ids found in raw shift rows."""
    player_ids = set()
    for row in raw_rows:
        player_id = _first_present(row, _PLAYER_ID_KEYS)
        if player_id is None:
            continue
        try:
            player_ids.add(int(player_id))
        except (TypeError, ValueError):
            continue
    return player_ids


def fetch_shift_rows_for_game(game_id: int) -> list[dict]:
    """Fetch raw shift rows for a single game from NHL shift charts endpoint."""
    url = f"{_NHL_API_BASE_URL}/gamecenter/{game_id}/shiftcharts"
    payload = _api_get(url)
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    return payload.get("data", [])


def parse_shift_rows(
    game_id: int,
    raw_rows: Iterable[dict],
    home_team_id=None,
    away_team_id=None,
    player_positions=None,
) -> List[ShiftRecord]:
    """Parse shift payload rows into normalized records."""
    parsed_records: List[ShiftRecord] = []
    for row in raw_rows:
        normalized = _normalized_shift_dict(
            game_id,
            row,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            player_positions=player_positions,
        )
        if normalized is None:
            continue

        parsed_records.append(ShiftRecord(**normalized))
    return parsed_records


def validate_shift_records(records: Iterable[ShiftRecord]) -> dict:
    """Run baseline data-quality checks required by the Phase 1 plan."""
    total_records = 0
    invalid_duration_rows = 0
    invalid_period_rows = 0
    for record in records:
        total_records += 1
        if record.end_seconds < record.start_seconds:
            invalid_duration_rows += 1
        if record.period <= 0:
            invalid_period_rows += 1

    return {
        "total_records": total_records,
        "invalid_duration_rows": invalid_duration_rows,
        "invalid_period_rows": invalid_period_rows,
    }
