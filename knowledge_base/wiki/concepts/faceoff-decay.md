# Faceoff Decay

> The spike in shot rate immediately after a faceoff and its exponential decay toward steady-state levels, with zone-specific dynamics.

<!-- data-version: v2 (coordinate-independent — decay analysis uses seconds_since_faceoff and is_goal, not shot coordinates) -->
<!-- data-revalidate: If distance-based shot quality decay curves are added, re-derive from v3 data. -->

## Overview

Immediately after a faceoff, the shot rate spikes as the winning team attempts to capitalize on organized possession. This spike decays rapidly — within 5-10 seconds for offensive zone faceoffs, somewhat longer for other zones — before settling into a steady-state rate driven by open play rather than set-piece positioning.

This temporal pattern is important for xG modeling because shots taken immediately after a faceoff have different characteristics than shots from sustained offensive pressure. Post-faceoff shots are often pre-planned set plays (a quick one-timer off the draw), while steady-state shots emerge from forechecking, cycling, and transition play.

## Key Details

### Recency Bins

The project classifies time since faceoff into five bins [1]:

| Bin | Seconds Since Faceoff | Label |
|-----|----------------------:|-------|
| Immediate | 0-5s | `immediate` |
| Early | 6-15s | `early` |
| Mid | 16-30s | `mid` |
| Late | 31-60s | `late` |
| Steady state | 61s+ | `steady_state` |

These bins are defined by the `_FACEOFF_RECENCY_BINS` constant in `xg_features.py` [1]. The boundaries were chosen to capture the observed decay pattern: the sharpest drop occurs in the first 5 seconds, with diminishing change after 30 seconds.

### Post-Faceoff Window

A binary `is_post_faceoff_window` flag marks shots within 10 seconds of the last faceoff (`_POST_FACEOFF_WINDOW_SECONDS = 10`) [1]. This provides a simpler feature for models that don't need the full bin granularity.

### Zone-Specific Dynamics

The decay pattern differs by faceoff zone [2]:

- **Offensive zone (O):** Largest spike (immediate shot on a set play), fastest decay. Most of the signal is in the first 5 seconds.
- **Neutral zone (N):** Moderate spike. The winning team must still carry the puck into the offensive zone, adding a few seconds of delay.
- **Defensive zone (D):** Smallest spike. The winning team must transition the full length of the ice before generating a shot.

The `faceoff_zone_recency_interaction()` function creates combined features (e.g., `O_immediate`, `D_early`) that capture these zone-specific patterns [1].

### Tracking Implementation

Faceoff tracking resets per period [1]:

1. For each period, the code tracks the most recent faceoff event (elapsed time and zone code)
2. For each shot, `seconds_since_faceoff = shot_elapsed - faceoff_elapsed`
3. Shots before the first faceoff in a period have NULL for both `seconds_since_faceoff` and `faceoff_zone_code`

### Known Considerations

- **Faceoff win/loss not tracked:** The current schema records which zone the faceoff occurred in but not which team won the draw. A lost offensive zone faceoff can lead to a counterattack, which the model cannot distinguish from a won faceoff.
- **Multiple faceoffs:** Only the most recent faceoff per period is tracked. If a whistle and new faceoff occur shortly after a previous one, the counter resets.

## Relevance to This Project

Faceoff decay features are Phase 2 features (Component 03) stored in `shot_events.seconds_since_faceoff` and `shot_events.faceoff_zone_code` [3]. The validation notebook `notebooks/faceoff_decay_analysis.ipynb` tests whether the decay pattern is present and whether the recency bins improve xG model calibration [4].

Last verified: 2026-04-06

## Sources

[1] Feature implementation — `src/xg_features.py` (`classify_faceoff_recency()`, `faceoff_zone_recency_interaction()`, `is_post_faceoff_window()`, `_FACEOFF_RECENCY_BINS`, `_POST_FACEOFF_WINDOW_SECONDS`)
[2] Component design — `docs/xg_model_components/03_faceoff_decay_modeling.md`
[3] Shot event schema — `src/database.py` (`seconds_since_faceoff`, `faceoff_zone_code` columns)
[4] Validation notebook — `notebooks/faceoff_decay_analysis.ipynb`

## Related Pages

- [Zone Starts](zone-starts.md) — the zone context that drives different decay patterns
- [NHL API Shot Events](../data/nhl-api-shot-events.md) — where faceoff context is stored
- [Expected Goals (xG)](expected-goals-xg.md) — the model that uses faceoff decay as a feature

## Revision History

- 2026-04-06 — Created. Compiled from xg_features.py faceoff constants and component 03 design doc.
