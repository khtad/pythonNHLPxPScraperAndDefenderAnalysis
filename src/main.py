import datetime

from nhl_api import get_weekly_schedule, get_play_by_play_data
from database import (create_table, insert_data, create_connection,
                      create_collection_log_table, is_game_collected,
                      mark_date_collected, get_last_collected_date,
                      deduplicate_existing_tables)

DATABASE_PATH = "nhl_data.db"
NHL_FIRST_GAME_DATE = datetime.date(2007, 10, 3)  # earliest available game in NHL API

def main():
    start_date = NHL_FIRST_GAME_DATE
    end_date = datetime.date.today()

    # Connect to the database
    conn = create_connection(DATABASE_PATH)
    create_collection_log_table(conn)
    deduplicate_existing_tables(conn)

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

            for game_id in game_ids:
                if is_game_collected(conn, game_id):
                    print(f"Skipping already-collected game {game_id}")
                    games_collected += 1
                    continue

                play_by_play_data = get_play_by_play_data(game_id)
                if play_by_play_data:
                    create_table(conn, game_id)
                    insert_data(conn, game_id, play_by_play_data)
                    games_collected += 1

            mark_date_collected(conn, date_str, games_found, games_collected)

        if not next_start_date:
            break
        current_date = datetime.date.fromisoformat(next_start_date)

    conn.close()

if __name__ == "__main__":
    main()
