# Rest and Travel Effects

> How rest days between games, travel distance, and timezone crossing affect team performance and shot quality.

<!-- data-version: v2 (coordinate-independent — rest/travel features use game_context table, not shot coordinates) -->
<!-- data-revalidate: No changes needed after v3 backfill unless distance-stratified rest effects are added. -->

## Overview

NHL teams play 82 regular season games across 7 months, frequently traveling thousands of kilometers between arenas in different timezones. The physical toll of travel and insufficient rest is hypothesized to affect performance through fatigue, disrupted sleep, and reduced practice time. Back-to-back games (playing on consecutive nights) are the most extreme case, with the second game often showing measurable performance degradation.

For xG modeling, rest and travel effects provide team-level context features. A team playing its third game in four nights on the road should have its shot quality expectations adjusted downward relative to a well-rested home team.

## Key Details

### Rest Days

The `compute_rest_days()` function calculates the integer number of days between consecutive games for each team [1]. Key classifications:

| Rest Days | Label | Frequency |
|----------:|-------|-----------|
| 1 | Back-to-back | ~15-18% of games |
| 2 | Normal rest | ~50% of games |
| 3+ | Extended rest | ~30% of games |

The `is_back_to_back()` function returns a binary flag for 1-day rest [1].

### Travel Distance

The `haversine_distance()` function computes great-circle distance between arenas using latitude/longitude from the arena reference data [1][2]. This gives the straight-line distance in kilometers — actual travel distance is typically longer but strongly correlated.

### Timezone Delta

The `compute_timezone_delta()` function computes the difference between the away team's home timezone and the game venue's timezone [1]. Positive values mean the away team traveled east (body clock is earlier than local time); negative means westward travel.

Research in other sports suggests eastward travel is more disruptive than westward, but evidence in hockey is mixed. The maximum NHL timezone crossing is 3 hours (Eastern to Pacific).

### Comparative Rest

The most analytically useful rest feature is the difference between the two teams' rest days (comparative rest), not absolute rest. A team on 1-day rest facing another team on 1-day rest is in a different situation than the same team facing one with 3 days of rest.

### Multicollinearity Warning

The `game_context` table stores all three of `home_rest_days`, `away_rest_days`, and `rest_advantage`. By construction `rest_advantage = home_rest_days - away_rest_days` for every row, so the three columns are linearly dependent. A Phase 2 VIF review confirmed this empirically against the live database [5]: the two source columns produce VIF ≈ 1.00 when regressed against each other, but including all three simultaneously drives the VIF of `rest_advantage` (and of each source column) to ∞. Any design matrix built from `game_context` must include at most two of the three — typically the two source columns, or `rest_advantage` paired with a single baseline such as `home_rest_days`. Back-to-back indicators (`home_is_back_to_back`, `away_is_back_to_back`) and travel features (`travel_distance_km`, `timezone_delta`) are not linearly dependent on the rest triple and can be included alongside whichever rest pair is chosen.

The same review measured pipeline health via `validate_game_context_quality()` [6]. Structural nulls (the first game of each team's season, where no prior game exists) are exempt by design. After that exemption, non-structural nulls on travel and timezone columns sit at 1.07% of rows (281 / 26 343), just above the 1% acceptance target. The gap is a data-completeness issue tracked under Phase 2.5.5, not a multicollinearity concern.

### Known Confounders

- **Home/away:** Travel effects are confounded with home-ice advantage (crowd, last change, favorable matchups). Models must include a home indicator alongside travel features.
- **Schedule strength:** Teams with more back-to-backs may also face weaker opponents if the schedule is structured that way.
- **Season timing:** Late-season fatigue accumulates, making rest effects potentially non-linear over the season.

## Relevance to This Project

Rest and travel features are Phase 2, Component 02 [3]. They are stored in the `game_context` table and computed from the `games` table combined with `arena_reference.py` data [2]. The validation notebook `notebooks/rest_travel_analysis.ipynb` tests whether these features show measurable effects on shot quality and game outcomes [4].

Deferred feature work includes schedule density metrics (3-in-4, 4-in-6 game windows) and cumulative travel burden — these are gated on basic rest/travel validation showing signal.

Last verified: 2026-04-19

## Sources

[1] Feature functions — `src/xg_features.py` (`compute_rest_days()`, `is_back_to_back()`, `haversine_distance()`, `compute_timezone_delta()`)
[2] Arena reference — `src/arena_reference.py` (`ARENA_DATA`)
[3] Component design — `docs/xg_model_components/02_rest_travel_and_zone_context.md`
[4] Validation notebook — `notebooks/rest_travel_analysis.ipynb`
[5] VIF helper — `src/stats_helpers.py` (`compute_vif()`, `VIF_THRESHOLD`); Phase 2 findings block in `docs/xg_model_roadmap.md`.
[6] Game-context validator — `src/database.py` (`validate_game_context_quality()`)

## Related Pages

- [Arena and Venue Reference](../data/arena-venue-reference.md) — the geographic data used for travel computation
- [Expected Goals (xG)](expected-goals-xg.md) — the model that uses rest/travel as contextual features
- [Venue and Scorekeeper Bias](venue-scorekeeper-bias.md) — another venue-level effect that interacts with travel patterns

## Revision History

- 2026-04-19 — Added Multicollinearity Warning (rest_advantage is a perfect linear combination of home/away rest) and recorded the 1.07% travel/timezone null rate from `validate_game_context_quality` as a Phase 2.5.5 item. Sources [5] and [6] added.
- 2026-04-06 — Created. Compiled from xg_features.py travel functions, arena_reference.py, and component 02 design doc.
