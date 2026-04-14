# Venue and Scorekeeper Bias

> How different NHL venues systematically record events differently, distorting shot coordinates and event frequencies in ways that must be corrected for fair cross-venue analysis.

<!-- data-version: v2 -->
<!-- data-revalidate: After v3 backfill, rerun venue-level coordinate distribution analysis. The mean x/y and stddev comparisons in venue_bias_analysis.ipynb should be re-derived from clean data since coordinate normalization directly affects this analysis. -->

## Overview

NHL events are recorded by in-arena scorekeepers who observe the game and log each event's type, location, and participants. Different scorekeepers at different venues have systematically different recording tendencies. Some venues record more shot events (particularly missed shots and blocked shots), some record coordinates with a consistent spatial bias (shifted toward center ice or toward a particular end), and some have higher variance in coordinate placement.

These venue-specific biases are a significant confound for any model that uses shot location as a feature. If one venue systematically records shots as closer to the goal than they actually are, an xG model trained on that venue's data will overestimate shot danger. The bias also affects cross-venue player comparisons — a player's shot metrics at a high-recording venue appear inflated relative to the same player at a low-recording venue.

## Key Details

### Types of Venue Bias

1. **Coordinate bias:** Systematic shifts in mean x or y coordinate relative to the league average. Some venues place shots closer to the net, others further out.
2. **Coordinate variance:** Some venues have wider spread in coordinates (possibly more careful tracking), others have clustering (possibly more estimation by the scorekeeper).
3. **Event frequency bias:** Some venues record more total events per game, particularly for subjective event types like missed shots and blocked shots.
4. **Temporal patterns:** Bias may change between seasons (new scorekeepers) or even within seasons.

### Detection Approach

The project's venue bias analysis (`notebooks/venue_bias_analysis.ipynb`) computes per-venue statistics and compares them to the league average [1]:

- Mean and standard deviation of x_coord and y_coord per venue
- Total shot event count per game per venue
- Distance-to-goal distribution per venue
- Season-over-season stability of venue effects

### Correction Strategies

The component design doc outlines a hierarchical partial-pooling approach [2]:

1. **Venue-level intercepts:** Estimate a per-venue bias term that shifts coordinates toward the league mean
2. **Partial pooling by season:** Shrink venue estimates toward the league mean to avoid overfitting to small samples, with season-specific adjustments
3. **Raw vs corrected comparatives:** Always preserve raw data alongside corrections so the impact of correction can be validated

### External Precedent: Schuckers CDF Matching

Schuckers & Curro (2011, 2013) pioneered a quantile-based rink bias correction [3]:

1. Calculate CDF of shot distances for home vs. away teams at each venue, conditioned on shot type (slap vs. non-slap)
2. Assume all venues share the same league-average underlying distance distribution
3. For each shot at venue R, adjust its distance by matching its quantile in the venue-specific CDF to the league-wide CDF

This approach corrects distance distortion without assuming the bias is a simple location shift. Notable bias venues in their era included Madison Square Garden. The CDF-matching method is a concrete implementation option for this project's venue correction features.

### Relationship to Coordinate Normalization

Venue bias is distinct from the coordinate normalization issue (see [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md)). Normalization handles the attacking-direction convention (ensuring all shots face +x). Venue bias correction handles systematic spatial distortion after normalization. Both must be applied for coordinates to be trustworthy.

## Relevance to This Project

Venue bias estimation is Phase 2, Component 04 [2]. The analysis notebook `notebooks/venue_bias_analysis.ipynb` implements detection [1]. Correction features are planned but not yet implemented.

The venue bias analysis is particularly sensitive to the v2 coordinate normalization bug. Pre-2020 data with ~50% unnormalized coordinates will produce spurious venue effects that are actually normalization failures. This analysis should be re-derived after the v3 backfill completes.

Last verified: 2026-04-06

## Sources

[1] Venue bias analysis — `notebooks/venue_bias_analysis.ipynb`
[2] Component design — `docs/xg_model_components/04_scorekeeper_bias.md`
[3] Schuckers & Curro rink bias correction — `knowledge_base/raw/external/2026-04-08_schuckers-curro-thor-digr.md`

## Related Pages

- [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md) — the upstream normalization that must be correct before venue bias can be estimated
- [Arena and Venue Reference](../data/arena-venue-reference.md) — the static venue data used for venue identification
- [Expected Goals (xG)](expected-goals-xg.md) — the model that venue bias corrections feed into
- [Public xG Model Survey](../comparisons/public-xg-model-survey.md) — how public models handle venue/rink bias

## Revision History

- 2026-04-08 — Added Schuckers CDF-matching rink bias correction method and link to public model survey.
- 2026-04-06 — Created. Compiled from venue bias notebook and component 04 design doc.
