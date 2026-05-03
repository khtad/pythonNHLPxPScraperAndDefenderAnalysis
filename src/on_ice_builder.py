"""On-ice interval builder for roster-change impact analysis."""

import json
from dataclasses import dataclass
from typing import Iterable

from shifts import clock_to_seconds

ON_ICE_SKATER_COUNT = 5
ON_ICE_SLOT_COUNT_PER_TEAM = 6
SHOT_SLOT_TEMPLATE_KEYS = tuple(
    [f"home_on_ice_{slot}_player_id" for slot in range(1, ON_ICE_SLOT_COUNT_PER_TEAM + 1)]
    + [f"away_on_ice_{slot}_player_id" for slot in range(1, ON_ICE_SLOT_COUNT_PER_TEAM + 1)]
)


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


def _extract_sideshift_value(row: dict, *keys: str):
    for key in keys:
        if key in row:
            return row[key]
    return None


def _derive_strength_state(home_skaters: list[int], away_skaters: list[int]) -> str:
    return f"{len(home_skaters)}v{len(away_skaters)}"


def _interval_contains(interval: OnIceInterval, seconds_in_period: int) -> bool:
    return interval.start_s <= seconds_in_period < interval.end_s


def _finalize_slots(skaters: list[int], goalie_id: int | None) -> list[int | None]:
    sorted_skaters = sorted(skaters)[:ON_ICE_SKATER_COUNT]
    padded_skaters = sorted_skaters + [None] * (ON_ICE_SKATER_COUNT - len(sorted_skaters))
    return padded_skaters + [goalie_id]


def build_on_ice_intervals(game_id: int, shift_rows: Iterable[dict]) -> list[OnIceInterval]:
    """Build intervalized on-ice representation from normalized shift rows."""
    rows = [row for row in shift_rows if int(row.get("end_seconds", 0)) > int(row.get("start_seconds", 0))]
    periods = sorted({int(row["period"]) for row in rows if "period" in row})
    intervals: list[OnIceInterval] = []

    for period in periods:
        period_rows = [row for row in rows if int(row["period"]) == period]
        boundaries = sorted({int(row["start_seconds"]) for row in period_rows} | {int(row["end_seconds"]) for row in period_rows})
        for start_s, end_s in zip(boundaries, boundaries[1:]):
            if end_s <= start_s:
                continue

            active_rows = [
                row for row in period_rows
                if int(row["start_seconds"]) < end_s and int(row["end_seconds"]) > start_s
            ]

            home_skaters = sorted({
                int(row["player_id"]) for row in active_rows
                if _extract_sideshift_value(row, "team_side", "side") == "home"
                and str(_extract_sideshift_value(row, "position", "position_code", "positionCode") or "").upper() != "G"
            })
            away_skaters = sorted({
                int(row["player_id"]) for row in active_rows
                if _extract_sideshift_value(row, "team_side", "side") == "away"
                and str(_extract_sideshift_value(row, "position", "position_code", "positionCode") or "").upper() != "G"
            })
            home_goalie_ids = sorted({
                int(row["player_id"]) for row in active_rows
                if _extract_sideshift_value(row, "team_side", "side") == "home"
                and str(_extract_sideshift_value(row, "position", "position_code", "positionCode") or "").upper() == "G"
            })
            away_goalie_ids = sorted({
                int(row["player_id"]) for row in active_rows
                if _extract_sideshift_value(row, "team_side", "side") == "away"
                and str(_extract_sideshift_value(row, "position", "position_code", "positionCode") or "").upper() == "G"
            })

            if not home_skaters and not away_skaters:
                continue

            intervals.append(
                OnIceInterval(
                    game_id=game_id,
                    period=period,
                    start_s=start_s,
                    end_s=end_s,
                    home_skaters_json=json.dumps(home_skaters),
                    away_skaters_json=json.dumps(away_skaters),
                    home_goalie_player_id=home_goalie_ids[0] if home_goalie_ids else None,
                    away_goalie_player_id=away_goalie_ids[0] if away_goalie_ids else None,
                    strength_state=_derive_strength_state(home_skaters, away_skaters),
                )
            )
    return intervals


def attach_on_ice_slots_to_shots(shot_rows: Iterable[dict], interval_rows: Iterable[OnIceInterval]) -> list[dict]:
    """Populate shot rows with 12 on-ice slots from intervalized shift data."""
    intervals = list(interval_rows)
    if not intervals:
        return list(shot_rows)

    interval_lookup: dict[tuple[int, int], list[OnIceInterval]] = {}
    for interval in intervals:
        key = (interval.game_id, interval.period)
        interval_lookup.setdefault(key, []).append(interval)

    for key in interval_lookup:
        interval_lookup[key].sort(key=lambda i: (i.start_s, i.end_s))

    enriched_shots: list[dict] = []
    for shot in shot_rows:
        updated_shot = dict(shot)
        for slot_key in SHOT_SLOT_TEMPLATE_KEYS:
            updated_shot.setdefault(slot_key, None)

        shot_period = int(updated_shot.get("period", 0))
        shot_seconds = clock_to_seconds(updated_shot.get("time_in_period", 0))
        shot_game_id = int(updated_shot.get("game_id", 0))
        candidates = interval_lookup.get((shot_game_id, shot_period), [])

        matched_interval = next((interval for interval in candidates if _interval_contains(interval, shot_seconds)), None)
        if matched_interval is None and candidates:
            matched_interval = candidates[-1]

        if matched_interval is not None:
            home_skaters = json.loads(matched_interval.home_skaters_json)
            away_skaters = json.loads(matched_interval.away_skaters_json)
            home_slots = _finalize_slots(home_skaters, matched_interval.home_goalie_player_id)
            away_slots = _finalize_slots(away_skaters, matched_interval.away_goalie_player_id)

            for slot_index, player_id in enumerate(home_slots, start=1):
                updated_shot[f"home_on_ice_{slot_index}_player_id"] = player_id
            for slot_index, player_id in enumerate(away_slots, start=1):
                updated_shot[f"away_on_ice_{slot_index}_player_id"] = player_id

        enriched_shots.append(updated_shot)

    return enriched_shots
