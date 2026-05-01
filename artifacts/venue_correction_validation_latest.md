# Venue Correction Validation Scorecard

Generated: 2026-05-01T01:46:31+00:00

Correction method: `distance_mean_shrinkage_v1 (latest prior-season only)`

Training snapshot: `schema=v5; seasons=20092010-20252026; rows=1,853,808; adjusted_rows=1,606,666`

## Acceptance Gates

| Gate | Result | Metric |
|------|--------|--------|
| Held-out log loss non-worse | PASS | delta = -0.000017 |
| Home-ice over-correction guardrail | PASS | removed = -0.013, max = 0.500 |
| Distance/location residual z-scores | FAIL | max abs(z) = 4.067, limit < 2.000 |
| Event-frequency residual z-scores | FAIL | max abs(z) = 3.572, limit < 2.000 |

## Summary Metrics

- Overall pass: FAIL
- Holdout rows: 1,524,903
- Distance residual venue-seasons evaluated: 532
- Event-frequency residual venue-seasons evaluated: 525
- Baseline log loss: 0.229287
- Corrected log loss: 0.229270
- Baseline home advantage: 0.001853
- Corrected home advantage: 0.001876
- Worst distance/location residual: `20092010:Madison Square Garden`
- Worst event-frequency residual: `20112012:Prudential Center`

## Event-Frequency Diagnostics

Primary frequency gate: sample-adequate `regular_season:training_attempts`

- Candidate frequency anomalies: 187
- Supported real-scorekeeper regimes: 82

| Scope | Group | Venue-season | z | Events/game | Paired diff/game | 95% CI | d | Classification | Known prior |
|-------|-------|--------------|---|-------------|------------------|--------|---|----------------|-------------|
| `training_contract` | `all_attempts` | `20232024:MetLife Stadium` | 9.598 | 112.00 | 14.994 | [9.188, 20.800] | 1.826 | `insufficient_evidence` | NO |
| `regular_season` | `training_attempts` | `20232024:MetLife Stadium` | 9.597 | 112.00 | 14.638 | [8.450, 20.825] | 1.673 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20232024:MetLife Stadium` | 9.597 | 112.00 | 15.006 | [9.188, 20.825] | 1.824 | `insufficient_evidence` | NO |
| `regular_season` | `all_attempts` | `20232024:MetLife Stadium` | 9.587 | 112.00 | 14.625 | [8.450, 20.800] | 1.675 | `insufficient_evidence` | NO |
| `regular_season` | `training_attempts` | `20252026:Raymond James Stadium` | 6.105 | 107.00 | 1.200 | [1.200, 1.200] | 0.000 | `insufficient_evidence` | NO |
| `regular_season` | `all_attempts` | `20252026:Raymond James Stadium` | 6.095 | 107.00 | 1.175 | [1.175, 1.175] | 0.000 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20252026:Raymond James Stadium` | 5.924 | 107.00 | 2.326 | [2.326, 2.326] | 0.000 | `insufficient_evidence` | NO |
| `training_contract` | `all_attempts` | `20252026:Raymond James Stadium` | 5.911 | 107.00 | 2.302 | [2.302, 2.302] | 0.000 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20182019:Lincoln Financial Field` | 5.902 | 105.00 | 9.429 | [9.429, 9.429] | 0.000 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20182019:Scandinavium` | -5.689 | 68.00 | -8.200 | [-8.200, -8.200] | 0.000 | `insufficient_evidence` | NO |

## Notes

Generated from live SQLite data with forward-chaining temporal CV. Each shot uses the latest venue distance adjustment from a season before the shot's season; same-season venue corrections are not used for holdout rows. Distance residual z-scores are venue-season corrected-distance mean z-scores. Event-frequency residual z-scores use sample-adequate regular-season training attempts as the primary gate; blocked-shot and all-attempt frequencies are reported as diagnostics and remain outside the current shot-level xG training contract.
