# Knowledge Base Schema

## Purpose and Scope

This wiki contains **NHL analytics domain knowledge**: statistical concepts, data sources, modeling methods, public research, and lessons learned from this project. It serves as a compiled, interlinked reference that an LLM can navigate via `index.md` to answer domain questions and inform model design decisions.

**What belongs here:**
- What a concept IS (xG, RAPM, score effects, venue bias)
- How a method WORKS (calibration, temporal CV, ridge regression)
- Where data COMES FROM and what it LOOKS LIKE (NHL API, coordinate systems, shot types)
- How models are BUILT and EVALUATED (architectures, performance, comparisons)

**What does NOT belong here:**
- Implementation plans and roadmaps → `docs/`
- Development guardrails, testing instructions, SQL conventions → `CLAUDE.md`
- Code → `src/`
- Statistical analyses and exploratory work → `notebooks/`

The wiki may **reference** all of the above but never duplicates or replaces them.

---

## Article Template

Every wiki article must follow this structure:

```markdown
# [Title]

> One-sentence summary for use in index.md

## Overview

[2-4 paragraphs explaining the concept/method/topic]

## Key Details

[Specifics: formulas, thresholds, taxonomies, parameter ranges, enumerations]

## Relevance to This Project

[How this concept connects to our xG model, RAPM work, or data pipeline.
Link to specific docs/, notebooks/, or src/ files where applicable.]

## Sources

[1] Description or title — path or URL
[2] ...

## Related Pages

- [Page Title](../category/filename.md)
- ...

## Revision History

- YYYY-MM-DD — Created. [Brief description]
```

**Rules:**
- The one-line summary after the title is mandatory. It is copied verbatim into `index.md`.
- Every article must have content in all six sections. If a section is genuinely not applicable, write "None." with a brief explanation.
- The Revision History records every substantive edit with a date and description.

---

## Category Definitions

| Directory | Scope | Examples |
|-----------|-------|---------|
| `wiki/concepts/` | What a thing IS | xG, RAPM, Corsi, score effects, zone starts, faceoff decay |
| `wiki/methods/` | How to DO something | Ridge regression, bootstrapping, calibration analysis, temporal CV |
| `wiki/data/` | Where data COMES FROM and what it LOOKS LIKE | NHL API endpoints, coordinate systems, shot type taxonomy, manpower codes |
| `wiki/models/` | Specific model ARCHITECTURES and their evaluation | Logistic xG baseline, public xG model survey |
| `wiki/comparisons/` | Structured A-vs-B or multi-option analyses | Public xG models compared, regularization methods compared |
| `wiki/meta/` | Wiki-about-wiki pages | Knowledge gaps, coverage map |

---

## File Naming Conventions

- **Wiki articles:** lowercase, hyphens for spaces, `.md` extension. Example: `expected-goals-xg.md`
- **Raw external sources:** `YYYY-MM-DD_short-slug.md` where the date is when the source was added (not its publication date). Example: `2026-04-05_moneypuck-methodology.md`
- **Raw project references:** `YYYY-MM-DD_short-slug.md` following the same convention. Example: `2026-04-05_shot-event-schema-ref.md`
- File names must be unique across all category directories.
- No subdirectories within category folders — keep each category flat.

---

## Cross-Referencing Rules

1. Every article must link to **at least one** related wiki page in its Related Pages section.
2. When an article mentions a concept that has its own wiki page, use a relative markdown link: `[concept name](../category/filename.md)`.
3. Orphaned pages (zero inbound links from any other wiki page) are flagged during lint.
4. Links from wiki articles to project artifacts use relative paths from the repo root: `docs/xg_model_components/03_faceoff_decay_modeling.md`, `notebooks/venue_bias_analysis.ipynb`, `src/xg_features.py`.

---

## Citation Rules

1. Every factual claim in Key Details must cite a source using `[n]` inline notation.
2. The Sources section lists citations as a numbered list with descriptions and paths/URLs.
3. Sources linking to `raw/` files use relative paths from `knowledge_base/`.
4. Sources linking to project artifacts use repo-root-relative paths.
5. Claims derived from project code or notebooks cite the specific file. Example: `[1] Shot type enum — src/database.py VALID_SHOT_TYPES`.
6. Claims from external sources cite the raw file and, if available, the original URL.
7. Unsourced claims in Overview paragraphs are acceptable only for widely known background context (e.g., "hockey is played on ice"). Domain-specific claims always require citations.

