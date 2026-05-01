# Shot Type Taxonomy

> The 11 recognized shot types in the NHL API, their definitions, frequency distribution, and relevance to xG modeling.

<!-- data-version: v5 (coordinate-independent counts from current shot_events) -->

## Overview

Every shot event in the NHL play-by-play feed is tagged with a `shotType` field describing the technique used. This project recognizes 11 valid shot types, defined in the `VALID_SHOT_TYPES` constant [1]. Shot type is one of the strongest categorical predictors of goal probability — tip-ins and deflections convert at roughly double the rate of slap shots due to reduced goalie reaction time and unpredictable trajectories.

The shot type value comes directly from the NHL API's `details.shotType` field on shot-on-goal, goal, missed-shot, and blocked-shot events [2]. The validation enum now accepts the current live values observed in v5 `shot_events`, including `deflected` and `between-legs` [1][3].

## Key Details

### Recognized Shot Types

| Shot Type | Description | Count | Goals | Goal Rate |
|-----------|-------------|------:|------:|----------:|
| `wrist` | Standard wrist shot; quick release, moderate power | 1,055,241 | 75,025 | 7.11% |
| `slap` | Full windup slap shot; high velocity, longer release | 377,218 | 16,763 | 4.44% |
| `snap` | Hybrid between wrist and slap; quick release with more power | 320,947 | 25,833 | 8.05% |
| `backhand` | Shot from the backhand side of the blade | 162,351 | 15,217 | 9.37% |
| `tip-in` | Redirect of a teammate's shot near the crease | 140,712 | 14,519 | 10.32% |
| `deflected` | Unintentional redirect off a player or equipment | 41,989 | 4,288 | 10.21% |
| `wrap-around` | Attempt from behind the net, wrapping the puck around the post | 20,314 | 1,087 | 5.35% |
| `poke` | Poke check or stick extension attempt on a loose puck | 1,921 | 253 | 13.17% |
| `bat` | Baseball-style swing at an airborne puck | 1,901 | 233 | 12.26% |
| `between-legs` | Shot released between the shooter's legs | 332 | 28 | 8.43% |
| `cradle` | Lacrosse-style scoop and tuck | 37 | 6 | 16.22% |

Counts are from the full live database after v5 backfill (2007-2026, 2,122,963 `shot_events` rows) [3].

### Validation Enum vs API Values

The validation constant `VALID_SHOT_TYPES` in `database.py` now matches the live API values observed in `shot_events`: it uses `"deflected"` rather than the unused `"deflection"` spelling and includes `"between-legs"` [1][3].

### Goal Rate Patterns

Shot types cluster into three tiers by conversion rate [3]:

- **High conversion (10-17%):** tip-in, deflected, poke, bat, cradle — close-range or redirect shots with reduced goalie preparation time
- **Medium conversion (7-9%):** wrist, snap, backhand, between-legs — standard shooting techniques with moderate release times
- **Low conversion (4-5%):** slap, wrap-around — high-distance or low-angle attempts

These tiers suggest that shot type encodes both technique and shot context (distance, traffic, goalie readiness), making it a useful but partially confounded xG feature.

## Relevance to This Project

Shot type is a first-tier feature in the xG model (Phase 1, Component 01) [4]. It is stored in the `shot_events.shot_type` column and validated at ingestion time [1][2]. The goal rate variation across types (4.45% to 17.14%) represents substantial predictive signal, but the feature is correlated with distance and angle — tip-ins and deflections cluster near the crease while slap shots are taken from further out. The xG model should include shot type alongside distance/angle to capture the residual effect of technique after controlling for location.

Last verified: 2026-04-28

## Sources

[1] Validation enum and quality checks — `src/database.py` (`VALID_SHOT_TYPES`, `validate_shot_events_quality()`)
[2] Shot event extraction — `src/xg_features.py` (`extract_shot_events()`, `SHOT_EVENT_TYPE_KEYS`)
[3] Frequency analysis — query against `data/nhl_data.db` shot_events table after v5 backfill, 2026-04-28
[4] Component design — `docs/xg_model_components/01_shot_and_state_features.md`

## Related Pages

- [NHL API Shot Events](nhl-api-shot-events.md) — schema and storage of shot events
- [Coordinate System and Normalization](coordinate-system-and-normalization.md) — shot location features that interact with shot type

## Revision History

- 2026-04-28 — Updated. Refreshed counts from v5 `shot_events` and recorded that `VALID_SHOT_TYPES` now accepts `deflected` and `between-legs`.
- 2026-04-06 — Created. Compiled from database.py enum, xg_features.py extraction, and frequency analysis.
