---
id: VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
title: Victus Processing Data Layout Contract
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
related_components:
  - src.workspace.config
  - src.workspace.data_layout
  - src.application.metadata
  - src.application.pdf_extraction
  - src.application.pdf_processing
  - src.application.claims
  - src.application.ports.llm
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-ARCHITECTURE
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
- Claim outputs live under `data/runtime/04-claims_by_model/`.
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
    04-claims_by_model/
      {model_slug}/
        {paper_id}.claims.json
    tmp/
    logs/
    queues/
  reports/
    audits/
    exports/
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
- The merged structured paper output is `paper.processed.json`; the trimmed
  handoff artifact is `paper.final.json`.
- `paper.json` is a legacy PDF-processing final output name. When encountered,
  the current pipeline renames it to `paper.processed.json` if the canonical
  output is absent.
- Raw LLM batch outputs are retained under `raw_batches/`.
- Stage status files are operational state, not disposable debug logs.
- Claim outputs are grouped by model.
- Claim output model directory names use lowercase model slugs with `/` and
  spaces replaced by `_`.
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

### Claims

- **Input:** structured paper JSON accepted by the claims parser.
- **Output:** `{paper}.claims.json` under model-specific output directories.
- **Identity:** output stem is derived from the input JSON filename.

## 6. Failure Expectations

- Stages should preserve existing final artifacts unless explicit force or
  overwrite behavior is requested.
- Restarted stages should skip completed outputs when supported.
- Validation failures should prevent invalid outputs from being treated as
  successful stage results.
- Partial failures should be visible through status artifacts or CLI output.
- Provider quota, retry, and fallback behavior is owned by LiteLLM.
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
