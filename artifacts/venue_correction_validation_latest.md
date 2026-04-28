# Venue Correction Validation Scorecard

Generated: 2026-04-28T21:33:45+00:00

Correction method: `distance_mean_shrinkage_v1 (latest prior-season only)`

Training snapshot: `schema=v5; seasons=20092010-20252026; rows=1,965,107; adjusted_rows=1,708,834`

## Acceptance Gates

| Gate | Result | Metric |
|------|--------|--------|
| Held-out log loss non-worse | PASS | delta = -0.000018 |
| Home-ice over-correction guardrail | PASS | removed = -0.011, max = 0.500 |
| Residual venue z-scores | FAIL | max abs(z) = 4.038, limit < 2.000 |

## Summary Metrics

- Overall pass: FAIL
- Holdout rows: 1,620,390
- Venues evaluated: 532
- Baseline log loss: 0.236553
- Corrected log loss: 0.236534
- Baseline home advantage: 0.002007
- Corrected home advantage: 0.002030
- Worst residual venue: `20092010:Madison Square Garden`

## Notes

Generated from live SQLite data with forward-chaining temporal CV. Each shot uses the latest venue distance adjustment from a season before the shot's season; same-season venue corrections are not used for holdout rows. Residual z-scores are venue-season corrected-distance mean z-scores, because the implemented correction targets distance bias rather than shot-count bias.
