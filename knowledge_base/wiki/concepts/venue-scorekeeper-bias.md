# Venue and Scorekeeper Bias

> How different NHL venues systematically record events differently, distorting shot coordinates and event frequencies in ways that must be corrected for fair cross-venue analysis.

<!-- data-version: v5 -->
<!-- data-revalidate: Re-run venue-correction validation after future shot-event schema changes or correction-policy changes. Re-derive venue-level coordinate distribution analysis if coordinate normalization changes. -->

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
- Normalized event-frequency residuals by venue-season, event group, and game-type scope
- Paired away-team-season comparisons for frequency anomalies
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

Venue bias estimation is Phase 2, Component 04 [2]. The analysis notebook `notebooks/venue_bias_analysis.ipynb` implements detection [1].

Phase 2 also wired the per-season diagnostic populator into the scraper pipeline: `finalize_season_diagnostics(conn)` in `src/main.py` iterates every season in `games` and calls `populate_venue_diagnostics(conn, season)` at the end of both the scrape loop and `backfill_missing_game_data()` [4]. The populator is idempotent (`INSERT OR REPLACE`), so the `venue_bias_diagnostics` table now fills automatically and stays current as new seasons land. Before this wiring, the populator existed but was never invoked, so the diagnostic table was empty on the live DB. Consumers of venue bias features should read from `venue_bias_diagnostics` rather than recomputing per-season.

The initial correction layer is now implemented in `src/database.py` [5]. `populate_venue_bias_corrections(conn, season)` computes a per-venue distance adjustment toward the season league mean and shrinks it by sample size (`sample_shots / (sample_shots + prior)`), storing parameters in `venue_bias_corrections`. `finalize_season_diagnostics()` now runs both diagnostic and correction population each season [4]. At consumption time, `load_game_shots_with_venue_correction()` adds `distance_to_goal_corrected` using the persisted adjustment while preserving raw distance values [5].

This is an implementation baseline, not final model policy. The Phase 2.5.4 scorecard harness is implemented: `evaluate_venue_correction_scorecard()` combines held-out log-loss, home-ice over-correction, distance/location residual z-score, and event-frequency residual z-score gates, while `scripts/export_venue_correction_validation.py` formats the artifact [6].

The event-frequency refresh adds `src/venue_bias.py` helpers for venue-season event rates, frequency z-scores, paired away-team-season comparisons, bootstrap CIs, paired Cohen's d, known-regime priors, and anomaly classification [6]. The primary frequency gate uses sample-adequate regular-season training attempts. Blocked-shot and all-attempt frequencies are reported as diagnostics because they are important scorekeeper-bias evidence but remain outside the current shot-level xG training contract [6].

After the v5 backfill, `scripts/export_venue_correction_validation_from_db.py` ran the live validation from SQLite using forward-chaining temporal CV and only prior-season venue distance corrections for each held-out shot [6]. The 2026-05-01 refresh uses the same tightened model-training contract as `load_training_shot_events`: schema v5, season >= 20092010, regular/playoff in-game shots, no regular-season shootouts, non-blocked target-consistent shot rows, and non-null core model features. The live scorecard passes held-out log-loss (`delta = -0.000017`) and the home-ice over-correction guardrail (`removed = -0.013`, limit 0.500), but fails the residual corrected-distance venue-season z-score gate (`max |z| = 4.067`, limit < 2.000; worst venue-season `20092010:Madison Square Garden`) and the sample-adequate event-frequency residual gate (`max |z| = 3.453`, limit < 2.000; worst venue-season `20152016:Prudential Center`) [6]. The current shrinkage distance correction therefore remains exploratory and should not feed production xG training until both residual families pass or a different correction/exclusion policy is selected [2][6].

The venue bias analysis was particularly sensitive to the v2 coordinate normalization bug. Pre-2020 data with ~50% unnormalized coordinates would have produced spurious venue effects that were actually normalization failures. The current v5 refresh resolves the stale-schema blocker, but venue-level coordinate analyses should still be re-derived after any future coordinate-normalization or correction-policy change.

Last verified: 2026-05-01

## Sources

[1] Venue bias analysis — `notebooks/venue_bias_analysis.ipynb`
[2] Component design — `docs/xg_model_components/04_scorekeeper_bias.md`
[3] Schuckers & Curro rink bias correction — `knowledge_base/raw/external/2026-04-08_schuckers-curro-thor-digr.md`
[4] Diagnostic populator wiring — `src/main.py` (`finalize_season_diagnostics()`), `src/database.py` (`populate_venue_diagnostics()`)
[5] Venue correction implementation — `src/database.py` (`create_venue_bias_corrections_table()`, `populate_venue_bias_corrections()`, `load_game_shots_with_venue_correction()`)

[6] Venue correction validation harness and live result - `src/validation.py` (`evaluate_venue_correction_scorecard()`), `src/venue_bias.py`, `scripts/export_venue_correction_validation.py`, `scripts/export_venue_correction_validation_from_db.py`, `notebooks/venue_bias_analysis.ipynb`, `artifacts/venue_correction_validation_latest.md`, `tests/test_venue_bias.py`, `tests/test_venue_correction_validation_export.py`, `tests/test_venue_correction_validation_from_db.py`

## Related Pages

- [Coordinate System and Normalization](../data/coordinate-system-and-normalization.md) — the upstream normalization that must be correct before venue bias can be estimated
- [Arena and Venue Reference](../data/arena-venue-reference.md) — the static venue data used for venue identification
- [Expected Goals (xG)](expected-goals-xg.md) — the model that venue bias corrections feed into
- [Public xG Model Survey](../comparisons/public-xg-model-survey.md) — how public models handle venue/rink bias
- [Rink Event Visualization](../methods/rink-event-visualization.md) — plotting venue shot distributions on a rink surface for visual bias detection

## Revision History

- 2026-05-01 - Added event-frequency scorekeeper diagnostics, anomaly classification, and the refreshed live scorecard result with separate distance/location and event-frequency residual gates.
- 2026-04-28 - Recorded the live v5 DB-backed venue-correction validation result: log-loss and home-ice guardrails pass, residual corrected-distance z-score fails.
- 2026-04-28 - Added Phase 2.5.4 scorecard harness status and source references for held-out/log-loss, home-ice guardrail, and residual z-score validation gates.
- 2026-04-30 - Refreshed live DB scorecard metrics after the training-contract cleanup.

- 2026-04-24 — Updated status: initial venue correction layer now implemented (`venue_bias_corrections` + shrinkage-adjusted distance correction), and wired into seasonal finalization; documented remaining held-out validation requirements.
- 2026-04-19 — Documented that Phase 2 wired `finalize_season_diagnostics` into the pipeline, so `venue_bias_diagnostics` is now populated on every scrape/backfill run. Source [4] added.
- 2026-04-18 — Added cross-link to new Rink Event Visualization methods article.
- 2026-04-08 — Added Schuckers CDF-matching rink bias correction method and link to public model survey.
- 2026-04-06 — Created. Compiled from venue bias notebook and component 04 design doc.
