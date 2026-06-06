---
id: ADR-001-TESTING-WORKSPACE-PER-PAPER
title: Per-Paper Testing Workspace
status: accepted
updated_at: 2026-06-06
owners:
  - architecture
related_docs:
  - VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
  - VICTUS-PROCESSING-STAGE-HANDOFFS-CONTRACT
  - VICTUS-PROCESSING-PDF-PROCESSING-OPERATIONS
tags:
  - adr
  - testing
  - pdf-processing
---

# Per-Paper Testing Workspace

## 1. Context

Reviewing PDF-processing failures was slow because source PDFs, Markdown,
Markdown batch cuts, raw model batch outputs, structured JSON, classifier
artifacts, and evidence artifacts were spread across stage directories.

Operators also often already have Docling Markdown generated, so rerunning
Docling during testing wastes time and makes iteration slower.

## 2. Decision

`pdf-processing testing` writes a complete per-paper review workspace under
`data/testing/{paper_id}/`.

The testing workspace contains the source PDF copy, `paper.md`, Markdown batch
debug files, PDF-processing outputs, paper-classification artifacts, and
evidence artifacts or a skip artifact.

The command supports `--reuse-markdown`, which copies an existing
`{paper_id}/paper.md` from the configured Markdown source directory and starts
testing from Markdown structuring instead of rerunning Docling.

## 3. Tradeoffs

Positive:

- Keeps all inspection artifacts for one paper in one directory.
- Avoids repeated Docling work when Markdown already exists.
- Preserves the production runtime layout while adding a review-focused
  workspace.

Negative:

- Duplicates PDFs and Markdown under `data/testing/`.
- Testing behavior has one extra branch: PDF-to-Markdown or reused Markdown.
- Operators must keep `paper_id` consistent between active PDFs and existing
  Markdown directories.

## 4. Alternatives Considered

- Merge `data/runtime/02-pdfs` and `data/runtime/03-pdf_processing`.
  Rejected because it mixes source inputs with derived artifacts and weakens
  stage ownership.
- Copy artifacts after a normal runtime run.
  Rejected because post-hoc copying can drift from the actual testing outputs.
- Always rerun Docling during testing.
  Rejected because generated Markdown is often already available and Docling is
  an expensive repeated step.

## 5. Consequences

Future testing features should write review artifacts inside
`data/testing/{paper_id}/` rather than adding scattered audit folders.

The runtime layout remains the source-of-truth stage layout. The testing layout
is an operator review workspace, not a replacement for runtime stage
boundaries.

## 6. Related Documents

- [Data Layout](../contracts/data-layout.md)
- [Stage Handoffs](../contracts/stage-handoffs.md)
- [PDF Processing Operations](../operations/pdf-processing.md)
