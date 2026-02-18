# Player Database Design Plan

## Recommendation at a Glance

Do **not** copy every play-by-play row into each player's table.

Instead:

1. Keep a **single canonical events layer** (your existing play-by-play game/event tables).
2. Add a **normalized player-game feature layer** keyed by `(player_id, game_id)`.
3. Build rolling metrics from that feature layer (materialized tables or views).

This avoids data duplication, keeps lineage clear, and makes recomputation of new features straightforward.

---

## Why not duplicate each event row per player?

Duplicating event rows across player tables creates several long-term problems:

- **Storage explosion**: one event can involve multiple players; copying per player multiplies rows quickly.
- **Update complexity**: if parsing logic changes, all duplicated player tables must be re-written.
- **Inconsistent truth**: duplicated copies can drift from source events.
- **Feature agility loss**: adding a new feature should be a query/recompute, not a full ETL rewrite.

Best practice is to treat event data as the source of truth and derive player features downstream.

---

## Target data model (SQLite-friendly)

### 1) Raw event tables (already present)

- Existing per-game raw table pattern: `game_<game_id>`.
- Keep as your ingestion layer.

### 2) Core dimension tables

- `players(player_id PRIMARY KEY, first_name, last_name, shoots_catches, position, team_id, ... )`
- `games(game_id PRIMARY KEY, game_date, season, home_team_id, away_team_id, ... )`
- `teams(team_id PRIMARY KEY, team_abbrev, team_name, ... )`

### 3) Event participation bridge (optional but powerful)

- `event_players(game_id, event_idx, player_id, role, team_id, on_ice_flag, PRIMARY KEY(game_id, event_idx, player_id, role))`

Use this if you parse richer event JSON and need clean joins from events to players.

### 4) Player-game fact table (main analytics table)

- `player_game_stats(player_id, game_id, team_id, position_group, toi_seconds, goals, assists, shots, blocks, hits, penalties_drawn, penalties_taken, faceoff_wins, faceoff_losses, xgf, xga, ... , PRIMARY KEY(player_id, game_id))`

This is where each player has one row per game and where your model features live.

### 5) Rolling/rank feature table (materialized)

- `player_game_features(player_id, game_id, season, game_number_for_player, toi_rank_pos_5g, toi_rank_pos_10g, toi_rolling_mean_5g, points_rolling_10g, ... , PRIMARY KEY(player_id, game_id))`

This can be rebuilt from `player_game_stats` as feature definitions evolve.

---

## Feature computation strategy

For your use case (e.g., rolling TOI rank by position):

1. Define **position groups**: `F`, `D`, `G` in `player_game_stats.position_group`.
2. For each game date (or game_id order), compute per-position ranks among active players.
3. Compute rolling windows on prior games only (to avoid leakage), such as:
   - `toi_rolling_mean_5g`
   - `toi_rank_pos_5g`
4. Persist results in `player_game_features`.

If SQLite window functions are available, use `ROW_NUMBER()`, `RANK()`, `AVG() OVER (...)`.
Otherwise compute in Python/pandas and upsert back.

---

## Suggested implementation phases

### Phase 1: Stabilize source schema

- Keep raw game tables intact.
- Add canonical IDs in parsing (at minimum: `game_id`, `event_idx`, `event_type`, player IDs where available).

### Phase 2: Build normalized entities

- Create `players`, `games`, `teams`.
- Backfill from existing data and API metadata.

### Phase 3: Build player-game stats

- Create ETL job that aggregates raw events to one row per `(player_id, game_id)`.
- Add basic indexes:
  - `player_game_stats(player_id, game_id)`
  - `player_game_stats(game_id)`
  - `player_game_stats(position_group, game_id)`

### Phase 4: Build rolling features

- Add a deterministic feature pipeline with a clear cutoff rule (only prior games).
- Materialize into `player_game_features`.
- Version feature definitions (e.g., `feature_set_version` column).

### Phase 5: Validation & monitoring

- Add data-quality checks:
  - no duplicate `(player_id, game_id)`
  - TOI non-negative and bounded
  - position group in `{F, D, G}`
- Add spot-check queries for known players/games.

---

## Practical answer to your direct question

From a design perspective, it is better to **query/aggregate from the existing events database** than to copy each event row into each player's table.

Use:

- event tables as immutable raw source,
- a player-game table for modeled stats/features,
- a rolling-feature table for fast training/inference reads.

This structure gives you scalability, reproducibility, and easier feature evolution.
