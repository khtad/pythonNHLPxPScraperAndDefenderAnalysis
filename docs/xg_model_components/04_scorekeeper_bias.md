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
  over-correction, and max residual venue z-score.

## Extension points
- Official-specific bias estimation where metadata supports.
- Period-specific in-rink bias patterns.
