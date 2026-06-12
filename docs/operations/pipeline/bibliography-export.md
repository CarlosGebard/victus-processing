---
id: VICTUS-PROCESSING-PIPELINE-BIBLIOGRAPHY-EXPORT
title: Bibliography Export Pipeline
status: source-of-truth
updated_at: 2026-06-11
tags:
  - operations
  - pipeline
  - bibliography
---

# Bibliography Export

Purpose: export accepted metadata records into a DOI-only BibTeX file for
external tools such as Zotero.

Command:

```bash
uv run victus-processing bibliography-export generate-bib
```

Input:

- `data/lake/paper_metadata.jsonl` records with `domain_screening.decision=keep`.

Output:

- `data/lake/paper_metadata.bib`.

This command is a utility export. It is not a full pipeline stage and must not
claim PDF retrieval, PDF matching, or PDF artifact ownership.

Validation:

```bash
uv run victus-processing bibliography-export generate-bib --help
```
