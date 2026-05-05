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



### 2026-04-24 — UPDATE

**Action:** Updated wiki after venue correction baseline implementation and API transport-error hardening
**Source:** `src/database.py` (`create_venue_bias_corrections_table`, `populate_venue_bias_corrections`, `load_game_shots_with_venue_correction`), `src/main.py` (`finalize_season_diagnostics` correction call), `src/nhl_api.py` (`_api_get_with_status` transport exception handling), `docs/xg_model_roadmap.md`
**Pages touched:**
- Updated `wiki/concepts/venue-scorekeeper-bias.md` — changed status from “correction planned” to “initial correction layer implemented”; documented shrinkage-based distance adjustment flow, storage in `venue_bias_corrections`, and remaining held-out acceptance requirements.
- Updated `wiki/data/nhl-api-endpoints.md` — documented `_api_get_with_status` behavior for `requests.RequestException` transport failures.
- Updated `index.md` — bumped last-updated date and summary line.
**Notes:** No new wiki pages created. This update records implementation-state changes in project code and roadmap status; empirical venue-bias statistics remain data-version-dependent and still require the held-out validation pass defined in Phase 2.5.4 acceptance criteria.

### 2026-04-24 — UPDATE

**Action:** Added explicit PR-precondition governance for knowledge-base maintenance
**Source:** `CLAUDE.md` (Development Guardrails), `knowledge_base/SCHEMA.md`
**Pages touched:**
- Created `wiki/meta/knowledge-base-maintenance-workflow.md` — documented required pre-PR KB maintenance steps (wiki update, index refresh, and log entry) plus auditability requirement for no-change cases.
- Updated `index.md` — added meta-page link and refreshed Last updated summary.
**Notes:** Governance/documentation-only update. No empirical data claims changed and no `data-version` tags required.

### 2026-04-28 — UPDATE

**Action:** Added executable KB preflight guardrail and refreshed shot-event schema status for Phase 2.5.3 validation-scorecard readiness
**Source:** `scripts/check_knowledge_base_update.py`, `tests/test_knowledge_base_governance.py`, `CLAUDE.md`, `src/database.py` (`_migrate_shot_events_v4_to_v5`, `_XG_EVENT_SCHEMA_VERSION`), `artifacts/validation_scorecard_latest.md`, `docs/xg_model_roadmap.md`
**Pages touched:**
- Updated `wiki/meta/knowledge-base-maintenance-workflow.md` — added the `scripts/check_knowledge_base_update.py` preflight, explicit agent planning requirement, and source reference for the regression tests.
- Updated `wiki/data/nhl-api-shot-events.md` — refreshed the schema description to v5, added `shot_event_type` and on-ice slot documentation, and recorded the partial v5 coverage blocker for validation-scorecard export.
- Updated `index.md` — bumped Last updated date and summary line.
**Notes:** Prevents repeat omissions by making KB maintenance a visible work item and an executable preflight. The validation-scorecard branch safely promoted 1,574,298 local `shot_events` rows from v4 to v5, but 546,702 remain stale; 507,543 of those are otherwise training-eligible post-2009 complete-geometry rows, so live Phase 2.5.3 scorecard export remains blocked until current-schema coverage is complete.

### 2026-04-28 - UPDATE

**Action:** Added Phase 2.5.4 venue-correction validation scorecard harness
**Source:** `src/validation.py` (`evaluate_venue_correction_scorecard`), `scripts/export_venue_correction_validation.py`, `tests/test_validation.py`, `tests/test_venue_correction_validation_export.py`, `docs/xg_model_roadmap.md`, `docs/xg_model_components/04_scorekeeper_bias.md`
**Pages touched:**
- Updated `wiki/concepts/venue-scorekeeper-bias.md` - documented the new scorecard harness that combines held-out log-loss, home-ice over-correction, and residual venue z-score gates before accepting venue correction for xG training.
- Updated `index.md` - bumped Last updated date and summary line.
**Notes:** DB-independent harness work only. Live Phase 2.5.4 metrics still wait on the v5 database update and a future metrics-generation run.

### 2026-04-28 - UPDATE

