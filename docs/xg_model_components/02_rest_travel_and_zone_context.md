# Component 02: Rest, Travel, and Zone Context

## Scope
Context features influencing shot quality and game flow:
- comparative rest,
- travel burden,
- zone start,
- on-the-fly change estimation.

## Deliverables
- Team rest days and back-to-back flags.
- Comparative rest differentials between teams.
- Travel distance/time-zone delta features.
- Zone-start estimator at shift and sequence levels.
- Change-on-the-fly probability features from shift/event timing.

## Validation
- Distribution checks by team/season.
- Sanity checks against known schedule constraints.
- Correlation and multicollinearity review before model fit.

## Extension points
- Fatigue accumulation windows (e.g., 7-day load).
- Player-level travel/rest personalization.
