# Validation Scorecard (Latest Run)

Generated: 2026-04-28T21:27:35+00:00

Database: `data\nhl_data.db`

Notebook: `C:\Users\micha\source\repos\pythonNHLPxPScraperAndDefenderAnalysis\notebooks\model_validation_framework.ipynb`

Current shot-event schema rows: 2,122,963 (`v5`)

Source: `scripts/export_validation_scorecard.py` executed the validation notebook and extracted the scorecard block.

```text
======================================================================
VALIDATION SCORECARD
======================================================================
  [PASS] Data quality (contract checks)
         All zero
  [FAIL] Discrimination (AUC >= 0.75)
         Mean AUC = 0.7264
  [FAIL] Calibration slope [0.95, 1.05]
         Slope = 0.8737
  [FAIL] Hosmer-Lemeshow (p > 0.05)
         p = 0.0000
  [PASS] Temporal stability (drift < 0.02/season)
         Slope = -0.0012/season
  [FAIL] Subgroup calibration (error < 3pp)
         Max error = 10.96pp
  [PASS] Feature ablation (>= 1 group improves)
         Best: all_combined (dAUC = +0.0283)
  [FAIL] Leakage audit (no HIGH/AMBIGUOUS)
         4 features flagged

======================================================================
RESULT: 3/8 checks passed, 5 failed
BLOCKED — resolve failures before training.

Failed checks require investigation:
  - Discrimination (AUC >= 0.75): Mean AUC = 0.7264
  - Calibration slope [0.95, 1.05]: Slope = 0.8737
  - Hosmer-Lemeshow (p > 0.05): p = 0.0000
  - Subgroup calibration (error < 3pp): Max error = 10.96pp
  - Leakage audit (no HIGH/AMBIGUOUS): 4 features flagged
```
