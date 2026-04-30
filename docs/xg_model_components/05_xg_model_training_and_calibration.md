# Component 05: xG Model Training and Calibration

## Scope
Train and calibrate shot-level xG models using the engineered feature stack.

## Deliverables
- Baseline model (e.g., logistic/GBDT) and segmented-state variants.
- Train/validation/test splits with temporal integrity.
- Fold-safe calibration layer: base model trained before the prior season, Platt calibrator fit on the prior season, next season held out for evaluation.
- Performance dashboard: log loss, Brier score, AUC, reliability curves, calibration slope, max decile calibration error, expected calibration error, and Hosmer-Lemeshow diagnostic.

## Validation
- Temporal cross-validation by season blocks.
- Calibration stability by manpower state and score state.
- Practical calibration gates: slope in [0.95, 1.05], max decile calibration error < 1pp, expected calibration error < 0.5pp, subgroup max error < 3pp. Hosmer-Lemeshow is reported as diagnostic only.
- Drift detection triggers with retraining thresholds.

## Extension points
- Ensemble modeling.
- Bayesian xG uncertainty outputs.
