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

## Current Implementation Status (as of 2026-05-01)

Status here is verified against the live database, not just self-reported from prior commits.

| Phase | Status | Evidence |
|-------|--------|----------|
| Phase 0 — contracts, schema, reproducibility | **Complete** | `_XG_EVENT_SCHEMA_VERSION = "v5"` (`src/database.py`); live validation run found all 2,122,963 `shot_events` rows at v5 and zero stale training-eligible rows; version-aware backfill (`game_has_current_shot_events`, `delete_game_shot_events`) present; `validate_shot_events_quality` covers enums/ranges/duplicates. |
| Phase 1 — event/state foundation | **Complete** | `normalize_coordinates`, distance/angle, 11-type shot taxonomy, score/manpower/time classifiers in `src/xg_features.py`. Pre-2020 negative-x rate is now 0.0 (was ~50% at v2). Pre-event score tracker `_track_score` prevents post-goal leakage. |
| Phase 2 — context feature engineering | **Complete (with two criteria formally deferred)** | `game_context` populated (26,343 rows at v1) with rest/travel/timezone features; `validate_game_context_quality` added. Faceoff decay bins implemented. `populate_venue_diagnostics` is wired into the scraper pipeline via `finalize_season_diagnostics` and runs per season. VIF review done on live data (see below). The two remaining acceptance criteria — held-out faceoff-decay validation and zone-start change-on-the-fly inference — are formally deferred to their gating dependencies: Phase 2.5.2 (`src/validation.py` helpers) and a future shifts-ingestion branch, respectively. |
| Phase 2.5 — rigor foundation (new, gates Phase 3) | **In progress** | 2.5.1 and 2.5.2 are implemented in `src/` with tests; live player readiness now passes with 4,694 `players`, 831,573 `player_game_stats` rows, and 831,573 current-version `player_game_features` rows. 2.5.3 now has a live v5 validation scorecard artifact that passes all 8 gates; 2.5.4 now has an initial correction table (`venue_bias_corrections`), shrinkage-based distance adjustment parameters wired into `finalize_season_diagnostics`, event-frequency scorekeeper diagnostics, rolling venue-regime classification, a JSON scorecard exporter, and a DB-backed live runner. The latest live venue-correction scorecard passes held-out log-loss and home-ice guardrail gates but fails both distance/location and event-frequency residual z-score gates under the prior max-z policy; the next live run can evaluate the new regime-aware gates. 2.5.5 has a recorded decision and an enforced loader guard (`load_training_shot_events`) excluding pre-2009 seasons and non-training shot rows. |
| Phase 3 — baseline xG model | **Ready to start** | No training code in `src/`. The live validation scorecard now passes 8/8 gates with a selected calibrated logistic model (`artifacts/validation_scorecard_latest.md`), so Phase 3 model implementation can proceed while keeping unresolved features excluded. |
| Phase 4 — enhanced xG model | **Not started** | Depends on Phase 3. |
| Phase 5 — RAPM on xG | **Blocked on downstream prerequisites** | Player identity and player-game foundations are populated and validated. Remaining blockers are validated xG predictions with uncertainty plus future shift/TOI/on-ice data needed for a true RAPM design matrix. |
| Phase 6–7 — team strength, hardening | **Not started** | Depends on Phase 3–5. |

### Critical blockers (must close before Phase 3 modeling is meaningful)

