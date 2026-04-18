"""Shift chart ingestion scaffolding for roster-change decomposition program."""

from dataclasses import dataclass
from typing import Iterable, List

SHIFT_TIME_DRIFT_TOLERANCE_SECONDS = 1
SHIFT_SCHEMA_VERSION = "v1"


@dataclass(frozen=True)
class ShiftRecord:
    game_id: int
    player_id: int
    period: int
    start_seconds: int
    end_seconds: int
    shift_schema_version: str = SHIFT_SCHEMA_VERSION


def fetch_shift_rows_for_game(game_id: int) -> list[dict]:
    """Fetch raw shift rows for a single game.

    Placeholder implementation for Phase 1 scaffolding.
    """
    _ = game_id
    return []


def parse_shift_rows(game_id: int, raw_rows: Iterable[dict]) -> List[ShiftRecord]:
    """Parse shift payload rows into normalized records."""
    parsed_records: List[ShiftRecord] = []
    for row in raw_rows:
        parsed_records.append(
            ShiftRecord(
                game_id=game_id,
                player_id=int(row["player_id"]),
                period=int(row["period"]),
                start_seconds=int(row["start_seconds"]),
                end_seconds=int(row["end_seconds"]),
            )
        )
    return parsed_records


def validate_shift_records(records: Iterable[ShiftRecord]) -> dict:
    """Run baseline data-quality checks required by the Phase 1 plan."""
    total_records = 0
    invalid_duration_rows = 0
    for record in records:
        total_records += 1
        if record.end_seconds < record.start_seconds:
            invalid_duration_rows += 1
    return {
        "total_records": total_records,
        "invalid_duration_rows": invalid_duration_rows,
    }
