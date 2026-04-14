# Coordinate System and Normalization

> NHL rink coordinate conventions, the normalization process that orients all shots toward the +x goal, and known data gaps by era.

<!-- data-version: v2 -->
<!-- data-revalidate: After v3 backfill, rerun negative-x-rate queries by era to confirm fix worked. Update the "Historical Data Quality Impact" table with v3 actual results. Update "Current status" in Relevance section. -->

## Overview

The NHL Stats API reports shot locations as (x, y) coordinates on a standard rink surface. The rink is centered at (0, 0) with the long axis along x and the short axis along y. The two goals sit at approximately (89, 0) and (-89, 0). Teams switch attacking direction after each period, so the same team's offensive-zone shots appear at positive x in one period and negative x in the next.

To make coordinates comparable across teams, periods, and games, this project normalizes all shot coordinates so the shooting team always attacks toward +x. The goal target is fixed at (89, 0) after normalization, and distance/angle calculations use this reference point [1].

The normalization depends on the `homeTeamDefendingSide` field from the NHL API, which indicates which end the home team defends in a given play. This field is available starting approximately the 2019-2020 season. For older games where it is absent, a sign-based heuristic is used as a fallback [1].

## Key Details

### Rink Dimensions

| Measurement | Value | Source |
|-------------|-------|--------|
| Full rink length | 200 ft (x: -100 to +100) | NHL standard [3] |
| Full rink width | 85 ft (y: -42.5 to +42.5) | NHL standard [3] |
| Goal line x-position | +/- 89 ft | NHL standard [3] |
| Blue line x-position | +/- 25 ft from center | NHL standard [3] |
| Center line | x = 0 | NHL standard [3] |

Coordinate bounds enforced in validation [2]:
- `x_coord`: [-100.0, +100.0]
- `y_coord`: [-42.5, +42.5]

### Normalization Logic

The `normalize_coordinates()` function in `src/xg_features.py` [1]:

1. **When `homeTeamDefendingSide` is available** (post-2020 games):
   - If `defending_side == "left"`: home team attacks toward +x, away toward -x
   - If `defending_side == "right"`: home team attacks toward -x, away toward +x
   - Coordinates are flipped `(-x, -y)` when the shooting team attacks toward -x

2. **When `homeTeamDefendingSide` is `None`** (pre-2020 games, v3 fallback):
   - If raw `x < 0`: flip to `(-x, -y)`, assuming the shot was toward the -x goal
   - If raw `x >= 0`: keep as-is

### Distance and Angle Formulas

After normalization, the shooting team always attacks the goal at (89, 0) [1]:

- **Distance:** `sqrt((x - 89)^2 + y^2)` — Euclidean distance in feet
- **Angle:** `atan2(|y|, 89 - x)` in degrees — 0 = dead center, 90 = goal line, >90 = behind net

### `homeTeamDefendingSide` API Field

| Era | Availability | Values | Behavior |
|-----|-------------|--------|----------|
| Pre-2020 (seasons before 20192020) | Absent (`None` for all plays) | N/A | Fallback heuristic used [4] |
| 2019-2020 onward | Present on every play | `"left"` or `"right"` | Alternates per period (e.g., right → left → right) [4] |

The field is attached to each play object in the API response, not to the game or period level. It changes value between periods to reflect teams switching ends [4].

### Known Limitations of the Sign-Based Fallback

The v3 heuristic (`if x < 0, flip`) is correct for the ~96% of shots taken in the offensive zone (near the attacking goal). It fails for shots taken from behind center ice (~4% of shots) [4]:

- A team attacking toward +x with a shot from behind center (raw `x < 0`): **incorrectly flipped** to positive x (appears close to goal instead of far away)
- A team attacking toward -x with a shot from behind center (raw `x > 0`): **incorrectly kept** at positive x (appears close to goal instead of far away)

These are predominantly long-range, low-danger events. The error inflates their computed distance_to_goal rather than deflating it, so they do not contaminate high-danger shot analysis.

### Historical Data Quality Impact (v2 Bug)

Schema v2 stored raw coordinates unchanged when `homeTeamDefendingSide` was absent, affecting all pre-2020 seasons (~1.3M shots) [4]:

| Metric | v2 (buggy) | v3 (with fallback) |
|--------|-----------|-------------------|
| Pre-2020 negative x rate | ~50% | ~0% (all flipped to positive) |
| Pre-2020 avg distance (negative x shots) | ~150 ft | Corrected to ~35 ft |
| Pre-2020 goal rate at "150 ft" | 6.9% (impossible) | N/A (fixed) |
| Post-2020 (unaffected) | ~2% negative x | ~2% negative x |

The v3 backfill (running `backfill_missing_game_data()`) reprocesses all games with the corrected normalization. A completeness-check bug that prevented the backfill from detecting stale v2 rows was fixed on 2026-04-06 [4].

## Relevance to This Project

Coordinate normalization is upstream of every location-based feature in the xG model: distance to goal, angle to goal, shot zone classification, and any future spatial features. Errors in normalization propagate directly into training data quality.

**Current status:** A v3 backfill is in progress as of 2026-04-06 to reprocess all pre-2020 shot events with the corrected normalization heuristic. Post-2020 data is unaffected.

**Model training implication:** Pre-2020 data, even after v3 backfill, has a ~4% residual error rate from the sign-based heuristic. Options include: (a) using all data with awareness of this limitation, (b) weighting post-2020 data more heavily, or (c) excluding pre-2020 data from location-sensitive features while retaining it for non-spatial features.

Last verified: 2026-04-06

## Sources

[1] Normalization and distance functions — `src/xg_features.py` (`normalize_coordinates()`, `compute_distance_to_goal()`, `compute_angle_to_goal()`, `GOAL_X_COORD`, `GOAL_Y_COORD`)
[2] Coordinate bounds and validation — `src/database.py` (`NORMALIZED_X_COORD_MIN/MAX`, `NORMALIZED_Y_COORD_MIN/MAX`, `validate_shot_events_quality()`)
[3] NHL rink dimensions — standard NHL playing surface (200 x 85 ft, goals at 89 ft from center)
[4] Shot distance diagnostic — `knowledge_base/raw/project/2026-04-06_shot-distance-diagnostic.md`, `notebooks/shot_distance_diagnostic.ipynb`

## Related Pages

- [NHL API Shot Events](nhl-api-shot-events.md)
- [NHL API Endpoints](nhl-api-endpoints.md) — the play-by-play endpoint that provides coordinates and `homeTeamDefendingSide`

## Revision History

- 2026-04-06 — Created. Compiled from xg_features.py normalization logic, database.py validation bounds, and shot distance diagnostic notebook findings.
