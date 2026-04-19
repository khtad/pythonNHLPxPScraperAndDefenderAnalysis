# NHL xG Model Roadmap (Main Plan)

## Purpose
This document is the main plan for building a full expected-goals (xG) system that can support:

1. shot-level xG estimation,
2. player RAPM-style value estimation,
3. team strength from aggregated player impacts.

The target architecture must be modular enough to support incremental delivery and future model upgrades.

**Priority: RAPM-input quality.** This xG model is the input to an RAPM player-value model. Miscalibration, unmodeled uncertainty, or systematic bias in xG cascades into biased player and team estimates. Where rigor and speed trade off, this roadmap prefers rigor.

---

## Requested Feature Review and Suggested Improvements

## Your requested feature set (accepted)
- Shot type.
- Shot location.
- Game state by score (up/down buckets), time remaining, and expected points context.
- Game state by manpower (5v5, 5v4, 4v4, 5v3, 4v5, 3v5).
- Comparative rest with travel terms.
- Zone starts plus change-on-the-fly estimation.
- Post-faceoff shot volume/xG spike with decay.
- RAPM adjustments to player xG estimation.
- Team strength from aggregate player RAPM.
- Venue scorekeeper bias estimation.

## Recommended additions and refinements
1. **Separate model families by game state**
   - Build at least separate heads for even-strength, power-play, and short-handed contexts.
   - Rationale: shot danger calibration differs substantially by manpower state.

2. **Include shot preconditions and sequence context**
   - Rebounds, rush indicators, east-west pass proxy, prior event type, and time since prior event.
   - These generally improve discrimination beyond static location alone.

3. **Explicitly model shooter/goalie handedness interactions**
   - Include off-wing and same/opposite-handed release effects where data quality allows.
   - **Detailed plan:** See `docs/xg_model_components/09_handedness_and_effective_angle.md`
   - Phase B1: populate `shoots_catches`, add `is_off_wing` flag, let ridge regression learn interactions
   - Phase B2: geometric effective goal exposure angle (deferred until data validates the off-wing effect)

4. **Calibrate by season blocks (or era) and monitor drift**
   - Rink tracking and league style shifts can alter feature-outcome relationships.

5. **Define uncertainty outputs from day one**
   - Preserve confidence/credible intervals for player and team estimates, not just point values.

6. **Add strict leakage controls**
   - Ensure no post-shot or future-game information leaks into feature generation.

7. **Establish a reproducible feature store contract**
   - Versioned feature schema and deterministic generation to prevent silent training/inference mismatches.

---

## Target End-State Architecture

- **Layer A — Event Foundation:** canonical shot/event table, coordinate normalization, game-state labeling.
- **Layer B — Feature Store:** shot-level features, sequence context, rest/travel, zone start/change estimates, venue tags.
- **Layer C — xG Models:** calibrated probability models, segmented by state, with ongoing drift checks.
- **Layer D — RAPM on xG:** regularized player impacts on xGF/xGA, contextual adjustment terms.
- **Layer E — Team Strength Engine:** lineup/deployment-weighted aggregation to team Off/Def/Goalie strength.
- **Layer F — Reporting:** quality dashboards, uncertainty tracking, versioned rating outputs.

---

## Issues and Considerations

1. **Data quality and missingness**
   - Some historical feeds may have inconsistent coordinates, event timing, or shift metadata.

2. **Identifiability in RAPM**
   - Teammate and deployment confounding requires strong regularization and partial pooling.

3. **State imbalance**
   - Rare states (e.g., 3v5) need pooling strategy or hierarchical shrinkage.

4. **Venue effects vs true signal**
   - Scorekeeper bias correction must avoid removing legitimate home-ice tactical signal.

5. **Latency and recomputation cost**
   - Frequent backfills can be expensive; design incremental updates and artifact versioning.

6. **Explainability requirements**
   - Decision users need interpretable decomposition from shot quality to player to team strength.

7. **Forward compatibility**
   - Ensure model outputs can be consumed by future forecasting and scenario simulation tools.

