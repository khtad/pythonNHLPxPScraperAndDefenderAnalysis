# Component 04: Venue Scorekeeper Bias Estimation

## Scope
Estimate and correct rink/venue scorer effects that distort event recording and derived features.

## Deliverables
- Venue-level bias diagnostics for shot coordinates and event frequencies.
- Hierarchical venue-bias model with partial pooling by season.
- Corrected feature outputs and raw-vs-corrected comparatives.

## Validation
- Cross-venue residual comparison pre/post correction.
- Out-of-sample performance impact on xG calibration.
- Guardrail tests to avoid over-correction of true home effects.
- `scripts/export_venue_correction_validation.py` exports the Phase 2.5.4
  scorecard once a metrics JSON has been generated from a current database.
  The scorecard gates are held-out log-loss non-worsening, home-ice
  over-correction, distance/location residuals, and sample-adequate
  event-frequency residuals. Residual z-scores mark candidate venue-seasons
  for regime-aware review rather than acting as automatic vetoes.
- `scripts/export_venue_correction_validation_from_db.py` generates that
  metrics payload directly from SQLite with forward-chaining temporal CV and
  prior-season-only venue distance corrections under the shared model-training
  contract. It also computes normalized event-frequency diagnostics by
  venue-season, event group, and game-type scope plus paired distance-location
  diagnostics from in-memory prior-corrected distances. The distance diagnostic
  compares each visiting team's corrected shot distance at a venue against that
  same team's away shots elsewhere in the same season, stratified by shot type
  and manpower state. The primary frequency gate uses sample-adequate
  regular-season training attempts; blocked-shot and all-attempt frequencies
  are diagnostic only. The 2026-05-05 live v5 refresh uses the regime-aware
  residual gate. It passes held-out log-loss and home-ice guardrails but still
  fails the residual corrected-distance gate (`max |z| = 4.067`, 10 blocking
  regimes) and event-frequency residual gate (`max |z| = 3.572`, 5 blocking
  regimes), so the current correction remains exploratory rather than a
  production xG training feature.
- The 2026-05-03 rolling venue-regime extension, expanded with paired
  distance evidence on 2026-05-05, adds a less brittle
  acceptance path for historically real scorer spikes. `src/venue_bias.py`
  now computes prior-only rolling residual estimates for production-safe
  context, centered rolling estimates for exploratory historical diagnosis,
  and regime labels: `persistent_bias`, `temporary_supported_regime`, and
  `unexplained_or_confounded`. `evaluate_venue_correction_scorecard()` can
  use those labels so `|z| >= 2` is a candidate residual rather than an
  automatic veto. Supported temporary or persistent regimes are reported
  without automatically failing the correction layer. Unexplained/confounded
  residuals, population-wide shifts, insufficient evidence, held-out log-loss
  harm, and home-ice over-correction remain blocking.

## Extension points
- Official-specific bias estimation where metadata supports.
- Period-specific in-rink bias patterns.
- Change-point or EMA parameter search for venue-regime smoothing, with
  prior-season-only production estimates and centered estimates reserved for
  diagnostics.