1. **Player database blocker is closed.** Live validation on 2026-05-01 found `ids_missing_and_not_unavailable = 0`, 2,301/2,301 players with ≥ 50 career shots have `shoots_catches`, `player_game_stats` covers all 831,573 event-derived player-game pairs, and `player_game_features` now has 831,573 current-version rows with zero missing, duplicate, stale-version, or unsupported-value rows. The remaining RAPM data gap is shift/TOI/on-ice exposure and xG prediction/residual inputs, not player identity metadata.
2. **2007–2008 shot-distance anomaly.** Average `distance_to_goal` for 2007–08 is ~19–20 units vs ~34 for 2009+. `wrap-around` and `deflected` shots have `NULL` distances in 2007–08 (coordinates absent in that era). **Phase 2.5.5 decision:** exclude pre-2009 seasons from model-training inputs; enforced by `load_training_shot_events` and test coverage.
3. **Venue bias correction is implemented but not accepted.** `scripts/export_venue_correction_validation_from_db.py` runs the Phase 2.5.4 gates against live v5 data using only prior-season venue adjustments for each held-out shot and the same tightened training contract as the validation scorecard. The 2026-05-01 scorecard passes held-out log-loss (`delta = -0.000017`) and home-ice over-correction (`removed = -0.013`, limit 0.500) but fails distance/location residuals (`max |z| = 4.067`, limit < 2.000; worst venue-season `20092010:Madison Square Garden`) and sample-adequate event-frequency residuals (`max |z| = 3.572`, limit < 2.000; worst venue-season `20112012:Prudential Center`) under the original max-z residual policy. As of 2026-05-03, the scorecard also supports a rolling venue-regime policy: prior-only rolling estimates provide production-safe context, centered rolling estimates are diagnostic only, and candidate spikes are labeled `persistent_bias`, `temporary_supported_regime`, or `unexplained_or_confounded`. Keep the correction out of production xG training until a live regime-aware run shows no blocking unexplained/confounded residuals, does not worsen held-out log-loss, and does not over-remove home-ice advantage.
4. **Validation scorecard blocker is resolved for selected features.** The 2026-04-30 live v5 validation framework run passes 8/8 gates: mean AUC 0.7551, calibration slope 0.9870, max decile error 0.407 pp, ECE 0.193 pp, subgroup max error 1.24 pp, and AUC drift +0.0001/season. Faceoff, rest/travel, raw venue features, and other unresolved candidates remain listed as excluded pending and do not feed the selected model.

### Phase 2 multicollinearity review (VIF, live data, 2026-04-19)

Computed with `compute_vif` (`src/stats_helpers.py`) over the complete-case subset of `game_context` (26,027 of 26,343 rows after dropping nulls). Threshold: `VIF_THRESHOLD = 5.0`.

| Feature set | max VIF | Finding |
|---|---|---|
| All seven `game_context` features | ∞ | `rest_advantage`, `home_rest_days`, `away_rest_days` all return ∞ because `rest_advantage == home_rest_days − away_rest_days` is an exact linear combination. |
| Drop `rest_advantage` (recommended) | 2.755 (`away_rest_days`) | All six remaining features pass (`home_rest_days` 2.744, `away_is_back_to_back` 1.074, `home_is_back_to_back` 1.072, `travel_distance_km` 1.011, `timezone_delta` 1.002). |

**Decision for Phase 3 feature matrix.** Do **not** include `rest_advantage` alongside `home_rest_days` + `away_rest_days` in the same model. The composite adds no information and breaks identifiability. Either include both absolute rest levels (recommended for ridge — richer signal, bounded VIF), or include only `rest_advantage` (loses information about absolute rest). Keep `rest_advantage` in the schema as an analytical convenience but exclude it from the training design matrix.