---

## Current Implementation Status (as of 2026-04-19)

Status here is verified against the live database, not just self-reported from prior commits.

| Phase | Status | Evidence |
|-------|--------|----------|
| Phase 0 — contracts, schema, reproducibility | **Complete** | `_XG_EVENT_SCHEMA_VERSION = "v3"` (`src/database.py:21`); all 2,099,820 shots in `shot_events` are at v3; version-aware backfill (`game_has_current_shot_events`, `delete_game_shot_events`) present; `validate_shot_events_quality` covers enums/ranges/duplicates. |
| Phase 1 — event/state foundation | **Complete** | `normalize_coordinates`, distance/angle, 10-type shot taxonomy, score/manpower/time classifiers in `src/xg_features.py`. Pre-2020 negative-x rate is now 0.0 (was ~50% at v2). Pre-event score tracker `_track_score` prevents post-goal leakage. |
| Phase 2 — context feature engineering | **Partial (not "mostly complete")** | `game_context` populated (26,100 rows at v1) with rest/travel/timezone features. Faceoff decay bins implemented. **Venue bias: diagnostics code exists but `venue_bias_diagnostics` table is empty (0 rows); correction layer is not implemented.** Zone starts: only raw `faceoff_zone_code` captured; no on-the-fly/change-of-possession inference. |
| Phase 2.5 — rigor foundation (new, gates Phase 3) | **Not started** | See new section below. |
| Phase 3 — baseline xG model | **Not started** | No training code in `src/`. Validation framework exists only as notebook cells in `notebooks/model_validation_framework.ipynb` (scaffolding; never executed end-to-end on live data per `knowledge_base/log.md` 2026-04-07). |
| Phase 4 — enhanced xG model | **Not started** | Depends on Phase 3. |
| Phase 5 — RAPM on xG | **Blocked on data** | `players` dim has **0 rows**; `player_game_stats` and `player_game_features` are empty; no player/roster endpoint in `src/nhl_api.py`. |
| Phase 6–7 — team strength, hardening | **Not started** | Depends on Phase 3–5. |

### Critical blockers (must close before Phase 3 modeling is meaningful)

1. **`players` dim is empty (0 rows).** Blocks handedness features (off-wing flag, effective-angle interactions), `player_game_stats`, `player_game_features`, and every step of RAPM. No player metadata endpoint exists in `src/nhl_api.py`.
2. **2007–2008 shot-distance anomaly.** Average `distance_to_goal` for 2007–08 is ~19–20 units vs ~34 for 2009+. `wrap-around` and `deflected` shots have `NULL` distances in 2007–08 (coordinates absent in that era). This is a residual data-quality issue beyond the v2→v3 fix and must be triaged (exclude, repair, or tier) before training data is assembled.
3. **Venue bias correction is unimplemented.** `populate_venue_diagnostics` exists at `src/database.py:894-948` but the diagnostics table is empty and there is no correction layer. Diagnostics alone do not improve xG; they must be applied.
4. **Validation framework is unvalidated.** The helpers (`bootstrap_goal_rate_ci`, `cohens_h`, `hosmer_lemeshow_test`, `calibration_slope_intercept`, `run_temporal_cv`) live only inside `notebooks/model_validation_framework.ipynb`. They are not importable from `src/` and the notebook has never been executed against the live v3 database.

### Recommended model approach for Phase 3

Ridge-penalized logistic regression is the preferred baseline for this project (user preference, and well-suited to a calibrated binary target with interaction-heavy feature matrices):

- `sklearn.linear_model.LogisticRegressionCV(penalty='l2')` with scikit-learn-native CV for λ selection.
- Explicit interaction terms (shot_type × distance, shot_type × angle, is_off_wing × shot_type, is_off_wing × angle) — roughly 70 features after expansion.
- **Segmented training:** at minimum three heads — even-strength, power-play, short-handed — because shot-danger calibration differs substantially by manpower state and RAPM aggregates across these states.
- **Temporal split:** forward-chaining season-block CV per `run_temporal_cv` (≥ 3 train seasons, ≥ 3 held-out test seasons).
- **Benchmark (do not tune):** a GBDT baseline (LightGBM or XGBoost) on the same feature matrix, purely to confirm the ridge-logistic model is not leaving meaningful lift on the table. Report AUC/log-loss delta and move on.

