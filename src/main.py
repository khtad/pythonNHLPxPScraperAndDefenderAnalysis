import datetime
import os

from nhl_api import get_weekly_schedule, get_full_play_by_play
from database import (create_table, insert_data, create_connection,
                      create_collection_log_table, is_game_collected,
                      mark_date_collected, get_last_collected_date,
                      fix_incomplete_collection_log,
                      deduplicate_existing_tables,
                      ensure_xg_schema, game_has_shot_events,
                      insert_shot_events, game_has_metadata,
                      upsert_game_metadata, upsert_team,
                      ensure_player_database_schema,
                      populate_game_context,
                      get_collected_game_ids,
                      DATABASE_DIR, DATABASE_PATH)
from xg_features import extract_shot_events, extract_game_metadata

NHL_FIRST_GAME_DATE = datetime.date(2007, 10, 3)  # earliest available game in NHL API
_BACKFILL_STATUS_SEPARATOR = ", "


def _get_game_processing_state(conn, game_id):
    raw_events_present = is_game_collected(conn, game_id)
    metadata_present = game_has_metadata(conn, game_id)
    shot_events_present = game_has_shot_events(conn, game_id)
    return raw_events_present, metadata_present, shot_events_present


def _format_missing_game_data(raw_events_present, metadata_present, shot_events_present):
    missing_parts = []
    if not raw_events_present:
        missing_parts.append("raw events")
    if not metadata_present:
        missing_parts.append("metadata")
    if not shot_events_present:
        missing_parts.append("shot events")
    return _BACKFILL_STATUS_SEPARATOR.join(missing_parts)


def _process_game(conn, game_id, raw_events_present, metadata_present, shot_events_present):
    if raw_events_present and metadata_present and shot_events_present:
        print(f"Skipping fully-processed game {game_id}")
        return True

    if raw_events_present:
        missing_data = _format_missing_game_data(
            raw_events_present, metadata_present, shot_events_present,
        )
        print(f"Backfilling game {game_id} ({missing_data})")

    full_data = get_full_play_by_play(game_id)
    if full_data is None:
        print(f"No data returned for game {game_id}, skipping")
        return True

    if not raw_events_present:
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

    if not metadata_present:
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

    if not shot_events_present:
        shot_events = extract_shot_events(full_data)
        if shot_events:
            insert_shot_events(conn, shot_events)

    return True


def backfill_missing_game_data(limit=None):
    """Backfill metadata and shot events for already-collected raw games."""
    os.makedirs(DATABASE_DIR, exist_ok=True)

    conn = create_connection(DATABASE_PATH)
    create_collection_log_table(conn)
    fix_incomplete_collection_log(conn)
    deduplicate_existing_tables(conn)
    ensure_player_database_schema(conn)
    ensure_xg_schema(conn)

    game_ids = get_collected_game_ids(conn)
    missing_game_ids = []
    for game_id in game_ids:
        processing_state = _get_game_processing_state(conn, game_id)
        if not all(processing_state):
            missing_game_ids.append(game_id)

    if limit is not None:
        missing_game_ids = missing_game_ids[:limit]

    print(f"Found {len(missing_game_ids)} collected games missing derived data")

    processed_games = 0
    for game_id in missing_game_ids:
        if _process_game(conn, game_id, *_get_game_processing_state(conn, game_id)):
            processed_games += 1

    conn.close()
    print(f"Finished backfill for {processed_games} games")
    return processed_games


def run_scraper_and_backfill(backfill_limit=None):
    """Run the scheduled scraper update, then backfill missing derived data."""
    main()
    return backfill_missing_game_data(limit=backfill_limit)

def main():
    start_date = NHL_FIRST_GAME_DATE
    end_date = datetime.date.today()

    os.makedirs(DATABASE_DIR, exist_ok=True)

    conn = create_connection(DATABASE_PATH)
    create_collection_log_table(conn)
    fix_incomplete_collection_log(conn)
    deduplicate_existing_tables(conn)
    ensure_player_database_schema(conn)
    ensure_xg_schema(conn)

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

            for game_id in game_ids:
                processing_state = _get_game_processing_state(conn, game_id)
                if _process_game(conn, game_id, *processing_state):
                    games_collected += 1

            mark_date_collected(conn, date_str, games_found, games_collected)

        if not next_start_date:
            break
        current_date = datetime.date.fromisoformat(next_start_date)

    conn.close()


if __name__ == "__main__":
    run_scraper_and_backfill()
