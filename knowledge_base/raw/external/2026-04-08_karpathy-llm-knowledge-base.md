# Karpathy LLM Knowledge Base Architecture

> **Source:** https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
> **Author:** Andrej Karpathy
> **Retrieved:** 2026-04-08
> **Type:** Meta-reference — knowledge base architecture pattern

## Core Concept

Instead of retrieving from raw documents on each query (RAG), have LLMs incrementally build and maintain a persistent wiki — a structured markdown knowledge base that compounds over time rather than re-deriving knowledge repeatedly.

## Three-Layer Architecture

### Raw Sources Layer
- Immutable, curator-selected documents (articles, papers, images)
- Never modified by the LLM
- Serves as auditable source of truth

### Wiki Layer
- LLM-generated markdown files organized by content type
- Includes summaries, entity pages, concept pages, comparisons, syntheses
- The LLM owns this layer entirely — creating, updating, cross-referencing

### Schema Layer
- Configuration document (e.g., CLAUDE.md) defining wiki structure, conventions, and workflows
- Specifies how to ingest sources, answer queries, and maintain integrity

## Key Operations

### Ingest
Process new sources: read, discuss takeaways, write summaries, update entity/concept pages, log changes. A single source typically touches 10-15 pages.

### Query
Search relevant wiki pages, synthesize answers with citations. Valuable answers become new filed pages rather than disappearing into chat history.

### Lint
Periodic health checks for:
- Contradictions between articles
- Stale claims
- Orphan pages (no inbound links)
- Missing cross-references
- Data gaps

## Navigation

- **index.md** — content catalog listing all pages by category with one-line summaries. Updated on each ingest.
- **log.md** — chronological append-only record of ingests, queries, and lint passes.

## Scaling

At moderate scale (~100 sources, hundreds of pages), the index file enables adequate discovery. Vector search tools (e.g., qmd with BM25/vector hybrid + LLM re-ranking) useful as wikis grow beyond this.

## Key Insight

The maintenance burden — updating cross-references, noting contradictions, ensuring consistency — falls on the LLM, which "doesn't get bored." Humans curate sources and ask questions; the LLM handles bookkeeping. Knowledge compounds because synthesis happens once and is kept current rather than re-derived.

## Why Markdown Over RAG

Every claim traces to a specific .md file a human can read, edit, or delete. No black-box embeddings. Auditable by design.
