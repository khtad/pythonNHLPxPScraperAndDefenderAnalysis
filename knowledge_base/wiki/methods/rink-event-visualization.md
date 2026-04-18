# Rink Event Visualization

> How to overlay NHL shot events on a rink surface for visual-reasoning debugging: drawing functions, density-estimation tradeoffs, and per-game inspection patterns.

## Overview

Rink event maps plot shot locations on a 200 × 85 ft rink diagram so an analyst can verify spatial claims with domain intuition. They are a first-line sanity check on coordinate normalization: if the `normalize_coordinates()` pipeline is working, shots from every team and period should concentrate in the attacking slot around (89, 0). A bimodal density with peaks at x = ±89 indicates a normalization regression. A shift of density away from the slot toward a specific corner indicates venue-level coordinate bias.

Two visualization modes answer different questions. Aggregate density (hexbin, heatmap, or KDE) over the full dataset answers "does the population of shots look right?" and is the workhorse for diagnosing era-wide or dataset-wide issues. Per-game scatter answers "does this specific game match what I know happened?" and is the workhorse for surfacing anomalies the analyst can cross-check against memory, box scores, or recorded play. Both modes share the same rink geometry and coordinate conventions.

The project's reusable visualization helpers live in `src/rink_viz.py` [1]. They take a matplotlib axis plus pre-fetched shot dicts so they compose with any existing notebook's figure layout. The database-side helpers `load_game_shots()` and `get_random_game_id()` in `src/database.py` [2] feed per-game views.

## Key Details

### Rink Geometry Constants

All drawn at the dimensions in [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md), hoisted as named constants in `src/rink_viz.py` [1]:

| Constant | Value (ft) |
|----------|-----------|
| `RINK_HALF_LENGTH` | 100.0 |
| `RINK_HALF_WIDTH` | 42.5 |
| `GOAL_X` | 89.0 |
| `BLUE_LINE_X` | 25.0 |
| `CREASE_RADIUS` | 6.0 |
| `FACEOFF_CIRCLE_RADIUS` | 15.0 |
| `FACEOFF_DOT_X` / `FACEOFF_DOT_Y` | 69.0 / 22.0 |

### Drawing Functions

| Function | Use case |
|----------|----------|
| `draw_half_rink(ax)` | Offensive-zone-only view; recommended when all shots are normalized toward +x and you only care about the attacking half [1]. |
| `draw_full_rink(ax)` | Both ends visible; required when plotting raw pre-normalization coordinates or when illustrating the v2 coordinate bug [1]. |
| `plot_shots(ax, shots, color_by="period", goal_markers=True)` | Scatter overlay; filters shots with `x_coord is None`, groups by period using `PERIOD_COLORS`, renders goals as star markers above non-goals [1]. |
| `plot_game_shot_chart(ax, shots, full_rink=False)` | Composite: draws the rink, then scatters the shots [1]. |

### Density-Method Recommendation

`plot_shot_density(ax, shots, method=...)` supports three methods [1]:

| Method | Speed at ~2M shots | Behavior near boards | When to use |
|--------|--------------------|-----------------------|-------------|
| `hexbin` (default) | Fast (single C pass) | Cells clip cleanly at axis limits | Full-dataset aggregates; general workhorse |
| `heatmap` | Fast | Rectangular bins, clip cleanly | When you want equal-area rectangular cells |
| `kde` | Slow (O(N × grid)) | Kernel bleeds past the boards | Small samples where smoothness helps visual reasoning |

Hexbin is the default because it is exact, fast, and does not bleed density across the end boards — the latter is a visual artifact that makes KDE maps misleading at the rink edges. Above 50,000 points the hexbin automatically switches to log-count scaling (`bins="log"`) so the high-frequency slot cell does not saturate the colormap and hide variation elsewhere [1].

### Shot-Dict Contract

Visualization helpers consume an iterable of dicts with the shape returned by `load_game_shots()` [2]. Required keys: `x_coord`, `y_coord`, `is_goal`, `period`. Coordinate values of `None` are silently filtered so unnormalizable raw events do not crash the plot.

### Style Conventions

- Period palette: P1 blue, P2 orange, P3 green, OT red, SO purple (`PERIOD_COLORS`) [1].
- Goals render as star markers (`*`, size 120) above non-goal circles (size 30), so even rare goal events are visible at a glance [1].
- `sns.set_theme(style="whitegrid")` at the top of every notebook keeps the background consistent with the rest of the project's charts.

## Relevance to This Project

Rink event maps are used in three places today:

- `notebooks/shot_distance_diagnostic.ipynb` — per-game half-rink and full-rink charts that compare post-2020 (correctly normalized) and pre-2020 (v2 bug) game coordinates. Refactored to import from `src/rink_viz.py` rather than re-defining the rink inline.
- `notebooks/event_map_gallery.ipynb` — aggregate hexbin of the full dataset, per-period facet, and a random-game panel driven by `get_random_game_id()` + `load_game_shots()`. The aggregate hexbin is the quickest way to confirm that a recent pipeline change did not regress normalization.
- `notebooks/venue_bias_analysis.ipynb` — present only through the shared coordinate conventions today; rink-density panels are a natural follow-up.

**Current status (2026-04-18):** `src/rink_viz.py` is the canonical visualization module. Any future notebook that plots shot coordinates should import from it rather than duplicating rink geometry.

Last verified: 2026-04-18

## Sources

[1] Rink drawing, density, and scatter helpers — `src/rink_viz.py` (`draw_half_rink`, `draw_full_rink`, `plot_shots`, `plot_shot_density`, `plot_game_shot_chart`, `PERIOD_COLORS`, geometry constants)
[2] Per-game shot loader and random-game helper — `src/database.py` (`load_game_shots`, `get_random_game_id`)
[3] Rink dimensions and coordinate normalization — `knowledge_base/wiki/data/coordinate-system-and-normalization.md`

## Related Pages

- [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md) — the upstream normalization that these plots assume has already been applied
- [Venue and Scorekeeper Bias](../concepts/venue-scorekeeper-bias.md) — rink maps are the fastest way to see coordinate-bias shifts visually
- [Shot Type Taxonomy](../data/shot-type-taxonomy.md) — candidate grouping variable for future `plot_shots(color_by=...)` extensions
- [NHL API Shot Events](../data/nhl-api-shot-events.md) — schema of the shot dicts that the visualization helpers consume

## Revision History

- 2026-04-18 — Created. Extracted rink-drawing helpers from `notebooks/shot_distance_diagnostic.ipynb` into `src/rink_viz.py`; documented density-method tradeoffs (hexbin default, kde for small samples, heatmap for rectangular bins) and per-game random-game workflow.
