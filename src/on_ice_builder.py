"""On-ice interval builder scaffolding for roster-change impact analysis."""

from dataclasses import dataclass
from typing import Iterable


ON_ICE_SKATER_COUNT = 5
ON_ICE_SLOT_COUNT_PER_TEAM = 6


@dataclass(frozen=True)
class OnIceInterval:
    game_id: int
    period: int
    start_s: int
    end_s: int
    home_skaters_json: str
    away_skaters_json: str
    home_goalie_player_id: int | None
    away_goalie_player_id: int | None
    strength_state: str | None


def build_on_ice_intervals(game_id: int, shift_rows: Iterable[dict]) -> list[OnIceInterval]:
    """Build intervalized on-ice representation from shift rows.

    Placeholder for the Phase 1 implementation.
    """
    _ = (game_id, shift_rows)
    return []


def attach_on_ice_slots_to_shots(shot_rows: Iterable[dict], interval_rows: Iterable[OnIceInterval]) -> list[dict]:
    """Populate 12 on-ice slots in shot rows.

    Placeholder that returns input rows unchanged.
    """
    _ = interval_rows
    return list(shot_rows)
