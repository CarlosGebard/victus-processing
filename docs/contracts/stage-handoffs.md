---
id: VICTUS-PROCESSING-STAGE-HANDOFFS-CONTRACT
title: Victus Processing Stage Handoffs Contract
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
related_components:
  - src.metadata
  - src.pdf_extraction
  - src.pdf_processing
  - src.claims
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - contracts
  - stages
  - handoffs
---

# Stage Handoffs Contract

## 1. Purpose

This contract defines the stable boundaries between processing stages. Agents
must preserve these handoffs before changing stage internals.

## 2. Scope

Covered stages:

- metadata;
- bibliography;
- PDF normalization;
- PDF-processing Markdown and Gemini extraction;
- claims extraction.

Not covered:

- external retrieval service guarantees;
- downstream analytics or indexing;
- production deployment orchestration.

## 3. Guarantees

- Stages communicate through durable local files, not hidden process memory.
- Each stage may be run independently through the CLI.
- A stage may skip completed artifacts when a final output already exists.
- Stage handoff paths are repository-relative unless explicitly configured
  otherwise.
- Model-mediated stages retain enough local output for inspection after a run.

## 4. Handoff Map

```text
data/inputs/seeds/*.jsonl or --doi
  -> metadata JSON under data/runtime/01-candidates/active/
  -> optional BibTeX and relation/audit reports
  -> active PDFs under data/runtime/02-pdfs/active/
  -> data/runtime/03-pdf_processing/{paper_id}/paper.md
  -> data/runtime/03-pdf_processing/{paper_id}/raw_batches/*.json
  -> data/runtime/03-pdf_processing/{paper_id}/paper.processed.json
  -> data/runtime/04-claims_by_model/{model_slug}/{paper_id}.claims.json
```

## 5. Stage Contracts

### Metadata

- Inputs are DOI seed queues or a single DOI argument.
- Outputs are metadata records and reviewed/discarded candidate state.
- The stage owns pre-PDF candidate state only.
- `document_id` must not be treated as the post-PDF `paper_id` unless a
  specific compatibility path explicitly maps it.

### Bibliography

- Inputs are metadata JSON files or an explicit CSV.
- Output is a BibTeX file.
- The command is a derived export and must not mutate candidate state.

### PDF Normalization

- Inputs are raw PDFs plus DOI/PDF relation data.
- Outputs are normalized active PDFs.
- PDFs without resolved DOI relation belong in the configured unmatched
  location.
- Downstream `paper_id` is derived from active PDF filename stem.

### PDF Processing

- Inputs are active PDFs, Markdown prompts, Gemini credentials, and
  `pdf_processing` config.
- Outputs are `paper.md`, raw Gemini batch JSON, `paper.processed.json`, and
  status JSONL.
- `paper.md` is generated with Docling and may be reused unless forced.
- Raw batch files must be written before final merge so partial model output can
  be inspected.
- Final success requires a merged structured JSON file and a done status.

### Claims

- Inputs are structured paper JSON files accepted by the claims parser.
- Outputs are claims grouped by model slug.
- Claims validation must happen before writing a successful output file.
- `--skip-existing` preserves existing claims outputs.

## 6. Failure Expectations

- A failed stage must not be represented as a successful final artifact.
- PDF-processing classified errors include `docling_failed`,
  `batching_failed`, `llm_failed`, or `processing_failed`.
- Directory-level PDF-processing continues other pending PDFs when one PDF
  fails.
- Quota/cooldown state for Gemini survives process restarts.
- Claims extraction records per-file failures in CLI output and continues
  through the remaining input files.

## 7. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Data Layout](data-layout.md)
- [Artifact Schemas](artifact-schemas.md)
- [PDF processing operations](../operations/pdf-processing.md)
