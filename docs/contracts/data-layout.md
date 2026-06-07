---
id: VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
title: Victus Processing Data Layout Contract
status: source-of-truth
updated_at: 2026-06-06
related_components:
  - src.workspace.config
  - src.workspace.data_layout
  - src.application.metadata_extraction
  - src.application.metadata_to_pdf
  - src.application.pdf_processing
  - src.application.evidence_extraction
  - src.application.ports.llm
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-ARCHITECTURE
  - VICTUS-PROCESSING-TESTING-PIPELINE-CONTRACT
tags:
  - contracts
  - data-layout
  - artifacts
---

# Data Layout Contract

## 1. Purpose

This contract governs local artifact locations, identity terms, and stage
handoffs under `data/`.

## 2. Scope

Covered:

- local runtime directories;
- stage input and output locations;
- pre-PDF and post-PDF identities;
- status persistence locations;
- compatibility expectations between stages.

Not covered:

- external API payloads;
- production deployment storage;
- downstream analytics schemas;
- vendor-side availability or billing.

## 3. Guarantees

- Runtime artifacts live under `data/` by default.
- Relative configured paths resolve from the repository root.
- `config/*.yaml` provides domain defaults.
- Optional root `config.yaml` may override domain defaults.
- `src.workspace.config.ROOT_DIR` is the repository root.
- `src.workspace.config.get_data_layout_dirs()` defines the directory set
  created by `victus-processing data-layout create`.
- Pre-PDF candidate state lives under `data/runtime/01-candidates/`.
- Active PDFs live under `data/runtime/02-pdfs/active/` by default.
- PDF-processing artifacts live under `data/runtime/03-pdf_processing/`.
- Evidence outputs live under `data/runtime/04-evidence/`.
- Testing review artifacts live under `data/testing/`.
- Registry artifacts live under `data/registry/`.
- Report and audit artifacts live under `data/reports/`.
- `data/` is runtime state and must not be treated as disposable source code.

## 3.1 Canonical Directory Structure

```text
data/
  inputs/
    generated_seed_dois/
    imports/
    rules/
    seeds/
  registry/
  runtime/
    01-candidates/
      active/
      discarded/
    02-pdfs/
      active/
    03-pdf_processing/
      {paper_id}/
        paper.md
        raw_batches/
        paper.processed.json
        paper.final.json
      processing_status.jsonl
      markdown_status.jsonl
    04-evidence/
      {paper_id}/
        trimmed.json
        experiment_map.json
        canonical_evidence.json
    tmp/
    logs/
    queues/
  reports/
    audits/
    exports/
  testing/
    {paper_id}/
      source.pdf
      paper.md
      markdown_batches/
      raw_batches/
      paper.processed.json
      paper.final.json
      paper.classifier_input.json
      paper.classification.json
      evidence_skipped.json
      trimmed.json
      experiment_map.json
      experiment_packets.json
      canonical_evidence.json
  archive/
    legacy/
    experiments/
```

Compatibility paths may still exist in workspace helpers, including
`data/candidates/`, `data/papers/`, `data/runtime/docling/`, and
`data/runtime/pdf_retrieval/`. New stage contracts must prefer the runtime
layout above unless an explicit compatibility task requires the legacy path.

## 4. Invariants

- `document_id` identifies pre-PDF metadata candidates.
- `paper_id` identifies post-PDF processing artifacts.
- For active PDFs, `paper_id` is the PDF filename stem.
- Active candidate metadata files use `*.metadata.json`.
- The reviewed candidate index is `data/runtime/01-candidates/reviewed.jsonl`.
- Discarded candidate state is kept under
  `data/runtime/01-candidates/discarded/`.
- Active PDFs must be readable PDF files before `pdf-processing` consumes them.
- PDF-processing writes per-paper artifacts under
  `data/runtime/03-pdf_processing/{paper_id}/`.
- PDF-processing must not write one paper's artifacts into another paper's
  directory.
- The merged structured paper output is `paper.processed.json`; the current
  compatibility trimmed artifact is `paper.final.json`.
- `paper.json` is a legacy PDF-processing final output name. When encountered,
  the current pipeline renames it to `paper.processed.json` if the canonical
  output is absent.
- Raw LLM batch outputs are retained under `raw_batches/`.
- Stage status files are operational state, not disposable debug logs.
- Evidence outputs are grouped by `paper_id`.
- The registry file for document artifacts is `data/registry/documents.jsonl`.
- DOI slugs are lowercase and replace characters outside `[a-z0-9._-]` with
  `-`.

## 5. Inputs and Outputs

### Metadata Stage

- **Input:** DOI seed files under `data/inputs/seeds/` or DOI arguments.
- **Output:** candidate metadata JSON under
  `data/runtime/01-candidates/active/`, reviewed index, discarded index.
- **Identity:** `document_id`, DOI, and DOI-derived base names.

### Bibliography

- **Input:** active metadata JSON or an explicit CSV.
- **Output:** BibTeX, defaulting to `data/runtime/01-candidates/active/papers.bib`.

### PDF Normalization

- **Input:** raw PDFs and DOI/PDF relation data.
- **Output:** active PDFs under `data/runtime/02-pdfs/active/`.
- **Identity:** destination file stem becomes the downstream `paper_id`.

### PDF Processing

- **Input:** active PDFs.
- **Output:** `paper.md`, `raw_batches/`, `paper.processed.json`,
  `paper.final.json`, `processing_status.jsonl`, and optional
  `markdown_status.jsonl`.
- **Identity:** `paper_id` equals the input PDF stem.

### Evidence

- **Input:** structured paper metadata and blocks.
- **Output:** `trimmed.json`, `experiment_map.json`, and
  `canonical_evidence.json` under `data/runtime/04-evidence/{paper_id}/`.
- **Identity:** `paper_id` follows the post-PDF artifact identity; evidence
  records remain traceable through block identifiers.

### Testing Review Artifacts

- **Input:** active PDFs.
- **Output:** `source.pdf`, `paper.md`, Markdown batch debug artifacts,
  PDF-processing artifacts, and evidence artifacts under
  `data/testing/{paper_id}/`.
- **Identity:** `paper_id` equals the active PDF filename stem.

## 6. Failure Expectations

- Stages should preserve existing final artifacts unless explicit force or
  overwrite behavior is requested.
- Restarted stages should skip completed outputs when supported.
- Validation failures should prevent invalid outputs from being treated as
  successful stage results.
- Partial failures should be visible through status artifacts or CLI output.
- Provider quota, retry, and fallback behavior is handled by LiteLLM.
- `processing_status.jsonl` rows with `status: failed` must include an error
  code when the pipeline can classify the failure.
- Invalid or missing model output JSON must fail the stage rather than producing
  a successful final artifact.

## 7. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Configuration and CLI](configuration-and-cli.md)
- [Stage Handoffs](stage-handoffs.md)
- [Artifact Schemas](artifact-schemas.md)
- [Architecture](../100-ARCHITECTURE.md)
- [System Context](../000-SYSTEM-CONTEXT.md)
