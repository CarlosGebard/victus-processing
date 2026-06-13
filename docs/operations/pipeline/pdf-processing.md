---
id: VICTUS-PROCESSING-PIPELINE-PDF-PROCESSING
title: PDF Processing Pipeline
status: source-of-truth
updated_at: 2026-06-13
tags:
  - operations
  - pipeline
  - pdf-processing
---

# PDF Processing

Purpose: convert canonical PDF or Markdown artifacts into StructuredBlock rows.

Commands:

```bash
uv run victus-processing pdf-processing markdown --limit 10
uv run victus-processing pdf-processing run --limit 5
uv run victus-processing pdf-processing run --pdf data/artifacts/pdfs/{paper_id}.pdf
uv run victus-processing pdf-processing json-from-markdown --input-dir data/artifacts/markdown --shuffle --limit 5
```

Inputs:

- PDF artifacts under `data/artifacts/pdfs/`;
- Markdown artifacts under `data/artifacts/markdown/`;
- PDF-processing prompts under `src/prompts/`;
- `config/pdf_processing.yaml`;
- LiteLLM provider credentials and routing configuration.

Outputs:

- `structured_blocks` PostgreSQL rows;
- `paper_processing_state.last_successful_stage = pdf.process` after refresh;
- `paper_processing_state.next_stage = classification.classify` after refresh.

Validation:

```bash
uv run victus-processing pdf-processing --help
uv run victus-processing pdf-processing run --help
uv run victus-processing processing-state refresh
```
