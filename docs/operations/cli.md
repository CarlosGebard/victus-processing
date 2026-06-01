---
id: VICTUS-PROCESSING-CLI-OPERATIONS
title: Victus Processing CLI Operations
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
tags:
  - operations
  - cli
---

# CLI Operations

`victus-processing` is the local command surface for paper-processing work.

Use built-in help as the source of truth:

```bash
uv run victus-processing --help
```

Command groups:

- `metadata`: discover, fetch, and seed paper metadata;
- `bib`: generate bibliography artifacts;
- `pdfs`: normalize raw PDFs into active inputs;
- `pdf-processing`: convert PDFs and produce structured paper artifacts;
- `claims`: extract claim outputs from structured paper JSON;
- `bridge`: optional Victus infrastructure integration;
- `data-layout`: create or inspect local runtime directories.

Common flow:

```bash
uv run victus-processing data-layout create
uv run victus-processing metadata explore --mode broad-nutrition
uv run victus-processing pdfs normalize
uv run victus-processing pdf-processing run
uv run victus-processing claims extract --pattern "*/paper.final.json" --skip-existing
```

Compatibility note: `claims extract` defaults to `*/*.final.json`.

Related: [Operations](../200-OPERATIONS.md).
