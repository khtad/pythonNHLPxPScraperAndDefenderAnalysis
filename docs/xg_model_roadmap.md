# NHL xG Model Roadmap (Main Plan)

## Purpose
This document updates the prior strength-estimation plan and pivots toward building a full expected-goals (xG) system that can support:

1. shot-level xG estimation,
2. player RAPM-style value estimation,
3. team strength from aggregated player impacts.

The target architecture must be modular enough to support incremental delivery and future model upgrades.

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
- Add rest/travel comparative features.
- Add zone start and change-on-the-fly estimates.
- Add post-faceoff decay features.
- Add venue and scorer metadata.

## Phase 3: Baseline xG model
- Train initial shot-level xG model (segmented by major game states).
- Calibrate probabilities and benchmark discrimination/calibration metrics.
- Introduce venue-bias correction and evaluate net impact.

## Phase 4: Enhanced xG model
- Add richer sequence features (rebound/rush/proxy passing context).
- Add season-era drift monitoring and recalibration workflow.
- Freeze versioned inference artifacts.

## Phase 5: RAPM on xG
- Build xG-based RAPM for offensive and defensive player impacts.
- Add regularization, hierarchical pooling, and uncertainty estimation.
- Validate stability versus responsiveness by position and role.

## Phase 6: Team strength from player RAPM
- Aggregate active-player RAPM into team offense/defense strengths.
- Keep goalie strength as separate module tied to shot-stopping residuals.
- Publish team vectors with uncertainty and trend deltas.

## Phase 7: Production hardening
- Automate data QA, retraining cadence, and drift alerts.
- Add reporting dashboards and reproducible backtest suite.
- Document model governance, changelog, and rollback procedures.

---

## Component Documents
Detailed component plans are in:

1. `docs/xg_model_components/01_shot_and_state_features.md`
2. `docs/xg_model_components/02_rest_travel_and_zone_context.md`
3. `docs/xg_model_components/03_faceoff_decay_modeling.md`
4. `docs/xg_model_components/04_scorekeeper_bias.md`
5. `docs/xg_model_components/05_xg_model_training_and_calibration.md`
6. `docs/xg_model_components/06_rapm_on_xg.md`
7. `docs/xg_model_components/07_team_strength_aggregation.md`
8. `docs/xg_model_components/08_platform_extensibility_and_reuse.md`

These sub-documents define deliverables, implementation ideas, validation criteria, and extension points for each major system component.
