---
name: knowledge-base
description: Maintain, update, and lint the NHL analytics knowledge base under `knowledge_base/`. Use when the user asks to ingest a new source, update existing wiki articles, run a lint/health check, or refresh articles after a schema/data-version bump. The skill defers to `knowledge_base/SCHEMA.md` for all authoring rules and workflows — read it first, every time.
---

# Knowledge Base Skill

This skill is an operational wrapper around the knowledge base. **`knowledge_base/SCHEMA.md` is the authoritative governance document** — article template, category definitions, file naming, cross-reference rules, citation rules, ingest workflow, lint workflow, staleness policy, and data-version dependency tracking all live there. When SCHEMA.md and this file disagree, SCHEMA.md wins.

## Pick a mode from the user's request

| User cue | Mode | SCHEMA.md section |
|----------|------|-------------------|
| "ingest X", "add source", "compile from <notebook/doc>" | **INGEST** | Ingest Workflow |
| "update the X article", "X changed in the codebase, reflect it" | **UPDATE** | (scoped edits; same rules as ingest) |
| "lint the KB", "audit", "health check", "check for dead links" | **LINT** | Lint Workflow |
| "backfill finished", "data-version bumped, refresh empirical claims" | **REFRESH** | Data-Version Dependency Tracking |

If the request does not clearly map to one mode, ask a single clarifying question before touching files.

## Pre-flight (every mode)

1. Read `knowledge_base/SCHEMA.md` in full.
2. Read `knowledge_base/index.md` to see the current catalog.
3. Read the last ~5 entries in `knowledge_base/log.md` to match operational cadence and avoid duplicating recent work.

## Invariants (every mode)

- No article is committed that would fail any of the 8 Lint Workflow checks on day one.
- Every factual claim in Key Details has a `[n]` citation resolving to a Sources entry.
- Every new wiki page has ≥1 outbound link (Related Pages) **and** ≥1 inbound link (update the other side).
- Articles containing empirical data (counts, rates, distributions) declare `<!-- data-version: vN -->` and `<!-- data-revalidate: ... -->` directly after the title/summary. Articles with only static/code-derived content omit the tags.
- File naming: wiki articles use lowercase-hyphen-kebab; raw sources use `YYYY-MM-DD_short-slug.md`. Names are unique across all categories.
- **Absolute paths to project artifacts** (e.g., `docs/xg_model_components/...`, `src/...`, `notebooks/...`) are repo-root-relative. **Wiki → wiki** links are relative (`../category/file.md`).
- Every operation appends an entry to `log.md`. The log is append-only — never edit an existing entry.

## INGEST mode

Follow SCHEMA.md §Ingest Workflow steps 1-9. Operational notes:

- Step 1 (raw source): put external sources in `raw/external/`, project references in `raw/project/`. Raw files are immutable after creation — if a source gets revised later, add a new dated file rather than overwriting.
- Step 3 (summary page): not every source warrants a new wiki page. If the source only reinforces existing claims, skip the new page and go straight to step 4.
- Step 7 (index.md): update the "Last updated" date line at the top. Add new wiki pages under the correct category, and new raw sources to the Raw Sources table.
- Step 8 (log entry): use the template below.

## UPDATE mode

Scoped edits to existing articles triggered by a code change, new finding, or review feedback. Same invariants as INGEST; additionally:

- Bump the article's Revision History with today's date and a one-line description of the change.
- If the update affects a cross-reference (e.g., a claim that cited page A now needs to cite page B), check that both sides of the link remain consistent.
- If the update touches empirical data, bump the `data-version` tag to the current `_XG_EVENT_SCHEMA_VERSION` (read from `src/database.py`) and update the `data-revalidate` note if the revalidation recipe has changed.

## LINT mode

Execute each of SCHEMA.md §Lint Workflow's 8 checks in order. Suggested implementation:

