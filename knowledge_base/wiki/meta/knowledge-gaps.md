# Knowledge Gaps

> Concepts mentioned but not yet covered, empty wiki categories, pending data refreshes, and planned articles — a living inventory of what the knowledge base does not yet contain.

## Overview

This page catalogs known gaps in the knowledge base. It is updated after each batch ingest and during lint passes. Gaps fall into four categories: concepts referenced in existing articles but lacking their own page, wiki categories with no articles, articles pending data-version refresh, and external sources not yet ingested. The purpose is to make the "unknown unknowns" visible so that future ingest work can be prioritized.

## Key Details

### Concepts Mentioned Without Own Pages

These terms appear in existing wiki articles but do not have dedicated pages. Priority indicates how relevant they are to current project work.

| Concept | Mentioned In | Priority | Notes |
|---------|-------------|----------|-------|
| Corsi | expected-goals-xg.md, score-effects.md | Low | Shot attempt count metric; relevant context for xG but not a modeling input |
| Fenwick | score-effects.md | Low | Unblocked shot attempt count; similar context role to Corsi |
| Expected rebounds | expected-goals-xg.md | Medium | Rebound probability as an xG feature; gated on Phase 2+ feature engineering |
| Pre-shot movement | nhl-api-shot-events.md, score-states.md | Medium | Rush vs. sustained pressure distinction; depends on sequence-context features |
| Rush chances | expected-goals-xg.md, manpower-states.md | Medium | Shots off the rush; requires event-sequence parsing not yet implemented |
| Team strength aggregation | — | Low | Component 07 in roadmap; gated on RAPM completion |
| Platform extensibility | — | Low | Component 08 in roadmap; infrastructure, not domain knowledge |

### Empty Wiki Categories

| Category | Gated On | Planned Articles |
|----------|----------|-----------------|
| `wiki/models/` | xG model training (Phase 3) | Logistic xG baseline |
| `wiki/comparisons/` | ~~External source ingestion (Phase 2)~~ **Partially filled** | ~~Public xG model survey~~, regularization methods compared |

The `wiki/comparisons/` category now has its first article ([Public xG Model Survey](../comparisons/public-xg-model-survey.md)) following Phase 2 external source ingestion. The regularization methods comparison is still gated on RAPM implementation. The `wiki/models/` category remains empty pending model training.

### Articles Pending Data-Version Refresh

After the v3 backfill completes, the following articles need their `data-version: v2` tags updated. Articles marked "coordinate-independent" can be verified quickly (counts unchanged) but should still be spot-checked.

| Article | Coordinate-Dependent? | Refresh Action |
|---------|----------------------|----------------|
| coordinate-system-and-normalization.md | Yes | Rerun negative-x-rate queries, update era gap tables |
| nhl-api-shot-events.md | Yes | Update v2 bug status, confirm v3 coverage |
| handedness-effective-angle.md | Yes | Revalidate y_coord-dependent effective angle analysis |
| venue-scorekeeper-bias.md | Yes | Rerun coordinate distribution analysis per venue |
| expected-goals-xg.md | Partially | No empirical tables, but verify distance/angle references |
| shot-type-taxonomy.md | No | Spot-check frequencies (should be unchanged) |
| manpower-states.md | No | Spot-check frequencies (should be unchanged) |
| score-states.md | No | Spot-check frequencies (should be unchanged) |
| zone-starts.md | No | Verify faceoff_zone_code analysis (uses zone, not coords) |
| faceoff-decay.md | No | Verify decay curves (uses seconds, not coords) |
| score-effects.md | No | Verify volume/quality tables (goal rate, not coords) |
| rest-travel-effects.md | No | Verify game_context features (no coordinate dependency) |

### External Sources — Ingestion Status

All planned external sources have been ingested (Phase 2, 2026-04-08):

| Source | Status | Raw File | Wiki Impact |
|--------|--------|----------|-------------|
| MoneyPuck xG methodology | **Ingested** | `raw/external/2026-04-08_moneypuck-xg-methodology.md` | [Public xG Model Survey](../comparisons/public-xg-model-survey.md) |
| Evolving Hockey WAR/xG | **Ingested** | `raw/external/2026-04-08_evolving-hockey-xg-and-war.md` | Public xG Model Survey, RAPM article |
| HockeyViz Magnus model | **Ingested** | `raw/external/2026-04-08_hockeyviz-magnus-model.md` | Public xG Model Survey, RAPM article |
| NHL API documentation (community) | **Ingested** | `raw/external/2026-04-08_nhl-api-community-documentation.md` | NHL API Endpoints article |
| Schuckers & Curro (THoR/DIGR) | **Ingested** | `raw/external/2026-04-08_schuckers-curro-thor-digr.md` | Venue bias article, Public xG Model Survey, RAPM article |
| Karpathy knowledge base gist | **Ingested** | `raw/external/2026-04-08_karpathy-llm-knowledge-base.md` | Meta-reference (no wiki updates needed) |

### Component Docs Without Wiki Coverage

The `docs/xg_model_components/` directory has 10 design documents. Most map to existing concept or method articles, but two do not:

| Component Doc | Wiki Coverage |
|---------------|--------------|
| 07_team_strength_aggregation.md | No article (gated on RAPM) |
| 08_platform_extensibility_and_reuse.md | No article (infrastructure, not domain) |

## Relevance to This Project

This page guides prioritization of future wiki work. The highest-impact gaps are:

1. **v3 data refresh** — once the backfill completes, 4 coordinate-dependent articles need revalidation
2. ~~**External source ingestion**~~ **Done** (Phase 2 completed 2026-04-08). Remaining comparison article: regularization methods compared (gated on RAPM implementation).
3. **Model articles** — once the logistic baseline is trained, the first `wiki/models/` article becomes possible
4. **Rebound/rush concepts** — these are medium-priority modeling features that will need articles when Phase 2+ feature engineering begins

Last verified: 2026-04-08 (updated after Phase 2 external source ingestion)

## Sources

[1] Implementation plan — `docs/knowledge_base_implementation_plan.md` (Phase 2, Phase 3)
[2] Data-version tracking — `knowledge_base/SCHEMA.md` (Staleness Policy, Data-Version Dependency Tracking)
[3] Gap survey — automated scan of all 19 wiki articles for unresolved concept references, 2026-04-08

## Related Pages

- [Expected Goals (xG)](../concepts/expected-goals-xg.md) — mentions several uncovered concepts (Corsi, rebounds, rush)
- [RAPM](../methods/rapm-regularized-adjusted-plus-minus.md) — gates team strength aggregation and comparison articles

## Revision History

- 2026-04-08 — Updated after Phase 2 external source ingestion. All 6 external sources ingested; comparisons category partially filled; external sources table updated to ingestion status.
- 2026-04-08 — Created. Initial gap survey after Phase 1A-1C completion (19 articles). Cataloged 7 uncovered concepts, 2 empty categories, 12 articles pending v3 refresh, 5 candidate external sources.
