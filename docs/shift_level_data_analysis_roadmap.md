# Shift-Level Data Analysis Roadmap

## Purpose
Roadmap for building the roster-change decomposition data stack from raw shift charts through causal inference outputs.

## Phases

| Phase | Scope | Status (2026-04-18) |
|---|---|---|
| Phase 1 | Shift ingestion, normalization, intervalization, and shot on-ice slot attachment | **Complete** |
| Phase 2 | Persist shifts/on-ice intervals and add idempotent backfill jobs | Planned |
| Phase 3 | QoT/QoC shift feature generation and validation | Planned |
| Phase 4 | RAPM estimation and uncertainty calibration | Planned |
| Phase 5 | Causal event studies and decomposition outputs | Planned |

## Phase 1 deliverables (completed)
- Parse shift chart rows into normalized records.
- Validate baseline shift quality (duration and period checks).
- Construct non-overlapping on-ice intervals by period.
- Attach interval-derived home/away on-ice slots to shot rows.

## Implementation references
- `src/shifts.py`
- `src/on_ice_builder.py`
- `tests/test_shift_phase1.py`
