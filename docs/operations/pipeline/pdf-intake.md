---
id: VICTUS-PROCESSING-PIPELINE-PDF-INTAKE
title: PDF Intake Pipeline
status: source-of-truth
updated_at: 2026-06-11
tags:
  - operations
  - pipeline
  - pdf-intake
---

# PDF Intake

Purpose: link manually obtained PDFs to canonical metadata and promote them to
stable paper artifacts.

## Operational Model

PDF retrieval is intentionally outside this repository. Operators may use
Zotero or another manual workflow, then place downloaded PDFs under:

```text
data/artifacts/intake/pdfs/
```

Link one PDF:

```bash
uv run victus-processing pdf-intake link \
  --metadata-id meta:s2:example \
  --pdf data/artifacts/intake/pdfs/example.pdf
```

The command moves the source PDF by default.

Outputs:

- `data/artifacts/pdfs/{paper_id}.pdf`;
- append-only link record in `data/lake/paper_pdf_links.jsonl`.

For new manual intake, `paper_id` is generated from `metadata_id` and the source
and artifact paths are different:

```text
source_pdf_path: data/artifacts/intake/pdfs/example.pdf
artifact_pdf_path: data/artifacts/pdfs/{paper_id}.pdf
```

Use `--copy` when the intake source should be preserved.

## Existing Artifacts

Backfill link records for already-normalized PDFs:

```bash
uv run victus-processing pdf-intake backfill-links --overwrite
```

Backfill reads:

- existing PDFs from `data/artifacts/pdfs/`;
- legacy DOI links from `data/lake/links.jsonl`;
- metadata records from `data/lake/paper_metadata.jsonl`.

For backfilled records, `paper_id` is the existing artifact filename stem. This
preserves compatibility with already-created PDFs and downstream outputs.

For backfilled records, `source_pdf_path` and `artifact_pdf_path` may be equal
because the original intake source is no longer observable. In that case the
artifact itself is the only durable source path.

Backfill skips PDFs when it cannot resolve:

```text
artifact filename stem -> legacy DOI -> metadata_id
```

Validation:

```bash
uv run victus-processing pdf-intake link --help
uv run victus-processing pdf-intake backfill-links --help
```
