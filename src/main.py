import datetime

from nhl_api import get_game_ids_for_date, get_play_by_play_data
from database import (create_table, insert_data, create_connection,
                      create_collection_log_table, is_game_collected,
                      mark_date_collected, get_last_collected_date,
                      deduplicate_existing_tables)

def main():
    database = "nhl_data.db"
    start_date = datetime.date(2007, 10, 3)
    end_date = datetime.date.today()

    # Connect to the database
    conn = create_connection(database)
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
        date_str = current_date.isoformat()
        game_ids = get_game_ids_for_date(current_date)
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
        current_date += datetime.timedelta(days=1)

    conn.close()

if __name__ == "__main__":
    main()