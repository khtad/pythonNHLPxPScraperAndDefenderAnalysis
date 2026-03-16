import datetime
import os

from nhl_api import get_weekly_schedule, get_full_play_by_play
from database import (create_table, insert_data, create_connection,
                      create_collection_log_table, is_game_collected,
                      mark_date_collected, get_last_collected_date,
                      fix_incomplete_collection_log,
                      deduplicate_existing_tables,
                      ensure_xg_schema, game_has_shot_events,
                      insert_shot_events,
                      DATABASE_DIR, DATABASE_PATH)
from xg_features import extract_shot_events

NHL_FIRST_GAME_DATE = datetime.date(2007, 10, 3)  # earliest available game in NHL API

def main():
    start_date = NHL_FIRST_GAME_DATE
    end_date = datetime.date.today()

    # Ensure the data directory exists
    os.makedirs(DATABASE_DIR, exist_ok=True)

    # Connect to the database
    conn = create_connection(DATABASE_PATH)
    create_collection_log_table(conn)
    fix_incomplete_collection_log(conn)
    deduplicate_existing_tables(conn)
    ensure_xg_schema(conn)

    # Resume from the day after the last fully-collected date
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
                if is_game_collected(conn, game_id):
                    print(f"Skipping already-collected game {game_id}")
                    games_collected += 1
                    continue

                full_data = get_full_play_by_play(game_id)
                if full_data is None:
                    print(f"No data returned for game {game_id}, skipping")
                    games_collected += 1
                    continue

                # Raw storage (simplified rows)
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

                # Shot event extraction
                if not game_has_shot_events(conn, game_id):
                    shot_events = extract_shot_events(full_data)
                    if shot_events:
                        insert_shot_events(conn, shot_events)

                games_collected += 1

            mark_date_collected(conn, date_str, games_found, games_collected)

        if not next_start_date:
            break
        current_date = datetime.date.fromisoformat(next_start_date)

    conn.close()

if __name__ == "__main__":
    main()
