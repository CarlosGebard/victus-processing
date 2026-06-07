---
id: VICTUS-PROCESSING-PIPELINE-METADATA-TO-PDF
title: Metadata To PDF Pipeline
status: source-of-truth
updated_at: 2026-06-06
tags:
  - operations
  - pipeline
  - metadata-to-pdf
---

# Metadata To PDF

Purpose: turn canonical metadata and raw PDF relation data into bibliography
artifacts and normalized active PDFs.

Commands:

```bash
uv run victus-processing metadata-to-pdf generate-bib
uv run victus-processing metadata-to-pdf normalize-pdfs
```

Inputs:

- candidate metadata JSON or explicit CSV input;
- `doi_pdf_relations*.csv`;
- raw PDF files.

Outputs:

- BibTeX file, defaulting to `data/runtime/01-candidates/active/papers.bib`;
- active PDFs under `data/runtime/02-pdfs/active/`;
- unmatched PDFs under the configured unmatched directory.

Validation:

```bash
uv run victus-processing metadata-to-pdf --help
uv run victus-processing metadata-to-pdf normalize-pdfs --help
```
