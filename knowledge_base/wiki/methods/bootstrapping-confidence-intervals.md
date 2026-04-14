# Bootstrapping and Confidence Intervals

> Bootstrap resampling for goal-rate confidence intervals, Wilson intervals for proportions, and sample size adequacy checks at the project's ~8% base rate.

## Overview

With 2+ million shots in the database, even tiny differences in goal rate become statistically significant by conventional hypothesis tests. A 0.1 percentage point difference between two shot types is detectable with chi-squared but completely irrelevant for model design. Confidence intervals and sample size checks serve the opposite role from hypothesis tests: they tell you how *precise* an estimate is and whether a cell has enough data to detect a *meaningful* difference.

The project requires confidence intervals on all reported rates and proportions — bare point estimates are never sufficient to justify a feature inclusion decision [1]. Bootstrap CIs are preferred over analytic (Wilson/Wald) intervals because they make no distributional assumptions and naturally handle the complex dependencies in stratified hockey data (shots within games, games within seasons).

## Key Details

### Bootstrap CI for Goal Rates

The `bootstrap_goal_rate_ci()` function implements a parametric bootstrap [2]:

1. Given *goals* successes in *shots* trials, compute point estimate p̂ = goals / shots
2. Draw `N_BOOTSTRAP_SAMPLES` (10,000) samples of size *shots* from Binomial(shots, p̂)
3. Compute the rate for each sample
4. Return the 2.5th and 97.5th percentiles as the 95% CI bounds

```python
boot_rates = rng.binomial(n=shots, p=goals/shots, size=n_boot) / shots
ci_lower = np.percentile(boot_rates, 2.5)
ci_upper = np.percentile(boot_rates, 97.5)
```

The seed is fixed (`seed=42`) for reproducibility [2]. This is a parametric bootstrap (resampling from the fitted binomial) rather than a nonparametric bootstrap (resampling raw observations), which is appropriate for the simple goal/no-goal proportion case.

### Wilson Interval

For quick calculations where bootstrapping is impractical, the Wilson score interval provides a better alternative to the Wald interval for proportions near 0 or 1 [1]:

```
p̂ ± z * sqrt(p̂(1-p̂)/n + z²/(4n²)) / (1 + z²/n)
```

The Wilson interval never produces negative bounds (unlike Wald) and has better coverage properties for rare events like the ~8% goal rate.

### Sample Size Adequacy

At the project's ~8% base rate, detecting a 50% relative difference (4 percentage points absolute) at 80% power requires approximately 400 shots per cell [1][2]:

| Base Rate | Relative Δ | Absolute Δ | Required n | Power |
|-----------|-----------|-----------|-----------|-------|
| 8% | 50% | 4 pp | ~400 | 80% |
| 8% | 25% | 2 pp | ~1,600 | 80% |
| 8% | 10% | 0.8 pp | ~10,000 | 80% |

The constant `MIN_SHOTS_PER_CELL = 400` encodes this threshold [2]. Cells with fewer shots are flagged as underpowered in the `analyze_categorical_feature()` output, and conclusions must not be drawn from them [1].

### Application to Categorical Features

The `analyze_categorical_feature()` function runs the full statistical battery on any categorical feature in `shot_events` [2]:

1. Query per-category shot and goal counts
2. Run chi-squared test for overall variation
3. Compute bootstrap CI for each category's goal rate
4. Compute Cohen's h vs. overall rate for each category
5. Flag underpowered categories (< 400 shots)

This produces a structured report distinguishing statistical significance (chi-squared p-value) from practical significance (Cohen's h threshold) and data adequacy (sample size flag).

## Relevance to This Project

Bootstrap CIs and sample size checks are required by the `CLAUDE.md` statistical rigor framework for all analyses [1]. Every notebook that reports a rate or proportion must include a CI. The validation framework notebook (`model_validation_framework.ipynb`) uses `bootstrap_goal_rate_ci()` as the primary CI method for Step 2 (statistical rigor retrofit) [2].

The sample size threshold directly affects which stratified analyses are trustworthy. When crossing zone start × time window × manpower state, many cells drop below 400 shots and must be flagged rather than interpreted [3].

Last verified: 2026-04-07

## Sources

[1] CI and sample size requirements — `CLAUDE.md` (Statistical Analysis Rigor Requirements, items 1 and 4)
[2] Implementation — `notebooks/model_validation_framework.ipynb` (`bootstrap_goal_rate_ci()`, `analyze_categorical_feature()`, `N_BOOTSTRAP_SAMPLES`, `MIN_SHOTS_PER_CELL`)
[3] Validation design — `docs/xg_model_components/06_model_validation_framework.md` (Step 2)

## Related Pages

- [Effect Size Measures](effect-size-measures.md) — Cohen's h/d for practical significance, complementary to CIs
- [Score States](../data/score-states.md) — categorical feature whose rate table was computed with bootstrap CIs
- [Manpower States](../data/manpower-states.md) — another categorical feature requiring per-cell adequacy checks

## Revision History

- 2026-04-07 — Created. Compiled from model_validation_framework.ipynb helper functions, CLAUDE.md rigor section, and component 06 design doc.