---

## Rigor Standards

These standards apply to every phase from 2.5 onward and are derived from the project's statistical rigor framework in `CLAUDE.md` and the reference implementation in `notebooks/model_validation_framework.ipynb`. They are **non-negotiable for any result that informs a model design decision or a production artifact.** Exploratory analyses may label themselves as such and relax (1)–(2) only.

1. **Interval estimation.** Every reported rate or proportion carries a 95% bootstrap or Wilson confidence interval. Helper: `bootstrap_goal_rate_ci`. Point estimates without intervals are not acceptable evidence.

2. **Group comparisons.** Differences between categories are tested with chi-squared or Fisher's exact and accompanied by a Cohen's h effect size. Practical significance requires `|h| ≥ 0.2` AND adequate power. Helper: `cohens_h`.

3. **Sample adequacy.** At this project's ~8% goal base rate, a stratified cell needs at least **400 shots** to detect a 50% relative rate difference at 80% power. Cells below this threshold are flagged; no conclusions drawn.

4. **Temporal separation.** Training and evaluation use forward-chaining season-block CV (`run_temporal_cv`) with `MIN_TRAIN_SEASONS = 3` and at least three held-out test seasons that never participate in tuning.

5. **Calibration.** A probability model passes calibration if: Hosmer-Lemeshow p > 0.05, calibration slope ∈ [0.95, 1.05], and max subgroup calibration error < 3 percentage points. Each segment (even-strength, power-play, short-handed, plus score-state strata) is checked separately.

6. **Temporal stability.** AUC drift must be < 0.02 per season across held-out seasons. Drift beyond that is documented and triggers recalibration.

7. **Leakage audit.** Every candidate feature has a row in a written leakage-audit table (columns: *temporal availability*, *post-event information risk*, *confounder risk*, *resolution*). No feature enters a training set without this row.

8. **Uncertainty contract for RAPM input.** Every xG prediction delivered to the RAPM layer must carry either a bootstrap replicate set or a parametric variance. Point estimates alone break downstream credible intervals.

9. **Pre-registration for feature inclusion.** For any feature ablation, record the expected sign, effect-size threshold, and pass/fail criterion before running the evaluation. This prevents post-hoc threshold tuning.

---

## Roadmap to Completion

## Phase 0: Contracts, schema, and reproducibility
- Define canonical event schema and feature schema versions.
- Define training/inference data contracts and leakage guardrails.
- Build validation checks for required columns and value ranges.

## Phase 1: Event/state foundation
- Normalize shot coordinates and shot type taxonomy.
- Build score-state, time-remaining, manpower-state labels.
- Tag faceoffs and sequence boundaries.

## Phase 2: Context feature engineering

Deliverables:
- Rest/travel comparative features (`game_context`).
- Zone-start and change-on-the-fly estimates.
- Post-faceoff decay features.
- Venue and scorer metadata.

Acceptance criteria:
- `game_context` populated for every game with a `shot_events` row; null rates on rest/travel/timezone fields < 1%.
- Faceoff-decay bin boundaries validated on held-out data (decay terms improve held-out log-loss vs. a no-decay baseline by a pre-registered Δ threshold).
- Zone-start features carry a documented inference accuracy estimate (compare inferred zone to recorded faceoff_zone_code where overlap exists).
- Multicollinearity review across rest/travel/score-state features; VIF < 5 for each.

## Phase 2.5: Rigor Foundation (gates Phase 3)

Five deliverables, each gated by a quantitative acceptance criterion. This phase is new and exists because Phase 3 training against the current codebase would produce an under-specified model with empty player metadata, unvalidated evaluation code, and no venue correction — all of which would silently degrade the downstream RAPM.

