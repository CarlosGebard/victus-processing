---
id: VICTUS-PROCESSING-PIPELINE-METADATA-EXTRACTION
title: Metadata Extraction Pipeline
status: source-of-truth
updated_at: 2026-06-06
tags:
  - operations
  - pipeline
  - metadata-extraction
---

# Metadata Extraction

Purpose: discover paper candidates, fetch canonical metadata, and prepare DOI
seed queues.

Commands:

```bash
uv run victus-processing metadata-extraction explore --mode broad-nutrition
uv run victus-processing metadata-extraction from-doi --doi 10.1000/demo
uv run victus-processing metadata-extraction seed-dois --mode broad-nutrition --limit 200
```

Inputs:

- exploration configuration;
- seed DOI queues;
- Semantic Scholar access, with stricter public limits when no API key is set.

Outputs:

- candidate metadata JSON under `data/runtime/01-candidates/active/`;
- reviewed and discarded candidate indexes;
- DOI seed queues for configured profiles.

Validation:

```bash
uv run victus-processing metadata-extraction --help
uv run victus-processing metadata-extraction explore --help
```
