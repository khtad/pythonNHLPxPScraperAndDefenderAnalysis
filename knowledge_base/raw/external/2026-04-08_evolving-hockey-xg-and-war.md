# Evolving Hockey xG Model and WAR/GAR Framework

> **Source:** https://evolving-hockey.com/blog/a-new-expected-goals-model-for-predicting-goals-in-the-nhl/ , https://evolving-hockey.com/blog/wins-above-replacement-the-process-part-2/
> **Authors:** Josh & Luke Younggren (EvolvingWild)
> **Retrieved:** 2026-04-08
> **Type:** Public xG model + player evaluation framework documentation

## Part 1: Expected Goals Model

### Algorithm

eXtreme Gradient Boosting (XGBoost). Binary classification: 1 = Fenwick shot resulted in goal, 0 = did not.

### Strength State Separation

Four separate models trained independently:

1. **Even-Strength** (5v5, 4v4, 3v3)
2. **Powerplay / Man-Advantage** (5v4, 4v3, 5v3, 6v5, 6v4)
3. **Shorthanded Offense** (4v5, 3v4, 3v5)
4. **Empty Net**

Rationale: significant differences in play styles and scoring rates between strength states.

### Training Data

- EV: 537,519 shots (2010-11 through 2016-17, 7 seasons)
- PP: 113,573 shots (same 7 seasons)
- SH: 23,714 shots (2007-08 through 2016-17, 10 seasons)
- EN: 3,680 shots (10 seasons)
- Excluded: 6v3 situations, penalty shots, shootouts

### Features (15 conceptual, 43 with dummy expansion)

**Continuous:**
- Shot distance (from coordinates)
- Shot angle (from coordinates)
- Game seconds and period
- Coordinates (current event x, y)
- Coordinates (prior event x, y)
- Distance from last event
- Time since last event

**Categorical / Boolean:**
- Strength state indicators: state_5v5, state_4v4, state_3v3
- Score state (8 categories): score_down_4 through score_up_4
- Shot type (7 categories): wrist, deflected, tip, slap, backhand, snap, wrap
- Prior event indicators (same/opposite team): shot, miss, block, giveaway, takeaway, hit, faceoff
- Home/away indicator

### Hyperparameter Tuning

Modified random search, 5-fold CV, 200+ iterations (~16 hours per model).

**Even-Strength final parameters:**
- eta: 0.068, max_depth: 6, gamma: 0.12
- subsample: 0.78, colsample_bytree: 0.76
- min_child_weight: 5, max_delta_step: 5, nrounds: 189

### Model Evaluation

| Model | CV AUC | CV Log Loss | OOS AUC (2017-18) | OOS Log Loss |
|-------|--------|-------------|---------------------|--------------|
| Even-Strength | 0.7822 | 0.1847 | 0.7747 | 0.1897 |
| Powerplay | 0.7183 | 0.2716 | 0.7018 | 0.2817 |
| Shorthanded | 0.7975 | 0.2148 | 0.8369 | 0.2035 |

AUC used as primary optimization metric.

### Variable Importance

Shot distance is most important across all strength states. Authors caution that tree-based importance measures reflect feature usage in splits, not linear coefficients.

### Shooting Talent

Attempted Bayesian shooting talent variable (inspired by David Robinson's baseball work) but XGBoost excluded it. Harry Shomer's two-stage approach (using initial xG predictions as talent inputs) noted as promising alternative.

### Acknowledged Limitations

- No passing information (origin, timing, cross-ice passes)
- No player positioning (requires tracking data)
- No zone entry quality (stretch passes, controlled vs uncontrolled)

## Part 2: WAR/GAR Framework

### RAPM Foundation

Regularized Adjusted Plus-Minus using ridge regression (L2 / Tikhonov regularization). Operates at the shift level using RTSS data. Accounts for all players on ice, score state, and zone starts.

**Four RAPM models built:**
1. Even-Strength Offense (target: goals for)
2. Even-Strength Defense (target: expected goals against)
3. Powerplay Offense (target: goals for)
4. Shorthanded Defense (target: expected goals against)

Each separated by forwards and defensemen = 8 total RAPM outputs. Training span: 11 seasons (2007-08 through 2017-18).

### Statistical Plus-Minus (SPM) Layer

Two-stage modeling: RAPM coefficients become targets for SPM models using RTSS-derived metrics as predictors.

**SPM feature set includes:**
- TOI metrics and percentages
- Individual shot generation (iSF, iFF, iCF, ixG) — adjusted and unadjusted
- Zone-specific statistics (offensive/neutral/defensive)
- Faceoff percentages (regressed)
- Relative-to-teammate metrics (using total teammate performance, not "without player")
- Giveaways, takeaways, hit differential by zone

### Algorithm Ensemble

Five algorithms tested; three selected per component via 300-iteration CV (80/20 split):
- Ordinary Least Squares
- Elastic Net
- Support Vector Machines (linear kernel)
- Cubist
- Bagged MARS

Weighted voting ensemble optimizing out-of-sample RMSE.

### Team Adjustment

Adapted from basketball's Box Plus/Minus. Scaling multipliers empirically determined (grid search 0.1-3.0):
- EV Offense: 1.6x
- EV Defense: 1.4x
- PP Offense: 1.3x
- SH Defense: 1.3x

### GAR Components

| Component | Abbrev | Description |
|-----------|--------|-------------|
| EV Offense | EVO | Even-strength offense goals above replacement |
| EV Defense | EVD | Even-strength defense goals above replacement |
| PP Offense | PPO | Powerplay offense goals above replacement |
| SH Defense | SHD | Shorthanded defense goals above replacement |
| Penalties Taken | Take | Inverted, position-adjusted |
| Penalties Drawn | Draw | Position-adjusted |

GAR = EVO + EVD + PPO + SHD + Take + Draw

WAR and SPAR derived via regression of team goal differential to wins/standing points (rolling 3-season windows).

### TOI Thresholds

- Even-strength: 60 minutes minimum
- Special teams: 25 minutes minimum
- Below threshold: regressed to average (0.0)

### Replacement Level

Aggregate rate below average of all skaters outside top 13 forwards or top 7 defensemen per team per season (2007-2019).
