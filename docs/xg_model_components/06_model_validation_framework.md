# Component 06: Model Validation Framework

## Status

**Live v5 validated.** The notebook now runs end-to-end against the local v5 database through `scripts/export_validation_scorecard.py` and writes `artifacts/validation_scorecard_latest.md` plus the executed notebook artifact. The 2026-04-30 run passed all 8 scorecard gates with the selected calibrated model.

## Scope

Establish the validation infrastructure missing from the existing EDA notebooks (zone start, rest/travel, venue bias, faceoff decay) and produce a concrete pass/fail scorecard answering "are we ready to train an xG model?"

## Motivation: Assessment of Current Validation

### What the existing notebooks do well
- **Structured gate-decision framework** — each notebook answers a specific feature hypothesis
- **Pre-event score tracking** — `_track_score()` in `xg_features.py` prevents the most common leakage trap
- **Schema-layer data contracts** — `validate_shot_events_quality()` / `validate_player_game_stats_quality()` enforce enums, ranges, duplicates
- **Versioned derived data** — `_XG_EVENT_SCHEMA_VERSION` enables automatic stale-row detection
- **Venue bias analysis** — home-away asymmetry test is a well-designed quasi-experiment
- **Zone-separated decay** — exponential fits with R-squared provide quantitative bin boundary justification

### Critical gaps (High severity)

| Gap | Why it matters |
|-----|---------------|
| **No train/test separation** | All 4 notebooks compute stats on the entire dataset. Bin boundaries, z-score thresholds, and collinearity cutoffs are fit on the same data they'd be evaluated on. |
| **No statistical tests** | Every notebook relies on visual inspection and point estimates. With 100k+ shots, tiny meaningless differences appear "clear" in bar charts. No CIs, no p-values, no effect sizes. |
| **No calibration analysis** | For ~8% base rate, calibration matters more than discrimination. A naive 0.08-everywhere model has decent log loss. No reliability diagrams exist. |
| **No conditional feature importance** | Notebooks ask "does this feature correlate with goals?" but never "does it improve predictions given distance + angle + shot type?" Univariate signal is necessary but insufficient. |
| **No temporal stability check** | Data spans 2007-2025 with rule changes, tracking data introduction (2019), COVID hub cities (2020-21). No notebook checks if findings hold across eras. |
| **Incomplete leakage audit** | Score tracking is handled, but faceoff zone perspective (shooting team vs. faceoff winner), `seconds_since_faceoff` staleness, and game-context confounders (rest proxying for team quality) are unaddressed. |

### Medium severity gaps

| Gap | Why it matters |
|-----|---------------|
| **No sample size adequacy checks** | Stratified analyses (zone x time x manpower) create cells with <100 shots. At 8% base rate, need ~400+ events per cell for 80% power to detect 50% relative difference. |
| **Exponential decay R-squared is in-sample** | Faceoff decay fits never cross-validate. High R-squared with enough data doesn't prove generalization. |
| **Venue correction not validated end-to-end** | Z-scores flag outliers but no test shows correction improves held-out calibration. |

## Deliverables

A single notebook: `notebooks/model_validation_framework.ipynb`

### Step 1: Base rate stability analysis
- Compute `is_goal` rate by: season, manpower state, period, era (pre/post-tracking)
- Flag segments where base rate shifts >1pp
- Source: `shot_events` table joined with `games` for season

### Step 2: Statistical rigor retrofit
- For each feature group (zone start, rest/travel, venue, faceoff decay), compute:
  - Bootstrap 95% CIs on goal rates per category
  - Chi-squared tests for categorical features
  - Cohen's h effect sizes to separate statistical from practical significance
  - Minimum detectable effect given cell sizes
- Report which stratified cells are underpowered (<400 shots)

### Step 3: Temporal cross-validation harness
- Implement season-block CV: train on seasons 1..k, evaluate on k+1
- For calibrated scorecard predictions, train the base model before the prior season, fit a Platt calibrator on the immediately prior season, and evaluate the next season
- Use a selected logistic baseline on distance, angle, shot type, manpower state, score state, and scaled manpower-distance/angle interactions
- Compute per-fold: AUC-ROC, AUC-PR, log loss, Brier score
- Retain the simpler distance/angle/shot-type model as the ablation baseline that feature additions must beat

