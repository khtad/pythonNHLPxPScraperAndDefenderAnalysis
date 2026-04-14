# Project Artifact References

This directory holds lightweight reference notes that document when and how project artifacts (source code, notebooks, design docs) were used as sources for wiki articles.

These files do **not** duplicate the artifact content — the artifact itself (in `src/`, `docs/`, `notebooks/`) remains the source of truth. Reference notes record what was extracted and when, creating an audit trail.

## File Format

Name files as `YYYY-MM-DD_short-slug.md` where the date is when the artifact was referenced for wiki compilation.

Each file must follow this structure:

```markdown
# [Descriptive Title]

- **Artifact:** [Repo-relative path, e.g., src/xg_features.py]
- **Referenced:** [YYYY-MM-DD]

## What Was Extracted

[Brief summary of the domain knowledge extracted from this artifact]

## Wiki Pages Derived

- [Page Title](../../wiki/category/filename.md)
- ...
```

## Rules

- **One reference note per extraction session.** If the same artifact is revisited later for new information, create a new reference note.
- **Do not copy code.** Describe what was learned, not the implementation details.
- **Keep it brief.** The reference note is an audit trail, not a summary of the artifact. A few sentences suffice.
