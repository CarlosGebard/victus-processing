---
id: VICTUS-PROCESSING-PDF-PROCESSING-OPERATIONS
title: Victus Processing PDF Processing Operations
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
tags:
  - operations
  - pdf-processing
  - gemini
---

# PDF Processing Operations

PDF processing converts active PDFs into Markdown and structured paper JSON.

Runtime sequence:

```text
PDF -> Docling Markdown -> Markdown batches -> Gemini JSON -> merged JSON
```

Run all active PDFs:

```bash
uv run victus-processing pdf-processing run
```

Run one PDF:

```bash
uv run victus-processing pdf-processing run --pdf path/to/paper.pdf
```

Limit work:

```bash
uv run victus-processing pdf-processing run --limit 10
uv run victus-processing pdf-processing run --pdf path/to/paper.pdf --max-batches 3
```

Run Markdown-only conversion:

```bash
uv run victus-processing pdf-processing markdown --skip-existing
```

Operational inputs:

- active PDFs under `data/runtime/02-pdfs/active/`;
- prompts under `src/prompts/`;
- runtime defaults in `config/pdf_processing.yaml`;
- Gemini credentials from `GEMINI_KEY*`.

Operational outputs:

- `data/runtime/03-pdf_processing/{paper_id}/paper.md`;
- `data/runtime/03-pdf_processing/{paper_id}/raw_batches/`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.processed.json`;
- `data/runtime/03-pdf_processing/processing_status.jsonl`;
- `data/runtime/quotas/gemini.sqlite3`.

Claims handoff:

- current PDF-processing writes `paper.processed.json`;
- `claims extract` defaults to `*/*.final.json` for compatibility;
- use `--pattern "*/paper.processed.json"` when extracting claims from current
  PDF-processing outputs.

Quota behavior:

- request limits are configured in `config/pdf_processing.yaml`;
- 429, 5xx, and network failures place keys in cooldown;
- quota/cooldown state survives process restarts through SQLite.

Related: [Operations](../200-OPERATIONS.md),
[Data Layout Contract](../contracts/data-layout.md).
