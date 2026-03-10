# NHL Play-by-Play Scraper & Player Analytics

Scrapes NHL play-by-play (PXP) event data from the NHL Stats API and stores it in SQLite. Includes a normalized player analytics schema for player/game modeling workflows.

## Repository structure

```
├── src/
│   ├── main.py          # Entry point; scrape loop with resume support
│   ├── nhl_api.py       # NHL Stats API client (schedule + PXP endpoints)
│   └── database.py      # SQLite operations: raw events + normalized player schema
├── tests/
│   ├── conftest.py      # Pytest import path setup (adds src/ to sys.path)
│   ├── test_database.py # DB schema and data quality unit tests
│   └── test_nhl_api.py  # API parsing and error-path unit tests
├── docs/
│   └── player_database_plan.md  # Player schema design document
├── README.md
└── requirements.txt
```

## Data flow

```
main.main()
  → nhl_api.get_weekly_schedule(date)          # fetch a week of game IDs in one call
  → nhl_api.get_play_by_play_data(game_id)     # fetch PXP events (rate-limited: 2s between calls)
  → database.create_table(conn, game_id)       # create game_<id> table if not exists
  → database.insert_data(conn, game_id, data)  # insert events (deduped via UNIQUE constraint)
  → database.mark_date_collected(conn, ...)    # log completed date for resume support

Player schema bootstrap (call once after connecting):
  → database.ensure_player_database_schema(conn)
```

## Raw event schema

Each game is stored in a table named `game_<game_id>` with columns:

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment row ID |
| `period` | INTEGER | Period number |
| `time` | TEXT | Time elapsed in period |
| `event` | TEXT | Event type key |
| `description` | TEXT | Event description |

A `UNIQUE(period, time, event, description)` constraint prevents duplicate events on re-ingestion.

## Collection log

`collection_log` tracks progress per date:

| Column | Description |
|---|---|
| `date` | Date string (PK) |
| `games_found` | Number of games on that date |
| `games_collected` | Number successfully ingested |
| `completed_at` | ISO timestamp of completion |

The scraper resumes from the day after the last fully-collected date on restart.

## Normalized player schema

`ensure_player_database_schema(conn)` creates all tables below.

### Dimension tables

- **`players`** — `player_id`, `first_name`, `last_name`, `shoots_catches`, `position`, `team_id`
- **`games`** — `game_id`, `game_date`, `season`, `home_team_id`, `away_team_id`
- **`teams`** — `team_id`, `team_abbrev`, `team_name`

### `player_game_stats`

One row per `(player_id, game_id)`. Counting stats and xG placeholders:

`toi_seconds`, `goals`, `assists`, `shots`, `blocks`, `hits`, `penalties_drawn`, `penalties_taken`, `faceoff_wins`, `faceoff_losses`, `xgf`, `xga`

Indexes: `idx_player_game_stats_game_id`, `idx_player_game_stats_position_group_game_id`

Valid values for `position_group`: `F` (forward), `D` (defenseman), `G` (goalie)

### `player_game_features`

Materialized rolling features per `(player_id, game_id)`:

`season`, `game_number_for_player`, `toi_rank_pos_5g`, `toi_rank_pos_10g`, `toi_rolling_mean_5g`, `points_rolling_10g`, `feature_set_version`

### Data quality validation

```python
from database import validate_player_game_stats_quality

results = validate_player_game_stats_quality(conn, max_toi_seconds=3600)
# returns dict with: duplicate_player_game_rows, negative_toi_rows,
#                    toi_above_max_rows, invalid_position_group_rows
```

## Requirements

- Python 3.8+
- SQLite (bundled with Python)

```bash
pip install -r requirements.txt
```

Dependencies: `requests` (HTTP), `pytest` (tests).

## Usage

```bash
cd src
python main.py
```

Scrapes from `2007-10-03` (earliest available NHL API data) through today and stores results in `nhl_data.db`. On restart, the scraper resumes automatically from the last completed date.

## Testing

```bash
pytest -q
```

No live NHL API calls are made during tests (all HTTP is mocked). Coverage includes:

- Raw table creation, deduplication, and `INSERT OR IGNORE` behavior
- Collection log tracking and resume logic
- Player schema: dimension tables, fact table, feature table, data quality checks
- API schedule parsing and error-path handling

## Notes

- A full historical scrape (2007 to present) issues many thousands of API requests and will take a significant amount of time.
- The API client uses a persistent `requests.Session` and enforces a 2-second minimum interval between game endpoint calls to avoid overwhelming the NHL API.
- Raw game tables use `CREATE TABLE IF NOT EXISTS`, so re-running the scraper is safe and idempotent.
