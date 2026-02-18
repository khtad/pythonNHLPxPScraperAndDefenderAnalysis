# Component 03: Post-Faceoff Spike and Decay Modeling

## Scope
Capture temporary shot-volume/xG deviations immediately after faceoffs and decay toward steady-state.

## Deliverables
- Event sequence flag identifying shots within post-faceoff windows.
- Parametric/nonparametric decay features (e.g., seconds since faceoff splines).
- Separate handling for offensive/neutral/defensive-zone faceoffs.

## Validation
- Compare shot rates and xG by time-since-faceoff bins.
- Confirm decay behavior across manpower states.
- Test whether decay terms improve calibration and log loss.

## Extension points
- Team tactical signatures for set plays.
- Player-on-ice interaction with post-faceoff lift.
