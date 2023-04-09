# NHL Data Analysis

This project retrieves and stores NHL play-by-play game data from the 2007-2008 season to the present day. It analyzes team performance, focusing on how a team performs with and without its top defenseman in the lineup. The project uses Python for data collection, processing, and analysis, and SQLite for data storage.

## Features

- Fetch play-by-play game data from the NHL API
- Store game data in an SQLite database
- Identify the top defenseman for each team
- Calculate team performance metrics, including shooting percentage for unblocked shots, save percentage at different strengths, and marginal goals scored and conceded per game while missing the top defenseman
- Retrieve data for specific games from the SQLite database

## Requirements

- Python 3.6 or higher
- Requests library
- Beautiful Soup library
- SQLite

## Installation

1. Clone the repository:
    ```
    git clone https://github.com/yourusername/nhl-data-analysis.git

2. Change directory to the project folder:
    ```
    cd nhl-data-analysis

3. Install the required Python libraries:
    ```
    pip install -r requirements.txt

## Usage

1. Run the `main.py` script to fetch and store NHL play-by-play game data:
    ```
    python main.py

2. Use the `team_performance` function to analyze team performance for specific games:
    ```
    from team_performance import team_performance

    database = "nhl_data.db"
    game_id = "2007020003"
    team_id = 5
    top_defenseman_id = 33

    performance_data = team_performance(database, game_id, team_id, top_defenseman_id)
    print(performance_data)

Replace `game_id`, `team_id`, and `top_defenseman_id` with appropriate values for the game and team you want to analyze.

---
