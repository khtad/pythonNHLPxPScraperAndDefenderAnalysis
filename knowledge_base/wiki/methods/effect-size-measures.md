# Effect Size Measures

> Cohen's h for proportions and Cohen's d for continuous variables — separating practical significance from statistical significance in large-sample hockey data.

## Overview

With 2+ million shots, conventional hypothesis tests (chi-squared, t-tests) reject the null for almost any nonzero difference. A 0.05 percentage point difference in goal rate between two shot types is statistically significant at p < 0.001 but completely useless for xG modeling. Effect size measures quantify *how large* a difference is, independent of sample size, providing the practical significance assessment that p-values cannot.

The project mandates effect sizes for all group comparisons [1]. The decision rule is: a feature difference is practically meaningful only if |Cohen's h| >= 0.2 AND the comparison is adequately powered (>= 400 shots per cell at the ~8% base rate) [1][2]. Features that fail this threshold are not rejected outright but cannot be included in the model based on univariate analysis alone.

## Key Details

### Cohen's h (Proportions)

Cohen's h compares two proportions using the arcsine transformation [2]:

```
h = 2 * arcsin(sqrt(p₁)) - 2 * arcsin(sqrt(p₂))
```

The arcsine transformation stabilizes variance across the [0, 1] range, making h comparable regardless of the base rate. This is preferable to raw percentage-point differences, which have different practical impact at different base rates (a 2pp difference matters more at 5% than at 50%).

Conventional thresholds:

| |h| | Interpretation |
|-----|----------------|
| < 0.2 | Negligible |
| 0.2 – 0.5 | Small |
| 0.5 – 0.8 | Medium |
| > 0.8 | Large |

The `cohens_h()` function in the validation notebook implements this directly [2].

### Cohen's d (Continuous Variables)

Cohen's d compares two group means in units of pooled standard deviation:

```
d = (M₁ - M₂) / s_pooled
```

where s_pooled = sqrt(((n₁-1)s₁² + (n₂-1)s₂²) / (n₁+n₂-2)).

Conventional thresholds:

| |d| | Interpretation |
|-----|----------------|
| < 0.2 | Negligible |
| 0.2 – 0.5 | Small |
| 0.5 – 0.8 | Medium |
| > 0.8 | Large |

The shot distance diagnostic notebook used Cohen's d to compare period-2 vs period-1+3 shot distances, finding d = -0.04 for post-2020 data (negligible) vs d = -1.05 for pre-2020 data (massive — confirming the v2 normalization bug) [3].

### Decision Rule in This Project

The project applies a two-gate decision rule [1]:

1. **Statistical significance**: chi-squared or equivalent test p < 0.05
2. **Practical significance**: |Cohen's h| >= 0.2 (the `COHEN_H_SMALL` constant) AND adequate sample size (>= `MIN_SHOTS_PER_CELL` = 400)

Both gates must pass for a feature difference to be considered meaningful. This prevents two failure modes:
- Including features with statistically significant but negligible effects (large sample trap)
- Concluding a feature has no effect when the cell is simply underpowered (small sample trap)

### Application in the Validation Framework

The `analyze_categorical_feature()` function computes Cohen's h for each category relative to the overall goal rate [2]. Categories that exceed the threshold are highlighted as "practically meaningful" in the output. The function also flags underpowered categories to prevent false negatives.

Example output pattern:
```
Category         Shots    Goals   Rate      95% CI          Cohen h   Power
wrist           800,000  52,000  6.50%   [6.45, 6.55]      -0.042      OK
deflected        50,000   5,500  11.00%  [10.73, 11.27]    +0.231      OK  ← meaningful
bat               1,200      80   6.67%  [5.28, 8.19]      -0.030     LOW  ← underpowered
```

## Relevance to This Project

Effect size measures are one of the eight statistical rigor requirements in `CLAUDE.md` [1]. They appear in:

- **Step 2** of the validation framework: every categorical feature's per-category analysis includes Cohen's h [2]
- **Shot distance diagnostic**: Cohen's d confirmed the v2 normalization bug's impact [3]
- **Feature ablation** (Step 5): held-out metric deltas serve as a model-level effect size for conditional feature importance

The thresholds are deliberately conservative (0.2 is the "small" effect boundary) because at ~8% base rate, even small effects can compound across thousands of shots per game. Features with |h| between 0.1 and 0.2 may still be worth investigating via conditional ablation even if they fail the univariate threshold.

Last verified: 2026-04-07

## Sources

[1] Effect size requirements — `CLAUDE.md` (Statistical Analysis Rigor Requirements, item 3)
[2] Implementation — `notebooks/model_validation_framework.ipynb` (`cohens_h()`, `analyze_categorical_feature()`, `COHEN_H_SMALL`)
[3] Shot distance diagnostic — `notebooks/shot_distance_diagnostic.ipynb`, `knowledge_base/raw/project/2026-04-06_shot-distance-diagnostic.md`

## Related Pages

- [Bootstrapping and Confidence Intervals](bootstrapping-confidence-intervals.md) — CIs complement effect sizes by quantifying estimate precision
- [Temporal Cross-Validation](temporal-cross-validation.md) — ablation deltas from CV serve as model-level effect sizes
- [Score States](../data/score-states.md) — a categorical feature analyzed with Cohen's h

## Revision History

- 2026-04-07 — Created. Compiled from model_validation_framework.ipynb helper functions, CLAUDE.md rigor section, and shot distance diagnostic findings.
