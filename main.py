import datetime
import sqlite3

from nhl_api import get_game_ids_for_date, get_play_by_play_data
from database import create_table, insert_data, create_connection

def main():
    database = "nhl_data.db"
    start_date = datetime.date(2007, 10, 3)
    end_date = datetime.date.today()

    # Connect to the database
    conn = create_connection(database)

    # Loop through all dates between start_date and end_date
    current_date = start_date
    while current_date <= end_date:
        game_ids = get_game_ids_for_date(current_date)

        # Loop for fetching game data
        for game_id in game_ids:
            # Fetch play-by-play data for the game
            play_by_play_data = get_play_by_play_data(game_id)

            # If data is fetched successfully, create a table for the game and insert the data
            if play_by_play_data:
                create_table(conn, game_id)
                insert_data(conn, game_id, play_by_play_data)

        # Increment the current date by 1 day
        current_date += datetime.timedelta(days=1)

    conn.close()


if __name__ == "__main__":
    main()