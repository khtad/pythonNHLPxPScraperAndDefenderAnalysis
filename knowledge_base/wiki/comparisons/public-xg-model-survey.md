# Public xG Model Survey

> A structured comparison of three publicly documented expected goals models — MoneyPuck, Evolving Hockey, and HockeyViz Magnus — covering algorithm choice, feature sets, strength-state handling, and reported performance.

## Overview

Several public xG models are available for hockey analytics. Each takes a fundamentally different modeling approach while sharing the same core objective: estimating the probability that a given unblocked shot results in a goal. Understanding their design choices informs our own model's feature engineering and provides benchmarks for evaluation.

The three models compared here represent the major architectural archetypes in hockey xG: gradient boosting with engineered features (MoneyPuck), gradient boosting with strength-state separation (Evolving Hockey), and regularized logistic regression with spatial fabric (HockeyViz Magnus). A fourth academic contribution — Schuckers & Curro's THoR/DIGR — pioneered many foundational techniques used by all three.

## Key Details

### Algorithm Comparison

| Property | MoneyPuck | Evolving Hockey | HockeyViz Magnus |
|----------|-----------|-----------------|------------------|
| Algorithm | Gradient boosting (GBM) | XGBoost | Regularized logistic regression |
| Model count | 1 unified | 4 (by strength state) | 2+ (EV and ST separately) |
| Regularization | Built-in (GBM) | Built-in (XGBoost) | Ridge (L2); later versions penalty toward prior season |
| Interpretability | Feature importance only | Feature importance only | Coefficients as odds ratios |
| Shooter/goalie | Bayesian talent adjustment | Attempted; excluded by model | Explicit per-player indicators in design matrix |

### Feature Comparison

| Feature | MoneyPuck | Evolving Hockey | HockeyViz Magnus |
|---------|-----------|-----------------|------------------|
| Shot distance | Yes | Yes | Implicit (via hex grid) |
| Shot angle | Yes | Yes | Implicit (via hex grid) |
| Shot type | Yes | Yes (7 types) | Yes (as odds ratios) |
| Coordinates (x, y) | Yes | Yes (current + prior event) | Hex grid encoding |
| Score state | Not documented | Yes (8 categories) | Yes (trailing worse, leading negligible) |
| Manpower state | Opponent skater count, PP duration | Strength state indicators | EV/ST modeled separately |
| Time since last event | Yes | Yes | Not documented |
| Prior event type | Yes | Yes (same/opp team indicators) | Not documented |
| Speed / distance from prior | Yes (distance/time) | Distance from last event | Not documented |
| Rebound | Angle change/time metric | Via prior event indicators | Yes (~2x odds ratio) |
| Rush | Via speed metric | Via prior event indicators | Yes (~2x odds ratio) |
| Home/away | Not documented | Yes | Yes |
| Empty net | Yes | Separate model | Separate model |
| Shooter identity | Bayesian post-adjustment | Attempted, excluded | Explicit indicator in design matrix |
| Goaltender identity | Not documented | Not included | Explicit indicator in design matrix |

### Spatial Handling

The models take notably different approaches to encoding shot location [1][2][3]:

- **MoneyPuck and Evolving Hockey**: Use raw x,y coordinates plus derived distance and angle as continuous features. The tree-based algorithms learn nonlinear interactions between location and other features.
- **HockeyViz Magnus**: Encodes location via a hexagonal grid where each hex is a separate covariate with its own "starting odds" for shots. This approach implicitly handles distance/angle through spatial location and produces smooth probability surfaces. Hex granularity is tuned to match NHL coordinate recording accuracy.
- **Schuckers & Curro (THoR)**: Divided the offensive zone into 54 rectangular grid cells. Goal probability calculated per cell per shot type. Less granular than Magnus hexes but pioneered spatial binning for hockey xG.

### Strength-State Handling

Evolving Hockey is the most explicit about strength-state separation, training four completely independent models [2]:

| Model | Shots (training) | AUC (CV) | AUC (OOS) |
|-------|----------|----------|-----------|
| Even-Strength | 537,519 | 0.7822 | 0.7747 |
| Powerplay | 113,573 | 0.7183 | 0.7018 |
| Shorthanded | 23,714 | 0.7975 | 0.8369 |
| Empty Net | 3,680 | — | — |

MoneyPuck uses a single model with manpower features as inputs. Magnus models EV and ST separately but with the same regularized logistic framework.

### Rebound and Rush Handling

Each model addresses sequence context differently [1][2][3]:

