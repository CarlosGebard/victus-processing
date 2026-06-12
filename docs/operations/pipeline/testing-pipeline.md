---
id: VICTUS-PROCESSING-PIPELINE-TESTING
title: Testing Pipeline
status: source-of-truth
updated_at: 2026-06-06
tags:
  - operations
  - pipeline
  - testing-pipeline
---

# Testing Pipeline

Purpose: run the PDF-processing and evidence chain in per-paper review folders
under `data/testing`.

Commands:

```bash
uv run victus-processing testing-pipeline run
uv run victus-processing testing-pipeline run --paper-id {paper_id}
uv run victus-processing testing-pipeline run --paper-id {paper_id} --reuse-markdown
```

Inputs:

- PDF artifacts or selected `--paper-id` values;
- optional reused Markdown from a configured markdown directory;
- PDF-processing and evidence prompts;
- LiteLLM provider credentials and routing configuration.

Outputs:

- `data/testing/{paper_id}/source.pdf`;
- `data/testing/{paper_id}/paper.md`;
- `data/testing/{paper_id}/markdown_batches/`;
- `data/testing/{paper_id}/raw_batches/`;
- `data/testing/{paper_id}/paper.processed.json`;
- `data/testing/{paper_id}/paper.final.json`;
- `data/testing/{paper_id}/paper.classifier_input.json`;
- `data/testing/{paper_id}/paper.classification.json`;
- `data/testing/{paper_id}/evidence_skipped.json` for non-primary papers;
- `data/testing/{paper_id}/trimmed.json`;
- `data/testing/{paper_id}/experiment_map.json`;
- `data/testing/{paper_id}/experiment_packets.json`;
- `data/testing/{paper_id}/canonical_evidence.json`.

Validation:

```bash
uv run victus-processing testing-pipeline --help
uv run victus-processing testing-pipeline run --help
```
