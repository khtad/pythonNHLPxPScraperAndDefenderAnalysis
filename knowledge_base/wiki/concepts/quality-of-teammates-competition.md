# Quality of Teammates and Competition

## Purpose
Scaffold concept article defining QoT and QoC for shift-level analysis.

## Planned implementation
- QoT: shared-TOI weighted teammate RAPM excluding focal skater.
- QoC: shared-TOI weighted opponent RAPM.
- Separate offensive and defensive dimensions.


## Current project status
- **2026-04-18 (Phase 1 foundation delivered):** Shift ingestion (`src/shifts.py`) and on-ice intervalization (`src/on_ice_builder.py`) now provide the core shift-level data layer needed before QoT/QoC feature computation.
