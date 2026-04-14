# Shot Distance Diagnostic — Project Reference

**Artifact:** `notebooks/shot_distance_diagnostic.ipynb`
**Date referenced:** 2026-04-06
**Related code:** `src/xg_features.py` (`normalize_coordinates`), `src/main.py` (`_game_is_complete`, `_process_game`), `src/database.py` (`game_has_current_shot_events`)

## Summary

Diagnostic investigation into shot distance accuracy, prompted by concern that
the change of attacking direction between periods was not properly handled.

## Key Findings

### 1. Pre-2020 normalization failure (schema v2)

The NHL API does not provide `homeTeamDefendingSide` for games before the 2019-2020
season. The v2 extraction code stored raw coordinates unchanged when this field was
`None`, resulting in:

- **~50% of pre-2020 shots stored with wrong coordinates** (negative x_coord, ~150 ft
  average distance instead of ~35 ft)
- **6.9% goal rate on "negative x" shots** — physically impossible at 150 ft, confirming
  the coordinates are wrong
- **Period asymmetry in pre-2020 data:** For Caps home games, P1/P3 show ~75-80% negative
  x while P2 shows ~22% negative x. This reflects the raw attacking direction, not a
  period-specific normalization bug.

### 2. Post-2020 data is correct

The API provides `homeTeamDefendingSide` starting ~2019-2020. It alternates per period
(e.g., right → left → right). Post-2020 data shows:

- Only ~2% negative x (legitimate behind-center-ice shots)
- P2 vs P1+P3 distance difference: -1.03 ft (Cohen's d = -0.04, negligible)
- KS test p = 1.62e-04 but negligible effect size — statistically detectable due to
  large sample but not practically meaningful

### 3. Backfill was blocked by non-version-aware completeness check

All data was at schema v2, but `_game_is_complete()` used `game_has_shot_events()`
(any version) instead of `game_has_current_shot_events()` (current version only).
This caused the v3 backfill to skip all games that already had v2 rows.

**Fix applied:** Changed `_game_is_complete()` and `_process_game()` to use
`game_has_current_shot_events()`, and added `delete_game_shot_events()` to clear
stale v2 rows before re-inserting.

### 4. v3 heuristic limitations

The v3 fallback (`if raw x < 0, flip to positive`) correctly handles ~96% of pre-2020
shots (those taken in the offensive zone) but cannot fix the ~4% taken from behind
center ice where the raw x is positive but should be flipped.

## Data Points

| Metric | Pre-2020 | Post-2020 |
|--------|----------|-----------|
| Total Caps shots (P1-P3) | ~38,700 | ~24,600 |
| Negative x rate | ~50% | ~2% |
| P2 vs P1+P3 mean distance diff | -55.77 ft | -1.03 ft |
| Cohen's d (P2 vs P1+P3) | -1.05 (large) | -0.04 (negligible) |
| API `homeTeamDefendingSide` | None (absent) | Present, alternates per period |
