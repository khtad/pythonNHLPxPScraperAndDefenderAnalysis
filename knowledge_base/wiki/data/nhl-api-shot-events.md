# NHL API Shot Events

> Canonical schema for individual shot events extracted from NHL play-by-play data, with normalized coordinates, game-state context, and faceoff recency.

<!-- data-version: v5 -->
<!-- data-revalidate: Re-run validation-scorecard export after shot-event contract changes or future schema bumps. -->

## Overview

The `shot_events` table is the primary analytical fact table for this project's xG modeling work. Each row represents a single shot attempt from an NHL game, extracted from the NHL Stats API play-by-play endpoint. The table combines raw event data (who shot, from where, what type) with derived features (normalized coordinates, distance/angle to goal, score state, manpower state, faceoff context).

Shot events are extracted by `xg_features.extract_shot_events()`, which iterates over the plays array from the API response and filters for four event types: `shot-on-goal`, `goal`, `missed-shot`, and `blocked-shot` [1]. Each event is enriched with contextual features computed at extraction time.

The table uses schema versioning (`event_schema_version`) to support version-aware backfill: when extraction logic changes, the version constant is bumped and stale rows are automatically detected and reprocessed [2].

## Key Details

### Schema (current: v5)

| Column | Type | Description |
|--------|------|-------------|
| `shot_event_id` | INTEGER PK | Auto-incrementing surrogate key |
| `game_id` | INTEGER NOT NULL | NHL API game identifier |
| `event_idx` | INTEGER NOT NULL | Event ID within the game (from API `eventId`) |
| `shot_event_type` | TEXT | Source event type: `shot-on-goal`, `goal`, `missed-shot`, or `blocked-shot` |
| `period` | INTEGER NOT NULL | Period number |
| `time_in_period` | TEXT NOT NULL | "MM:SS" elapsed time in period |
| `time_remaining_seconds` | INTEGER NOT NULL | Seconds remaining in the period |
| `shot_type` | TEXT NOT NULL | One of 11 valid types (see [Shot Type Taxonomy](shot-type-taxonomy.md)) |
| `x_coord` | REAL | Normalized x-coordinate (feet). NULL if API coordinates missing. |
| `y_coord` | REAL | Normalized y-coordinate (feet). NULL if API coordinates missing. |
| `distance_to_goal` | REAL | Euclidean distance to goal (feet). See [Coordinate System](coordinate-system-and-normalization.md). |
| `angle_to_goal` | REAL | Angle in degrees (0 = dead center, 90 = goal line). |
| `is_goal` | INTEGER NOT NULL | 1 if the shot resulted in a goal, 0 otherwise |
| `shooting_team_id` | INTEGER NOT NULL | Team ID of the shooting team |
| `goalie_id` | INTEGER | Opposing goalie. NULL for empty-net situations. |
| `shooter_id` | INTEGER | Player who took the shot |
| `score_state` | TEXT | Pre-shot score differential (see [Score States](score-states.md)) |
| `manpower_state` | TEXT | Skater count situation (see [Manpower States](manpower-states.md)) |
| `seconds_since_faceoff` | INTEGER | Seconds elapsed since the last faceoff in the same period |
| `faceoff_zone_code` | TEXT | Zone of the last faceoff: "O" (offensive), "D" (defensive), "N" (neutral) |
| `home_on_ice_*_player_id`, `away_on_ice_*_player_id` | INTEGER | Up to six on-ice player ids per side, used by roster/shift decomposition phases |
| `event_schema_version` | TEXT NOT NULL | Schema version that produced this row (currently "v5") |

**Uniqueness constraint:** `UNIQUE(game_id, event_idx)` — one row per event per game.

**Index:** `idx_shot_events_game_id` on `game_id` for efficient per-game queries.

### Included Event Types

The four event types captured as shot events [1]:
- `shot-on-goal` — shot that reaches the goalie or enters the net
- `goal` — shot that results in a score
- `missed-shot` — shot that misses the net entirely
- `blocked-shot` — shot blocked by a non-goalie player

### Data Quality Validation

