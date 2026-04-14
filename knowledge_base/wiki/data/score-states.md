# Score States

> The 7 score-differential buckets used to classify game context at shot time, their behavioral effects on shot volume and quality.

<!-- data-version: v2 (coordinate-independent — counts and goal rates are unaffected by v3 normalization fix) -->

## Overview

The score state captures the shooting team's position relative to the opposing team at the moment a shot is taken. It is one of the most well-documented contextual effects in hockey analytics: trailing teams take more shots (pressing to equalize) while leading teams take fewer but higher-quality shots (selective shooting from favorable positions). This asymmetry means that raw shot counts overstate trailing-team performance, and xG models must account for score state to avoid systematic bias.

The score state is derived from a running tally of goals tracked by `_track_score()` in `xg_features.py` [1]. Each shot event records the *pre-shot* score (not the post-goal score for goal events), ensuring the feature reflects the game context at decision time rather than the outcome.

## Key Details

### Score State Buckets

| State | Score Differential | Count | Goals | Goal Rate |
|-------|-------------------:|------:|------:|----------:|
| `tied` | 0 | 771,724 | 54,303 | 7.04% |
| `up1` | +1 | 347,259 | 27,209 | 7.84% |
| `down1` | -1 | 400,664 | 26,378 | 6.58% |
| `up2` | +2 | 154,785 | 14,195 | 9.17% |
| `down2` | -2 | 191,926 | 12,763 | 6.65% |
| `up3plus` | +3 or more | 103,853 | 8,473 | 8.16% |
| `down3plus` | -3 or more | 129,609 | 8,222 | 6.34% |

Counts are from the full database (2007-2026, schema v2 data) [3].

### Classification Logic

The `classify_score_state()` function [1] computes `shooting_score - opposing_score` and maps the differential:

| Differential | State |
|-------------:|-------|
| 0 | `tied` |
| +1 | `up1` |
| +2 | `up2` |
| >= +3 | `up3plus` |
| -1 | `down1` |
| -2 | `down2` |
| <= -3 | `down3plus` |

The "+3 or more" and "-3 or more" buckets collapse large differentials because games with 4+ goal leads are rare and behaviorally similar to 3-goal leads [1].

### Score Effects on Shot Behavior

Two well-known patterns are visible in the data [3]:

**1. Volume asymmetry:** Trailing teams take more shots than leading teams at each differential level. At 1-goal differential: 400,664 shots when down vs 347,259 when up (~15% more). This reflects trailing teams' increased offensive urgency.

**2. Quality asymmetry:** Leading teams have higher goal rates at every differential level. At 1-goal: 7.84% when up vs 6.58% when down. At 2-goal: 9.17% when up vs 6.65% when down. Leading teams can afford to be selective, taking shots only from favorable positions, while trailing teams take lower-quality shots under time pressure.

### Pre-Shot Score Tracking

Goal events in the NHL API provide post-goal scores in their `details` object. The `_track_score()` function builds a parallel array of (home_score, away_score) tuples, where each entry reflects the score *before* that event [1]. This ensures:

- A goal scored to make it 2-1 is recorded with score state `tied` (pre-goal score was 1-1)
- The next shot after that goal sees score state `up1` or `down1`

### NULL Handling

Score state is NULL only when the scoring logic fails (e.g., missing team IDs). This is extremely rare in practice [2].

## Relevance to This Project

Score state is a first-tier xG feature (Phase 1, Component 01) [4]. It should be included as a categorical feature or interaction term in the xG model. The calibration analysis must check per-segment calibration separately by score state, as required by the statistical rigor framework in `CLAUDE.md`.

The volume/quality asymmetry also has implications for RAPM estimation (Phase 3): players who see more ice time in trailing situations will have inflated shot volumes but deflated shot quality, and the model must account for this to avoid biased player impact estimates.

Last verified: 2026-04-06

## Sources

[1] Score tracking and classification — `src/xg_features.py` (`_track_score()`, `classify_score_state()`)
[2] Validation and storage — `src/database.py` (`VALID_SCORE_STATES`, `validate_shot_events_quality()`)
[3] Frequency analysis — query against `data/nhl_data.db` shot_events table, 2026-04-06
[4] Component design — `docs/xg_model_components/01_shot_and_state_features.md`

## Related Pages

- [NHL API Shot Events](nhl-api-shot-events.md) — schema and storage of shot events
- [Manpower States](manpower-states.md) — another game-state contextual feature
- [Score Effects](../concepts/score-effects.md) — conceptual analysis of volume/quality asymmetry patterns by score state

## Revision History

- 2026-04-06 — Created. Compiled from xg_features.py score logic, database.py enum, and frequency analysis.
