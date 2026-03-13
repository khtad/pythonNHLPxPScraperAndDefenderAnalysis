# NHL Play-by-Play Scraper

Scrapes NHL play-by-play (PXP) data from the NHL Stats API and stores it in SQLite. Includes a normalized player analytics schema and the foundations for an expected goals (xG) model.

## Scope

- Fetch weekly schedules and play-by-play events from the NHL Stats API (`api-web.nhle.com`)
- Store each game's events in `nhl_data.db` as table `game_<game_id>`
- Resume interrupted scrapes without re-downloading completed games or skipping failed dates
- Maintain normalized player analytics tables for player/game modeling workflows
- Provide a canonical shot events schema for xG model development

## Project structure

```
src/
  main.py           Scrape loop with weekly pagination from 2007-10-03 to today
  nhl_api.py        NHL Stats API client (schedule + play-by-play endpoints)
  database.py       SQLite operations: raw events, collection tracking, player schema, xG schema
tests/
  conftest.py       Pytest path setup
  test_database.py  Schema, collection log, and data quality tests
  test_main.py      Scraper loop integration tests
  test_nhl_api.py   API parsing and error-path tests
  test_xg_schema.py xG Phase 0 schema and validation tests
docs/
  player_database_plan.md          Player schema design doc
  xg_model_roadmap.md              xG model development roadmap
  xg_model_components/             Detailed component design docs
  strength_estimation_approaches.md Team strength estimation approaches
```

## Collection tracking and resume

The scraper tracks progress in a `collection_log` table. Each date records how many games were found and how many were successfully collected:

- **Idempotent completion**: `completed_at` is only set when all games for a date succeed. Partial failures leave the date incomplete.
- **Resume from failures**: On restart, the scraper resumes from the earliest incomplete date, not the latest complete one, so no games are permanently skipped.
- **Per-game deduplication**: Already-collected games are skipped individually, so retrying an incomplete date only re-fetches the games that failed.
- **Legacy data migration**: `fix_incomplete_collection_log` runs at startup to correct any historical rows where `completed_at` was incorrectly set despite incomplete collection.

## Database schema

### Raw events layer

Per-game `game_<game_id>` tables with a `UNIQUE(period, time, event, description)` constraint. Legacy tables without the constraint are automatically deduplicated and migrated on startup.

### Player analytics (normalized)

Initialize with `ensure_player_database_schema(conn)`:

- **`players`**, **`games`**, **`teams`** — core dimension tables
- **`player_game_stats`** — one row per `(player_id, game_id)` with counting stats, TOI, and xG placeholders
- **`player_game_features`** — materialized rolling/rank features with `feature_set_version` tracking

### xG Phase 0: shot events

Initialize with `ensure_xg_schema(conn)`:

- **`shot_events`** — canonical shot event table with coordinates, shot type, score/manpower state, and `event_schema_version` for training reproducibility
- **Data contracts**: validated enums for shot types, manpower states, score states, and NHL rink coordinate bounds
- **`validate_shot_events_quality()`** — checks shot type, manpower/score state, coordinate ranges, is_goal values, time remaining, and duplicate events

### Data quality validation

- `validate_player_game_stats_quality()` — duplicate keys, negative/excessive TOI, invalid position groups
- `validate_shot_events_quality()` — invalid enums, out-of-range coordinates, negative time, duplicate events
- Both validators use shared helpers with parameterized queries and quoted identifiers

## Security

- All dynamic SQL identifiers are validated through `_quote_identifier` (rejects non-word characters)
- Column names from dict keys in `insert_data` are validated before use in queries
- All values use parameterized queries (`?` placeholders)

## Requirements

- Python 3.8+
- SQLite (included with standard Python)
- `requests` (runtime), `pytest` (testing) — see `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
cd src
python main.py
```

Scrapes from `2007-10-03` through today, storing results in `nhl_data.db`. The scraper automatically resumes from where it left off on subsequent runs.

## Testing

```bash
python3 -m venv /tmp/test-venv && /tmp/test-venv/bin/pip install -q pytest requests
/tmp/test-venv/bin/python -m pytest -q
```

Or if the venv already exists:

```bash
/tmp/test-venv/bin/python -m pytest -q
```

80 tests covering:

- Raw table creation, deduplication, and unique constraints
- Collection log idempotency (incomplete dates, retries, resume logic)
- Player-schema phases (dimensions, fact table, feature table, quality checks)
- xG Phase 0 (shot events DDL, validation paths, NULL coordinate handling)
- NHL API parsing, error paths, rate limiting, and session reuse
- Scraper loop pagination, date filtering, and resume behavior

No live NHL API calls are made during tests.

## Notes

- A full historical scrape issues many API requests; the built-in rate limiter spaces game API calls by 2 seconds.
- HTTP connections are reused via `requests.Session` to reduce TCP/TLS overhead.
- All SQL identifiers from external input are validated before use.