`validate_shot_events_quality()` checks [2]:
- `shot_event_type` must be in `VALID_SHOT_EVENT_TYPES` (4 values) or NULL
- `shot_type` must be in `VALID_SHOT_TYPES` (11 values)
- `manpower_state` must be in `VALID_MANPOWER_STATES` (15 values) or NULL
- `score_state` must be in `VALID_SCORE_STATES` (7 values) or NULL
- `x_coord` must be in [-100.0, 100.0] or NULL
- `y_coord` must be in [-42.5, 42.5] or NULL
- `is_goal` must be 0 or 1
- `time_remaining_seconds` must be >= 0
- No duplicate `(game_id, event_idx)` pairs

### Known Data Quality Issues

- **Missing coordinates:** Some API events lack `xCoord`/`yCoord`. These rows have NULL for `x_coord`, `y_coord`, `distance_to_goal`, and `angle_to_goal`. They cannot be used for location-based xG features.
- **Missing `homeTeamDefendingSide` (pre-2020):** The NHL API does not provide this field for games before the 2019-2020 season. Schema v2 stored raw coordinates unchanged, resulting in ~50% of pre-2020 shots having wrong coordinates (negative x, ~150 ft average distance). Schema v3 adds a sign-based fallback heuristic that corrects ~96% of affected shots. See [Coordinate System and Normalization](coordinate-system-and-normalization.md) for full details [1][3].
- **Faceoff tracking reset per period:** `seconds_since_faceoff` is NULL for shots before the first faceoff in a period [1].
- **Historical backfill completeness bug:** The `_game_is_complete()` check once used `game_has_shot_events()` (any version) rather than `game_has_current_shot_events()` (current version), preventing stale rows from being detected. Fixed 2026-04-06 [3].
- **Validation scorecard status:** As of 2026-04-28, the local live database has 2,122,963 `shot_events` rows at schema v5 and zero stale training-eligible rows. `scripts/export_validation_scorecard.py` now exports concrete live validation results rather than stopping on stale-schema coverage; Phase 3 remains blocked by model quality/calibration/leakage criteria in the scorecard artifact [4].

## Relevance to This Project

This table is the foundation for all xG modeling work. Every feature engineering step (Phases 1-4) and model training step (Phase 3+) operates on or derives from `shot_events` rows. The schema version system ensures that when feature extraction logic changes (e.g., coordinate normalization improvements, new faceoff recency calculations), all historical data is automatically reprocessed to maintain consistency.

Last verified: 2026-04-28 (schema version v5, `_XG_EVENT_SCHEMA_VERSION` in `src/database.py`; local live database has zero stale training-eligible rows).

## Sources

[1] Shot event extraction — `src/xg_features.py` (`extract_shot_events()`, `SHOT_EVENT_TYPE_KEYS`, `normalize_coordinates()`)
[2] Schema and validation — `src/database.py` (`create_shot_events_table()`, `validate_shot_events_quality()`, `_XG_EVENT_SCHEMA_VERSION`)
[3] Shot distance diagnostic — `knowledge_base/raw/project/2026-04-06_shot-distance-diagnostic.md`, `notebooks/shot_distance_diagnostic.ipynb`
[4] Validation scorecard run — `artifacts/validation_scorecard_latest.md`, `docs/xg_model_roadmap.md`, `scripts/export_validation_scorecard.py`

## Related Pages

- [Coordinate System and Normalization](coordinate-system-and-normalization.md)
- [Shot Type Taxonomy](shot-type-taxonomy.md)
- [Score States](score-states.md)
- [Manpower States](manpower-states.md)
- [NHL API Endpoints](nhl-api-endpoints.md)

## Revision History

- 2026-04-28 — Updated. Recorded completed v5 backfill, current validation-scorecard status, and the 11-value shot type enum.
- 2026-04-28 — Updated. Refreshed schema description to v5, added `shot_event_type` and on-ice slots, and documented the partial v5 coverage blocker for Phase 2.5.3.
- 2026-04-05 — Created. Initial compilation from src/xg_features.py and src/database.py.
- 2026-04-06 — Updated. Documented v2 normalization bug, backfill completeness bug fix, and link to coordinate system article. Added source [3]. Fixed cross-references to score states and manpower states (now data articles, not concept articles). Added NHL API Endpoints link.