**Action:** Added progress output to validation artifact exporters
**Source:** `scripts/export_validation_scorecard.py`, `scripts/export_venue_correction_validation.py`
**Pages touched:**
- None - operational script verbosity only; no domain wiki article claims changed.
**Notes:** The validation scorecard exporter now prints stage timestamps, schema-coverage summaries, streamed notebook execution output, and periodic notebook-execution heartbeats; it also terminates or kills the notebook child process if the exporter is interrupted. On Windows, it launches `nbconvert` through a Python entrypoint that sets `WindowsSelectorEventLoopPolicy` before importing nbconvert, suppressing the harmless ZMQ Proactor-loop warning without hiding other warnings. The venue-correction exporter now prints payload, gate, and artifact-write progress.

### 2026-04-28 - UPDATE

**Action:** Recorded live validation-scorecard run and refreshed shot-type taxonomy coverage
**Source:** `src/database.py` (`VALID_SHOT_TYPES`), `notebooks/model_validation_framework.ipynb`, `artifacts/validation_scorecard_latest.md`, `docs/xg_model_roadmap.md`
**Pages touched:**
- Updated `wiki/data/shot-type-taxonomy.md` - refreshed v5 counts and documented the 11 accepted shot types, including `deflected` and `between-legs`.
- Updated `wiki/data/nhl-api-shot-events.md` - recorded completed v5 backfill, zero stale training-eligible rows, and the live validation-scorecard status.
- Updated `index.md` - refreshed Last updated summary and the shot-type taxonomy entry.
**Notes:** The validation scorecard now runs against live v5 data and produces concrete results. Phase 3 remains blocked by scorecard failures, but the stale-schema execution blocker is resolved.

### 2026-04-28 - UPDATE

**Action:** Recorded live DB-backed venue-correction scorecard result
**Source:** `scripts/export_venue_correction_validation_from_db.py`, `artifacts/venue_correction_validation_latest.md`, `docs/xg_model_roadmap.md`, `docs/xg_model_components/04_scorekeeper_bias.md`
**Pages touched:**
- Updated `wiki/concepts/venue-scorekeeper-bias.md` - recorded the live v5 Phase 2.5.4 scorecard result, including leakage-safe prior-season correction usage and the residual corrected-distance z-score failure.
- Updated `index.md` - refreshed Last updated summary to include the venue-correction scorecard run.
**Notes:** The DB-backed runner passes held-out log-loss and home-ice over-correction gates but fails the residual venue z-score gate (`max |z| = 4.038`, worst venue-season `20092010:Madison Square Garden`). The current shrinkage distance correction remains exploratory and should not feed production xG training until the residual gate passes or a better correction policy is selected.

### 2026-04-30 - UPDATE

**Action:** Remediated live validation-scorecard failures and tightened the model-training contract
**Source:** `src/database.py` (`load_training_shot_events`), `src/validation.py` (`practical_calibration_metrics`, `run_temporal_cv_with_prior_season_calibration`, `evaluate_leakage_audit`), `notebooks/model_validation_framework.ipynb`, `artifacts/validation_scorecard_latest.md`, `artifacts/venue_correction_validation_latest.md`, `docs/xg_model_roadmap.md`, `docs/xg_model_components/05_xg_model_training_and_calibration.md`, `docs/xg_model_components/06_model_validation_framework.md`, `CLAUDE.md`
**Pages touched:**
- Updated `wiki/methods/calibration-analysis.md` - changed Hosmer-Lemeshow from hard gate to diagnostic and documented practical calibration gates.
- Updated `wiki/methods/temporal-cross-validation.md` - documented prior-season Platt calibration and selected scorecard feature families.
- Updated `wiki/data/nhl-api-shot-events.md` - documented the tightened loader contract and live training-row count.
- Updated `wiki/concepts/expected-goals-xg.md` - refreshed the calibration metric summary.
- Updated `wiki/concepts/venue-scorekeeper-bias.md` - refreshed live DB-backed venue scorecard metrics under the tightened contract.
- Updated `index.md` - refreshed Last updated summary.
**Notes:** The live validation scorecard now passes 8/8 gates (AUC 0.7551, slope 0.9870, max decile error 0.407 pp, ECE 0.193 pp, subgroup max error 1.24 pp). Venue correction remains exploratory because residual corrected-distance z-score still fails (`max |z| = 4.067`).

