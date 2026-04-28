# Knowledge Base Maintenance Workflow

> A governance checklist for when and how to update the NHL analytics knowledge base during normal development and pull-request preparation.

## Overview

The knowledge base is a living reference layer for NHL analytics concepts, methods, and data contracts used by this project. Because model decisions and roadmap gates rely on those references, wiki content can drift out of sync with code and docs if updates are treated as optional.

This page defines the minimum maintenance workflow to run before opening or updating a pull request. The workflow emphasizes traceability: every substantive update should be discoverable from `index.md` and auditable in chronological order via `log.md`.

## Key Details

1. Knowledge-base maintenance is a pull-request precondition in project guardrails.[1]
2. For any change that affects project knowledge (definitions, methodology status, roadmap state, or data assumptions), update the relevant wiki article(s) in `knowledge_base/wiki/`.[1][2]
3. If wiki content changes, update `knowledge_base/index.md` with a fresh "Last updated" date and any new page links.[2]
4. Append a dated operation entry to `knowledge_base/log.md` summarizing action, sources, and pages touched.[2]
5. If no wiki changes are needed for a PR, record that explicit determination in PR notes so the precondition is still auditable.[1]
6. Run `python scripts/check_knowledge_base_update.py --base-ref origin/main` before presenting a branch as PR-ready. The script flags changes to `src/`, `notebooks/`, `docs/`, `artifacts/`, and governance files unless `knowledge_base/log.md` is included or an explicit `--no-kb-needed` reason is supplied.[3]
7. Future agent plans should include a visible "knowledge-base update or explicit no-change note" item as soon as a task touches knowledge-relevant files. This makes the PR precondition part of the work loop rather than a final memory check.[1][3]

## Relevance to This Project

The roadmap's Phase 2.5+ rigor gates require transparent evidence trails. Keeping knowledge-base articles synchronized with implementation and planning docs prevents stale methodological claims from being reused in model design decisions.

This workflow directly supports consistency between `CLAUDE.md` guardrails and wiki governance defined in `knowledge_base/SCHEMA.md`.

Last verified: 2026-04-28

## Sources

[1] Development guardrails — `CLAUDE.md`
[2] Wiki governance — `knowledge_base/SCHEMA.md`
[3] Knowledge-base preflight — `scripts/check_knowledge_base_update.py`, `tests/test_knowledge_base_governance.py`

## Related Pages

- [Knowledge Gaps](knowledge-gaps.md)
- [Temporal Cross-Validation](../methods/temporal-cross-validation.md)

## Revision History

- 2026-04-28 — Updated. Added executable KB preflight and agent planning requirement after a missed KB update on the validation-scorecard branch.
- 2026-04-24 — Created. Added PR-precondition workflow for knowledge-base maintenance.
