# Zone Starts

> How the location of a faceoff (offensive, defensive, or neutral zone) affects subsequent shot generation and quality.

<!-- data-version: v2 (coordinate-independent — zone start analysis uses faceoff_zone_code, not shot coordinates) -->
<!-- data-revalidate: If post-faceoff shot distance analysis is added, re-derive from v3 data. -->

## Overview

A "zone start" refers to the location of a faceoff that initiates a shift or sequence of play. Faceoffs in the offensive zone (O) give the winning team immediate possession near the opponent's goal, while defensive zone (D) faceoffs start play near the team's own goal. Neutral zone (N) faceoffs are at center ice after goals, period starts, or offsides.

Zone starts matter for player evaluation because coaches deploy different players in different zones. Top offensive players may receive a disproportionate share of offensive zone starts, inflating their raw shot metrics. Conversely, defensive specialists absorb more defensive zone starts, depressing their numbers. Without controlling for zone starts, player evaluation metrics confound deployment decisions with player ability.

For xG modeling, the faceoff zone provides context about the sequence that generated a shot — a shot 8 seconds after an offensive zone faceoff is a qualitatively different event than the same shot after a neutral zone faceoff.

## Key Details

### Zone Codes

The NHL API tags each faceoff with a `zoneCode` in the event details [1]:

| Code | Meaning | Typical Outcome |
|------|---------|----------------|
| `O` | Offensive zone | High shot probability in the next 5-10 seconds |
| `D` | Defensive zone | Low shot probability; team must transition through neutral zone |
| `N` | Neutral zone | Moderate; often after goals or period starts |

### Interaction with Faceoff Decay

Zone starts interact strongly with the post-faceoff time window. The shot rate spike after an offensive zone faceoff is much larger than after a neutral or defensive zone faceoff, and it decays faster (see [Faceoff Decay](faceoff-decay.md)). The project captures this interaction via the `faceoff_zone_code` and `seconds_since_faceoff` columns in `shot_events` [2].

The `faceoff_zone_recency_interaction()` function creates combined features like `O_immediate` (offensive zone, 0-5 seconds since faceoff) for use as model inputs [1].

### Zone Start Adjustment in Player Evaluation

In player evaluation contexts (RAPM), zone starts are typically handled by:

1. **Inclusion as a covariate:** Adding zone-start proportion to the RAPM design matrix
2. **Filtering:** Excluding the first N seconds after a faceoff from shot-based metrics
3. **Separate modeling:** Building separate xG models for post-faceoff and sustained-play shots

This project uses approach (1) via the faceoff context features [3].

## Relevance to This Project

Zone start data is stored in `shot_events.faceoff_zone_code` and analyzed in `notebooks/zone_start_signal.ipynb` [2][4]. The zone-recency interaction feature (`O_immediate`, `D_early`, etc.) is a Phase 2 feature that captures the joint effect of faceoff zone and time elapsed [1].

Last verified: 2026-04-06

## Sources

[1] Faceoff feature functions — `src/xg_features.py` (`classify_faceoff_recency()`, `faceoff_zone_recency_interaction()`, `is_post_faceoff_window()`)
[2] Shot event schema — `src/database.py` (`faceoff_zone_code`, `seconds_since_faceoff` columns)
[3] Component design — `docs/xg_model_components/02_rest_travel_and_zone_context.md`
[4] Validation notebook — `notebooks/zone_start_signal.ipynb`

## Related Pages

- [Faceoff Decay](faceoff-decay.md) — the temporal dynamics of post-faceoff shot rates
- [NHL API Shot Events](../data/nhl-api-shot-events.md) — where zone start data is stored
- [Expected Goals (xG)](expected-goals-xg.md) — the model that uses zone context as a feature

## Revision History

- 2026-04-06 — Created. Compiled from xg_features.py faceoff functions and component design docs.
