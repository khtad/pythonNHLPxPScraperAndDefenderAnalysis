# NHL Play-by-Play Scraper (Clean Restart)

This project scrapes NHL play-by-play (PXP) data from NHL.com and stores it in SQLite. It now also includes a normalized player analytics schema based on `docs/player_database_plan.md`.

## Scope

- Fetch game IDs by date from the NHL Stats API
- Fetch play-by-play events for each game
- Store each game in `nhl_data.db` as table `game_<game_id>`
- Maintain normalized player analytics tables for player/game modeling workflows

## Project structure

- `main.py`: scrape loop from a start date through today
- `nhl_api.py`: NHL API calls for schedules and PXP feeds
- `database.py`: SQLite connection, raw game table creation, and player-schema helpers
- `docs/player_database_plan.md`: player database design document used for schema phases

## Player database schema (normalized)

Following the design plan, schema support is organized in implementation phases:

1. **Raw events layer**: per-game `game_<game_id>` tables (existing ingestion layer)
2. **Core dimensions**: `players`, `games`, `teams`
3. **Player-game fact table**: `player_game_stats` with one row per `(player_id, game_id)` and supporting indexes
4. **Rolling features table**: `player_game_features` with materialized rolling/rank features
5. **Quality checks**: `validate_player_game_stats_quality()` for duplicate keys, TOI bounds, and position-group validation

Use `ensure_player_database_schema(conn)` to initialize all normalized player tables.

## Requirements

- Python 3.8+
- SQLite (included with standard Python)
- Python dependencies in `requirements.txt`

## Installation

```bash
pip install -r requirements.txt
```

This installs runtime dependencies (`requests`) and test dependencies (`pytest`).

## Usage

```bash
python main.py
```

`main.py` currently scrapes from `2007-10-03` through today and stores results in `nhl_data.db`.

## Testing

Run automated tests with:

```bash
pytest -q
```

Coverage includes:

- Raw table safety and deduplication tests
- Collection log tests
- Player-schema phase tests (dimensions, fact table, feature table, data quality checks)
- NHL API parsing/error-path tests using mocks

No live NHL API calls are made during tests.

## Notes

- A full historical scrape can take a long time and issue many API requests.
- Existing tables are preserved because inserts use `CREATE TABLE IF NOT EXISTS` per game.
