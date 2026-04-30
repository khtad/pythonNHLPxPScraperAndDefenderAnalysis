# Venue Correction Validation Scorecard

Generated: 2026-04-30T11:54:13+00:00

Correction method: `distance_mean_shrinkage_v1 (latest prior-season only)`

Training snapshot: `schema=v5; seasons=20092010-20252026; rows=1,853,808; adjusted_rows=1,606,666`

## Acceptance Gates

| Gate | Result | Metric |
|------|--------|--------|
| Held-out log loss non-worse | PASS | delta = -0.000017 |
| Home-ice over-correction guardrail | PASS | removed = -0.013, max = 0.500 |
| Residual venue z-scores | FAIL | max abs(z) = 4.067, limit < 2.000 |

## Summary Metrics

- Overall pass: FAIL
- Holdout rows: 1,524,903
- Venues evaluated: 532
- Baseline log loss: 0.229287
- Corrected log loss: 0.229270
- Baseline home advantage: 0.001853
- Corrected home advantage: 0.001876
- Worst residual venue: `20092010:Madison Square Garden`

## Notes

Generated from live SQLite data with forward-chaining temporal CV. Each shot uses the latest venue distance adjustment from a season before the shot's season; same-season venue corrections are not used for holdout rows. Residual z-scores are venue-season corrected-distance mean z-scores, because the implemented correction targets distance bias rather than shot-count bias.