| # | Check | Operational recipe |
|---|-------|--------------------|
| 1 | Orphan detection | For each `wiki/*/*.md` filename, grep `knowledge_base/wiki/` for references. Zero inbound ⇒ orphan. `wiki/meta/*` exempt. |
| 2 | Dead link detection | For every `](../` or `](knowledge_base/` target in wiki articles, verify the path resolves to an existing file. |
| 3 | Index completeness | Compare `find knowledge_base/wiki -name '*.md'` (excluding `.gitkeep`) against entries in `index.md`. Report both directions of drift. |
| 4 | Citation audit | For each article, extract `[n]` markers in Key Details and verify each has a matching Sources entry. For Sources pointing to `raw/...`, verify the file exists. |
| 5 | Template compliance | Verify each article has all six required section headers (Overview, Key Details, Relevance to This Project, Sources, Related Pages, Revision History). Also verify the one-line summary blockquote after the title. |
| 6 | Staleness detection | Parse the most recent date in each Revision History. Flag anything older than 6 months relative to today's date. Flag articles referencing project state (schema versions, feature counts) that may have drifted. |
| 7 | Contradiction scan | For pairs of overlapping articles (e.g., shot-type taxonomy ↔ NHL API shot events), compare numeric thresholds, frequencies, and methodology claims. Flag inconsistencies. |
| 8 | Gap analysis | Update `wiki/meta/knowledge-gaps.md` with: concepts mentioned but lacking their own page, raw sources not yet fully ingested, project artifacts that changed since last reference. |

Collect all findings into a **single** `### YYYY-MM-DD — LINT` log entry. If corrective actions were taken during the pass, list them under a "Corrective actions" field in the same entry — do not open a separate `UPDATE` entry per fix.

When lint runs surface ≥5 orphan or dead-link issues, pause and ask the user whether to proceed with mass corrections or stop and file findings as a report first.

## REFRESH mode

Triggered after a `_XG_EVENT_SCHEMA_VERSION` bump + backfill. Follow SCHEMA.md §Data-Version Dependency Tracking §Refresh workflow:

1. Grep `knowledge_base/wiki/` for `<!-- data-version:` tags.
2. For each article whose `data-version` does not match the current `_XG_EVENT_SCHEMA_VERSION` (read it from `src/database.py`), execute the `data-revalidate` recipe — typically rerun specific queries and update frequencies/counts/rates in Key Details tables.
3. Update the article's `data-version` tag and append a Revision History entry.
4. Log a single `### YYYY-MM-DD — REFRESH` entry in `log.md` listing every article touched and a one-line summary of what changed.

Articles explicitly tagged `data-version: vN (coordinate-independent)` (or similar) are exempt — skip them.

## Log entry template

Append-only. Use today's date (`currentDate` in session context). One entry per operation.

```markdown
### YYYY-MM-DD — [INGEST|UPDATE|LINT|REFRESH]

**Action:** <one-line description of what was done>
**Source:** <comma-separated raw/ files, src/ files, notebooks, or "Internal">
**Pages touched:**
- Created `wiki/<category>/<file>.md` — <what the article covers>
- Updated `wiki/<category>/<file>.md` — <what changed>
- Updated `index.md` — <new entries / last-updated bump>
**Notes:** <rationale, follow-ups, data-version implications, gaps discovered>
```

For LINT: add a `**Findings:**` field (bulleted) and a `**Corrective actions:**` field (bulleted; may be "None — report only"). For REFRESH: prefix each touched article with its old→new `data-version` transition.

## PR scope

Knowledge base edits are almost always a separate conceptual PR from code changes, per CLAUDE.md's "Check conceptual PR scope" guardrail. Unless the user explicitly bundled them with code work, stage wiki edits on a dedicated branch such as `docs/kb-<topic>` or `chore/kb-<topic>`.

Exception: when a code change in the same PR directly invalidates a wiki claim (e.g., a schema column rename), updating the affected article in the same PR is preferable to leaving the wiki stale across branch merges.

## Completion checklist (before reporting done)

- [ ] All invariants above still hold for every touched article.
- [ ] `index.md` reflects new/removed articles and has an updated "Last updated" date (for INGEST/UPDATE).
- [ ] `log.md` has one new entry for this operation, matching the template.
- [ ] For INGEST/UPDATE affecting empirical data: `data-version` tags match current `_XG_EVENT_SCHEMA_VERSION`.
- [ ] For LINT: all 8 checks executed, findings consolidated in one entry, corrective actions (if any) recorded in the same entry.
- [ ] For REFRESH: every stale-tagged article either refreshed or explicitly noted as exempt.
