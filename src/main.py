import datetime
import os

from nhl_api import get_weekly_schedule, get_full_play_by_play, get_player_metadata
from database import (create_table, insert_data, create_connection,
                      create_collection_log_table, is_game_collected,
                      mark_date_collected, get_last_collected_date,
                      fix_incomplete_collection_log,
                      deduplicate_existing_tables,
                      ensure_xg_schema, game_has_shot_events,
                      game_has_current_shot_events,
                      delete_game_shot_events,
                      insert_shot_events, game_has_metadata,
                      upsert_game_metadata, upsert_team,
                      ensure_player_database_schema,
                      backfill_player_metadata,
                      populate_player_game_stats,
                      populate_player_game_features,
                      populate_game_context,
                      populate_venue_diagnostics,
                      populate_venue_bias_corrections,
                      get_collected_game_ids,
                      DATABASE_DIR, DATABASE_PATH)
from xg_features import extract_shot_events, extract_game_metadata
from backup import run_backup_cycle_safe
from shift_population import (
    format_shift_population_summary,
    populate_shift_data_for_game,
)

NHL_FIRST_GAME_DATE = datetime.date(2007, 10, 3)  # earliest available game in NHL API


def _init_database():
    """Create/open the database and run all schema migrations."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = create_connection(DATABASE_PATH)
    create_collection_log_table(conn)
    fix_incomplete_collection_log(conn)
    deduplicate_existing_tables(conn)
    ensure_player_database_schema(conn)
    ensure_xg_schema(conn)
    return conn


def _game_is_complete(conn, game_id):
    """Return True when raw events, metadata, and current-version shot events all exist."""
    return (is_game_collected(conn, game_id)
            and game_has_metadata(conn, game_id)
            and game_has_current_shot_events(conn, game_id))


def _process_game(conn, game_id):
    """Ensure a game has raw events, metadata, and shot events.

    Fetches play-by-play from the API only when at least one piece is missing.
    Returns True when the game can be counted as collected.
    """
    raw_present = is_game_collected(conn, game_id)
    meta_present = game_has_metadata(conn, game_id)
    shots_current = game_has_current_shot_events(conn, game_id)

    if raw_present and meta_present and shots_current:
        shift_result = populate_shift_data_for_game(conn, game_id)
        if shift_result.games_populated:
            print(f"  game {game_id}: {format_shift_population_summary(shift_result)}")
        return True

    if raw_present:
        missing = []
        if not meta_present:
            missing.append("metadata")
        if not shots_current:
            missing.append("shot events")
        print(f"  Backfilling game {game_id} ({', '.join(missing)})")
    else:
        print(f"  Collecting game {game_id} (new)")

    full_data = get_full_play_by_play(game_id)
    if full_data is None:
        print(f"No data returned for game {game_id}, skipping")
        return True

    if not raw_present:
        simplified_rows = [
            {
                "period": play.get("periodDescriptor", {}).get("number"),
                "time": play.get("timeInPeriod"),
                "event": play.get("typeDescKey"),
                "description": play.get("typeDescKey"),
            }
            for play in full_data.get("plays", [])
        ]
        create_table(conn, game_id)
        insert_data(conn, game_id, simplified_rows)

    if not meta_present:
        metadata = extract_game_metadata(full_data)
        if metadata:
            for prefix in ("home", "away"):
                tid = metadata.get(f"{prefix}_team_id")
                abbrev = metadata.get(f"{prefix}_team_abbrev")
                tname = metadata.get(f"{prefix}_team_name")
                if tid is not None:
                    upsert_team(conn, tid, abbrev, tname)

            upsert_game_metadata(
                conn, metadata["game_id"],
                metadata["game_date"], metadata["season"],
                metadata["home_team_id"], metadata["away_team_id"],
                venue_name=metadata.get("venue_name"),
                venue_city=metadata.get("venue_city"),
                venue_utc_offset=metadata.get("venue_utc_offset"),
            )
            populate_game_context(conn, game_id)

    if not shots_current:
        if game_has_shot_events(conn, game_id):
            delete_game_shot_events(conn, game_id)
        shot_events = extract_shot_events(full_data)
        if shot_events:
            insert_shot_events(conn, shot_events)
            print(f"  game {game_id}: inserted {len(shot_events)} shot events")
        else:
            print(f"  game {game_id}: no shot events extracted")

    if game_has_current_shot_events(conn, game_id):
        shift_result = populate_shift_data_for_game(conn, game_id)
        if shift_result.games_populated:
            print(f"  game {game_id}: {format_shift_population_summary(shift_result)}")

    return True


def finalize_season_diagnostics(conn):
    """Populate `venue_bias_diagnostics` for every season present in `games`.

    Runs after the scraper/backfill loop. Safe to re-run: the underlying
    `populate_venue_diagnostics` uses `INSERT OR REPLACE`.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT season FROM games "
        "WHERE season IS NOT NULL ORDER BY season"
    )
    seasons = [row[0] for row in cursor.fetchall()]
    for season in seasons:
        populate_venue_diagnostics(conn, season)
        populate_venue_bias_corrections(conn, season)
    print(f"Populated venue diagnostics for {len(seasons)} seasons")
    return len(seasons)


