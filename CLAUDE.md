# CLAUDE.md

## Project Overview

NHL Play-by-Play (PXP) scraper with a normalized player analytics schema. Raw events are scraped and stored per game, then aggregated into player/game fact and feature tables.

## Repository Structure

```
├── data/                           # Database storage directory (created at runtime)
│   └── nhl_data.db                 # SQLite database (not checked in)
├── src/
│   ├── main.py                     # Entry point; scrape loop iterating dates from 2007-10-03 to today
│   ├── nhl_api.py                  # NHL Stats API client (schedule + live feed endpoints)
│   └── database.py                 # SQLite operations for raw and normalized player schema
├── tests/
│   ├── conftest.py                 # Pytest import path setup (adds src/ to sys.path)
│   ├── test_database.py            # DB schema + data quality unit tests
│   └── test_nhl_api.py             # API parsing/error-path unit tests
├── docs/
│   └── player_database_plan.md     # Design doc driving player schema phases
├── README.md                       # Project documentation
└── requirements.txt                # Dependencies
```

## Database Path Constants

Defined in `database.py` and imported by `main.py`:

- `DATABASE_DIR` — absolute path to the `data/` directory at project root
- `DATABASE_FILENAME` — `"nhl_data.db"`
- `DATABASE_PATH` — full absolute path: `data/nhl_data.db`

`main.main()` ensures `DATABASE_DIR` exists via `os.makedirs` before connecting.

## Architecture & Data Flow

```
main.main()
  → nhl_api.get_weekly_schedule(date)
  → nhl_api.get_play_by_play_data(game_id)
  → database.create_table(conn, game_id)                  # raw game_<id>
  → database.insert_data(conn, game_id, data)             # raw events

player-schema bootstrap
  → database.ensure_player_database_schema(conn)
     → create_core_dimension_tables(conn)                 # players/games/teams
     → create_player_game_stats_table(conn)               # one row per player+game
     → create_player_game_features_table(conn)            # rolling materialized features
```

## Player Schema Details

- `players(player_id PRIMARY KEY, first_name, last_name, shoots_catches, position, team_id)`
- `games(game_id PRIMARY KEY, game_date, season, home_team_id, away_team_id)`
- `teams(team_id PRIMARY KEY, team_abbrev, team_name)`
- `player_game_stats(..., PRIMARY KEY(player_id, game_id))`
  - Includes `position_group`, `toi_seconds`, counting stats, and xG placeholders
  - Indexes:
    - `idx_player_game_stats_game_id`
    - `idx_player_game_stats_position_group_game_id`
- `player_game_features(..., PRIMARY KEY(player_id, game_id))`
  - Includes rolling/rank placeholders and `feature_set_version`

## Data Quality Validation

`validate_player_game_stats_quality(conn, max_toi_seconds=3600)` checks:

- duplicate `(player_id, game_id)` rows
- negative TOI
- TOI above a configurable maximum
- invalid `position_group` outside `{F, D, G}`

## Testing Notes

- Framework: `pytest` + in-memory SQLite + request mocks
- The player-schema tests are written in phase style (Phase 2-5 from the design doc)
- **How to run tests**: Use `python3 -m venv /tmp/test-venv && /tmp/test-venv/bin/pip install -q pytest requests && /tmp/test-venv/bin/python -m pytest -q` (or reuse the venv if it already exists: `/tmp/test-venv/bin/python -m pytest -q`). Do not call `pytest` directly — the system Python does not have pytest installed.
- **Notebook dependencies**: When creating or modifying Jupyter notebooks, automatically install any required packages (e.g., `matplotlib`, `seaborn`, `numpy`, `ipykernel`) into the project virtual environment at `/tmp/test-venv` using `/tmp/test-venv/bin/pip install`. Do not assume packages are already installed — always install before first use.

## Test Failures Encountered, Fixes, and Prevention Rules

