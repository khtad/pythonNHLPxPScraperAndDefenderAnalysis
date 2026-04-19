# AGENTS.md

This repository's project instructions, conventions, and guardrails are maintained in [`CLAUDE.md`](./CLAUDE.md).

**All agents — regardless of which model or tool is in use — must read and follow `CLAUDE.md` as the authoritative source of project rules.** This file exists so that non-Claude agents (e.g., Codex, Cursor, Aider, Copilot, local models) pick up the same guidance when `CLAUDE.md` is not automatically loaded.

## Required reading order

1. [`CLAUDE.md`](./CLAUDE.md) — project overview, architecture, testing, and all development guardrails.
2. [`knowledge_base/SCHEMA.md`](./knowledge_base/SCHEMA.md) — wiki governance, if touching `knowledge_base/`.
3. [`docs/xg_model_roadmap.md`](./docs/xg_model_roadmap.md) — xG model plan, if touching modeling code or notebooks.

## Fallback context

`CLAUDE.md` is the single source of truth. If guidance here ever conflicts with `CLAUDE.md`, `CLAUDE.md` wins. Do not duplicate rules into this file — update `CLAUDE.md` instead and leave this file as a pointer.
