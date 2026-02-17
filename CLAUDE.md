# CLAUDE.md

## Project Overview

NHL Play-by-Play (PXP) Data Scraper. Fetches play-by-play event data from the NHL Stats API and stores it in a local SQLite database. Pure data collection utility — no analysis or visualization.

## Repository Structure

```
├── main.py           # Entry point; scrape loop iterating dates from 2007-10-03 to today
├── nhl_api.py        # NHL Stats API client (schedule + live feed endpoints)
├── database.py       # SQLite operations (connection, table creation, inserts)
├── requirements.txt  # Python dependencies (requests)
├── README.md         # Project documentation
└── .idea/            # JetBrains IDE configuration (tracked in git)
```

## Architecture & Data Flow

```
main.main()
  → nhl_api.get_game_ids_for_date(date)     # GET statsapi.web.nhl.com/api/v1/schedule
  → nhl_api.get_play_by_play_data(game_id)  # GET statsapi.web.nhl.com/api/v1/game/{id}/feed/live
  → database.create_table(conn, game_id)     # CREATE TABLE IF NOT EXISTS game_{game_id}
  → database.insert_data(conn, game_id, data) # INSERT rows into game_{game_id}
```

Each game gets its own SQLite table named `game_<game_id>` with columns:
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT)
- `period` (INTEGER)
- `time` (TEXT) — period time
- `event` (TEXT) — event type
- `description` (TEXT) — event description

The database file is `nhl_data.db` (generated at runtime, not committed).

## Setup & Running

```bash
pip install -r requirements.txt
python main.py
```

Requires Python 3.8+. The only external dependency is `requests`.

## Key Technical Details

### API Endpoints Used
- Schedule: `https://statsapi.web.nhl.com/api/v1/schedule?date={date}`
- Live feed: `https://statsapi.web.nhl.com/api/v1/game/{game_id}/feed/live`

### Database
- SQLite via Python's built-in `sqlite3` module
- One persistent connection for the entire scrape run
- Tables use `CREATE TABLE IF NOT EXISTS` for idempotency (re-runs won't fail on existing tables, but will insert duplicate rows)
- Table names are dynamically constructed with f-strings: `f"game_{game_id}"`

### Error Handling
- API errors print to stdout and return empty list / None
- Database errors caught via `sqlite3.Error`
- No retry logic on API calls

### Rate Limiting
- Game API calls (`get_play_by_play_data`) are rate-limited to one call per 15 seconds
- Enforced via `time.monotonic()` tracking in `nhl_api.py`
- Schedule API calls (`get_game_ids_for_date`) are not rate-limited

## Code Conventions

- **Style**: Procedural / function-based. No classes.
- **Naming**: snake_case for all functions and variables
- **Imports**: Standard library first, then third-party, then local modules
- **Error reporting**: `print()` statements (no logging framework)
- **No tests**: The project has no test suite or testing framework

## Known Limitations

- No `.gitignore` at repository root (IDE `.idea/` directory is tracked)
- Duplicate data on re-run: `INSERT` has no deduplication checks
- Table names constructed via f-string (not parameterized) — safe only because `game_id` comes from the NHL API as an integer

## Pre-Submission Checklist

- **Unreachable code**: Check all control paths in every modified function for unreachable code. Verify that no statements follow unconditional `return`, `raise`, `break`, or `continue` within the same block, and that mutually exclusive conditions (e.g., `!= 200` then `== 200`) don't leave dead code after the final branch.
- **Interface simplicity**: Review all new or modified function signatures and module boundaries. Minimize the number of parameters, avoid unnecessary configuration options, and prefer simple interfaces over flexible ones. If a function can accomplish its job with fewer arguments or a narrower return type, simplify it before submitting.

## Development Notes

- The project was recently refactored (commit `583fb1e`) to remove analysis code (`center_analysis.py`, `data_processing.py`, `error_handling.py`) and focus purely on data scraping
- The `main` branch is the primary branch
- No CI/CD pipeline configured
- No linter or formatter configuration