---

## Ingest Workflow

When adding a new source to the knowledge base, follow these steps in order:

1. **Add raw source file.** Place in `raw/external/YYYY-MM-DD_slug.md` (external) or `raw/project/YYYY-MM-DD_slug.md` (project artifact reference). Raw files are immutable after creation. For external sources, include metadata (title, author, date published, URL) and the full text or substantive excerpt. For project references, include the artifact path, date referenced, and a brief summary of what will be extracted.

2. **Read and analyze.** Identify: (a) key concepts mentioned, (b) factual claims with evidence, (c) methods described, (d) data sources referenced, (e) which existing wiki pages are relevant.

3. **Write summary page (if warranted).** If the source introduces a substantial new topic, create a wiki article following the article template. Not every source needs its own page.

4. **Update existing wiki pages.** For each existing page the new source is relevant to: add information, update claims with better evidence, add the source to the Sources section, update Revision History.

5. **Create new pages for new concepts.** If the source introduces concepts not yet covered, create articles. Each must follow the template and include cross-references.

6. **Update cross-references.** Check all touched pages for missing cross-links. Every new page must be linked from at least one existing page.

7. **Update index.md.** Add new pages to the appropriate category with their one-line summary. Add the raw source to the Raw Sources table. Update the "Last updated" date.

8. **Append log.md entry.** Record the operation with the standard format (see log.md).

9. **Verify.** Quick self-check: Does every new page have >= 1 cross-reference? Does every factual claim have a citation? Is the source listed in index.md? Is the log entry complete?

---

## Lint Workflow

Periodic health checks. Run before each new development phase and after any batch of 5+ ingests.

| # | Check | Description |
|---|-------|-------------|
| 1 | **Orphan detection** | Every wiki page must have >= 1 inbound link from another wiki page. Exception: `meta/` pages. |
| 2 | **Dead link detection** | Every relative markdown link in wiki pages must resolve to an existing file. |
| 3 | **Index completeness** | Every file in `wiki/*/` must appear in `index.md`. Every `index.md` entry must point to an existing file. |
| 4 | **Citation audit** | Every `[n]` marker in Key Details must have a corresponding Sources entry. Cited `raw/` files must exist. |
| 5 | **Template compliance** | Every wiki article must have all required sections: Overview, Key Details, Relevance to This Project, Sources, Related Pages, Revision History. |
| 6 | **Staleness detection** | Flag articles whose most recent Revision History entry is > 6 months old. Flag articles referencing project state (schema versions, feature counts) that may have changed. |
| 7 | **Contradiction scan** | Check overlapping articles for inconsistent numeric thresholds, methodology descriptions, or factual claims. |
| 8 | **Gap analysis** | Update `meta/knowledge-gaps.md` with: concepts mentioned but lacking their own page, raw sources not yet fully ingested, project artifacts that changed since last reference. |

**Output:** Structured findings report appended as a LINT entry in `log.md`. Corrective actions taken during the lint pass are recorded in the same entry.

---

## Relationship to Other Project Documents

| Document | Governs | Wiki Interaction |
|----------|---------|-----------------|
| `CLAUDE.md` | Development behavior, SQL conventions, statistical rigor, testing | Wiki follows these standards but does not modify CLAUDE.md. Wiki articles may cite CLAUDE.md as a source for project methodology decisions. |
| `docs/xg_model_roadmap.md` | Implementation planning, phase definitions | Wiki may reference phases and link to the roadmap. Wiki never modifies implementation plans. |
| `docs/xg_model_components/` | Component design specs | Wiki articles may link to component docs for implementation details. Direction is wiki → docs, not docs → wiki. |
| `notebooks/` | Analytical results and explorations | Wiki may summarize notebook findings and cite them as sources. Notebooks remain the authoritative source for statistical results. |
| `src/` | Implementation code | Wiki may reference source files for data schemas, enums, and function definitions. |

---

## Staleness Policy

- Articles referencing project implementation state (schema versions, feature counts, phase status) must include a "Last verified: YYYY-MM-DD" note in their Relevance to This Project section.
- Articles with no Revision History update in > 6 months are flagged during lint.
- Flagged articles are reviewed and either updated or marked with a staleness acknowledgment in their Revision History.
- When project code changes affect a wiki article's claims (e.g., a schema version bump, a new feature added), the article should be updated in the same PR or the next maintenance pass.
