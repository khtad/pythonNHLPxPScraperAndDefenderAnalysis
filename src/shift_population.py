"""Populate shift and on-ice tables from NHL shift-chart payloads."""

from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from database import (
    DATABASE_PATH,
    create_connection,
    ensure_xg_schema,
    ensure_player_database_schema,
    game_has_current_shift_data,
    get_shift_backfill_game_ids,
    insert_shift_records,
    load_game_shots,
    load_game_team_ids,
    load_player_positions,
    replace_game_on_ice_intervals,
    update_shot_event_on_ice_slots,
)
from on_ice_builder import attach_on_ice_slots_to_shots, build_on_ice_intervals
from shifts import (
    extract_shift_player_ids,
    fetch_shift_rows_for_game,
    parse_shift_rows,
    shift_record_has_resolved_context,
)

FetchShiftRows = Callable[[int], list[dict]]


@dataclass(frozen=True)
class ShiftPopulationResult:
    games_scanned: int = 0
    games_populated: int = 0
    games_skipped: int = 0
    shift_rows_inserted: int = 0
    interval_rows_inserted: int = 0
    shot_rows_updated: int = 0

    def plus(self, other: "ShiftPopulationResult") -> "ShiftPopulationResult":
        return ShiftPopulationResult(
            games_scanned=self.games_scanned + other.games_scanned,
            games_populated=self.games_populated + other.games_populated,
            games_skipped=self.games_skipped + other.games_skipped,
            shift_rows_inserted=self.shift_rows_inserted + other.shift_rows_inserted,
            interval_rows_inserted=self.interval_rows_inserted + other.interval_rows_inserted,
            shot_rows_updated=self.shot_rows_updated + other.shot_rows_updated,
        )


def _valid_shift_records(records):
    return [
        record for record in records
        if record.period > 0 and record.end_seconds > record.start_seconds
    ]


def _has_resolved_shift_context(records):
    return all(shift_record_has_resolved_context(record) for record in records)


def populate_shift_data_for_game(
    conn,
    game_id: int,
    fetch_fn: FetchShiftRows = fetch_shift_rows_for_game,
) -> ShiftPopulationResult:
    """Populate shifts, intervals, and shot on-ice slots for one game."""
    if game_has_current_shift_data(conn, game_id):
        return ShiftPopulationResult(games_scanned=1, games_skipped=1)

    raw_rows = fetch_fn(game_id)
    if not raw_rows:
        return ShiftPopulationResult(games_scanned=1, games_skipped=1)

    home_team_id, away_team_id = load_game_team_ids(conn, game_id)
    player_positions = load_player_positions(conn, extract_shift_player_ids(raw_rows))
    shift_records = _valid_shift_records(
        parse_shift_rows(
            game_id,
            raw_rows,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            player_positions=player_positions,
        )
    )
    if not shift_records:
        return ShiftPopulationResult(games_scanned=1, games_skipped=1)
    if not _has_resolved_shift_context(shift_records):
        return ShiftPopulationResult(games_scanned=1, games_skipped=1)

    shift_dicts = [asdict(record) for record in shift_records]
    intervals = build_on_ice_intervals(game_id, shift_dicts)
    if not intervals:
        return ShiftPopulationResult(games_scanned=1, games_skipped=1)

    shot_rows = load_game_shots(conn, game_id)
    enriched_shots = attach_on_ice_slots_to_shots(shot_rows, intervals)

    try:
        shift_rows_inserted = insert_shift_records(conn, shift_records, commit=False)
        interval_rows_inserted = replace_game_on_ice_intervals(
            conn, game_id, intervals, commit=False
        )
        shot_rows_updated = update_shot_event_on_ice_slots(
            conn, enriched_shots, commit=False
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return ShiftPopulationResult(
        games_scanned=1,
        games_populated=1,
        shift_rows_inserted=shift_rows_inserted,
        interval_rows_inserted=interval_rows_inserted,
        shot_rows_updated=shot_rows_updated,
    )


def populate_shift_data_for_games(
    conn,
    game_ids: Iterable[int],
    fetch_fn: FetchShiftRows = fetch_shift_rows_for_game,
) -> ShiftPopulationResult:
    """Populate shift-derived tables for a sequence of games."""
    result = ShiftPopulationResult()
    for game_id in game_ids:
        result = result.plus(
            populate_shift_data_for_game(conn, int(game_id), fetch_fn=fetch_fn)
        )
    return result


def select_shift_backfill_game_ids(conn, all_games=False, limit=None, game_id=None):
    """Select game ids for the shift backfill CLI."""
    if game_id is not None:
        return [int(game_id)]
    if not all_games:
        raise ValueError("Pass --all or --game-id to select shift backfill games.")
    return get_shift_backfill_game_ids(conn, limit=limit)


def format_shift_population_summary(result: ShiftPopulationResult) -> str:
    """Return a stable one-line summary for CLI and scraper logs."""
    return (
        "Shift population: "
        f"games_scanned={result.games_scanned} "
        f"games_populated={result.games_populated} "
        f"games_skipped={result.games_skipped} "
        f"shift_rows_inserted={result.shift_rows_inserted} "
        f"interval_rows_inserted={result.interval_rows_inserted} "
        f"shot_rows_updated={result.shot_rows_updated}"
    )


def backfill_shift_data(
    database_path=DATABASE_PATH,
    all_games=False,
    limit=None,
    game_id=None,
    fetch_fn: FetchShiftRows = fetch_shift_rows_for_game,
) -> ShiftPopulationResult:
    """Open the database and populate shift-derived tables for selected games."""
    conn = create_connection(database_path)
    ensure_player_database_schema(conn)
    ensure_xg_schema(conn)
    try:
        game_ids = select_shift_backfill_game_ids(
            conn, all_games=all_games, limit=limit, game_id=game_id
        )
        return populate_shift_data_for_games(conn, game_ids, fetch_fn=fetch_fn)
    finally:
        conn.close()
