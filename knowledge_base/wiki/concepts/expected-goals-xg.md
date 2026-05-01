# Expected Goals (xG)

> A probabilistic model that assigns each shot a goal probability based on shot location, type, and game context — the foundational metric for this project.

<!-- data-version: v2 (conceptual article — no empirical tables, but model design references coordinate-dependent features) -->
<!-- data-revalidate: After v3 backfill, no changes needed unless distance/angle distribution findings are added. -->

## Overview

Expected Goals (xG) estimates the probability that a given shot attempt will result in a goal, based on historical conversion rates for similar shots. A wrist shot from the slot might receive an xG of 0.12 (12% chance of scoring), while a slap shot from the blue line might receive 0.03. Summing xG across all shots in a game gives each team an "expected goals" total that reflects shot quality rather than just shot quantity.

xG has become the standard currency of modern hockey analytics because it separates shooting skill and goaltending from shot generation quality. A team that generates 3.2 xG but scores 1 goal is creating good chances but getting unlucky or facing strong goaltending. Over time, xG converges with actual goals, making it a better predictor of future performance than raw goal counts.

The concept originated in soccer analytics and was adapted for hockey in the early 2010s by researchers and public models including War On Ice, Corsica, MoneyPuck, Evolving Hockey, and HockeyViz (Magnus). Each model uses slightly different feature sets and training approaches, but all share the core framework of shot-level probability estimation. Schuckers & Curro's DIGR/THoR work (2011-2013) pioneered spatial shot quality estimation and regularized player rating for hockey [6].

## Key Details

### Core Feature Categories

Most xG models, including this project's planned model, use features from these categories [1][2]:

1. **Shot location** — distance to goal, angle to goal (see [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md))
2. **Shot type** — wrist, slap, snap, backhand, etc. (see [Shot Type Taxonomy](../data/shot-type-taxonomy.md))
3. **Game state** — score differential (see [Score States](../data/score-states.md)), manpower situation (see [Manpower States](../data/manpower-states.md))
4. **Sequence context** — time since last event, rebound flag, rush vs sustained pressure
5. **Contextual modifiers** — [rest/travel effects](rest-travel-effects.md), zone start context, venue bias corrections, [handedness and effective angle](handedness-effective-angle.md)

### Model Architectures

Common approaches in public xG models:

- **Logistic regression** — interpretable, well-calibrated baseline; used by early models and HockeyViz Magnus (regularized logistic with hex spatial fabric) [6]
- **Gradient-boosted trees (GBDT)** — XGBoost/LightGBM; handles interactions and nonlinearities; used by MoneyPuck (GBM) and Evolving Hockey (XGBoost, separate models per strength state) [6]
- **Neural networks** — less common in hockey; risk of overfitting on ~100k-shot datasets
- **Ensemble/stacked** — combine logistic and GBDT predictions

This project plans to start with logistic regression as a baseline, then move to GBDT [3]. Public model benchmarks: Evolving Hockey reports even-strength AUC of ~0.78; see [Public xG Model Survey](../comparisons/public-xg-model-survey.md) for detailed comparison.

### Evaluation Metrics

A well-built xG model must satisfy [4]:

- **Discrimination** — AUC-ROC distinguishing goals from non-goals (typical: 0.75-0.80)
- **Calibration** — predicted probabilities match observed goal rates across bins (calibration slope in [0.95, 1.05], max decile error < 1pp, ECE < 0.5pp; Hosmer-Lemeshow reported diagnostically)
- **Temporal stability** — performance doesn't degrade across held-out seasons (AUC drift < 0.02/season)
- **Per-segment calibration** — calibration checked separately for even strength, power play, and short-handed

### Base Rate

The overall goal rate across all shot types in the database is approximately 6.5% (goals / total shot events). This is the naive baseline that any xG model must improve upon [5].

## Relevance to This Project

xG is the central modeling target. The project roadmap (`docs/xg_model_roadmap.md`) organizes all work around building, validating, and applying an xG model:

- **Phase 0-1:** Data foundation and feature engineering (shot events, game state, coordinates)
- **Phase 2:** Contextual features (rest/travel, faceoff decay, venue bias, zone starts)
- **Phase 3:** Model training, calibration, and validation
- **Phase 4+:** Player impact (RAPM on xG residuals), team strength aggregation

The statistical rigor requirements in `CLAUDE.md` define minimum standards for all eight evaluation criteria.

Last verified: 2026-04-30

## Sources

[1] Feature design — `docs/xg_model_components/01_shot_and_state_features.md`
[2] Contextual features — `docs/xg_model_components/02_rest_travel_and_zone_context.md`, `03_faceoff_decay_modeling.md`, `04_scorekeeper_bias.md`
[3] Model training plan — `docs/xg_model_components/05_xg_model_training_and_calibration.md`
[4] Validation framework — `docs/xg_model_components/06_model_validation_framework.md`, `notebooks/model_validation_framework.ipynb`
[5] Base rate — `data/nhl_data.db` shot_events table (2.1M shots, ~137k goals)
[6] Public model survey — `knowledge_base/wiki/comparisons/public-xg-model-survey.md`

## Related Pages

- [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md)
- [Shot Type Taxonomy](../data/shot-type-taxonomy.md)
- [Score States](../data/score-states.md)
- [Manpower States](../data/manpower-states.md)
- [Temporal Cross-Validation](../methods/temporal-cross-validation.md) — the evaluation harness for xG models
- [Calibration Analysis](../methods/calibration-analysis.md) — ensuring xG probabilities are well-calibrated
- [RAPM](../methods/rapm-regularized-adjusted-plus-minus.md) — player impact estimation using xG residuals
- [Public xG Model Survey](../comparisons/public-xg-model-survey.md) — structured comparison of MoneyPuck, Evolving Hockey, and HockeyViz Magnus

## Revision History

- 2026-04-30 — Updated calibration metric summary to match the live validation scorecard policy.
- 2026-04-08 — Added external model references (MoneyPuck, Evolving Hockey, HockeyViz Magnus, Schuckers & Curro) and link to public xG model survey.
- 2026-04-06 — Created. Compiled from project roadmap, component docs, and general hockey analytics domain knowledge.
