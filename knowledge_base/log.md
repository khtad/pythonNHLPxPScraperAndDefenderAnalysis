# Knowledge Base Log

> Append-only chronological record. Do not edit existing entries.
>
> Entry format: `### YYYY-MM-DD — [INGEST|UPDATE|LINT|SEED]`
> followed by Action, Source, Pages touched, and Notes fields.

## Entries

### 2026-04-05 — SEED

**Action:** Initialized knowledge base scaffold
**Source:** Internal — project bootstrap
**Pages touched:**
- Created `SCHEMA.md` (governance document)
- Created `index.md` (empty catalog)
- Created `log.md` (this file)
- Created `raw/external/README.md`
- Created `raw/project/README.md`
- Created `.gitkeep` files in all `wiki/` subdirectories
**Notes:** Phase A of the LLM Knowledge Base implementation plan. Directory structure and governance conventions established. No wiki articles yet.

### 2026-04-06 — INGEST

**Action:** Ingested shot distance diagnostic findings; created coordinate system article
**Source:** `notebooks/shot_distance_diagnostic.ipynb`, `src/xg_features.py`, `src/main.py`
**Pages touched:**
- Created `raw/project/2026-04-06_shot-distance-diagnostic.md` (diagnostic findings reference)
- Created `wiki/data/coordinate-system-and-normalization.md` (new article)
- Updated `wiki/data/nhl-api-shot-events.md` (added v2 bug docs, source [3], revision entry)
- Updated `index.md` (added both data articles, raw source entry)
**Notes:** Diagnostic investigation found that all 2.1M shot events were at schema v2 (pre-normalization fix). Pre-2020 seasons (~1.3M shots) had ~50% wrong coordinates due to missing `homeTeamDefendingSide` API field. A backfill completeness bug in `_game_is_complete()` was also found and fixed — it used `game_has_shot_events()` (any version) instead of `game_has_current_shot_events()` (current version). Post-2020 data confirmed correct; period-2 direction-change concern not supported for modern data (Cohen's d = -0.04).

### 2026-04-06 — INGEST

**Action:** Phase 1A batch compilation — created 5 data articles from project source code and database analysis
**Source:** `src/database.py` (enums), `src/xg_features.py` (parsing logic), `src/nhl_api.py` (endpoints), `src/arena_reference.py` (venue data), database frequency queries
**Pages touched:**
- Created `wiki/data/shot-type-taxonomy.md` — 10 shot types with frequency data and goal rates
- Created `wiki/data/manpower-states.md` — 15 manpower states with situation code parsing and frequency data
- Created `wiki/data/score-states.md` — 7 score-state buckets with behavioral effects
- Created `wiki/data/nhl-api-endpoints.md` — schedule and play-by-play endpoints, field availability by era
- Created `wiki/data/arena-venue-reference.md` — 32 teams + relocations, geographic coordinates, timezone offsets
- Updated `wiki/data/nhl-api-shot-events.md` — fixed cross-references to score states and manpower states (were pointing to non-existent concept paths), added NHL API Endpoints link
- Updated `wiki/data/coordinate-system-and-normalization.md` — added NHL API Endpoints cross-reference
- Updated `index.md` — added all 5 new articles
**Notes:** Completes Phase 1A of the knowledge base implementation plan (`docs/knowledge_base_implementation_plan.md`). All data articles now have bidirectional cross-references. The `nhl-api-shot-events.md` dangling links to shot-type-taxonomy and manpower/score states are now resolved. Frequency data drawn from full database (2.1M shots, 2007-2026) but note all data is still at schema v2 pending backfill.

### 2026-04-06 — UPDATE

**Action:** Added data-version dependency tracking to SCHEMA.md and tagged all articles
**Source:** Internal governance update
**Pages touched:**
- Updated `SCHEMA.md` — added "Data-Version Dependency Tracking" subsection to Staleness Policy with `data-version` / `data-revalidate` HTML comment convention and refresh workflow
- Tagged `wiki/data/coordinate-system-and-normalization.md` — `data-version: v2`, revalidate instruction for post-backfill negative-x-rate confirmation
- Tagged `wiki/data/nhl-api-shot-events.md` — `data-version: v2`, revalidate instruction for post-backfill status update
- Tagged `wiki/data/shot-type-taxonomy.md`, `manpower-states.md`, `score-states.md` — `data-version: v2 (coordinate-independent)`, explicitly noting these are unaffected by v3 normalization
**Notes:** After v3 backfill completes, run `grep -r 'data-version: v2' knowledge_base/wiki/` to find all articles needing refresh. Articles marked "coordinate-independent" can be skipped. Articles with `data-revalidate` instructions describe exactly what queries/updates to perform.

### 2026-04-06 — INGEST

**Action:** Phase 1B batch compilation — created 7 concept articles from component docs and domain knowledge
**Source:** `docs/xg_model_components/01-04, 09`, `src/xg_features.py`, `src/database.py`, domain knowledge
**Pages touched:**
- Created `wiki/concepts/expected-goals-xg.md` — xG definition, feature categories, evaluation metrics, base rate
- Created `wiki/concepts/score-effects.md` — volume/quality asymmetry by score state, mechanisms, model implications
- Created `wiki/concepts/zone-starts.md` — faceoff zone impact, interaction with decay, player evaluation adjustment
- Created `wiki/concepts/faceoff-decay.md` — post-faceoff spike, 5 recency bins, zone-specific dynamics
- Created `wiki/concepts/venue-scorekeeper-bias.md` — coordinate and frequency bias types, detection, correction strategies
- Created `wiki/concepts/rest-travel-effects.md` — rest days, travel distance, timezone delta, comparative rest
- Created `wiki/concepts/handedness-effective-angle.md` — off-wing classification, effective angle geometry, planned Phase B features
- Updated `index.md` — added all 7 concept articles
**Notes:** Completes Phase 1B of the knowledge base implementation plan. All articles tagged with `data-version: v2` and `data-revalidate` instructions. Venue bias and handedness articles are most sensitive to coordinate normalization and flagged accordingly. Score effects, faceoff decay, zone starts, and rest/travel are coordinate-independent. Total wiki: 14 articles (7 data + 7 concepts).

### 2026-04-07 — INGEST

**Action:** Phase 1C batch compilation — created 5 methods articles from validation framework notebook and CLAUDE.md rigor requirements
**Source:** `notebooks/model_validation_framework.ipynb` (helper functions, Steps 2-5), `CLAUDE.md` (Statistical Analysis Rigor Requirements), `docs/xg_model_components/05-06`
**Pages touched:**
- Created `wiki/methods/temporal-cross-validation.md` — season-block CV, forward-chaining, MIN_TRAIN_SEASONS, temporal stability
- Created `wiki/methods/calibration-analysis.md` — reliability diagrams, Hosmer-Lemeshow, calibration slope/intercept, per-segment checks
- Created `wiki/methods/bootstrapping-confidence-intervals.md` — bootstrap CIs, Wilson intervals, MIN_SHOTS_PER_CELL, sample adequacy
- Created `wiki/methods/rapm-regularized-adjusted-plus-minus.md` — design matrices, ridge/elastic-net, ORAPM/DRAPM separation
- Created `wiki/methods/effect-size-measures.md` — Cohen's h/d, COHEN_H_SMALL threshold, two-gate decision rule
- Updated `index.md` — added all 5 method articles
**Notes:** Completes Phase 1C of the knowledge base implementation plan. Methods articles are implementation-free (no empirical data tables) so no data-version tags needed. All articles cross-reference each other and link back to concept/data articles. Total wiki: 19 articles (7 data + 7 concepts + 5 methods).

### 2026-04-08 — INGEST

**Action:** Phase 2 — external source ingestion (6 sources: MoneyPuck, Evolving Hockey, HockeyViz Magnus, NHL API community docs, Schuckers & Curro, Karpathy LLM wiki)
**Source:** Web fetches from moneypuck.com, evolving-hockey.com, hockeyviz.com, github.com (Zmalski, dword4), Schuckers/Curro MIT Sloan papers (2011, 2013), Karpathy GitHub gist
**Pages touched:**
- Created `raw/external/2026-04-08_moneypuck-xg-methodology.md`
- Created `raw/external/2026-04-08_evolving-hockey-xg-and-war.md`
- Created `raw/external/2026-04-08_hockeyviz-magnus-model.md`
- Created `raw/external/2026-04-08_nhl-api-community-documentation.md`
- Created `raw/external/2026-04-08_schuckers-curro-thor-digr.md`
- Created `raw/external/2026-04-08_karpathy-llm-knowledge-base.md`
- Created `wiki/comparisons/public-xg-model-survey.md` (new article — first in comparisons category)
- Updated `wiki/concepts/expected-goals-xg.md` (added external model references, link to survey)
- Updated `wiki/methods/rapm-regularized-adjusted-plus-minus.md` (added Evolving Hockey WAR/GAR, THoR, Magnus RAPM implementations)
- Updated `wiki/concepts/venue-scorekeeper-bias.md` (added Schuckers CDF-matching rink bias correction)
- Updated `wiki/data/nhl-api-endpoints.md` (added community documentation references, legacy API note)
- Updated `wiki/meta/knowledge-gaps.md` (marked external sources as ingested, comparisons category partially filled)
- Updated `index.md` (added comparison article, 6 external raw sources)
**Notes:** Completes Phase 2 of the knowledge base implementation plan. All 6 external sources ingested into `raw/external/`. One new wiki article created (public xG model survey). Five existing articles updated with external references. HockeyViz site returned 403 on direct page fetches; Magnus content compiled from search result excerpts and cached descriptions. Schuckers/Curro THoR paper read in full via PDF extraction. Total wiki: 21 articles (7 data + 7 concepts + 5 methods + 1 comparison + 1 meta). Total raw external sources: 6.

### 2026-04-08 — INGEST

**Action:** Phase 1D — created knowledge gaps meta-article by surveying all 19 existing articles
**Source:** Automated gap scan of wiki articles, `docs/knowledge_base_implementation_plan.md`, `knowledge_base/SCHEMA.md`
**Pages touched:**
- Created `wiki/meta/knowledge-gaps.md` — 7 uncovered concepts, 2 empty categories, 12 articles pending v3 refresh, 5 candidate external sources, 2 component docs without wiki coverage
- Updated `index.md` — added meta article, updated last-updated date
**Notes:** Completes Phase 1 of the knowledge base implementation plan. All four sub-phases done: 1A (7 data articles), 1B (7 concept articles), 1C (5 methods articles), 1D (1 meta article). Total wiki: 20 articles. Next phase is Phase 2 (external source ingestion) — gated on user providing or approving external sources for ingest.

### 2026-04-18 — INGEST

**Action:** Added rink event-map visualization utilities and documented the method
**Source:** `src/rink_viz.py`, `src/database.py` (`load_game_shots`, `get_random_game_id`), `notebooks/event_map_gallery.ipynb`, `notebooks/shot_distance_diagnostic.ipynb` refactor
**Pages touched:**
- Created `wiki/methods/rink-event-visualization.md` — new methods article covering drawing functions, hexbin/heatmap/KDE density tradeoffs, and per-game inspection patterns
- Updated `wiki/data/coordinate-system-and-normalization.md` — added Related Pages link to new article, revision history entry
- Updated `wiki/concepts/venue-scorekeeper-bias.md` — added Related Pages link to new article, revision history entry
- Updated `index.md` — added methods entry, bumped last-updated date
**Notes:** Rink drawing helpers (`draw_half_rink`, `draw_full_rink`) extracted from `notebooks/shot_distance_diagnostic.ipynb` into `src/rink_viz.py` with named constants for geometry and style. Added `plot_shots` scatter helper and `plot_shot_density` with three methods — hexbin recommended for full-dataset aggregates (fast, no kernel bleed past boards; auto-switches to log-scale above 50k points). New `event_map_gallery.ipynb` demonstrates aggregate-hexbin + per-period facet + random-game workflow using `get_random_game_id()`. No derived-data values changed; no schema version bump. Article has no empirical data tables, so no `data-version` tag. Total wiki: 22 articles (7 data + 7 concepts + 6 methods + 1 comparison + 1 meta).

## 2026-04-18
**Action:** Updated shift-level knowledge base status after Phase 1 scaffold execution

**Files updated:**
- `knowledge_base/wiki/concepts/quality-of-teammates-competition.md`

**Notes:** Documented that shift ingestion and on-ice interval construction are now implemented and ready to feed QoT/QoC feature engineering phases.

### 2026-04-19 — UPDATE

**Action:** Recorded Phase 2 completion and multicollinearity finding; governance entry for PRs #44–#47
**Source:** `docs/xg_model_roadmap.md` (rigor-first rewrite, Phase 0/1 retroactive acceptance blocks, Phase 2 completion block), `src/stats_helpers.py`, `src/database.py` (`validate_game_context_quality`), `src/main.py` (`finalize_season_diagnostics`), live VIF analysis against `data/nhl_data.db`
**Pages touched:**
- Updated `wiki/concepts/rest-travel-effects.md` — added Multicollinearity Warning section (`rest_advantage = home_rest_days - away_rest_days` by construction → perfect linear dependence, VIF ∞ when all three included); recorded 1.07% non-structural travel/timezone null rate from `validate_game_context_quality` as Phase 2.5.5 work; added sources [5] and [6]; bumped last-verified date
- Updated `wiki/concepts/venue-scorekeeper-bias.md` — documented that `finalize_season_diagnostics` is now wired into the pipeline, so `venue_bias_diagnostics` auto-populates on scrape and backfill (previously scaffolded but never invoked); added source [4]; bumped last-verified date
- Updated `index.md` — bumped last-updated date
**Notes:** Governance-only updates for PR #44 (rigor-first roadmap rewrite establishing the eight-point Statistical Analysis Rigor framework), PR #45 / PR #46 (retroactive acceptance blocks for Phases 0 and 1), and the substantive content from PR #47 (Phase 2 completion: venue diagnostics wiring, `game_context` validator, VIF helper with live findings). Phase 2's acceptance criteria (2) and (3) — held-out faceoff-decay validation and zone-start change-on-the-fly inference — are formally deferred to their gating dependencies (Phase 2.5.2 for validation helpers, shifts ingestion for zone-start). No new articles; no v3 coordinate dependencies affected. Wiki counts unchanged.

### 2026-04-20 — UPDATE

**Action:** Recorded roadmap Phase 2.5.1 completion: player metadata pipeline
**Source:** `src/nhl_api.py` (`get_player_metadata`, `_parse_player_landing`), `src/database.py` (`upsert_player`, `upsert_players`, `get_missing_player_ids`, `backfill_player_metadata`, `populate_player_game_stats`), `src/main.py` (`refresh_player_tables`), `tests/test_nhl_api.py`, `tests/test_database.py`
**Pages touched:**
- Updated `wiki/data/nhl-api-endpoints.md` — added "Player Landing Endpoint" section documenting URL pattern, response shape, and parser behavior; updated overview and relevance sections from two to three endpoints; added source [5] for the player metadata pipeline; bumped last-verified date
- Updated `wiki/concepts/handedness-effective-angle.md` — flipped implementation-status table rows for `players.shoots_catches` and the player-landing endpoint from "not implemented" to "populated" / "implemented"; updated revalidate tag and relevance section; added sources [2] and [3]; bumped last-verified date
- Updated `index.md` — bumped last-updated date
**Notes:** Pipeline derives shooter/goalie ids from `shot_events`, fetches each missing player from `/v1/player/{id}/landing`, and upserts into the `players` dimension. `populate_player_game_stats` derives per-game counting stats (shots, goals) from `shot_events` and infers goalie `team_id` via the opponent of `shooting_team_id` in the `games` table. TOI and non-shot counters remain at their NOT NULL DEFAULT 0 values until shifts/boxscore data arrive in later phases — acceptable under `validate_player_game_stats_quality`. No new articles; no schema version bump (player tables are not derived-shot tables with a version column). Wiki counts unchanged.


