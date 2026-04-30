# Validation Scorecard (Latest Run)

Generated: 2026-04-30T13:28:34+00:00

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
  [PASS] Discrimination (AUC >= 0.75)
         Mean AUC = 0.7551
  [PASS] Calibration slope [0.95, 1.05]
         Slope = 0.9870
  [PASS] Practical calibration (max bin < 1pp, ECE < 0.5pp)
         Max bin = 0.407pp; ECE = 0.193pp; HL diagnostic p = 0
  [PASS] Temporal stability (drift < 0.02/season)
         Slope = +0.0001/season
  [PASS] Subgroup calibration (error < 3pp)
         Max error = 1.24pp
  [PASS] Feature ablation (>= 1 group improves)
         Best: all_combined (dAUC = +0.0298)
  [PASS] Leakage audit (selected features clear)
         0 selected features flagged; 9 excluded pending

======================================================================
RESULT: 8/8 checks passed, 0 failed
MODEL TRAINING MAY PROCEED.
```
