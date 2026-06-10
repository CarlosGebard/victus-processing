---
id: VICTUS-PROCESSING-CLI-OPERATIONS
title: Victus Processing CLI Operations
status: source-of-truth
updated_at: 2026-06-06
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

- `metadata-extraction`: discovers candidates, fetches metadata by DOI, and
  prepares DOI seed queues.
- `metadata-to-pdf`: generates bibliography artifacts and normalizes raw PDFs
  into active runtime inputs.
- `pdf-processing`: converts active PDFs to Markdown and structured paper JSON.
- `evidence-extraction`: classifies processed papers, maps experiments, builds
  packets, and writes canonical evidence.
- `testing-pipeline`: runs the PDF-processing and evidence chain in per-paper
  review folders under `data/testing`.
- `bridge`: optional Victus infrastructure integration. This group may be
  unavailable in local checkouts that do not include `ops/scripts/bridge`.
- `data-layout`: creates local runtime directories.

## Common Flow

Create the expected local `data/` layout:

```bash
uv run victus-processing data-layout create
```

Run the main local paper-processing flow:

```bash
uv run victus-processing metadata-extraction explore --mode broad-nutrition
uv run victus-processing metadata-to-pdf normalize-pdfs
uv run victus-processing pdf-processing run
uv run victus-processing evidence-extraction run
```

Use `--limit` while testing or debugging:

```bash
uv run victus-processing pdf-processing markdown --limit 1
uv run victus-processing pdf-processing run --limit 1
uv run victus-processing evidence-extraction run --limit 1
uv run victus-processing testing-pipeline run --limit 1
```

## Pipeline Runbooks

- [Metadata extraction](pipelines/metadata-extraction.md)
- [Metadata to PDF](pipelines/metadata-to-pdf.md)
- [PDF processing](pipelines/pdf-processing.md)
- [Evidence extraction](pipelines/evidence-extraction.md)
- [Testing pipeline](pipelines/testing-pipeline.md)

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

Related: [Operations](../200-OPERATIONS.md),
[Configuration and CLI Contract](../contracts/local/configuration-and-cli.md).
