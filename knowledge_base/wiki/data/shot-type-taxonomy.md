# Shot Type Taxonomy

> The 10 recognized shot types in the NHL API, their definitions, frequency distribution, and relevance to xG modeling.

<!-- data-version: v2 (coordinate-independent — counts and goal rates are unaffected by v3 normalization fix) -->

## Overview

Every shot event in the NHL play-by-play feed is tagged with a `shotType` field describing the technique used. This project recognizes 10 valid shot types, defined in the `VALID_SHOT_TYPES` constant [1]. Shot type is one of the strongest categorical predictors of goal probability — tip-ins and deflections convert at roughly double the rate of slap shots due to reduced goalie reaction time and unpredictable trajectories.

The shot type value comes directly from the NHL API's `details.shotType` field on shot-on-goal, goal, missed-shot, and blocked-shot events [2]. The API occasionally introduces new shot type strings (e.g., `between-legs`) that are not yet in the project's validation enum; these are flagged by `validate_shot_events_quality()` [1].

## Key Details

### Recognized Shot Types

| Shot Type | Description | Count | Goals | Goal Rate |
|-----------|-------------|------:|------:|----------:|
| `wrist` | Standard wrist shot; quick release, moderate power | 1,045,625 | 74,317 | 7.11% |
| `slap` | Full windup slap shot; high velocity, longer release | 374,369 | 16,652 | 4.45% |
| `snap` | Hybrid between wrist and slap; quick release with more power | 314,838 | 25,300 | 8.04% |
| `backhand` | Shot from the backhand side of the blade | 160,724 | 15,069 | 9.38% |
| `tip-in` | Redirect of a teammate's shot near the crease | 138,463 | 14,376 | 10.38% |
| `deflected` | Unintentional redirect off a player or equipment | 41,648 | 4,242 | 10.19% |
| `wrap-around` | Attempt from behind the net, wrapping the puck around the post | 20,184 | 1,081 | 5.36% |
| `poke` | Poke check or stick extension attempt on a loose puck | 1,834 | 247 | 13.47% |
| `bat` | Baseball-style swing at an airborne puck | 1,786 | 227 | 12.71% |
| `cradle` | Lacrosse-style scoop and tuck | 35 | 6 | 17.14% |

Counts are from the full database (2007-2026, schema v2 data) [3].

### Validation Enum vs API Values

The validation constant `VALID_SHOT_TYPES` in `database.py` uses `"deflection"`, but the NHL API returns `"deflected"` for this shot type. The validation function `validate_shot_events_quality()` will flag `"deflected"` rows as invalid unless the enum is updated [1]. Additionally, the API value `"between-legs"` (314 shots in the database) is not in the enum [3].

### Goal Rate Patterns

Shot types cluster into three tiers by conversion rate [3]:

- **High conversion (10-17%):** tip-in, deflected, poke, bat, cradle — close-range or redirect shots with reduced goalie preparation time
- **Medium conversion (7-9%):** wrist, snap, backhand, between-legs — standard shooting techniques with moderate release times
- **Low conversion (4-5%):** slap, wrap-around — high-distance or low-angle attempts

These tiers suggest that shot type encodes both technique and shot context (distance, traffic, goalie readiness), making it a useful but partially confounded xG feature.

## Relevance to This Project

Shot type is a first-tier feature in the xG model (Phase 1, Component 01) [4]. It is stored in the `shot_events.shot_type` column and validated at ingestion time [1][2]. The goal rate variation across types (4.45% to 17.14%) represents substantial predictive signal, but the feature is correlated with distance and angle — tip-ins and deflections cluster near the crease while slap shots are taken from further out. The xG model should include shot type alongside distance/angle to capture the residual effect of technique after controlling for location.

Last verified: 2026-04-06

## Sources

[1] Validation enum and quality checks — `src/database.py` (`VALID_SHOT_TYPES`, `validate_shot_events_quality()`)
[2] Shot event extraction — `src/xg_features.py` (`extract_shot_events()`, `SHOT_EVENT_TYPE_KEYS`)
[3] Frequency analysis — query against `data/nhl_data.db` shot_events table, 2026-04-06
[4] Component design — `docs/xg_model_components/01_shot_and_state_features.md`

## Related Pages

- [NHL API Shot Events](nhl-api-shot-events.md) — schema and storage of shot events
- [Coordinate System and Normalization](coordinate-system-and-normalization.md) — shot location features that interact with shot type

## Revision History

- 2026-04-06 — Created. Compiled from database.py enum, xg_features.py extraction, and frequency analysis.
