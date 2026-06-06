---
id: VICTUS-PROCESSING-CLI-OPERATIONS
title: Victus Processing CLI Operations
status: source-of-truth
updated_at: 2026-06-05
owners:
  - architecture
tags:
  - operations
  - cli
---

# CLI Operations

`victus-processing` is the local command surface for paper-processing work.

Run commands through `uv` from the repository root:

```bash
uv run victus-processing --help
```

Use built-in help as the runtime source of truth for exact flags:

```bash
uv run victus-processing <group> --help
uv run victus-processing <group> <command> --help
```

## Command Groups

- `metadata`: discovers candidates, fetches metadata by DOI, and prepares DOI
  seed queues.
- `bib`: generates bibliography artifacts.
- `pdfs`: normalizes raw PDFs into active runtime inputs.
- `pdf-processing`: converts PDFs to Markdown, extracts structured paper JSON,
  and generates evidence artifacts.
- `bridge`: optional Victus infrastructure integration. This group may be
  unavailable in local checkouts that do not include `ops/scripts/bridge`.
- `data-layout`: creates or inspects local runtime directories.

## Common Flow

Create the expected local `data/` layout:

```bash
uv run victus-processing data-layout create
```

Run the common local paper-processing flow:

```bash
uv run victus-processing metadata explore --mode broad-nutrition
uv run victus-processing pdfs normalize
uv run victus-processing pdf-processing run
uv run victus-processing pdf-processing evidence
```

Use `--limit` on batch commands while testing or debugging:

```bash
uv run victus-processing pdf-processing markdown --limit 1
uv run victus-processing pdf-processing testing --limit 1
uv run victus-processing pdf-processing run --limit 1
uv run victus-processing pdf-processing evidence --limit 1
```

## `metadata`

### `metadata explore`

Explores candidates from the configured seed DOI queue and writes canonical
metadata under the configured metadata directory.

```bash
uv run victus-processing metadata explore --mode broad-nutrition
uv run victus-processing metadata explore --mode dataset-gaps
```

Flags:

- `--mode`: exploration profile. Supported values are `broad-nutrition` and
  `dataset-gaps`. The default comes from `exploration.mode` in configuration.

Operational notes:

- Requires configured prompt and LLM access.
- Reads the seed DOI queue configured for the selected exploration profile.

### `metadata from-doi`

Creates one canonical metadata JSON from a DOI.

```bash
uv run victus-processing metadata from-doi --doi 10.1000/demo
uv run victus-processing metadata from-doi --doi 10.1000/demo --overwrite
```

Flags:

- `--doi`: DOI to fetch. Required.
- `--output-dir`: metadata output directory. Defaults to the configured metadata
  directory.
- `--overwrite`: replaces an existing metadata file for the DOI.

### `metadata seed-dois`

Generates DOI seed queues from existing local data.

```bash
uv run victus-processing metadata seed-dois --mode broad-nutrition --limit 200
uv run victus-processing metadata seed-dois --mode dataset-gaps --min-citations 25
```

Flags:

- `--mode`: seed profile. Supported values are `broad-nutrition` and
  `dataset-gaps`.
- `--min-citations`: minimum citation count required for exported DOI rows.
- `--limit`: maximum number of DOI rows to write.

Operational notes:

- `broad-nutrition` uses local metadata and the configured keyword dictionary.
- `dataset-gaps` uses pre-ingestion CSV data, local metadata, and configured gap
  topics.

## `bib`

### `bib generate`

Generates a BibTeX file from canonical metadata or an explicit CSV source.

```bash
uv run victus-processing bib generate
uv run victus-processing bib generate --input-csv data/reports/exports/missing_pdf_items.csv
uv run victus-processing bib generate --output data/reports/papers.bib
```

Flags:

- `--output`: optional `.bib` output path.
- `--input-csv`: optional CSV source.

## `pdfs`

### `pdfs normalize`

Copies raw PDFs into the active normalized PDF directory using
`doi_pdf_relations*.csv`.

```bash
uv run victus-processing pdfs normalize
uv run victus-processing pdfs normalize --relations-csv data/reports/doi_pdf_relations.csv
```

Flags:

- `--raw-dir`: source directory for raw PDFs.
- `--input-dir`: destination directory for normalized active PDFs.
- `--unmatched-dir`: destination for PDFs without resolved DOI.
- `--relations-csv`: explicit DOI/PDF relation CSV. If omitted, the CLI uses
  the latest discovered relation file under report or metadata locations.

## `pdf-processing`

### `pdf-processing markdown`

Converts active PDFs to `paper.md` with Docling only. This command does not run
LLM batching or evidence extraction.

```bash
uv run victus-processing pdf-processing markdown --limit 10
uv run victus-processing pdf-processing markdown --skip-existing
uv run victus-processing pdf-processing markdown --force --max-pages 150
```

Flags:

- `--input-dir`: input PDF directory.
- `--output-dir`: Markdown/runtime output directory.
- `--limit`: maximum PDFs to convert.
- `--skip-existing`: marks existing `paper.md` outputs as done and does not
  regenerate them.
- `--force`: regenerates even when status already says `done`.
- `--max-pages`: fails and skips PDFs above this page count. Default is `100`.
- `--status-file`: explicit JSONL status file. Defaults to
  `<output-dir>/markdown_status.jsonl`.

### `pdf-processing run`

Runs the full PDF-processing stage: Docling Markdown generation when needed,
Markdown batching, LLM processing, and final structured paper artifacts.