def refresh_player_tables(conn):
    """Backfill player metadata and refresh derived player tables.

    Runs after the scraper/backfill loop: the player-landing endpoint is
    only queried for shooter/goalie ids that are still missing from the
    players dimension. Player-game stats and features are rebuilt
    idempotently from the current shot-event foundation.
    """
    attempted, upserted, unavailable = backfill_player_metadata(
        conn, get_player_metadata
    )
    print(
        f"Player metadata backfill: attempted={attempted} "
        f"upserted={upserted} unavailable={unavailable}"
    )
    stats_rows = populate_player_game_stats(conn)
    print(f"Populated player_game_stats rows={stats_rows}")
    feature_rows = populate_player_game_features(conn)
    print(f"Populated player_game_features rows={feature_rows}")
    return {
        "metadata_attempted": attempted,
        "metadata_upserted": upserted,
        "metadata_unavailable": unavailable,
        "player_game_stats_rows": stats_rows,
        "player_game_features_rows": feature_rows,
    }


def backfill_missing_game_data(limit=None):
    """Backfill metadata and shot events for already-collected raw games."""
    conn = _init_database()

    game_ids = get_collected_game_ids(conn)
    missing_game_ids = [gid for gid in game_ids
                        if not _game_is_complete(conn, gid)]

    if limit is not None:
        missing_game_ids = missing_game_ids[:limit]

    print(f"Found {len(missing_game_ids)} collected games missing derived data")

    processed_games = 0
    total_missing = len(missing_game_ids)
    for i, game_id in enumerate(missing_game_ids, 1):
        print(f"[{i}/{total_missing}] game {game_id}")
        if _process_game(conn, game_id):
            processed_games += 1

    finalize_season_diagnostics(conn)
    refresh_player_tables(conn)

    conn.close()
    print(f"Finished backfill for {processed_games} games")
    return processed_games


def run_scraper_and_backfill(backfill_limit=None):
    """Run the scheduled scraper update, then backfill missing derived data."""
    main()
    processed = backfill_missing_game_data(limit=backfill_limit)
    run_backup_cycle_safe()
    return processed


def main():
    start_date = NHL_FIRST_GAME_DATE
    end_date = datetime.date.today()

    conn = _init_database()

    last_collected = get_last_collected_date(conn)
    if last_collected:
        current_date = max(start_date, last_collected + datetime.timedelta(days=1))
        print(f"Resuming collection from {current_date} (last completed: {last_collected})")
    else:
        current_date = start_date
        print(f"Starting fresh collection from {current_date}")

    while current_date <= end_date:
        schedule, next_start_date = get_weekly_schedule(current_date)

        for date_str in sorted(schedule):
            date_obj = datetime.date.fromisoformat(date_str)
            if date_obj < current_date or date_obj > end_date:
                continue

            game_ids = schedule[date_str]
            games_found = len(game_ids)
            games_collected = 0

            print(f"Processing date {date_str} ({games_found} games)")

            for i, game_id in enumerate(game_ids, 1):
                print(f"  [{i}/{games_found}] game {game_id}")
                if _process_game(conn, game_id):
                    games_collected += 1

            mark_date_collected(conn, date_str, games_found, games_collected)

        if not next_start_date:
            break
        current_date = datetime.date.fromisoformat(next_start_date)

    finalize_season_diagnostics(conn)
    refresh_player_tables(conn)

    conn.close()


if __name__ == "__main__":
    run_scraper_and_backfill()