### Step 4: Calibration analysis
- Reliability diagrams (calibration curves) for the baseline model
- Per-segment calibration: 5v5, PP, SH separately
- Hosmer-Lemeshow statistic/p-value across 10 decile bins as a diagnostic
- Practical calibration gates: slope in [0.95, 1.05], max decile calibration error < 1pp, expected calibration error < 0.5pp
- Calibration slope and intercept per held-out season

### Step 5: Conditional feature importance (ablation)
- For each candidate feature group, compare baseline+feature vs. baseline-only
- Metrics: delta log loss, delta AUC, delta Brier on held-out seasons
- Features that don't improve held-out metrics by a meaningful threshold get flagged
- For faceoff recency: explicitly compare continuous (log-transformed `seconds_since_faceoff`) vs. binned representations. The existing notebooks use round-number bin cutoffs (0-5s, 6-10s) which are arbitrary. The exponential decay fits from `faceoff_decay_analysis.ipynb` suggest a continuous feature is more natural; bins should only be used for diagnostics with data-driven boundaries from inflection points, not round numbers.

### Step 5b: Venue bias — per-season validation
- The existing `venue_bias_analysis.ipynb` already computes per-season z-scores and checks seasonal stability (section 7). The validation notebook will:
  - Verify that per-season venue corrections outperform pooled corrections on held-out data
  - Check for scorer turnover effects (venues where z-score sign flips between seasons)
  - Confirm that the `populate_venue_diagnostics(conn, season)` function's per-season design is validated end-to-end against model calibration

### Step 6: Leakage audit table
- Systematic per-feature documentation:
  - Available at shot time? (yes/no)
  - Encodes post-shot information? (yes/no)
  - Proxies for confounder? (assessment)
- Flag `faceoff_zone_code` perspective ambiguity and `seconds_since_faceoff` staleness

### Step 7: Validation scorecard
- Summary table with pass/fail criteria:
  - Discrimination: AUC-ROC > 0.75 on temporal holdout
  - Calibration: slope in [0.95, 1.05], max decile calibration error < 1pp, expected calibration error < 0.5pp; Hosmer-Lemeshow reported as diagnostic only
  - Temporal stability: <0.02 AUC degradation per season
  - Feature-level: each feature shows positive ablation delta
  - Subgroup: max absolute calibration error < 0.03 across segments

## Testing and debugging

The notebook is written against the real database schema (`shot_events`, `games`, `game_context`, `venue_bias_diagnostics`). Use `scripts/export_validation_scorecard.py --db-path data/nhl_data.db` for the authoritative live run; the exporter streams notebook progress and writes the committed Markdown scorecard artifact.

## Dependencies

`scikit-learn` (calibration_curve, roc_auc_score, brier_score_loss), `scipy` (chi2_contingency), `matplotlib`, `numpy`, `seaborn` — install into the project venv.

## Validation criteria (defining "sufficient")

For a rare-event binary classification problem with ~8% base rate, "sufficient validation" means:

1. **Discrimination:** AUC-ROC > 0.75 on held-out temporal test set
2. **Calibration:** Slope in [0.95, 1.05], max decile calibration error < 1pp, expected calibration error < 0.5pp, and max subgroup calibration error < 3pp within 5v5/PP/SH segments. Hosmer-Lemeshow is reported across 10 decile bins as a diagnostic, not a hard gate on million-row holdout pools.
3. **Temporal stability:** Metrics hold across 3+ consecutive held-out seasons without retraining; degradation >0.02 AUC per season signals concept drift
4. **Feature-level:** Each feature shows (a) statistically significant univariate association (bootstrap CI on odds ratio excludes 1.0), (b) positive ablation delta on held-out log loss, (c) no detected leakage
5. **Subgroup fairness:** Max absolute calibration error < 0.03 across manpower/score state segments
6. **Reproducibility:** Feature generation deterministic and versioned (already satisfied by schema versioning infrastructure)
