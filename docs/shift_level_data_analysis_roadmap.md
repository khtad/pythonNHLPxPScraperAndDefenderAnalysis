# Shift-Level Data Analysis Roadmap

## Purpose
Roadmap for building the roster-change decomposition data stack from raw shift charts through causal inference outputs.

## Phases

| Phase | Scope | Status (2026-05-01) |
|---|---|---|
| Phase 1 | Shift ingestion, normalization, intervalization, and shot on-ice slot attachment | **Complete** |
| Phase 2 | Persist shifts/on-ice intervals and add idempotent backfill jobs | **Complete** |
| Phase 3 | QoT/QoC shift feature generation and validation | Planned |
| Phase 4 | RAPM estimation and uncertainty calibration | Planned |
| Phase 5 | Causal event studies and decomposition outputs | Planned |

## Phase 1 deliverables (completed)
- Parse shift chart rows into normalized records.
- Validate baseline shift quality (duration and period checks).
- Construct non-overlapping on-ice intervals by period.
- Attach interval-derived home/away on-ice slots to shot rows.

## Phase 2 deliverables (completed)
- Persist normalized shift rows into `shifts` with player, team, side, position, timing, and schema-version fields.
- Persist intervalized on-ice rows into `on_ice_intervals`.
- Update shot-event on-ice slot columns from interval matches.
- Provide the historical CLI: `python scripts/backfill_shift_data.py --all`.
- Reuse the same per-game population pipeline from `main.py` for newly processed games.

## Implementation references
- `src/shifts.py`
- `src/on_ice_builder.py`
- `src/shift_population.py`
- `scripts/backfill_shift_data.py`
- `tests/test_shift_phase1.py`
- `tests/test_shift_population.py`
