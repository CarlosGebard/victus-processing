---
id: VICTUS-PROCESSING-PIPELINE-PDF-INTAKE
title: PDF Intake Pipeline
status: source-of-truth
updated_at: 2026-06-17
tags:
  - operations
  - pipeline
  - pdf-intake
---

# PDF Intake

Purpose: link obtained PDFs to canonical metadata and promote them to stable
paper artifacts.

## Manual Intake

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

## Open-Access Acquisition

Auxiliary modules under `src/application/metadata_to_pdf/` can build a
missing-PDF queue from metadata and query Unpaywall for open-access
availability. These modules are separate from the main `victus-processing` CLI.

Build a JSONL queue of kept metadata records that do not have a matching PDF
link yet:

```bash
uv run python -m src.application.metadata_to_pdf.build_missing_pdf_candidates --limit 500
```

Default output:

```text
data/lake/papers_missing_pdfs.jsonl
```

Query Unpaywall, record whether each paper is open-access, download available
PDFs, and promote valid PDFs to canonical artifacts:

```bash
export UNPAYWALL_EMAIL="operator@example.com"
uv run python -m src.application.metadata_to_pdf.fetch_unpaywall_pdfs --limit 50
```

Default outputs:

- `data/lake/unpaywall_pdf_status.jsonl`;
- `data/artifacts/intake/unpaywall-pdfs/{paper_id}.pdf`;
- `data/artifacts/pdfs/{paper_id}.pdf`;
- append-only link records in `data/lake/paper_pdf_links.jsonl`.

`unpaywall_pdf_status.jsonl` records `is_oa`, `oa_status`, selected `pdf_url`,
download result, promoted artifact path, and any per-paper error. A paper may be
open-access without a direct PDF URL; in that case the status record is written
but no PDF is promoted.

Use staging-only mode when auditing availability before writing canonical PDF
artifacts:

```bash
uv run python -m src.application.metadata_to_pdf.fetch_unpaywall_pdfs --limit 50 --staging-only
```

The fetch script only promotes payloads whose bytes begin with the PDF signature.
Failures are recorded per paper and do not stop the batch.

Reruns are resumable by default. Before querying Unpaywall, the fetch script
reads `data/lake/unpaywall_pdf_status.jsonl` and skips candidates whose
`metadata_id` and `paper_id` already have a status record. To intentionally
query previously checked papers again, use:

```bash
uv run python -m src.application.metadata_to_pdf.fetch_unpaywall_pdfs --limit 50 --retry-checked
```

To progressively fill missing `pdf_url` values in
`data/lake/unpaywall_pdf_status.jsonl`, recheck only candidates that do not
already have a status record with `pdf_url`:

```bash
uv run python -m src.application.metadata_to_pdf.fetch_unpaywall_pdfs --limit 50 --retry-missing-pdf-url
```

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
uv run python -m src.application.metadata_to_pdf.build_missing_pdf_candidates --help
uv run python -m src.application.metadata_to_pdf.fetch_unpaywall_pdfs --help
```
