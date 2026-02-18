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
└── .gitignore        # Git ignore rules (IDE files, .db files, virtualenvs)
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
- Table names are dynamically constructed and safely quoted via `_quote_identifier()`, which validates the name against `^\w+$` and wraps it in double quotes per the SQLite identifier-quoting convention

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
- **Testing**: See the Testing Strategy section below for planned test coverage

## Known Limitations

- `create_connection()` returns `None` on failure, but `main()` does not guard against this — a connection error will raise `AttributeError` on the first database call rather than producing a clear error message
- `insert_data()` interpolates column names from dictionary keys into SQL without validation; `_quote_identifier()` is only applied to table names. This is currently safe because the column names originate from hard-coded string literals in `nhl_api.py`, but the function's interface does not enforce that
- No retry logic on API calls — transient network errors cause silent data gaps
- No logging framework — all diagnostic output goes through `print()` to stdout with no severity levels or configurability

## Testing Strategy

### Framework

Use `pytest` with the standard library `unittest.mock` for mocking. No additional test dependencies beyond `pytest` itself.

### Why not 100% coverage?

100% test coverage is not a worthwhile objective for this project. The codebase is small and procedural, and several functions sit at boundaries where tests would provide little value:

- **`main()`** is pure orchestration glue. Testing it requires mocking both the API and database layers simultaneously, producing tests that duplicate the implementation rather than verifying behavior. Changes to `main()` would require parallel changes to its tests, adding maintenance cost without catching real bugs.
- **`create_connection()`** is a thin wrapper around `sqlite3.connect()`. Its success path tests the standard library; its failure path (returning `None`) is a known limitation, not behavior to enshrine as correct.
- **Rate-limiting logic** in `get_play_by_play_data()` depends on global mutable state and `time.sleep()`. It is simple enough to verify by inspection, and testing it requires patching multiple time functions for low payoff.

The goal is to cover the code that is most likely to break in ways that matter: data parsing, identifier safety, and database read/write correctness.

### Functions to test

#### `database.py` — test with in-memory SQLite (`sqlite3.connect(":memory:")`)

| Function | What to test |
|---|---|
| `_quote_identifier(name)` | Valid word-character names return double-quoted strings; names containing spaces, semicolons, quotes, or empty strings raise `ValueError` |
| `create_table(conn, table_name)` | Table `game_{table_name}` exists after call; calling twice does not raise (idempotency); `UNIQUE(period, time, event, description)` constraint is present in the created schema |
| `insert_data(conn, table_name, data_list)` | Rows are retrievable after insert; duplicate rows are silently ignored (`INSERT OR IGNORE`) rather than raising |
| `create_collection_log_table(conn)` | `collection_log` table exists with expected columns after call |
| `is_game_collected(conn, game_id)` | Returns `False` when table does not exist; returns `False` when table exists but is empty; returns `True` when table has rows |
| `mark_date_collected(conn, date_str, games_found, games_collected)` | Row is present in `collection_log` after call; calling again with the same date replaces the row (`INSERT OR REPLACE`) |
| `get_last_collected_date(conn)` | Returns `None` on an empty `collection_log`; returns the most recent date when multiple entries exist |
| `is_date_range_collected(conn, start_date, end_date)` | Returns `True` when every date in the range has a completed entry; returns `False` when any date is missing |
| `deduplicate_existing_tables(conn)` | Duplicate rows are removed; the `UNIQUE` constraint is present after migration; tables that already have the constraint are left untouched |

#### `nhl_api.py` — test with `unittest.mock.patch` on `requests.get`

| Function | What to test |
|---|---|
| `get_game_ids_for_date(date)` | Returns list of game IDs from well-formed schedule JSON; returns `[]` on non-200 status; returns `[]` when `dates` list is empty |
| `get_play_by_play_data(game_id)` | Returns correctly shaped list of dicts from well-formed live-feed JSON; returns `None` on non-200 status; returns `[]` when `allPlays` is empty; handles missing nested keys (e.g., no `about` or `result` in a play) gracefully |

## Testing Implementation Status

- Implemented the strategy in `tests/test_database.py` and `tests/test_nhl_api.py`.
- Added test path bootstrap in `tests/conftest.py` so pytest can reliably import project modules from the repository root.
- Verified logical-unit and mockup tests complete successfully via `pytest -q` (`25 passed`).

### Test Errors Encountered During Implementation

1. **Pytest collection import errors (`ModuleNotFoundError` for `database` and `nhl_api`)**
   - Cause: Running tests from the repository root did not automatically place the project root on `sys.path` in this environment.
   - Resolution: Added `tests/conftest.py` to insert the repository root into `sys.path` before tests import modules.

### Rules to Prevent Similar Future Test-Writing Errors

- Add an explicit pytest import-path setup (e.g., `tests/conftest.py` or equivalent packaging config) before writing module-level imports in test files.
- Run a quick `pytest -q` smoke test immediately after creating the first test file to catch collection-time issues early.
- Keep tests isolated from runtime side effects by using in-memory SQLite and `unittest.mock.patch` for network calls.

## Pre-Submission Checklist

- **Unreachable code**: Check all control paths in every modified function for unreachable code. Verify that no statements follow unconditional `return`, `raise`, `break`, or `continue` within the same block, and that mutually exclusive conditions (e.g., `!= 200` then `== 200`) don't leave dead code after the final branch.
- **Interface simplicity**: Review all new or modified function signatures and module boundaries. Minimize the number of parameters, avoid unnecessary configuration options, and prefer simple interfaces over flexible ones. If a function can accomplish its job with fewer arguments or a narrower return type, simplify it before submitting.

## Development Notes

- The project was recently refactored (commit `583fb1e`) to remove analysis code (`center_analysis.py`, `data_processing.py`, `error_handling.py`) and focus purely on data scraping
- The `main` branch is the primary branch
- No CI/CD pipeline configured
- No linter or formatter configuration
