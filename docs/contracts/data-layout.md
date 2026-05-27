---
id: VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
title: Victus Processing Data Layout Contract
status: draft
updated_at: 2026-05-26
owners:
  - architecture
related_components:
  - src.workspace.config
  - src.workspace.data_layout
  - src.metadata
  - src.pdf_extraction
  - src.pdf_processing
  - src.claims
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
- status and quota persistence locations;
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
- Pre-PDF candidate state lives under `data/runtime/01-candidates/`.
- Active PDFs live under `data/runtime/02-pdfs/active/` by default.
- PDF-processing artifacts live under `data/runtime/03-pdf_processing/`.
- Claim outputs live under `data/runtime/04-claims_by_model/`.
- Gemini quota state lives under `data/runtime/quotas/`.

## 4. Invariants

- `document_id` identifies pre-PDF metadata candidates.
- `paper_id` identifies post-PDF processing artifacts.
- Active candidate metadata files use `*.metadata.json`.
- The reviewed candidate index is `data/runtime/01-candidates/reviewed.jsonl`.
- Discarded candidate state is kept under
  `data/runtime/01-candidates/discarded/`.
- Active PDFs must be readable PDF files before `pdf-processing` consumes them.
- PDF-processing writes per-paper artifacts under
  `data/runtime/03-pdf_processing/{paper_id}/`.
- The merged structured paper output is `paper.processed.json`.
- Raw Gemini batch outputs are retained under `raw_batches/`.
- Stage status files are operational state, not disposable debug logs.
- Claim outputs are grouped by model.

## 5. Inputs and Outputs

### Metadata Stage

- **Input:** DOI seed files or DOI arguments.
- **Output:** candidate metadata JSON, reviewed index, discarded index.

### PDF Normalization

- **Input:** raw PDFs and DOI/PDF relation data.
- **Output:** active PDFs under `data/runtime/02-pdfs/active/`.

### PDF Processing

- **Input:** active PDFs.
- **Output:** `paper.md`, `raw_batches/`, `paper.processed.json`, status JSONL.

### Claims

- **Input:** structured paper JSON.
- **Output:** `{paper}.claims.json` under model-specific output directories.

## 6. Failure Expectations

- Stages should preserve existing final artifacts unless explicit force or
  overwrite behavior is requested.
- Restarted stages should skip completed outputs when supported.
- Validation failures should prevent invalid outputs from being treated as
  successful stage results.
- Partial failures should be visible through status artifacts or CLI output.
- Quota/cooldown state must persist outside process memory.

## 7. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Architecture](../100-ARCHITECTURE.md)
- [System Context](../000-SYSTEM-CONTEXT.md)
