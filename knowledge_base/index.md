# Knowledge Base Index

> Last updated: 2026-04-08 (Phase 2 external source ingestion)

## Concepts

- [Expected Goals (xG)](wiki/concepts/expected-goals-xg.md) — A probabilistic model that assigns each shot a goal probability based on shot location, type, and game context.
- [Score Effects](wiki/concepts/score-effects.md) — How the current score differential changes team shooting behavior — trailing teams take more but lower-quality shots.
- [Zone Starts](wiki/concepts/zone-starts.md) — How the location of a faceoff affects subsequent shot generation and quality.
- [Faceoff Decay](wiki/concepts/faceoff-decay.md) — The spike in shot rate immediately after a faceoff and its exponential decay toward steady-state levels.
- [Venue and Scorekeeper Bias](wiki/concepts/venue-scorekeeper-bias.md) — How different NHL venues systematically record events differently, distorting shot coordinates and event frequencies.
- [Rest and Travel Effects](wiki/concepts/rest-travel-effects.md) — How rest days, travel distance, and timezone crossing affect team performance and shot quality.
- [Handedness and Effective Angle](wiki/concepts/handedness-effective-angle.md) — How a shooter's stick hand determines which goal posts are accessible from a given ice position.

## Methods

- [Temporal Cross-Validation](wiki/methods/temporal-cross-validation.md) — Season-block CV for hockey data: why random splits leak future information, and how to implement forward-chaining temporal CV.
- [Calibration Analysis](wiki/methods/calibration-analysis.md) — Reliability diagrams, Hosmer-Lemeshow goodness-of-fit, and calibration slope/intercept for xG probability verification.
- [Bootstrapping and Confidence Intervals](wiki/methods/bootstrapping-confidence-intervals.md) — Bootstrap CIs for goal rates, Wilson intervals, and sample size adequacy checks at ~8% base rate.
- [RAPM (Regularized Adjusted Plus-Minus)](wiki/methods/rapm-regularized-adjusted-plus-minus.md) — Ridge/elastic-net regression to isolate individual player impact from on-ice context using xG residuals.
- [Effect Size Measures](wiki/methods/effect-size-measures.md) — Cohen's h/d for practical vs statistical significance, with decision rules for this project.

## Data

- [NHL API Shot Events](wiki/data/nhl-api-shot-events.md) — Canonical schema for individual shot events with normalized coordinates, game-state context, and faceoff recency.
- [Coordinate System and Normalization](wiki/data/coordinate-system-and-normalization.md) — NHL rink coordinate conventions, normalization toward +x, and known data gaps by era.
- [Shot Type Taxonomy](wiki/data/shot-type-taxonomy.md) — The 10 recognized shot types, their frequency distribution, and relevance to xG modeling.
- [Manpower States](wiki/data/manpower-states.md) — The 15 valid skater-count situations parsed from NHL API situation codes.
- [Score States](wiki/data/score-states.md) — The 7 score-differential buckets and their behavioral effects on shot volume and quality.
- [NHL API Endpoints](wiki/data/nhl-api-endpoints.md) — Schedule and play-by-play endpoints, response structure, rate limiting, and field availability by era.
- [Arena and Venue Reference](wiki/data/arena-venue-reference.md) — Static reference data for all 32 current NHL teams: city, timezone, and geographic coordinates.

## Models

_No articles yet._

## Comparisons

- [Public xG Model Survey](wiki/comparisons/public-xg-model-survey.md) — Structured comparison of MoneyPuck, Evolving Hockey, and HockeyViz Magnus xG models: algorithms, features, strength-state handling, and reported performance.

## Meta

- [Knowledge Gaps](wiki/meta/knowledge-gaps.md) — Concepts not yet covered, empty categories, pending data refreshes, and planned external source ingestion.

---

## Raw Sources

### External

| File | Added | Description |
|------|-------|-------------|
| `raw/external/2026-04-08_moneypuck-xg-methodology.md` | 2026-04-08 | MoneyPuck xG model: GBM, 15 features, flurry adjustment |
| `raw/external/2026-04-08_evolving-hockey-xg-and-war.md` | 2026-04-08 | Evolving Hockey xG (XGBoost, 4 models) + WAR/GAR framework (RAPM + SPM ensemble) |
| `raw/external/2026-04-08_hockeyviz-magnus-model.md` | 2026-04-08 | HockeyViz Magnus: regularized logistic regression, hex spatial fabric, xG/shooter/goalie decomposition |
| `raw/external/2026-04-08_nhl-api-community-documentation.md` | 2026-04-08 | Community NHL API endpoint documentation (Zmalski, dword4) |
| `raw/external/2026-04-08_schuckers-curro-thor-digr.md` | 2026-04-08 | Academic: THoR (ridge RAPM, NP20 event valuation) and DIGR (LOESS goalie maps, CDF rink bias correction) |
| `raw/external/2026-04-08_karpathy-llm-knowledge-base.md` | 2026-04-08 | Meta-reference: Karpathy LLM wiki architecture pattern |

### Project Artifacts Referenced

| Artifact | Type | Wiki Pages Citing It |
|----------|------|---------------------|
| `raw/project/2026-04-06_shot-distance-diagnostic.md` | Diagnostic notebook findings | [NHL API Shot Events](wiki/data/nhl-api-shot-events.md), [Coordinate System](wiki/data/coordinate-system-and-normalization.md), [NHL API Endpoints](wiki/data/nhl-api-endpoints.md) |