1. **Failure:** `ImportError` during pytest collection for newly referenced player-schema functions.
   - **Cause:** Tests were added first (TDD) before implementing the new functions in `database.py`.
   - **Fix:** Implemented missing schema functions:
     - `create_core_dimension_tables`
     - `create_player_game_stats_table`
     - `create_player_game_features_table`
     - `validate_player_game_stats_quality`
     - `ensure_player_database_schema`
   - **Rules to avoid repeat failures of this type:**
     - Add tests first for new behavior, then immediately implement all imported function stubs before running the full suite.
     - Run `pytest -q` after adding new imports to detect collection-time errors early.
     - Keep phase-based function names stable between tests and implementation to avoid naming drift.

2. **Failure:** Notebook analyses pointed at the correct `nhl_data.db`, but analysis tables were empty because the database contained only raw `game_<id>` tables and the scraper skipped those games before backfilling metadata and `shot_events`.
   - **Cause:** The scraper treated `is_game_collected(conn, game_id)` as equivalent to "fully processed", even though derived tables (`games`, `shot_events`, `game_context`, etc.) were still missing. A related catalog-scan bug also matched the `games` dimension table with `LIKE 'game_%'`.
   - **Fix:** Added a shared game-processing state check so a game is only skipped when raw rows, metadata, and derived shot rows all exist; added an explicit idempotent backfill entry point; restricted raw-table scans to names matching `game_<digits>` only.
   - **Rules to avoid repeat failures of this type:**
     - Treat raw ingestion and derived-data population as separate completeness checks. A game is not "done" unless raw rows and all required derived rows for the current pipeline stage exist.
     - Any scraper change that adds a new derived table or feature extraction step must also add or update a backfill path for existing databases. Never assume historical databases can be repaired from future incremental runs alone.
     - Backfill code must be idempotent by construction and by test: rerunning it against an already repaired database must perform no additional inserts and should avoid repeat API fetches for complete games.
     - When scanning `sqlite_master` for raw game tables, never rely on `LIKE 'game_%'` alone. Always filter to the stricter pattern `game_<digits>` so dimension tables such as `games` are never misclassified as raw event tables.
     - Notebook analysis instructions must not treat the presence of a large database file or raw game tables as evidence that analysis tables are populated. Include an explicit refresh/backfill step or note whenever notebooks depend on derived tables.

## Derived-Data Versioning & Backfill

Each derived table stores a schema version in every row, recording which code version produced it:

| Table | Version constant | Column |
|-------|-----------------|--------|
| `shot_events` | `_XG_EVENT_SCHEMA_VERSION` (database.py) | `event_schema_version` |
| `game_context` | `_GAME_CONTEXT_SCHEMA_VERSION` (database.py) | `context_schema_version` |
| `player_game_features` | `_FEATURE_SET_VERSION` (database.py) | `feature_set_version` |

**How version-aware backfill works:**

1. `_get_game_processing_state()` uses `game_has_current_shot_events()`, which checks both row existence AND `event_schema_version = _XG_EVENT_SCHEMA_VERSION`.
2. If rows exist but at an older version, the game is flagged as needing reprocessing.
3. `_process_game()` deletes stale-version rows via `delete_game_shot_events()` before re-inserting with the current version.
4. Running `backfill_missing_game_data()` automatically detects and replaces all stale rows.

**When to bump a version constant:**

Any change to code that affects the **values** written to a derived table requires a version bump. Examples:
- Changing coordinate normalization, distance/angle calculation, or any feature extraction logic (`xg_features.py`)
- Adding, removing, or redefining a column in a derived table
- Changing how manpower state, score state, or faceoff context is classified
- Fixing a bug in data parsing that changes what gets stored

Changes that do **not** require a version bump:
- Refactoring that doesn't change output values (renaming internal variables, extracting helpers)
- Adding new derived tables (they have their own version constant)
- Changes to raw event ingestion (`create_table`/`insert_data`) — raw tables have no version column

## Pre-Submission Checklist

