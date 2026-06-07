---
id: VICTUS-PROCESSING-TESTING-PIPELINE-CONTRACT
title: Victus Processing Testing Pipeline Contract
status: source-of-truth
updated_at: 2026-06-06
related_components:
  - src.cli
  - src.application.testing_pipeline.artifacts
  - src.application.pdf_processing.pipeline
  - src.application.evidence_extraction.evidence
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
  - VICTUS-PROCESSING-PAPER-CLASSIFICATION-CONTRACT
tags:
  - contracts
  - testing
  - pdf-processing
---

# Testing Pipeline Contract

## 1. Purpose

This contract defines the `testing-pipeline run` review workspace and the
artifact guarantees under `data/testing/{paper_id}/`.

## 2. Scope

Covered:

- per-paper testing output layout;
- source PDF copies;
- reused Markdown behavior;
- Markdown batch debug artifacts;
- PDF-processing and evidence artifacts produced in testing.

Not covered:

- production runtime deployment;
- cleanup policy for old testing artifacts;
- model-provider behavior.

## 3. Guarantees

- `testing-pipeline run` writes artifacts under `data/testing/{paper_id}/`.
- `source.pdf` is copied from the active PDF selected by `paper_id`.
- Without `--reuse-markdown`, testing may generate `paper.md` through Docling.
- With `--reuse-markdown`, testing copies an existing
  `{markdown_dir}/{paper_id}/paper.md` into the testing workspace and must not
  run Docling for that paper.
- Testing writes Markdown batch debug artifacts under `markdown_batches/`.
- Testing runs the same Markdown structuring, paper classification, and evidence
  routing contracts as the normal evidence stage.

## 4. Invariants

`paper_id` is the active PDF filename stem.

Required source PDF path:

```text
{pdf_dir}/{paper_id}.pdf
```

Required reused Markdown path when `--reuse-markdown` is enabled:

```text
{markdown_dir}/{paper_id}/paper.md
```

Testing output root:

```text
data/testing/{paper_id}/
```

Markdown batch debug artifacts use paired files:

```text
markdown_batches/batch_0001.md
markdown_batches/batch_0001.json
```

The `.md` file contains the exact Markdown chunk used for that batch. The
`.json` file contains batch index, character range, character count, section
context, tail context, and oversized-unit status.

## 5. Inputs and Outputs

Expected testing outputs:

```text
source.pdf
paper.md
markdown_batches/
raw_batches/
paper.processed.json
paper.final.json
paper.classifier_input.json
paper.classification.json
```

Primary-research papers additionally produce:

```text
trimmed.json
experiment_map.json
experiment_packets.json
canonical_evidence.json
```

Non-primary papers produce:

```text
evidence_skipped.json
```

## 6. Failure Expectations

- Missing selected source PDFs must fail explicitly.
- Missing reused Markdown must fail explicitly.
- Existing `source.pdf` and `paper.md` are preserved unless their overwrite
  flags are set.
- Non-primary classification is represented by `evidence_skipped.json`, not by a
  failed testing run.

## 7. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Data Layout](data-layout.md)
- [Paper Classification](paper-classification.md)
- [Testing Workspace ADR](../adr/001-testing-workspace-per-paper.md)
- [PDF Processing Operations](../operations/pdf-processing.md)