### 2026-05-01 - UPDATE

**Action:** Added event-frequency scorekeeper-bias diagnostics and refreshed the venue-correction scorecard policy
**Source:** `src/venue_bias.py`, `src/validation.py` (`evaluate_venue_correction_scorecard`), `scripts/export_venue_correction_validation.py`, `scripts/export_venue_correction_validation_from_db.py`, `notebooks/venue_bias_analysis.ipynb`, `artifacts/venue_correction_validation_latest.md`, `docs/xg_model_roadmap.md`, `docs/xg_model_components/04_scorekeeper_bias.md`, `CLAUDE.md`
**Pages touched:**
- Updated `wiki/concepts/venue-scorekeeper-bias.md` - documented event-frequency diagnostics, paired away-team-season comparison, anomaly classification, sample-adequate primary frequency gating, and the refreshed live scorecard result.
- Updated `index.md` - refreshed Last updated summary.
**Notes:** The venue-correction scorecard now separates distance/location residuals from event-frequency residuals. Frequency z-score league baselines and the primary acceptance gate exclude sample-inadequate venue-seasons, while one-off neutral/outdoor venues remain visible as `insufficient_evidence` diagnostics. The live DB-backed run still passes held-out log-loss and home-ice guardrails, but fails corrected-distance residuals (`max |z| = 4.067`, worst `20092010:Madison Square Garden`) and sample-adequate regular-season training-attempt frequency residuals (`max |z| = 3.572`, worst `20112012:Prudential Center`).

### 2026-05-01 - UPDATE

**Action:** Closed player database row-coverage blocker for RAPM prerequisites
**Source:** `src/database.py` (`populate_player_game_features`, `validate_player_game_features_quality`, `validate_player_database_readiness`), `src/main.py` (`refresh_player_tables`), `docs/xg_model_roadmap.md`, `docs/xg_model_components/09_handedness_and_effective_angle.md`, `CLAUDE.md`
**Pages touched:**
- Updated `wiki/methods/rapm-regularized-adjusted-plus-minus.md` - documented that player identity metadata, player-game stats, and player-game feature row coverage are populated, while RAPM still needs xG predictions and shift/TOI/on-ice exposure data.
- Updated `index.md` - refreshed Last updated summary.
**Notes:** Live readiness validation found `ids_missing_and_not_unavailable = 0`, 2,301/2,301 career 50-shot players with handedness populated, 831,573/831,573 event-derived player-game pairs covered by `player_game_stats`, and 831,573/831,573 `player_game_features` rows at the current feature-set version. Rolling TOI/points feature columns remain intentionally null until real TOI and assist inputs are available.

### 2026-05-01 - UPDATE

**Action:** Added shift-chart table population pipeline
**Source:** `src/shifts.py`, `src/on_ice_builder.py`, `src/shift_population.py`, `scripts/backfill_shift_data.py`, `src/database.py` (`shifts`, `on_ice_intervals`, shot-event slot update helpers), `src/main.py`, `docs/shift_level_data_analysis_roadmap.md`, `README.md`
**Pages touched:**
- Updated `wiki/data/nhl-api-endpoints.md` - documented the shift charts endpoint, consumed fields, and project population flow.
- Updated `wiki/data/nhl-api-shot-events.md` - documented that on-ice slot columns are populated from shift-chart intervals when available.
- Updated `index.md` - refreshed Last updated summary.
**Notes:** The new pipeline normalizes realistic NHL shift-chart payload keys, persists `shifts` and `on_ice_intervals` idempotently, updates `shot_events.home_on_ice_*` / `away_on_ice_*`, exposes `scripts/backfill_shift_data.py --all` for historical population, and reuses the same per-game function from `main.py` for newly processed games. QoT/QoC and RAPM output tables remain later-phase work.

### 2026-05-02 - UPDATE

