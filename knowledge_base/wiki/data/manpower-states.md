# Manpower States

> The 15 valid skater-count situations parsed from NHL API situation codes, their frequency distribution, and impact on shot quality.

<!-- data-version: v2 (coordinate-independent — counts and goal rates are unaffected by v3 normalization fix) -->

## Overview

NHL games feature varying numbers of skaters per side due to penalties, extra-attacker situations, and overtime rules. The manpower state — expressed as a string like "5v5" (shooting team skaters vs opposing team skaters) — is one of the most important contextual features for xG modeling. Power-play situations (5v4) generate higher-quality chances due to numerical advantage, while short-handed situations (4v5) produce lower shot volumes but sometimes high-danger breakaway opportunities.

The manpower state is derived from the NHL API's 4-digit `situationCode` field, which encodes goalies and skaters for both teams. The `parse_situation_code()` function in `xg_features.py` extracts skater counts, and `classify_manpower_state()` maps them to one of 15 recognized states [1]. The state is relative to the shooting team: "5v4" always means the shooting team has the advantage.

## Key Details

### Situation Code Format

The NHL API attaches a 4-digit `situationCode` to each play event [1]:

```
Position:  [0]           [1]            [2]            [3]
Meaning:   away_goalie   away_skaters   home_skaters   home_goalie
Values:    0 or 1        0-6            0-6            0 or 1
```

Example: `"1551"` = away goalie in, 5 away skaters, 5 home skaters, home goalie in (standard 5v5).

The project extracts only the skater counts (positions 1 and 2), then orients them relative to the shooting team [1].

### Valid Manpower States

| State | Shooting / Opposing | Situation | Count | Goals | Goal Rate |
|-------|--------------------:|-----------|------:|------:|----------:|
| `5v5` | 5 / 5 | Even strength | 1,479,555 | 86,011 | 5.81% |
| `5v4` | 5 / 4 | Power play | 268,944 | 24,615 | 9.15% |
| `4v5` | 4 / 5 | Short-handed | 46,043 | 3,329 | 7.23% |
| `4v4` | 4 / 4 | 4-on-4 even strength | 34,451 | 2,346 | 6.81% |
| `6v5` | 6 / 5 | Extra attacker (pulled goalie) | 31,005 | 2,385 | 7.69% |
| `3v3` | 3 / 3 | Overtime (post-2015) | 15,134 | 2,037 | 13.46% |
| `5v3` | 5 / 3 | Two-man advantage | 10,006 | 1,548 | 15.47% |
| `5v6` | 5 / 6 | Opposing extra attacker | 9,261 | 5,598 | 60.45% |
| `4v3` | 4 / 3 | Power play during 4-on-4 | 5,567 | 673 | 12.09% |
| `6v4` | 6 / 4 | Extra attacker + power play | 4,501 | 411 | 9.13% |
| `4v6` | 4 / 6 | Short-handed vs extra attacker | 676 | 355 | 52.51% |
| `3v5` | 3 / 5 | Two-man disadvantage | 348 | 16 | 4.60% |
| `3v4` | 3 / 4 | Short-handed during 4-on-4 | 310 | 31 | 10.00% |
| `6v3` | 6 / 3 | Extra attacker + two-man advantage | 134 | 20 | 14.93% |
| `3v6` | 3 / 6 | Two-man disadvantage vs extra attacker | 4 | 0 | 0.00% |

Counts are from the full database (2007-2026, schema v2 data) [3].

### Notable Patterns

- **Empty-net inflation:** The `5v6` and `4v6` states (opposing team has pulled their goalie) show extreme goal rates (60% and 52%) because most shots at an empty net score. These shots need special treatment in xG models — either separate modeling or exclusion [3].
- **3v3 overtime:** The 13.46% goal rate reflects the wide-open play of post-2015 overtime, where space and odd-man rushes are frequent. This state only exists in overtime periods [3].
- **Power play effect:** 5v4 (9.15%) vs 5v5 (5.81%) represents a ~58% relative increase in goal rate, confirming the large effect of numerical advantage [3].
- **Rare states:** `3v6`, `3v5`, `6v3`, and `3v4` have very small sample sizes (<400 shots). Statistical conclusions about these states are unreliable [3].

### NULL Handling

The manpower state is NULL when the `situationCode` is missing from the API response or cannot be parsed. NULL rows are excluded from manpower-stratified analyses but retained in the overall dataset [2].

## Relevance to This Project

Manpower state is a first-tier xG feature (Phase 1, Component 01) [4]. The xG model should segment or interact on manpower state because the relationship between shot location and goal probability changes substantially across states. The `CLAUDE.md` statistical rigor requirements specify that per-segment calibration must be checked separately for even strength, power play, and short-handed situations, with max subgroup calibration error < 3 percentage points.

Empty-net situations (5v6, 4v6) are a known modeling challenge: they should either be modeled separately with a near-1.0 expected goal probability or excluded from the primary xG model entirely.

Last verified: 2026-04-06

## Sources

[1] Situation code parsing — `src/xg_features.py` (`parse_situation_code()`, `classify_manpower_state()`)
[2] Validation and storage — `src/database.py` (`VALID_MANPOWER_STATES`, `validate_shot_events_quality()`)
[3] Frequency analysis — query against `data/nhl_data.db` shot_events table, 2026-04-06
[4] Component design — `docs/xg_model_components/01_shot_and_state_features.md`

## Related Pages

- [NHL API Shot Events](nhl-api-shot-events.md) — schema and storage of shot events
- [Shot Type Taxonomy](shot-type-taxonomy.md) — another categorical shot feature

## Revision History

- 2026-04-06 — Created. Compiled from xg_features.py parsing logic, database.py enum, and frequency analysis.
