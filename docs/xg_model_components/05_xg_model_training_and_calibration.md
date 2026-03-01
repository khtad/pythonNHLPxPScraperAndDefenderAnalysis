# Component 05: xG Model Training and Calibration

## Scope
Train and calibrate shot-level xG models using the engineered feature stack.

## Deliverables
- Baseline model (e.g., logistic/GBDT) and segmented-state variants.
- Train/validation/test splits with temporal integrity.
- Calibration layer (isotonic or Platt as appropriate).
- Performance dashboard: log loss, Brier score, AUC, calibration curves.

## Validation
- Temporal cross-validation by season blocks.
- Calibration stability by manpower state and score state.
- Drift detection triggers with retraining thresholds.

## Extension points
- Ensemble modeling.
- Bayesian xG uncertainty outputs.
