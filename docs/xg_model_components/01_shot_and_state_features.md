# Component 01: Shot and Game-State Features

## Scope
Core shot and state feature layer for xG:
- shot type,
- shot location,
- score-state by lead/deficit bucket,
- time remaining,
- expected points context,
- manpower state.

## Deliverables
- Canonical shot-type mapping table.
- Normalized coordinate system (attacking direction aligned).
- Score-state bucket generator (`up/down 1,2,3+`, tied).
- Manpower-state classifier (`5v5`, `5v4`, `4v4`, `5v3`, `4v5`, `3v5`).
- Time remaining and expected-points proxy features.

## Validation
- Coverage checks per season and venue.
- Class-balance report for manpower states.
- Feature leakage audit (all features available at shot timestamp).

## Extension points
- Continuous score differential embeddings.
- Overtime/shootout state handling modules.
