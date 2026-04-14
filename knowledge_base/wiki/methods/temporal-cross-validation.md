# Temporal Cross-Validation

> Season-block cross-validation for hockey data: why random splits leak future information, and how to implement forward-chaining temporal CV.

## Overview

Standard k-fold cross-validation randomly assigns observations to folds, which in time-series data allows future information to leak into training sets. In NHL shot data spanning 2007–2026, this is especially dangerous: rule changes (e.g., tracking data introduction in 2019–20), COVID hub cities in 2020–21, and gradual shifts in league-wide shooting patterns mean that observations from different eras are not exchangeable.

Temporal cross-validation (also called forward-chaining or walk-forward CV) respects the time ordering of data. Each fold trains on all seasons up to season *k* and evaluates on season *k+1*. This ensures that the model is always tested on genuinely unseen future data, producing honest estimates of how the model would perform in deployment.

The project implements season-block CV because seasons are the natural temporal unit in hockey — each season has a consistent rule set, roster composition, and schedule structure. Game-level or month-level splits would be possible but introduce within-season leakage when features like rolling averages or venue bias corrections are computed over a full season [1].

## Key Details

### Algorithm

Given seasons S₁, S₂, ..., Sₙ and a minimum training window of *m* seasons [1]:

```
for k in range(m, n):
    train_seasons = {S₁, S₂, ..., Sₖ}
    test_season = Sₖ₊₁
    fit model on train_seasons
    evaluate on test_season
    record per-fold metrics
```

The project uses `MIN_TRAIN_SEASONS = 3` to ensure the model has enough data to learn distance/angle/shot-type patterns before the first evaluation [1].

### Per-Fold Metrics

Each fold records [1][2]:

| Metric | Purpose | Target |
|--------|---------|--------|
| AUC-ROC | Discrimination (rank ordering) | > 0.75 |
| Log loss | Probabilistic accuracy | Lower is better |
| Brier score | Calibration-weighted accuracy | Lower is better |
| Calibration slope | Probability scale correctness | [0.95, 1.05] |

### Temporal Stability Check

After all folds, the project fits a linear trend to the sequence of AUC-ROC values across held-out seasons. AUC drift exceeding 0.02 per season signals concept drift and must be documented [2]. This catches scenarios where the model fits well on early data but degrades as the league evolves.

### Why Random Splits Fail for Hockey

Three specific leakage risks [2]:

1. **Venue bias corrections** computed on the full dataset encode future scorekeeper behavior into training features.
2. **Faceoff decay bin boundaries** fit on pooled data embed cross-era patterns that may not hold in any single season.
3. **Score-state distributions** shift across eras as league-wide scoring rates change, making pooled statistics unrepresentative of any particular season.

### Reference Implementation

The `run_temporal_cv()` function in `notebooks/model_validation_framework.ipynb` implements the full pipeline [1]. It accepts a feature matrix, label array, per-row season array, and sorted unique seasons, and returns a list of per-fold metric dictionaries. The baseline model is logistic regression on (distance, angle, shot_type) — the simplest credible xG model that feature additions must beat.

## Relevance to This Project

Temporal CV is the primary evaluation harness for all xG model development. Every candidate feature must improve held-out metrics in this harness to be included. The `CLAUDE.md` statistical rigor requirements mandate that "findings computed on the full dataset are exploratory only" and that "bin boundaries, thresholds, feature selection decisions, and decay-curve parameters must be validated on held-out data" [2].

The validation scorecard in the framework notebook uses temporal CV results for its pass/fail criteria on discrimination, calibration, and temporal stability.

Last verified: 2026-04-07

## Sources

[1] Temporal CV implementation — `notebooks/model_validation_framework.ipynb` (`run_temporal_cv()`, Step 3)
[2] Validation criteria and rigor requirements — `CLAUDE.md` (Statistical Analysis Rigor Requirements, items 5 and 7)
[3] CV design rationale — `docs/xg_model_components/06_model_validation_framework.md` (Steps 3–5)

## Related Pages

- [Calibration Analysis](calibration-analysis.md) — per-fold calibration checks that depend on temporal CV folds
- [Expected Goals (xG)](../concepts/expected-goals-xg.md) — the modeling target evaluated by temporal CV
- [Effect Size Measures](effect-size-measures.md) — separating statistical from practical significance in fold results

## Revision History

- 2026-04-07 — Created. Compiled from model_validation_framework.ipynb, CLAUDE.md rigor section, and component 06 design doc.
