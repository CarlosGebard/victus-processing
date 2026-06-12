---
id: VICTUS-PROCESSING-PIPELINE-EVIDENCE-EXTRACTION
title: Evidence Extraction Pipeline
status: source-of-truth
updated_at: 2026-06-06
tags:
  - operations
  - pipeline
  - evidence-extraction
---

# Evidence Extraction

Purpose: classify processed papers, trim evidence-relevant blocks, map
experiment scopes, build packets, and extract canonical evidence.

Commands:

```bash
uv run victus-processing evidence-extraction run
uv run victus-processing evidence-extraction run --input data/runtime/03-pdf_processing/{paper_id}/paper.processed.json
uv run victus-processing evidence-extraction run --skip-existing --limit 20
```

Inputs:

- `paper.processed.json` files from `pdf-processing run`;
- paper classifier, experiment mapper, and canonical evidence prompts;
- LiteLLM provider credentials and routing configuration.

Outputs:

- `data/runtime/04-evidence/{paper_id}/paper.classifier_input.json`;
- `data/runtime/04-evidence/{paper_id}/paper.classification.json`;
- `data/runtime/04-evidence/{paper_id}/evidence_skipped.json` for non-primary papers;
- `data/runtime/04-evidence/{paper_id}/trimmed.json`;
- `data/runtime/04-evidence/{paper_id}/experiment_map.json`;
- `data/runtime/04-evidence/{paper_id}/experiment_packets.json`;
- `data/runtime/04-evidence/{paper_id}/canonical_evidence.json`.

Validation:

```bash
uv run victus-processing evidence-extraction --help
uv run victus-processing evidence-extraction run --help
```