- **Unreachable code**: Check all control paths in every modified function for unreachable code. Verify that no statements follow unconditional `return`, `raise`, `break`, or `continue` within the same block, and that mutually exclusive conditions (e.g., `!= 200` then `== 200`) don't leave dead code after the final branch.
- **Interface simplicity**: Review all new or modified function signatures and module boundaries. Minimize the number of parameters, avoid unnecessary configuration options, and prefer simple interfaces over flexible ones. If a function can accomplish its job with fewer arguments or a narrower return type, simplify it before submitting.
- **Backfill impact check**: If any modified function changes the values written to a derived table (`shot_events`, `game_context`, `player_game_features`), bump the corresponding version constant in `database.py`. The version-aware backfill will automatically detect stale rows and reprocess them on the next run.

## Development Guardrails

- **Check conceptual PR scope before starting new work**: At the start of any new interaction, evaluate whether the requested work belongs in the same conceptual basket as the changes since the previous pull request. If it does not, stop before making code changes and ask the user how they want to handle the new chunk of work that would need to move through the PR process separately.
- Keep SQL identifiers validated and quoted when dynamic.
- **Validate all external input used in SQL**: Never interpolate raw strings into SQL — not even for column names. Values must use parameterized queries (`?` placeholders). Identifiers (table/column names) that originate from external input (API responses, user arguments, dict keys) must pass through `_quote_identifier`, which rejects anything that isn't `^\w+$`. If a function accepts a dict and uses its keys as column names, those keys must be validated or drawn from a known-safe allowlist before being spliced into the query string.
- Prefer normalized schema additions over duplicating raw event rows.
- Any new player feature should be derivable from `player_game_stats` and materialized into `player_game_features`.
- **No magic numbers or strings**: Never use bare numeric or string literals inline. Always define a descriptively named constant (e.g., `_GAME_API_MIN_INTERVAL = 2`, `NHL_FIRST_GAME_DATE = datetime.date(2007, 10, 3)`) and reference that constant in code and tests.
- **No duplicated logic across functions**: When two functions hit the same endpoint, parse the same structure, or build the same SQL, one must delegate to the other or both must call a shared helper. Never copy-paste a function body with minor variations.
- **Batch SQL operations**: Use `cursor.executemany` for multi-row inserts. Never build and execute the same parameterized query in a Python loop when the query text is identical across iterations. Hoist query construction outside loops.
- **Reuse HTTP connections**: Use `requests.Session` (module-level `_session`) for all HTTP calls to the same host. Never use bare `requests.get()` — it creates a new TCP+TLS connection per call. Mock tests should target `_session.get` via `@patch.object`, not `requests.get`.
- **Minimize round-trips in existence checks**: Prefer a single query with exception handling over multi-step check-then-act patterns (e.g., checking `sqlite_master` then querying the table). Use `SELECT 1 ... LIMIT 1` with `try/except OperationalError`.
- **Single-query catalog scans**: When reading metadata from `sqlite_master`, fetch all needed columns (`name, sql`, etc.) in one query. Never query the catalog in a loop (N+1 pattern).
- **Extract shared schema definitions**: If the same column list or DDL fragment appears in more than one SQL statement (e.g., `create_table` and a migration function), define it as a module-level constant and reference it everywhere.
- **Name parameters after what callers pass**: If every caller passes a game ID, name the parameter `game_id`, not `table_name`. Internal prefixing (e.g., `game_`) should happen inside the function via a helper like `_game_table_name(game_id)`.
- **Idempotent collection tracking**: `mark_date_collected` must only set `completed_at` when `games_collected >= games_found`. Incomplete dates (`completed_at IS NULL`) signal that the scraper should retry. `get_last_collected_date` must check for incomplete dates and return a resume point before the earliest incomplete date, ensuring no game data is permanently skipped.
- **Notebook path setup**: In Jupyter notebooks, never use `os.path.abspath("__file__")` — `"__file__"` is a string literal, not the `__file__` variable, and notebooks don't have `__file__` anyway. Instead, use CWD-based detection to find `src/`:
  ```python
  for _candidate in [os.path.join(os.getcwd(), "src"),
                     os.path.join(os.getcwd(), "..", "src")]:
      _candidate = os.path.abspath(_candidate)
      if os.path.isdir(_candidate) and _candidate not in sys.path:
          sys.path.insert(0, _candidate)
          break
  ```
  This handles both CWD=project root (VS Code default) and CWD=notebooks/.