**Null-rate review (same run, via `validate_game_context_quality`).** Out of 26,343 rows: 34 structural rest-day nulls (first game of each team's season), 49 additional rest nulls to investigate, 281 (1.07%) travel/timezone nulls that trace to missing arena coverage. Travel null rate is 0.07 pp above the 1% acceptance threshold and should be cleaned up during Phase 2.5.5 data-quality triage.

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

5. **Calibration.** A probability model passes calibration if: calibration slope ∈ [0.95, 1.05], max decile calibration error < 1 percentage point, expected calibration error < 0.5 percentage points, and max subgroup calibration error < 3 percentage points. Hosmer-Lemeshow statistic/p-value is reported as a diagnostic, not a hard pass/fail gate on million-row holdout pools. Each segment (even-strength, power-play, short-handed, plus score-state strata) is checked separately.

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

Acceptance criteria (retrospective — phase complete):
- Every derived table stamps the row-producing code version in a column: `shot_events.event_schema_version`, `game_context.context_schema_version`, `player_game_features.feature_set_version`. Version constants are single-sourced in `src/database.py` (`_XG_EVENT_SCHEMA_VERSION = "v5"`, `_GAME_CONTEXT_SCHEMA_VERSION = "v1"`).
- Version-aware backfill is idempotent: `game_has_current_shot_events` checks both row existence and current version; `delete_game_shot_events` removes stale rows before `_process_game` re-inserts. Rerunning the scraper against an already-current DB performs no additional inserts.
- 100% of live `shot_events` rows are at the current version (verified 2026-04-30: 2,122,963/2,122,963 at v5).
- Quality validators (`validate_shot_events_quality`, `validate_player_game_stats_quality`) cover duplicate keys, enum domains, negative TOI, and value ranges and are exercised by `tests/`.

## Phase 1: Event/state foundation
- Normalize shot coordinates and shot type taxonomy.
- Build score-state, time-remaining, manpower-state labels.
- Tag faceoffs and sequence boundaries.

Acceptance criteria (retrospective — phase complete):
- Coordinate normalization (`normalize_coordinates`, `src/xg_features.py:96-120`) produces a right-attacking-zone convention. Pre-2020 negative-x rate is 0.0 on current-schema data (was ~50% at v2); verified by live DB query.
- Shot-type taxonomy accepts the 11 raw NHL `shotType` values present in current `shot_events` (no `unknown`/`other` fallthrough for in-vocabulary values).
- Score-state labels derive from a pre-event tracker (`_track_score`, `src/xg_features.py:136-157`) so a shot's `pre_event_score_diff` reflects the state at shot time, not after any goal that shot may produce. This is the project's primary leakage guardrail at Phase 1.
- Manpower-state and time-remaining classifiers produce non-null labels for every row in `shot_events` (covered by quality validators).
- Faceoff and sequence-boundary tagging captured in `faceoff_zone_code` on every row following a faceoff event within the same sequence window.

## Phase 2: Context feature engineering

Deliverables:
- Rest/travel comparative features (`game_context`).
- Zone-start and change-on-the-fly estimates.
- Post-faceoff decay features.
- Venue and scorer metadata.

Acceptance criteria:
- ✅ `game_context` populated for every game with a `shot_events` row; null rates on rest/travel/timezone fields < 1%. **Met (modulo 0.07 pp overage on travel/timezone, tracked under 2.5.5).** Validator: `validate_game_context_quality` in `src/database.py`.
- ⏸ Faceoff-decay bin boundaries validated on held-out data. **Deferred to Phase 2.5.2** — requires `src/validation.py` helpers (`run_temporal_cv`, `bootstrap_goal_rate_ci`) which currently live only in the notebook.
- ⏸ Zone-start features carry a documented inference accuracy estimate. **Deferred to shifts ingestion** — proper change-on-the-fly inference needs a populated `shifts` table. The raw `faceoff_zone_code` + `seconds_since_faceoff` captured today is a usable-but-weak proxy; the richer feature follows shift data.
- ✅ Multicollinearity review across rest/travel/score-state features; VIF < 5 for each. **Met**, with the finding that `rest_advantage` is a perfect linear combination of `home_rest_days − away_rest_days` and must be excluded from the Phase 3 design matrix. Remaining six features: max VIF = 2.76. See "Phase 2 multicollinearity review" block above.
- ✅ Venue bias diagnostics populated per season via `finalize_season_diagnostics` (`src/main.py`), running after the scraper/backfill loop.
- ❌ Venue correction layer has live DB-backed acceptance results but is not accepted for production xG training yet: held-out log-loss and home-ice guardrail pass, while distance/location and event-frequency residual z-score gates fail under the 2026-05-01 max-z Phase 2.5.4 scorecard. A rolling venue-regime scorecard path is now implemented and needs a fresh live artifact before acceptance can be reconsidered.

## Phase 2.5: Rigor Foundation (gates Phase 3)

Five deliverables, each gated by a quantitative acceptance criterion. This phase is new and exists because Phase 3 training against the current codebase would produce an under-specified model with empty player metadata, unvalidated evaluation code, and no venue correction — all of which would silently degrade the downstream RAPM.

### 2.5.1 Player metadata pipeline

- Add `get_player_metadata(player_id)` to `src/nhl_api.py`, using the module-level `_session` (per CLAUDE.md HTTP-reuse rule). Target endpoint: NHL player landing page or equivalent that returns `shoots_catches`, position, handedness, first/last name, and team history.
- Add `upsert_player(conn, player)` in `src/database.py` and use `executemany` for the backfill loop.
- Backfill every distinct `shooter_id` and `goalie_id` in `shot_events` (~2k–3k players); idempotent by construction.
- Populate `player_game_stats` and `player_game_features` as part of the same run. `player_game_features` v1 materializes row coverage, season, and `game_number_for_player`; TOI/points rolling columns remain `NULL` until shift or boxscore ingestion supplies real TOI and assist inputs.

Acceptance:
- ✅ `players.shoots_catches` populated for ≥ 99% of players with ≥ 50 career shots. Live result: 2,301/2,301 covered.
- ✅ `player_game_stats` covers every `(player_id, game_id)` that appears in raw event data; `validate_player_game_stats_quality` returns zero issues. Live result: 831,573/831,573 pairs covered.
- ✅ `player_game_features` covers every `player_game_stats` row at the current `_FEATURE_SET_VERSION`; `validate_player_game_features_quality` returns zero issues. Live result: 831,573/831,573 rows covered.

### 2.5.2 Promote validation helpers to `src/validation.py`

- Extract `bootstrap_goal_rate_ci`, `cohens_h`, `hosmer_lemeshow_test`, `calibration_slope_intercept`, `run_temporal_cv`, and constants `MIN_SHOTS_PER_CELL`, `COHEN_H_SMALL`, `MIN_TRAIN_SEASONS` from `notebooks/model_validation_framework.ipynb` into `src/validation.py`.
- Add `tests/test_validation.py` covering: CI coverage at known proportions (binomial simulation, target 95% coverage ± 1 pp), Hosmer-Lemeshow on synthetic calibrated vs miscalibrated data, Cohen's h sign/scale, and a small `run_temporal_cv` fixture that exercises forward-chaining without leakage.
- Refactor the notebook to import from `src/validation.py` (no duplicated logic).

Acceptance:
- All helpers importable from `src/`.
- `pytest -q` passes with the new tests.
- No duplicated validation logic remains in the notebook.

### 2.5.3 Run validation framework end-to-end on live v5 data

- Execute `notebooks/model_validation_framework.ipynb` against the real database. This is the first end-to-end validation run after the v5 backfill.
- Publish a committed scorecard artifact summarizing: base rate by season/manpower/era with CIs, feature ablation results, temporal CV metrics, calibration diagnostics, leakage-audit conclusions.
- **Execution harness added (2026-04-24):** `scripts/export_validation_scorecard.py` now executes the notebook and extracts the `VALIDATION SCORECARD` block into `artifacts/validation_scorecard_latest.md`.
- **Live run completed (2026-04-30):** after v5 backfill completed and the scorecard gates were remediated, `scripts/export_validation_scorecard.py` executed the validation notebook and exported `artifacts/validation_scorecard_latest.md` with 8/8 gates passing. The selected calibrated model uses distance, angle, shot type, manpower state, score state, and scaled manpower-distance/angle interactions; unresolved faceoff, rest/travel, and venue features remain excluded pending.

Acceptance:
- ✅ All pass/fail cells return concrete numbers (no NotImplemented / skipped cells).
- ✅ Scorecard artifact produced alongside the notebook (`artifacts/validation_scorecard_latest.md`; generated notebook: `artifacts/model_validation_framework.executed.ipynb`).
- ✅ Live v5 scorecard passes all gates: AUC 0.7551, calibration slope 0.9870, max decile error 0.407 pp, ECE 0.193 pp, subgroup max error 1.24 pp, AUC drift +0.0001/season.

### 2.5.4 Venue bias correction implementation

- Populate `venue_bias_diagnostics` for all venue-seasons with ≥ `MIN_SHOTS_PER_CELL` shots (currently 0 rows).
- Implement correction. Two approaches are documented in `knowledge_base/wiki/concepts/venue-scorekeeper-bias.md`:
  - **CDF-matching (Schuckers):** quantile-map each venue's shot-distance distribution to the league distribution.
  - **Hierarchical venue intercepts:** add a partially-pooled venue-season intercept to the xG model, shrinking toward a league prior.
- Implement one approach; decision recorded.
- **Guardrail evaluator added (2026-04-24):** `src/validation.py::evaluate_venue_correction_holdout` now computes held-out log-loss delta and the share of baseline home-ice advantage removed by correction, with a pre-registered threshold `VENUE_CORRECTION_MAX_HOME_ICE_ADVANTAGE_REMOVAL = 0.5` and regression tests in `tests/test_validation.py`.
- **Scorecard harness added (2026-04-28, expanded 2026-05-01 and 2026-05-03):** `src/validation.py::evaluate_venue_correction_scorecard` combines held-out log-loss, home-ice over-correction, distance/location residual z-score, and event-frequency residual z-score gates; it now optionally evaluates residual gates using rolling venue-regime diagnostics instead of a blunt max-z veto. `scripts/export_venue_correction_validation.py` exports a Markdown artifact from a metrics JSON payload.
- **Live DB runner added and executed (refreshed 2026-05-01; regime-aware path added 2026-05-03):** `scripts/export_venue_correction_validation_from_db.py` builds leakage-safe temporal CV metrics from SQLite by applying only the latest prior-season venue distance adjustment to each held-out shot, using the same model-training contract as `load_training_shot_events`. It now also computes normalized event-frequency diagnostics by venue-season, event group, and game-type scope. The primary frequency gate uses sample-adequate regular-season training attempts; blocked-shot and all-attempt frequencies are diagnostic only. The runner now attaches rolling venue-regime diagnostics: prior-only rolling estimates are production-safe, centered rolling estimates are explicitly diagnostic, and supported temporary or persistent regimes are reportable rather than automatically blocking. It writes `artifacts/venue_correction_validation_latest.md`. Current committed result remains the 2026-05-01 max-z artifact: log-loss and home-ice gates pass, corrected-distance residuals fail (`max |z| = 4.067`), and event-frequency residuals fail (`max |z| = 3.572`), so the current correction policy remains exploratory until the regime-aware scorecard is rerun.

Acceptance:
- ✅ Held-out log-loss does not worsen after applying correction (live DB scorecard `delta = -0.000017`).
- ❌ Distance/location residual gate has not yet passed. Under the original max-z policy, every sample-adequate corrected-distance venue-season must satisfy `|z| < 2` (live DB scorecard `max |z| = 4.067`). Under the new regime-aware policy, residuals above threshold are accepted only if classified as supported `persistent_bias` or `temporary_supported_regime`; `unexplained_or_confounded`, `population_shift_detected`, and `insufficient_evidence` rows remain blocking.
- ❌ Event-frequency residual gate has not yet passed. Under the original max-z policy, every sample-adequate regular-season training-attempt venue-season must satisfy `|z| < 2` (live DB scorecard `max |z| = 3.572`). Under the new regime-aware policy, supported scorer regimes can be reported as non-blocking, while unexplained/confounded frequency residuals remain blocking. Frequency diagnostics also report blocked-shot and all-attempt event groups as non-blocking diagnostics.
- ✅ Guardrail test (pre-registered): correction must not eliminate > 50% of the home-ice goal-rate advantage (live DB scorecard `removed = -0.013`, limit 0.500).

### 2.5.5 Pre-2009 data-quality triage

- Investigate the 2007–08 shot-distance anomaly (avg distance ~19–20 vs ~34 for 2009+; NULL distances for `wrap-around` and `deflected` shots in those seasons).
- **Decision (2026-04-24): choose option (a)** — exclude pre-2009 seasons from model training for the baseline xG path. Rationale: pre-2009 shot coordinates are structurally incomplete in the source feed, so distance/angle repair would require non-trivial reconstruction assumptions that are out of scope for Phase 2.5 and risk introducing synthetic bias. This exclusion is now enforced in `src/database.py::load_training_shot_events` with tests in `tests/test_database.py`.
- **Training contract tightened (2026-04-30):** `load_training_shot_events` now also restricts model inputs to regular-season/playoff in-game shots, excludes regular-season shootouts and blocked shots, requires non-null geometry/type/manpower/score state, and rejects rows where `shot_event_type` disagrees with `is_goal`. The DB-backed venue-correction runner uses the same contract.

Acceptance:
- ✅ Written decision recorded in this roadmap.
- If pre-2009 data is kept for training, no NULL `distance_to_goal` in the final training input.
- ✅ If excluded, the exclusion is enforced in the model's training-data loader with a test.

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
- Calibration slope ∈ [0.95, 1.05].
- Max decile calibration error < 1 percentage point and expected calibration error < 0.5 percentage points; report Hosmer-Lemeshow as a diagnostic.
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
- Player design matrix built from populated `players` dim and `player_game_features`; no longer blocked on Phase 2.5.1, but still requires xG prediction/residual inputs plus shift/TOI/on-ice exposure data.
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
- `05_xg_model_training_and_calibration.md` — explicit practical calibration targets (slope, max decile error, ECE, subgroup error); minimum segment sample sizes.
- `06_rapm_on_xg.md` (RAPM component) — uncertainty interval methodology; λ selection procedure; year-over-year stability threshold.
- `07_team_strength_aggregation.md` — aggregation-weight specification; uncertainty propagation methodology; baseline and pre-registered lift threshold.
- `09_handedness_and_effective_angle.md` — replace visual/qualitative checks with formal hypothesis tests; Phase B2 precondition defined as a specific statistical criterion.

`08_platform_extensibility_and_reuse.md` is infrastructure; no statistical rigor update needed beyond explicit contract assertions.