- **MoneyPuck**: No explicit rebound/rush flags. Uses "speed" (distance/time between events) and "rebound angle change" (angle difference/time between consecutive shots) as continuous features. Also applies a **flurry adjustment** — discounting successive shots so a sequence never exceeds 1.0 combined xG.
- **Evolving Hockey**: No explicit rebound/rush classifiers either. Prior event indicators (shot/miss/block by same or opposing team) plus time-since-last-event capture sequence context implicitly.
- **HockeyViz Magnus**: Explicit rebound and rush indicator covariates, each with an odds ratio of approximately 2x — meaning rebounds and rush chances roughly double the base xG from any given location.

### Reported Performance

| Model | Metric | Even-Strength | Notes |
|-------|--------|---------------|-------|
| Evolving Hockey | AUC (OOS) | 0.7747 | 2017-18 hold-out season |
| Evolving Hockey | Log Loss (OOS) | 0.1897 | 2017-18 hold-out season |
| MoneyPuck | Top-15% capture rate | >50% of goals | 2015-16 hold-out season |
| HockeyViz Magnus | — | Not published | Regularized logistic; no public AUC/log loss |

Direct comparison is limited because models use different metrics, training periods, and holdout seasons. Our project should report AUC, log loss, Brier score, and calibration metrics to enable meaningful comparison against these benchmarks (see [Calibration Analysis](../methods/calibration-analysis.md)).

### Academic Foundation: Schuckers & Curro

The THoR/DIGR work provides historical context for many techniques used by the public models [4]:

- **Pioneered regularized regression for hockey player rating** (ridge regression, 2013), predating the Evolving Hockey and Magnus implementations
- **Introduced NP20 (Net Probability after 20 seconds)** — valuing every on-ice event by its probability of leading to a goal, not just shots
- **Developed rink bias correction via CDF matching** — adjusting per-venue shot distance distributions by matching quantiles to the league-wide distribution, conditioned on shot type
- **DIGR used LOESS spatial smoothing** for goaltender evaluation — nonparametric spatial save probability maps that avoid arbitrary bin boundaries

## Relevance to This Project

These external models inform our work in several ways:

1. **Feature engineering baseline**: All three models use distance, angle, shot type, and sequence context. Our model should include at minimum these features. The split on whether to use explicit rebound/rush flags vs. continuous sequence metrics is a design decision worth testing.
2. **Performance benchmarks**: Evolving Hockey's EV AUC of ~0.78 is the primary public benchmark. Our model should target this range.
3. **Strength-state modeling**: Evolving Hockey's approach of training separate models per strength state is worth evaluating against our planned per-segment calibration checks.
4. **Spatial encoding**: Magnus's hex fabric represents an alternative to explicit distance/angle features. If our logistic baseline underperforms, hex-based spatial encoding is a candidate improvement.
5. **Rink bias correction**: Schuckers' CDF-matching method for venue bias correction is a concrete implementation option for our planned venue bias features.
6. **Flurry adjustment**: MoneyPuck's sequence-level xG cap (never >1.0 for a flurry) addresses a real issue with rapid successive shots that our model should also handle.

Last verified: 2026-04-08

## Sources

[1] MoneyPuck methodology — `knowledge_base/raw/external/2026-04-08_moneypuck-xg-methodology.md` (source: moneypuck.com/about.htm)
[2] Evolving Hockey xG model — `knowledge_base/raw/external/2026-04-08_evolving-hockey-xg-and-war.md` (source: evolving-hockey.com/blog)
[3] HockeyViz Magnus model — `knowledge_base/raw/external/2026-04-08_hockeyviz-magnus-model.md` (source: hockeyviz.com/txt/magnusEV)
[4] Schuckers & Curro THoR/DIGR — `knowledge_base/raw/external/2026-04-08_schuckers-curro-thor-digr.md` (MIT Sloan 2011, 2013)

## Related Pages

- [Expected Goals (xG)](../concepts/expected-goals-xg.md) — the core concept all these models implement
- [Shot Type Taxonomy](../data/shot-type-taxonomy.md) — our project's shot type definitions, used by all models
- [Score States](../data/score-states.md) — our score-state bucketing, comparable to Evolving Hockey's 8-category scheme
- [Manpower States](../data/manpower-states.md) — our manpower state definitions, relevant to strength-state model separation
- [Venue and Scorekeeper Bias](../concepts/venue-scorekeeper-bias.md) — Schuckers' CDF correction method applies here
- [RAPM](../methods/rapm-regularized-adjusted-plus-minus.md) — Evolving Hockey's WAR/GAR builds on xG via RAPM
- [Calibration Analysis](../methods/calibration-analysis.md) — our evaluation framework for comparing against these benchmarks
- [Effect Size Measures](../methods/effect-size-measures.md) — for assessing practical significance of model differences
- [Knowledge Gaps](../meta/knowledge-gaps.md) — tracks remaining comparison articles and model articles gated on future work

## Revision History

- 2026-04-08 — Created. Phase 2 external source ingestion. Compiled from MoneyPuck, Evolving Hockey, HockeyViz Magnus, and Schuckers/Curro raw sources.
