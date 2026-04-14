# Knowledge Base Implementation Plan

## Background

This plan completes the Karpathy-style LLM Knowledge Base scaffolded in commit
`45a62d5`. The architecture follows the pattern described in
[Karpathy's original post](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
and the [VentureBeat analysis](https://venturebeat.com/data/karpathy-shares-llm-knowledge-base-architecture-that-bypasses-rag-with-an):

- **Raw → Wiki compilation**: Raw sources (papers, docs, code references) go into
  `raw/`. The LLM reads them and compiles structured wiki articles with summaries,
  key details, cross-references, and citations.
- **LLM as librarian**: The LLM writes and maintains the wiki. Humans rarely edit
  directly. Every new finding, notebook result, or external source gets ingested
  through the SCHEMA.md workflow.
- **Index-based navigation**: At the project's scale (~50-100 articles), the LLM
  navigates via `index.md` summaries rather than vector search.
- **Self-healing through linting**: Periodic health checks find inconsistencies,
  dead links, orphaned pages, and stale references.
- **Auditable**: Every claim traces to a specific `.md` file. No black-box embeddings.

## Current State

| Component | Status |
|-----------|--------|
| `SCHEMA.md` governance | Complete |
| `index.md` catalog | 2 entries |
| `log.md` operations log | 2 entries |
| `raw/external/` | Empty |
| `raw/project/` | 1 reference (shot distance diagnostic) |
| `wiki/data/` | 2 articles (shot events, coordinate system) |
| `wiki/concepts/` | Empty |
| `wiki/methods/` | Empty |
| `wiki/models/` | Empty |
| `wiki/comparisons/` | Empty |
| `wiki/meta/` | Empty |

## Phase 1: Core Compilation (Batch Ingest from Project Artifacts)

**Goal:** Compile the existing project docs, source code, and notebooks into a
first-pass wiki covering the foundational domain concepts. This is the "compilation
step" — turning the project's raw knowledge into structured, interlinked articles.

### Phase 1A: Data Articles

Source material: `src/database.py` enums, `src/xg_features.py` constants,
`src/nhl_api.py`, `src/arena_reference.py`, `docs/xg_model_components/01_*.md`

| Article | File | Summary |
|---------|------|---------|
| Shot Type Taxonomy | `wiki/data/shot-type-taxonomy.md` | The 10 valid shot types, definitions, frequency distribution, and xG relevance |
| Manpower States | `wiki/data/manpower-states.md` | The 15 valid manpower codes, NHL situation code parsing, how they map to game situations |
| Score States | `wiki/data/score-states.md` | The 7 score-state buckets, how they're derived from running score, behavioral effects |
| NHL API Endpoints | `wiki/data/nhl-api-endpoints.md` | Schedule and play-by-play endpoints, rate limits, response structure, field availability by era |
| Arena and Venue Reference | `wiki/data/arena-venue-reference.md` | 32 teams + relocations, lat/lon, timezone offsets, venue metadata |

Also needed: raw project references for `src/database.py` enums and
`src/arena_reference.py` as source material.

**Resolves:** The dangling links from `nhl-api-shot-events.md` to
`shot-type-taxonomy.md` and from future concept pages to manpower/score state
definitions.

### Phase 1B: Concept Articles

Source material: `docs/xg_model_components/01-04, 09`, `notebooks/*.ipynb`,
existing hockey analytics knowledge

| Article | File | Summary |
|---------|------|---------|
| Expected Goals (xG) | `wiki/concepts/expected-goals-xg.md` | What xG is, how it's calculated, why it matters, public model landscape |
| Score Effects | `wiki/concepts/score-effects.md` | How leading/trailing changes shot volume and quality; relevance to xG |
| Zone Starts | `wiki/concepts/zone-starts.md` | Offensive/defensive/neutral zone faceoffs and their impact on subsequent play |
| Faceoff Decay | `wiki/concepts/faceoff-decay.md` | Post-faceoff shot rate spike and exponential decay; time bins; zone interactions |
| Venue and Scorekeeper Bias | `wiki/concepts/venue-scorekeeper-bias.md` | How different venues record events differently; coordinate and frequency distortion |
| Rest and Travel Effects | `wiki/concepts/rest-travel-effects.md` | Back-to-back fatigue, travel burden, timezone crossing effects on performance |
| Handedness and Effective Angle | `wiki/concepts/handedness-effective-angle.md` | Shooter hand, off-wing advantage, effective goal-exposure angle |

### Phase 1C: Methods Articles

Source material: `docs/xg_model_components/05-07`,
`docs/xg_model_components/06_model_validation_framework.md`,
`notebooks/model_validation_framework.ipynb`, `CLAUDE.md` statistical rigor section

| Article | File | Summary |
|---------|------|---------|
| Temporal Cross-Validation | `wiki/methods/temporal-cross-validation.md` | Season-block CV for hockey data; why random splits leak; implementation |
| Calibration Analysis | `wiki/methods/calibration-analysis.md` | Reliability diagrams, Hosmer-Lemeshow, calibration slope/intercept; per-segment checks |
| Bootstrapping and Confidence Intervals | `wiki/methods/bootstrapping-confidence-intervals.md` | Bootstrap CIs for rates/proportions; Wilson intervals; sample size requirements |
| RAPM (Regularized Adjusted Plus-Minus) | `wiki/methods/rapm-regularized-adjusted-plus-minus.md` | Design matrices, ridge/elastic-net estimation, player impact isolation |
| Effect Size Measures | `wiki/methods/effect-size-measures.md` | Cohen's h/d, practical vs statistical significance, decision rules for this project |

### Phase 1D: Meta Articles

| Article | File | Summary |
|---------|------|---------|
| Knowledge Gaps | `wiki/meta/knowledge-gaps.md` | Concepts mentioned but not yet covered, stale references, planned articles |

## Phase 2: External Source Ingestion

**Goal:** Bring in external references that inform the project's modeling decisions.
These follow the full ingest workflow: raw source → read and analyze → compile into
wiki or update existing articles.

Candidate external sources (prioritized):
1. MoneyPuck xG methodology (public xG model benchmark)
2. Evolving Hockey WAR/xG methodology
3. NHL API documentation (official, if available)
4. Academic papers on xG modeling (e.g., Schuckers & Curro)
5. Karpathy's original knowledge base gist (meta-reference for our own architecture)

Each external source goes through:
1. Save to `raw/external/YYYY-MM-DD_slug.md` with metadata
2. LLM reads and identifies relevant concepts
3. Update existing wiki articles or create new ones
4. Update `index.md` and `log.md`

## Phase 3: Model and Comparison Articles

**Goal:** As xG model training progresses, document specific model architectures
and structured comparisons.

| Article | File | Summary |
|---------|------|---------|
| Logistic xG Baseline | `wiki/models/logistic-xg-baseline.md` | Feature set, training setup, performance metrics, calibration results |
| Public xG Model Survey | `wiki/comparisons/public-xg-model-survey.md` | MoneyPuck, Evolving Hockey, etc. — what features they use, reported performance |
| Regularization Methods Compared | `wiki/comparisons/regularization-methods-compared.md` | Ridge vs elastic-net vs hierarchical Bayes for RAPM |

These articles are gated on actual model training results existing.

## Phase 4: Ongoing Maintenance

Once the initial compilation is complete, the knowledge base enters steady-state
maintenance mode:

1. **Ingest-on-discovery**: Every new notebook finding, code change affecting domain
   logic, or external source gets ingested via the SCHEMA.md workflow.
2. **Lint after every 5 ingests**: Run the full lint checklist (orphan detection,
   dead links, index completeness, citation audit, template compliance, staleness,
   contradictions, gap analysis).
3. **Phase-boundary lint**: Run a full lint pass before starting each new development
   phase from the xG roadmap.
4. **Schema version tracking**: When version constants bump in `database.py`, update
   any wiki articles that reference specific schema versions.

## Execution Order

The phases above describe logical groupings. Within Phase 1, the recommended
execution order is:

1. **1A first** (Data articles) — these are referenced by concept and method articles
   and resolve existing dangling links.
2. **1B next** (Concepts) — these are the domain backbone and link heavily to data
   articles.
3. **1C then** (Methods) — these reference concepts and data articles.
4. **1D last** (Meta) — the knowledge gaps article is populated by surveying what's
   missing after 1A-1C.

Each article within a sub-phase is independent and can be written in parallel (e.g.,
by multiple agent invocations).

## Scale Estimate

| Category | Articles | Est. Words Each | Total Words |
|----------|----------|-----------------|-------------|
| Data (1A + existing) | 7 | 800-1200 | ~7,000 |
| Concepts (1B) | 7 | 600-1000 | ~5,600 |
| Methods (1C) | 5 | 800-1200 | ~5,000 |
| Models (Phase 3) | 1-3 | 800-1200 | ~3,000 |
| Comparisons (Phase 3) | 2 | 1000-1500 | ~2,500 |
| Meta (1D) | 1 | 400-600 | ~500 |
| **Total** | **~25** | | **~24,000** |

Well within the ~100 article / ~400k word range where Karpathy reports index-based
navigation works well without RAG infrastructure.
