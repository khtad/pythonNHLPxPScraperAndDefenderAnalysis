# NHL Play-by-Play Scraper (Clean Restart)

This project is now focused on one purpose only: scrape NHL play-by-play (PXP) data from NHL.com and store it in SQLite.

## Scope

- Fetch game IDs by date from the NHL Stats API
- Fetch play-by-play events for each game
- Store each game in `nhl_data.db` as table `game_<game_id>`

## Project structure

- `main.py`: scrape loop from a start date through today
- `nhl_api.py`: NHL API calls for schedules and PXP feeds
- `database.py`: SQLite connection, table creation, and inserts

## Requirements

- Python 3.8+
- SQLite (included with standard Python)
- Python dependencies in `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

`main.py` currently scrapes from `2007-10-03` through today and stores results in `nhl_data.db`.

## Notes

- A full historical scrape can take a long time and issue many API requests.
- Existing tables are preserved because inserts use `CREATE TABLE IF NOT EXISTS` per game.