### 2.5.1 Player metadata pipeline

- Add `get_player_metadata(player_id)` to `src/nhl_api.py`, using the module-level `_session` (per CLAUDE.md HTTP-reuse rule). Target endpoint: NHL player landing page or equivalent that returns `shoots_catches`, position, handedness, first/last name, and team history.
- Add `upsert_player(conn, player)` in `src/database.py` and use `executemany` for the backfill loop.
- Backfill every distinct `shooter_id` and `goalie_id` in `shot_events` (~2k–3k players); idempotent by construction.
- Populate `player_game_stats` and `player_game_features` as part of the same run.

Acceptance:
- `players.shoots_catches` populated for ≥ 99% of players with ≥ 50 career shots.
- `player_game_stats` covers every `(player_id, game_id)` that appears in raw event data; `validate_player_game_stats_quality` returns zero issues.

### 2.5.2 Promote validation helpers to `src/validation.py`

- Extract `bootstrap_goal_rate_ci`, `cohens_h`, `hosmer_lemeshow_test`, `calibration_slope_intercept`, `run_temporal_cv`, and constants `MIN_SHOTS_PER_CELL`, `COHEN_H_SMALL`, `MIN_TRAIN_SEASONS` from `notebooks/model_validation_framework.ipynb` into `src/validation.py`.
- Add `tests/test_validation.py` covering: CI coverage at known proportions (binomial simulation, target 95% coverage ± 1 pp), Hosmer-Lemeshow on synthetic calibrated vs miscalibrated data, Cohen's h sign/scale, and a small `run_temporal_cv` fixture that exercises forward-chaining without leakage.
- Refactor the notebook to import from `src/validation.py` (no duplicated logic).

Acceptance:
- All helpers importable from `src/`.
- `pytest -q` passes with the new tests.
- No duplicated validation logic remains in the notebook.

### 2.5.3 Run validation framework end-to-end on live v3 data

- Execute `notebooks/model_validation_framework.ipynb` against the real database. This is the first end-to-end validation run; the notebook has never been exercised on live data.
- Publish a committed scorecard artifact summarizing: base rate by season/manpower/era with CIs, feature ablation results, temporal CV metrics, calibration diagnostics, leakage-audit conclusions.

Acceptance:
- All pass/fail cells return concrete numbers (no NotImplemented / skipped cells).
- Scorecard artifact committed alongside the notebook.

### 2.5.4 Venue bias correction implementation

- Populate `venue_bias_diagnostics` for all venue-seasons with ≥ `MIN_SHOTS_PER_CELL` shots (currently 0 rows).
- Implement correction. Two approaches are documented in `knowledge_base/wiki/concepts/venue-scorekeeper-bias.md`:
  - **CDF-matching (Schuckers):** quantile-map each venue's shot-distance distribution to the league distribution.
  - **Hierarchical venue intercepts:** add a partially-pooled venue-season intercept to the xG model, shrinking toward a league prior.
- Implement one approach; decision recorded.

Acceptance:
- Held-out log-loss does not worsen after applying correction.
- Per-venue residual shot-count z-score `|z| < 2` after correction.
- Guardrail test (pre-registered): correction must not eliminate > X% of the home-ice goal-rate advantage, where X is chosen from the literature before evaluation (to prevent over-correction on legitimate tactical signal).

### 2.5.5 Pre-2009 data-quality triage

- Investigate the 2007–08 shot-distance anomaly (avg distance ~19–20 vs ~34 for 2009+; NULL distances for `wrap-around` and `deflected` shots in those seasons).
- Decide among: (a) exclude pre-2009 seasons from training; (b) repair via coordinate recovery from raw event rows; (c) add a `data_quality_tier` column to `shot_events` and weight training accordingly.

Acceptance:
- Written decision recorded in this roadmap or in component 01.
- If pre-2009 data is kept for training, no NULL `distance_to_goal` in the final training input.
- If excluded, the exclusion is enforced in the model's training-data loader with a test.

## Phase 3: Baseline xG model

