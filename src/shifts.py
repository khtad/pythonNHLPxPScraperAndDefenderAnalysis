"""Shift chart ingestion utilities for roster-change decomposition program."""

from dataclasses import dataclass
from typing import Iterable, List

from nhl_api import _api_get, _NHL_API_BASE_URL

SHIFT_TIME_DRIFT_TOLERANCE_SECONDS = 1
SHIFT_SCHEMA_VERSION = "v1"
_REQUIRED_SHIFT_ROW_KEYS = (
    "player_id",
    "period",
    "start_seconds",
    "end_seconds",
)


@dataclass(frozen=True)
class ShiftRecord:
    game_id: int
    player_id: int
    period: int
    start_seconds: int
    end_seconds: int
    shift_schema_version: str = SHIFT_SCHEMA_VERSION


def _clock_to_seconds(clock_value: int | str) -> int:
    """Normalize period clock values to elapsed-seconds integers."""
    if isinstance(clock_value, int):
        return clock_value

    if ":" not in clock_value:
        return int(clock_value)

    minutes_str, seconds_str = clock_value.split(":", maxsplit=1)
    return int(minutes_str) * 60 + int(seconds_str)


def fetch_shift_rows_for_game(game_id: int) -> list[dict]:
    """Fetch raw shift rows for a single game from NHL shift charts endpoint."""
    url = f"{_NHL_API_BASE_URL}/gamecenter/{game_id}/shiftcharts"
    payload = _api_get(url)
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    return payload.get("data", [])


def parse_shift_rows(game_id: int, raw_rows: Iterable[dict]) -> List[ShiftRecord]:
    """Parse shift payload rows into normalized records."""
    parsed_records: List[ShiftRecord] = []
    for row in raw_rows:
        missing_keys = [key for key in _REQUIRED_SHIFT_ROW_KEYS if key not in row]
        if missing_keys:
            continue

        parsed_records.append(
            ShiftRecord(
                game_id=game_id,
                player_id=int(row["player_id"]),
                period=int(row["period"]),
                start_seconds=_clock_to_seconds(row["start_seconds"]),
                end_seconds=_clock_to_seconds(row["end_seconds"]),
            )
        )
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
