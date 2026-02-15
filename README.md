# NHL Play-by-Play Scraper and Analysis

This project collects NHL play-by-play data from the NHL Stats API, stores it in SQLite, and includes analysis helpers for player/lineup performance.

## What the project currently does

- Scrapes NHL game IDs by date and downloads play-by-play events
- Stores each game in SQLite (`nhl_data.db`) as a separate table (`game_<game_id>`)
- Logs API errors to `error_log.txt`
- Includes center-identification logic using faceoff-derived Elo calculations (`center_analysis.py`)
- Includes additional team/defenseman helper functions in `data_processing.py` and `nhl_api.py`

## Project structure

- `main.py`: end-to-end ingestion loop and example center-identification run
- `nhl_api.py`: NHL API requests and parsing helpers
- `database.py`: SQLite table creation and inserts
- `center_analysis.py`: faceoff rates and Elo-based center identification
- `data_processing.py`: game/team performance helper functions
- `error_handling.py`: simple file-based error logger

## Tech Stack

- Python 3.8+
- SQLite (bundled with standard Python installations)
- Python packages listed in `requirements.txt`

## Project Layout

1. Clone the repository.
2. Open a terminal in the project directory.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

### Nightly update example

Run the main pipeline:

```bash
python main.py
```

By default, `main.py`:

- Pulls game data from 2007-10-03 through today
- Writes game events into `nhl_data.db`
- Runs an example center-identification workflow for game `2007020003`

## Notes

- The full historical scrape can take a long time and make many API calls.
- If API requests fail, details are appended to `error_log.txt`.
