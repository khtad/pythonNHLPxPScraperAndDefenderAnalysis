# RAPM (Regularized Adjusted Plus-Minus)

> Ridge or elastic-net regression to isolate individual player offensive and defensive impact from on-ice/off-ice context, using xG-based response variables.

## Overview

Raw plus-minus (goals for minus goals against while a player is on ice) is confounded by teammate quality, opponent quality, and deployment context. Adjusted Plus-Minus (APM) addresses this by building a large regression where each observation is an ice-time segment, the predictors are indicator variables for every player on ice, and the response is a goal or shot-quality metric. The coefficient for each player estimates their marginal contribution after controlling for who else was on ice.

Unregularized APM is numerically unstable because the player design matrix is sparse and highly collinear (certain players almost always play together). Regularized APM (RAPM) adds a penalty term — typically ridge (L2) or elastic-net (L1+L2) — that shrinks coefficients toward zero and stabilizes estimates. This is the standard approach in modern hockey analytics for player evaluation [1].

The project plans to apply RAPM to xG residuals rather than raw goals, separating shot generation quality from shooting/goaltending luck. This produces "expected goals above replacement"-style metrics that are more stable and predictive than goal-based RAPM [1].

## Key Details

### Design Matrix

Each row represents a shift or ice-time segment. The columns are [1]:

- **Player indicators**: +1 if the player is on ice for the "home" team, -1 if on ice for the "away" team, 0 otherwise
- **Response variable**: xG differential (team xGF - team xGA) for the segment, or a per-shot binary outcome depending on the formulation

The matrix is extremely sparse: each row has at most 12 non-zero entries (6 skaters per team) out of potentially 1,000+ player columns.

### Regularization

| Method | Penalty | Effect |
|--------|---------|--------|
| Ridge (L2) | λ Σ βⱼ² | Shrinks all coefficients toward zero; keeps all players in the model |
| Elastic-net | α λ Σ |βⱼ| + (1-α) λ Σ βⱼ² | Shrinks and can zero out low-signal players |
| Hierarchical Bayes | Position/usage priors | Informative shrinkage toward position-group means |

Ridge is the most common choice in public hockey RAPM implementations because zeroing out a player (as Lasso/elastic-net can do) is undesirable — every NHL player has *some* impact. The regularization strength λ is chosen by cross-validation [1].

### External RAPM Implementations

Two public implementations provide reference architectures [4][5]:

- **Evolving Hockey WAR/GAR**: Builds 4 RAPM models (EV offense, EV defense, PP offense, SH defense) with ridge regression on shift-level data across 11 seasons. RAPM coefficients become targets for a second-stage SPM (Statistical Plus-Minus) model using a 5-algorithm ensemble (OLS, elastic-net, SVM, Cubist, bagged MARS). Team-strength adjustments scale components by empirically determined multipliers (1.3x-1.6x).
- **Schuckers & Curro THoR**: Ridge regression with +1/-1/0 player indicators plus zone-start covariates. Response variable is NP20 (net probability of a goal within 20 seconds per event). Chose ridge parameter by minimizing traded-player rating variability ratio (rho). Pioneered regularized player rating for hockey (2013).

HockeyViz Magnus takes a different approach, embedding per-shooter and per-goaltender indicators directly in the xG logistic regression design matrix with ridge penalty toward the previous season's estimate [6].

### Offensive and Defensive Separation

The project plans separate offensive and defensive RAPM estimates [1]:

- **Offensive RAPM (ORAPM)**: response = team xGF per 60 minutes while the player is on ice
- **Defensive RAPM (DRAPM)**: response = team xGA per 60 minutes while the player is on ice (lower is better)
- **Total RAPM**: ORAPM - DRAPM

This separation is valuable because forwards and defensemen contribute differently on each side of the puck, and aggregating masks the distinction.

### Validation Requirements

Per the component design doc [1]:

1. **Year-over-year stability**: player RAPM estimates should correlate r > 0.5 between consecutive seasons for players with 500+ minutes
2. **Position-group sanity**: defensemen should generally have higher DRAPM than forwards; elite scorers should dominate ORAPM
3. **Sensitivity to λ**: results should be qualitatively stable across a 10x range of regularization strength
4. **Uncertainty intervals**: bootstrap or Bayesian credible intervals on each player's estimate

### Known Challenges

- **Collinearity**: linemates who always play together have near-identical design matrix columns, making individual attribution ambiguous. Regularization handles this numerically but the conceptual ambiguity remains.
- **Sample size**: players with limited ice time have estimates dominated by the prior (regularization), not the data. The project should report effective sample size alongside estimates.
- **Usage bias**: players deployed in favorable situations (offensive zone starts, weaker opponents) will have inflated raw RAPM. Context adjustments (score state, zone start) should be included as covariates.

## Relevance to This Project

RAPM is Phase 4+ in the xG roadmap — it depends on having a validated xG model first [1][2]. The player design matrices will use data from the `player_game_stats` table (which tracks per-game TOI and position), and the xG residuals will come from the `shot_events` table with model predictions applied.

The `player_game_features` table has placeholder columns for rolling RAPM-derived features, with `feature_set_version` tracking which model version produced them [3].

Last verified: 2026-04-07

## Sources

[1] RAPM design — `docs/xg_model_components/06_rapm_on_xg.md`
[2] Project roadmap — `docs/xg_model_roadmap.md` (Phase 4)
[3] Player schema — `src/database.py` (`create_player_game_features_table()`, `_FEATURE_SET_VERSION`)
[4] Evolving Hockey WAR — `knowledge_base/raw/external/2026-04-08_evolving-hockey-xg-and-war.md`
[5] Schuckers & Curro THoR — `knowledge_base/raw/external/2026-04-08_schuckers-curro-thor-digr.md`
[6] HockeyViz Magnus — `knowledge_base/raw/external/2026-04-08_hockeyviz-magnus-model.md`

## Related Pages

- [Expected Goals (xG)](../concepts/expected-goals-xg.md) — the model whose residuals serve as the RAPM response variable
- [Temporal Cross-Validation](temporal-cross-validation.md) — the evaluation harness used for regularization strength selection
- [Calibration Analysis](calibration-analysis.md) — the xG model must be well-calibrated before RAPM residuals are meaningful
- [Public xG Model Survey](../comparisons/public-xg-model-survey.md) — external RAPM implementations in context of public xG models

## Revision History

- 2026-04-08 — Added external RAPM implementations (Evolving Hockey WAR/GAR, Schuckers/Curro THoR, HockeyViz Magnus).
- 2026-04-07 — Created. Compiled from component 06 (RAPM on xG) design doc, xG roadmap, and database.py player schema.
