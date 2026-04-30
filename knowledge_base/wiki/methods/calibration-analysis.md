# Calibration Analysis

> Reliability diagrams, practical calibration error gates, Hosmer-Lemeshow diagnostics, and calibration slope/intercept — ensuring xG probabilities mean what they say.

## Overview

A well-discriminating model (high AUC) can still produce poorly calibrated probabilities — predicting 12% goal probability for shots that actually convert at 6%. For an xG model at the project's ~8% base rate, calibration matters at least as much as discrimination: a naive model predicting 0.08 everywhere already has decent log loss. The purpose of calibration analysis is to verify that predicted probabilities match observed frequencies across the full range of predictions.

Calibration is especially critical because xG values are summed across shots to produce game-level and player-level expected goal totals. If individual shot probabilities are systematically biased, the aggregated totals inherit and amplify that bias. A model that overestimates power-play goal probability by 2 percentage points will make every team's PP look better than it actually is.

The project's calibration requirements follow the framework in `CLAUDE.md`: per-segment checks (even strength, power play, short-handed), per-season stability, and explicit pass/fail criteria [1].

## Key Details

### Reliability Diagram

The reliability diagram plots mean predicted probability (x-axis) against observed frequency (y-axis) within quantile-based bins. Perfect calibration falls on the diagonal. The project uses 10 decile bins (`CALIBRATION_N_BINS = 10`) [2].

Deviations from the diagonal reveal systematic bias:
- Points above the diagonal: model underestimates goal probability (underconfident)
- Points below: model overestimates (overconfident)
- S-shaped curves: model is overconfident at extremes, typical of unrecalibrated logistic models

### Hosmer-Lemeshow Test

The Hosmer-Lemeshow (H-L) test formalizes the reliability diagram as a chi-squared goodness-of-fit test [2]:

1. Sort predictions into *g* decile bins by predicted probability
2. Within each bin *b*, compute observed positives *O_b* and expected positives *E_b* = Σ p̂ᵢ
3. Compute H-L statistic: Σ (O_b - E_b)² / E_b + Σ (O_b⁻ - E_b⁻)² / E_b⁻
4. Compare to χ² with df = g - 2

The H-L p-value is now reported as a diagnostic rather than a hard gate. With million-row holdout pools, the test can reject practically acceptable calibration because tiny bin-level differences are statistically detectable. The validation scorecard therefore prints the H-L statistic/p-value but uses practical calibration gates for pass/fail [1][2].

The `hosmer_lemeshow_test()` function in the validation notebook implements this using `np.digitize()` for binning and `scipy.stats.chi2.cdf()` for the p-value [2].

### Practical Calibration Error Gates

The pass/fail scorecard uses two quantile-bin error metrics from `practical_calibration_metrics()` [2]:

- **Max decile calibration error:** largest absolute observed-vs-predicted goal-rate gap across the 10 bins. Target: < 1 percentage point (`MAX_DECILE_CALIBRATION_ERROR = 0.01`).
- **Expected calibration error (ECE):** sample-weighted average absolute bin gap. Target: < 0.5 percentage points (`EXPECTED_CALIBRATION_ERROR_TARGET = 0.005`).

These gates keep the calibration decision tied to practical probability error rather than sample-size-sensitive significance alone.

### Calibration Slope and Intercept

A complementary diagnostic regresses the observed outcomes on the log-odds of the predicted probabilities via logistic regression [2]:

- **Slope = 1.0** → predictions are correctly scaled
- **Slope < 1.0** → predictions are too extreme (spread too wide)
- **Slope > 1.0** → predictions are too conservative (compressed toward the mean)
- **Intercept = 0** → no overall bias in predicted level

Pass criterion: slope in [0.95, 1.05] [1].

The `calibration_slope_intercept()` function clips probabilities to [ε, 1-ε] to avoid log(0), then fits a single-feature logistic regression on the log-odds [2].

### Per-Segment Calibration

The project requires calibration to be checked separately across manpower-state segments [1]:

| Segment | States Included |
|---------|----------------|
| Even Strength | 5v5, 4v4, 3v3 |
| Power Play | 5v4, 5v3, 4v3 |
| Short-Handed | 4v5, 3v5, 3v4 |

Maximum subgroup calibration error must be < 3 percentage points (`MAX_SUBGROUP_CALIBRATION_ERROR = 0.03`) [2]. This catches models that are well-calibrated overall but systematically wrong for rare game states.

### Per-Season Stability

Calibration slope is tracked per held-out season from the temporal CV harness. Degrading slope over time signals concept drift — the model's probability estimates become stale as the league evolves [1].

## Relevance to This Project

Calibration analysis is Step 4 of the model validation framework (`notebooks/model_validation_framework.ipynb`) and a required component of the validation scorecard [2]. No xG model may be deployed or used for player evaluation until it passes all practical calibration checks.

The `CLAUDE.md` rigor requirements mandate reporting reliability diagrams, Hosmer-Lemeshow statistic/p-value as a diagnostic, calibration slope/intercept (target slope in [0.95, 1.05]), max decile calibration error (< 1pp), expected calibration error (< 0.5pp), and per-segment calibration with max subgroup error < 3 percentage points [1].

The 2026-04-30 live validation scorecard passed the practical calibration gates: calibration slope 0.9870, max decile error 0.407 pp, ECE 0.193 pp, and max manpower-segment error 1.24 pp. Hosmer-Lemeshow p remained effectively 0 and is recorded as diagnostic only [2].

Last verified: 2026-04-30

## Sources

[1] Calibration requirements — `CLAUDE.md` (Statistical Analysis Rigor Requirements, item 6)
[2] Implementation — `notebooks/model_validation_framework.ipynb` (`hosmer_lemeshow_test()`, `practical_calibration_metrics()`, `calibration_slope_intercept()`, Steps 4a-4c), `artifacts/validation_scorecard_latest.md`
[3] Validation design — `docs/xg_model_components/06_model_validation_framework.md` (Step 4)
[4] Model training spec — `docs/xg_model_components/05_xg_model_training_and_calibration.md`

## Related Pages

- [Temporal Cross-Validation](temporal-cross-validation.md) — the evaluation harness that produces the predictions used for calibration analysis
- [Expected Goals (xG)](../concepts/expected-goals-xg.md) — the model whose calibration is being assessed
- [Manpower States](../data/manpower-states.md) — the segment definitions used for per-segment calibration

## Revision History

- 2026-04-07 — Created. Compiled from model_validation_framework.ipynb calibration cells, CLAUDE.md rigor section, and component 05/06 design docs.
- 2026-04-30 — Updated. Converted Hosmer-Lemeshow from hard gate to diagnostic and documented practical calibration gates plus the passing live v5 scorecard metrics.
