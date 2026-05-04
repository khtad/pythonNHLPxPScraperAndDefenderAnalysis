# Venue Correction Validation Scorecard

Generated: 2026-05-03T17:06:52+00:00

Correction method: `distance_mean_shrinkage_v1 (latest prior-season only)`

Training snapshot: `schema=v5; seasons=20092010-20252026; rows=1,854,812; adjusted_rows=1,607,409`

## Acceptance Gates

| Gate | Result | Metric |
|------|--------|--------|
| Held-out log loss non-worse | PASS | delta = -0.000017 |
| Home-ice over-correction guardrail | PASS | removed = -0.013, max = 0.500 |
| Distance/location residual z-scores | FAIL | blocking regimes = 24, supported regimes = 4, max abs(z) = 4.067, limit < 2.000 |
| Event-frequency residual z-scores | FAIL | blocking regimes = 4, supported regimes = 23, max abs(z) = 3.572, limit < 2.000 |

## Summary Metrics

- Overall pass: FAIL
- Holdout rows: 1,525,907
- Distance residual venue-seasons evaluated: 532
- Distance residual gate mode: `regime_aware`
- Distance blocking regimes: 24
- Distance supported regimes: 4
- Event-frequency residual venue-seasons evaluated: 525
- Event-frequency residual gate mode: `regime_aware`
- Event-frequency blocking regimes: 4
- Event-frequency supported regimes: 23
- Baseline log loss: 0.229272
- Corrected log loss: 0.229255
- Baseline home advantage: 0.001848
- Corrected home advantage: 0.001872
- Worst distance/location residual: `20092010:Madison Square Garden`
- Worst event-frequency residual: `20112012:Prudential Center`

## Rolling Venue-Regime Diagnostics


| Metric | Venue-season | z | Classification | Prior roll | Centered roll | Population anomaly share | Evidence | Known prior |
|--------|--------------|---|----------------|------------|---------------|--------------------------|----------|-------------|
| `distance_location` | `20092010:Madison Square Garden` | -4.067 | `persistent_bias` | n/a | -3.114 | 0.032 | NO | YES |
| `distance_location` | `20172018:Bell MTS Place` | 3.123 | `unexplained_or_confounded` | n/a | 1.456 | 0.091 | NO | NO |
| `distance_location` | `20192020:United Center` | -3.121 | `unexplained_or_confounded` | -1.237 | -1.840 | 0.062 | NO | NO |
| `distance_location` | `20222023:SAP Center at San Jose` | -2.885 | `unexplained_or_confounded` | 0.700 | 0.009 | 0.062 | NO | NO |
| `distance_location` | `20182019:NYCB Live/Nassau Coliseum` | -2.838 | `unexplained_or_confounded` | n/a | -1.383 | 0.031 | NO | NO |
| `distance_location` | `20202021:Amalie Arena` | -2.801 | `unexplained_or_confounded` | 0.476 | -0.896 | 0.065 | NO | NO |
| `distance_location` | `20122013:Wells Fargo Center` | 2.690 | `unexplained_or_confounded` | -0.618 | 0.947 | 0.067 | NO | NO |
| `distance_location` | `20112012:American Airlines Center` | 2.640 | `unexplained_or_confounded` | -0.110 | -0.144 | 0.031 | NO | NO |
| `distance_location` | `20222023:Little Caesars Arena` | 2.635 | `unexplained_or_confounded` | -0.547 | 0.596 | 0.062 | NO | NO |
| `distance_location` | `20212022:Enterprise Center` | -2.628 | `unexplained_or_confounded` | -0.049 | -0.280 | 0.061 | NO | NO |
| `event_frequency` | `20112012:Prudential Center` | -3.572 | `persistent_bias` | -3.033 | -3.103 | 0.033 | YES | NO |
| `event_frequency` | `20152016:Prudential Center` | -3.485 | `persistent_bias` | -2.771 | -2.592 | 0.067 | YES | NO |
| `event_frequency` | `20102011:Prudential Center` | -3.155 | `persistent_bias` | -2.910 | -3.212 | 0.033 | YES | NO |
| `event_frequency` | `20182019:Scotiabank Arena` | 2.982 | `temporary_supported_regime` | n/a | 2.445 | 0.031 | YES | NO |
| `event_frequency` | `20132014:Prudential Center` | -2.967 | `persistent_bias` | -3.103 | -2.771 | 0.033 | YES | NO |
| `event_frequency` | `20092010:Prudential Center` | -2.910 | `persistent_bias` | n/a | -3.033 | 0.033 | YES | NO |
| `event_frequency` | `20202021:Amalie Arena` | -2.845 | `unexplained_or_confounded` | -0.292 | -1.640 | 0.032 | NO | NO |
| `event_frequency` | `20252026:American Airlines Center` | -2.785 | `temporary_supported_regime` | 0.085 | -1.350 | 0.062 | YES | NO |
| `event_frequency` | `20142015:Prudential Center` | -2.765 | `persistent_bias` | -3.040 | -3.073 | 0.067 | YES | NO |
| `event_frequency` | `20232024:Nationwide Arena` | 2.607 | `temporary_supported_regime` | 0.538 | 1.465 | 0.062 | YES | NO |

