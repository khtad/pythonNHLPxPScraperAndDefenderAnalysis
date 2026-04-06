# External Raw Sources

This directory holds immutable source documents from outside the project: research papers, blog posts, methodology writeups, API documentation, and other reference material.

## File Format

Name files as `YYYY-MM-DD_short-slug.md` where the date is when the source was **added** to the knowledge base (not its publication date).

Each file must begin with a metadata block:

```markdown
# [Original Title]

- **Author(s):** [Names or organization]
- **Published:** [Date or "undated"]
- **URL:** [Original URL, if applicable]
- **Added:** [YYYY-MM-DD]

---

[Full text, substantive excerpt, or detailed summary below]
```

## Rules

- **Immutable:** Once created, raw source files are never edited. If a correction is needed, add a new source file with a note referencing the original.
- **Copyright:** For copyrighted material, store only: metadata, a brief summary, and key excerpts with attribution. Do not copy full text of paywalled or rights-restricted content.
- **Openly licensed material:** Full text may be stored with appropriate attribution.
- **One source per file:** Do not combine multiple sources into a single file.