**Action:** Corrected shift-chart endpoint documentation
**Source:** `src/shifts.py`, `tests/test_shift_phase1.py`, `CLAUDE.md`
**Pages touched:**
- Updated `wiki/data/nhl-api-endpoints.md` - corrected the shift charts URL from the Web API `gamecenter/{game_id}/shiftcharts` route to the NHL Stats REST `shiftcharts?cayenneExp=gameId=...` route.
- Updated `index.md` - refreshed Last updated summary and endpoint article description.
**Notes:** Runtime scraper logs showed uniform 404 responses from the old shift-chart URL. The project now documents that schedule, play-by-play, and player landing come from `api-web.nhle.com/v1`, while shift charts come from `api.nhle.com/stats/rest/en`.

### 2026-05-03 - UPDATE

**Action:** Added rolling venue-regime scorekeeper-bias diagnostics
**Source:** `src/venue_bias.py`, `src/validation.py` (`evaluate_venue_correction_scorecard`), `scripts/export_venue_correction_validation.py`, `scripts/export_venue_correction_validation_from_db.py`, `docs/xg_model_roadmap.md`, `docs/xg_model_components/04_scorekeeper_bias.md`
**Pages touched:**
- Updated `wiki/concepts/venue-scorekeeper-bias.md` - documented prior-only rolling estimates, centered exploratory diagnostics, regime classifications, and regime-aware scorecard acceptance semantics.
- Updated `index.md` - refreshed Last updated summary.
**Notes:** The venue-correction scorecard can now distinguish blocking unexplained/confounded residuals from supported persistent or temporary scorekeeper regimes. The committed live scorecard artifact is still the 2026-05-01 max-z result; venue correction remains exploratory until the DB-backed scorecard is rerun with the new regime-aware diagnostics and passes all hard gates.

### 2026-05-04 - UPDATE

**Action:** Recorded the executed live regime-aware venue-correction scorecard result
**Source:** `artifacts/venue_correction_validation_latest.md`, `docs/xg_model_roadmap.md`, `docs/xg_model_components/04_scorekeeper_bias.md`, `knowledge_base/wiki/concepts/venue-scorekeeper-bias.md`
**Pages touched:**
- Updated `wiki/concepts/venue-scorekeeper-bias.md` - documented that the live scorecard now runs in `regime_aware` mode and still fails because blocking unexplained/confounded residuals remain.
- Updated `index.md` - refreshed Last updated summary.
**Notes:** This supersedes the 2026-05-03 note that the committed artifact still needed a regime-aware rerun. The current live artifact treats `|z| >= 2` as a candidate residual rather than an automatic veto; supported `persistent_bias` and `temporary_supported_regime` rows are non-blocking, while `unexplained_or_confounded`, `population_shift_detected`, and `insufficient_evidence` remain blocking. The latest result passes held-out log-loss and home-ice guardrails but fails distance/location residuals (24 blocking regimes, 4 supported regimes) and event-frequency residuals (4 blocking regimes, 23 supported regimes), so venue correction remains exploratory.

### 2026-05-05 - UPDATE

**Action:** Added paired/stratified distance-location venue-regime evidence
**Source:** `src/venue_bias.py`, `scripts/export_venue_correction_validation_from_db.py`, `scripts/export_venue_correction_validation.py`, `tests/test_venue_bias.py`, `tests/test_venue_correction_validation_export.py`, `tests/test_venue_correction_validation_from_db.py`, `artifacts/venue_correction_validation_latest.md`, `docs/xg_model_roadmap.md`, `docs/xg_model_components/04_scorekeeper_bias.md`
**Pages touched:**
- Updated `wiki/concepts/venue-scorekeeper-bias.md` - documented paired visiting-team distance comparisons, shot-type/manpower stratification, evidence thresholds, and the refreshed live scorecard result.
- Updated `index.md` - refreshed Last updated summary.
**Notes:** The DB-backed runner now computes distance-location paired evidence from in-memory prior-corrected shot distances without mutating `shot_events` or `venue_bias_corrections`. The 2026-05-05 artifact still fails overall but reduces distance/location blockers to 10 with 18 supported regimes; event-frequency residuals show 5 blockers and 22 supported regimes. Venue correction remains exploratory until both residual gates have zero blocking regimes while log-loss and home-ice guardrails still pass.
