---
id: VICTUS-PROCESSING-PIPELINE-PDF-PROCESSING
title: PDF Processing Pipeline
status: source-of-truth
updated_at: 2026-06-06
tags:
  - operations
  - pipeline
  - pdf-processing
---

# PDF Processing

Purpose: convert canonical PDF artifacts into Markdown and structured paper
JSON.

Commands:

```bash
uv run victus-processing pdf-processing markdown --limit 10
uv run victus-processing pdf-processing run --limit 5
uv run victus-processing pdf-processing run --pdf data/artifacts/pdfs/{paper_id}.pdf
```

Inputs:

- PDF artifacts under `data/artifacts/pdfs/`;
- PDF-processing prompts under `src/prompts/`;
- `config/pdf_processing.yaml`;
- LiteLLM provider credentials and routing configuration.

Outputs:

- `data/runtime/03-pdf_processing/{paper_id}/paper.md`;
- `data/runtime/03-pdf_processing/{paper_id}/raw_batches/`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.processed.json`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.final.json`;
- `data/runtime/03-pdf_processing/processing_status.jsonl`.

Validation:

```bash
uv run victus-processing pdf-processing --help
uv run victus-processing pdf-processing run --help
```