## Event-Frequency Diagnostics

Primary frequency gate: sample-adequate `regular_season:training_attempts`

- Candidate frequency anomalies: 189
- Supported real-scorekeeper regimes: 82

| Scope | Group | Venue-season | z | Events/game | Paired diff/game | 95% CI | d | Classification | Known prior |
|-------|-------|--------------|---|-------------|------------------|--------|---|----------------|-------------|
| `training_contract` | `all_attempts` | `20232024:MetLife Stadium` | 9.598 | 112.00 | 14.994 | [9.188, 20.800] | 1.826 | `insufficient_evidence` | NO |
| `regular_season` | `training_attempts` | `20232024:MetLife Stadium` | 9.597 | 112.00 | 14.638 | [8.450, 20.825] | 1.673 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20232024:MetLife Stadium` | 9.597 | 112.00 | 15.006 | [9.188, 20.825] | 1.824 | `insufficient_evidence` | NO |
| `regular_season` | `all_attempts` | `20232024:MetLife Stadium` | 9.587 | 112.00 | 14.625 | [8.450, 20.800] | 1.675 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20252026:Raymond James Stadium` | 6.287 | 107.00 | 1.256 | [1.256, 1.256] | 0.000 | `insufficient_evidence` | NO |
| `training_contract` | `all_attempts` | `20252026:Raymond James Stadium` | 6.273 | 107.00 | 1.233 | [1.233, 1.233] | 0.000 | `insufficient_evidence` | NO |
| `regular_season` | `training_attempts` | `20252026:Raymond James Stadium` | 6.105 | 107.00 | 1.200 | [1.200, 1.200] | 0.000 | `insufficient_evidence` | NO |
| `regular_season` | `all_attempts` | `20252026:Raymond James Stadium` | 6.095 | 107.00 | 1.175 | [1.175, 1.175] | 0.000 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20182019:Lincoln Financial Field` | 5.902 | 105.00 | 9.429 | [9.429, 9.429] | 0.000 | `insufficient_evidence` | NO |
| `training_contract` | `training_attempts` | `20182019:Scandinavium` | -5.689 | 68.00 | -8.200 | [-8.200, -8.200] | 0.000 | `insufficient_evidence` | NO |

## Notes

Generated from live SQLite data with forward-chaining temporal CV. Each shot uses the latest venue distance adjustment from a season before the shot's season; same-season venue corrections are not used for holdout rows. Distance residual z-scores are venue-season corrected-distance mean z-scores. Rolling venue-regime diagnostics use prior-only rolling estimates for production-safe context and centered rolling estimates only for exploratory historical-spike labeling. Event-frequency residual z-scores use sample-adequate regular-season training attempts as the primary gate; blocked-shot and all-attempt frequencies are reported as diagnostics and remain outside the current shot-level xG training contract.
