import datetime
import sqlite3

from nhl_api import get_game_ids_for_date, get_play_by_play_data
from database import create_table, insert_data, create_connection
from center_analysis import (calculate_faceoffs_per_minute, update_elo_ratings, identify_center_by_elo)

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

    database = "nhl_data.db"
    game_id = "2007020003"

    faceoffs_per_minute = calculate_faceoffs_per_minute(database, game_id)

    # Initialize Elo ratings for players
    elo_ratings = {player_id: 1500 for player_id in faceoffs_per_minute.keys()}

    # Update Elo ratings based on faceoff outcomes
    updated_elo_ratings = update_elo_ratings(database, game_id, elo_ratings)

    # Identify the center using Elo ratings
    center = identify_center_by_elo(updated_elo_ratings)

    print(f"The center in game {game_id} is player {center}.")

if __name__ == "__main__":
    main()