```bash
uv run victus-processing pdf-processing run --limit 5
uv run victus-processing pdf-processing run --pdf data/runtime/02-pdfs/active/paper.pdf
uv run victus-processing pdf-processing run --markdown data/runtime/03-pdf_processing/paper/paper.md
```

Flags:

- `--pdf`: process one PDF file.
- `--markdown`: process one existing `paper.md` file.
- `--input-dir`: process PDFs from a directory when neither `--pdf` nor
  `--markdown` is provided.
- `--limit`: maximum PDFs to process from `--input-dir`.
- `--workers`: number of PDFs to process in parallel.
- `--output-dir`: runtime output directory.
- `--prompt-first-batch`: alternate prompt file for the first Markdown batch.
- `--prompt-continuation-batch`: alternate prompt file for continuation
  batches.
- `--force-markdown`: regenerates existing Docling Markdown.
- `--max-batches`: maximum Markdown batches to process for each PDF.

Operational notes:

- `--pdf` and `--markdown` are mutually exclusive.
- Requires configured prompt and LLM access.

### `pdf-processing testing`

Runs the complete per-paper testing pipeline under `data/testing`. For each
selected PDF, it copies `source.pdf`, creates or reuses `paper.md`, runs Markdown
structuring, and then runs mapper plus canonical evidence extraction.

```bash
uv run victus-processing pdf-processing testing
uv run victus-processing pdf-processing testing --paper-id paper-1
uv run victus-processing pdf-processing testing --paper-id paper-1 --reuse-markdown
uv run victus-processing pdf-processing testing --limit 10 --force-markdown
```

Flags:

- `--pdf-dir`: source directory for active PDFs. Defaults to the configured
  PDF-processing input directory.
- `--markdown-dir`: source directory containing existing `<paper_id>/paper.md`
  files for `--reuse-markdown`.
- `--output-dir`: testing destination root. Defaults to `data/testing`.
- `--paper-id`: paper to process. May be repeated. If omitted, the command scans
  PDFs from `--pdf-dir`.
- `--limit`: maximum papers to process when `--paper-id` is omitted.
- `--overwrite-source`: replaces an existing testing `source.pdf` copy.
- `--reuse-markdown`: copies an existing `paper.md` from `--markdown-dir` and
  skips Docling.
- `--overwrite-markdown`: replaces an existing testing `paper.md` copy when
  using `--reuse-markdown`.
- `--prompt-first-batch`: alternate prompt file for the first Markdown batch.
- `--prompt-continuation-batch`: alternate prompt file for continuation
  batches.
- `--force-markdown`: regenerates existing Docling Markdown.
- `--max-batches`: maximum Markdown batches to process for each PDF.
- `--evidence-model`: alternate LLM model for evidence extraction.
- `--skip-existing-evidence`: skips papers with existing
  `canonical_evidence.json`.

Output layout:

```text
data/testing/<paper_id>/source.pdf
data/testing/<paper_id>/paper.md
data/testing/<paper_id>/markdown_batches/
data/testing/<paper_id>/raw_batches/
data/testing/<paper_id>/paper.processed.json
data/testing/<paper_id>/paper.final.json
data/testing/<paper_id>/paper.classifier_input.json
data/testing/<paper_id>/paper.classification.json
data/testing/<paper_id>/evidence_skipped.json
data/testing/<paper_id>/trimmed.json
data/testing/<paper_id>/experiment_map.json
data/testing/<paper_id>/experiment_packets.json
data/testing/<paper_id>/canonical_evidence.json
```

### `pdf-processing evidence`

Generates evidence artifacts from `paper.processed.json` inputs.

```bash
uv run victus-processing pdf-processing evidence
uv run victus-processing pdf-processing evidence --input data/runtime/03-pdf_processing/paper/paper.processed.json
uv run victus-processing pdf-processing evidence --skip-existing --limit 20
```

Flags:

- `--input`: a `paper.processed.json` file or a directory of
  PDF-processing artifacts.
- `--output-dir`: evidence output directory.
- `--pattern`: glob used when `--input` is a directory. Default is
  `*/paper.processed.json`.
- `--limit`: maximum papers to process when `--input` is a directory.
- `--model`: alternate LLM model for evidence extraction.
- `--skip-existing`: skips papers with existing `canonical_evidence.json`.

Outputs:

- `trimmed.json`
- `experiment_map.json`
- `canonical_evidence.json`

## `data-layout`

### `data-layout create`

Ensures the canonical `data/` runtime directories exist.

```bash
uv run victus-processing data-layout create
uv run victus-processing data-layout create --dry-run
```

Flags:

- `--dry-run`: prints the required directories without creating them.

## `bridge`

The `bridge` group is reserved for Victus infrastructure integration:
registering PDFs, publishing artifacts or events, marking stages, and checking
infrastructure status.

Run help in an environment that includes the bridge module:

```bash
uv run victus-processing bridge --help
```

If the bridge module is absent, the CLI exits with an explicit availability
error.

## Infisical Helper

Infisical-backed CLI inspection:

```bash
uv run victus-infisical-env run --env dev --path / -- victus-processing --help
```

Useful forms:

```bash
uv run victus-infisical-env export --env dev --path / --output .env
uv run victus-infisical-env run --env dev --path / -- victus-processing pdf-processing run --limit 1
```

## Validation

Smoke-test CLI routing after changing command behavior:

```bash
uv run pytest tests/test_cli_smoke.py -q
```

Related: [Operations](../200-OPERATIONS.md).