Deliverables:
- `src/xg_model.py` exposing `train_segmented_xg(conn)` and `predict_xg(shot_events_df) -> (point_estimate, variance)`.
- At minimum three segmented model heads: even-strength, power-play, short-handed. Use hierarchical pooling across segments (league prior with partial pooling) if PP/SH cell counts fall below sample-adequacy in any stratification.
- Explicit leakage-audit table produced before fit, covering every feature.
- Ridge-penalized logistic regression via `LogisticRegressionCV(penalty='l2')`; feature matrix with explicit interaction terms (shot_type × distance, shot_type × angle, is_off_wing × shot_type, is_off_wing × angle).
- GBDT benchmark (LightGBM or XGBoost) on the same features, reported but not tuned, as a lift sanity check.
- Forward-chaining season-block CV; final held-out seasons frozen and unseen during tuning.
- Versioned inference artifact with a documented feature-set version and training snapshot ID.

Acceptance criteria (per segment, held-out evaluation):
- AUC-ROC > 0.75.
- Hosmer-Lemeshow p > 0.05.
- Calibration slope ∈ [0.95, 1.05].
- Max subgroup calibration error < 3 percentage points (score-state × manpower strata).
- AUC drift < 0.02/season across held-out seasons.
- Sample adequacy ≥ 400 shots/cell for every reported stratification.
- Leakage-audit table complete with no unresolved high-risk features.

## Phase 4: Enhanced xG model

Deliverables:
- Sequence features: rebound flag, rush indicator, time-since-prior-event, prior-event-type, proxy east-west pass. Each passes the leakage audit.
- Handedness features per component 09 Phase B1 (off-wing flag, off-wing × shot-type interactions). Phase B2 (geometric effective angle) gated on B1 results.
- **Uncertainty contract:** every xG prediction carries either a bootstrap replicate set (B ≥ 200 over ridge paths) or a parametric variance (from the logistic posterior). Predictions are persisted in a new `shot_xg_predictions` table with its own schema-version column (`_XG_PREDICTION_SCHEMA_VERSION`).
- Drift-detection job (monthly cadence): re-evaluate on latest season block; auto-flag if AUC drift > 0.02/season or calibration slope leaves [0.90, 1.10].
- Frozen v1 production inference artifact with reproducible training script.

Acceptance criteria:
- Each new feature passes pre-registration: documented expected sign and effect-size threshold **before** ablation, then confirmed in the ablation against held-out log-loss.
- Uncertainty coverage: 95% predictive intervals contain the observed goal rate within ± 1 pp on held-out segments.
- Drift-detection job runs to completion and emits a scorecard; at least one synthetic drift test confirms the alert triggers as expected.
- All Phase 3 acceptance criteria continue to hold on the enhanced model.

## Phase 5: RAPM on xG

Deliverables:
- Player design matrix built from populated `players` dim and `player_game_features` (blocked on Phase 2.5.1).
- Ridge (or elastic-net) regression on xGF/xGA; separate offensive (ORAPM) and defensive (DRAPM) outputs per `knowledge_base/wiki/methods/rapm-regularized-adjusted-plus-minus.md`.
- **Uncertainty propagation:** run RAPM on each bootstrap replicate of xG predictions (or via a parametric delta-method equivalent) and report player impacts with bootstrap CIs. Point-only RAPM is not accepted.
- Covariates: zone-start share, quality-of-teammate/competition, score-state exposure (per component 02).
- Regularization selection: nested CV to pick λ; report top-N / bottom-N ranking sensitivity to λ across a 10× range.

Acceptance criteria:
- Year-over-year player-impact Pearson r > 0.5 on players with ≥ pre-registered TOI threshold.
- Position-group sanity: top DRAPM cohort is defender-heavy; top ORAPM cohort is forward-heavy; goalies handled in a separate module.
- Max top-20 rank shift under 10× λ change ≤ pre-registered N%.
- Uncertainty intervals: coverage calibrated to nominal level on a synthetic design matrix with known truth.

## Phase 6: Team strength from player RAPM

