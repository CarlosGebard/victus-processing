---
id: VICTUS-PROCESSING-PIPELINE-EVIDENCE-EXTRACTION
title: Evidence Extraction Pipeline
status: source-of-truth
updated_at: 2026-06-13
tags:
  - operations
  - pipeline
  - evidence-extraction
---

# Evidence Extraction

Purpose: classify structured papers, map experiment scopes, build packets, and
extract canonical evidence from PostgreSQL-backed scientific outputs.

Commands:

```bash
uv run victus-processing evidence-extraction run
uv run victus-processing evidence-extraction run --skip-existing --limit 20
```

Inputs:

- StructuredBlock rows produced by PDF processing;
- paper classifier, experiment mapper, and canonical evidence prompts;
- LiteLLM provider credentials and routing configuration.

Outputs:

- `paper_classifications` PostgreSQL rows;
- `experiment_maps` PostgreSQL rows for primary-research papers;
- `canonical_evidence` PostgreSQL rows after extraction;
- `paper_processing_state` refresh shows the next missing stage.

Validation:

```bash
uv run victus-processing evidence-extraction --help
uv run victus-processing evidence-extraction run --help
```
