# CLAUDE.md

## Project Overview

NHL Play-by-Play (PXP) scraper with a normalized player analytics schema. Raw events are scraped and stored per game, then aggregated into player/game fact and feature tables.

## Repository Structure

```
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

## Architecture & Data Flow

```
main.main()
  → nhl_api.get_game_ids_for_date(date)
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

## Pre-Submission Checklist

- **Unreachable code**: Check all control paths in every modified function for unreachable code. Verify that no statements follow unconditional `return`, `raise`, `break`, or `continue` within the same block, and that mutually exclusive conditions (e.g., `!= 200` then `== 200`) don't leave dead code after the final branch.
- **Interface simplicity**: Review all new or modified function signatures and module boundaries. Minimize the number of parameters, avoid unnecessary configuration options, and prefer simple interfaces over flexible ones. If a function can accomplish its job with fewer arguments or a narrower return type, simplify it before submitting.

## Development Guardrails

- Keep SQL identifiers validated and quoted when dynamic.
- Prefer normalized schema additions over duplicating raw event rows.
- Any new player feature should be derivable from `player_game_stats` and materialized into `player_game_features`.