Deliverables:
- Deployment-weighted aggregation of active-player ORAPM / DRAPM into team offense / defense vectors.
- Goalie strength as a separate module, tied to shot-stopping residuals (actual saves vs model-predicted saves given xG).
- Team vectors carry uncertainty intervals inherited from player RAPM (propagated via bootstrap replicates).
- Trend-delta reporting (week-over-week / month-over-month).

Acceptance criteria:
- Team-strength predictive lift over a team-only baseline is positive and significant on a held-out schedule, with pre-registered minimum AUC or log-loss improvement.
- Aggregation weights (TOI-based vs projected-TOI-based) documented; a sensitivity comparison is committed.
- Team CIs are non-trivial (median width > 0) and respect the uncertainty from RAPM.

## Phase 7: Production hardening

Deliverables:
- Automated data QA, retraining cadence, and drift alerts (consuming the Phase 4 drift-detection job output).
- Reproducible backtest suite callable from a single script.
- Model governance doc (changelog, roll-forward / rollback procedure, artifact retention policy).
- Reporting dashboards for xG segments, RAPM leaderboards with CIs, and team vectors with uncertainty bands.

Acceptance criteria:
- A full retraining run, starting from a clean checkout, reproduces the frozen production artifact bit-for-bit (given the same snapshot).
- Rollback procedure validated by a dry run (revert to previous artifact and confirm prediction parity with the prior scorecard).
- Drift alerts exercised by at least one synthetic test and one natural season transition.

---

## Component Documents

Detailed component plans are in:

1. `docs/xg_model_components/01_shot_and_state_features.md`
2. `docs/xg_model_components/02_rest_travel_and_zone_context.md`
3. `docs/xg_model_components/03_faceoff_decay_modeling.md`
4. `docs/xg_model_components/04_scorekeeper_bias.md`
5. `docs/xg_model_components/05_xg_model_training_and_calibration.md`
6. `docs/xg_model_components/06_model_validation_framework.md` — **rigor template; other components should reference its pass/fail scorecard.**
7. `docs/xg_model_components/06_rapm_on_xg.md`
8. `docs/xg_model_components/07_team_strength_aggregation.md`
9. `docs/xg_model_components/08_platform_extensibility_and_reuse.md`
10. `docs/xg_model_components/09_handedness_and_effective_angle.md`

These sub-documents define deliverables, implementation ideas, validation criteria, and extension points for each major system component.

### Component Doc Rigor Follow-up (not part of this roadmap's scope)

A rigor audit of the component docs found that only `06_model_validation_framework.md` fully meets the project's statistical rigor bar. The following docs should be updated in a separate pass to reference the validation-framework scorecard and adopt quantitative acceptance criteria (confidence intervals, effect sizes, per-segment calibration thresholds, sample adequacy):

- `01_shot_and_state_features.md` — needs formal leakage-audit methodology and quantitative coverage/class-balance thresholds.
- `02_rest_travel_and_zone_context.md` — zone-start inference accuracy estimate; VIF targets for multicollinearity review.
- `03_faceoff_decay_modeling.md` — cross-validated bin boundaries; pre-registered held-out log-loss improvement threshold.
- `04_scorekeeper_bias.md` — partial-pooling prior justification; pre-registered held-out improvement threshold and over-correction guardrail.
- `05_xg_model_training_and_calibration.md` — explicit calibration targets (slope, Hosmer-Lemeshow); minimum segment sample sizes.
- `06_rapm_on_xg.md` (RAPM component) — uncertainty interval methodology; λ selection procedure; year-over-year stability threshold.
- `07_team_strength_aggregation.md` — aggregation-weight specification; uncertainty propagation methodology; baseline and pre-registered lift threshold.
- `09_handedness_and_effective_angle.md` — replace visual/qualitative checks with formal hypothesis tests; Phase B2 precondition defined as a specific statistical criterion.

`08_platform_extensibility_and_reuse.md` is infrastructure; no statistical rigor update needed beyond explicit contract assertions.
