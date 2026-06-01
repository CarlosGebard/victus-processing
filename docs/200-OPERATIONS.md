---
id: VICTUS-PROCESSING-OPERATIONS
title: Victus Processing Operations
status: active
updated_at: 2026-05-27
related_docs:
  - VICTUS-PROCESSING-SYSTEM-CONTEXT
  - VICTUS-PROCESSING-ARCHITECTURE
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - operations
  - runtime
  - local-execution
---

# Operations

## 1. Operational Overview

`victus-processing` is operated as a local CLI-driven batch pipeline. Operators
run explicit stages, inspect local artifacts, and rerun failed or incomplete
work from persisted state.

Primary operational responsibilities:

- prepare local runtime directories;
- configure API credentials for selected stages;
- run metadata, PDF, PDF-processing, and claim stages;
- inspect status artifacts and CLI output;
- preserve local `data/` artifacts unless cleanup is intentional.

## 2. Runtime Environments

- **Local development:** primary supported runtime. Uses `uv`, local files, and
  environment variables or `.env`.
- **CI validation:** focused smoke tests for CLI availability and command
  routing.
- **Container runtime:** Dockerfile exists, but no production deployment flow is
  defined in this repository.
- **Victus bridge runtime:** optional integration path when bridge dependencies
  and infrastructure configuration are available.

## 3. Execution Workflows

Create or verify local runtime layout:

```bash
uv run victus-processing data-layout create
```

Inspect CLI:

```bash
uv run victus-processing --help
```

Run the main local flow:

```bash
uv run victus-processing metadata explore --mode broad-nutrition
uv run victus-processing pdfs normalize
uv run victus-processing pdf-processing run
uv run victus-processing claims extract --pattern "*/paper.final.json" --skip-existing
```

Run a single DOI metadata fetch:

```bash
uv run victus-processing metadata from-doi --doi 10.1000/demo
```

Run smoke validation:

```bash
uv run pytest tests/test_cli_smoke.py -q
```

More CLI detail: [CLI operations](operations/cli.md).

PDF-processing detail: [PDF processing operations](operations/pdf-processing.md).

## 4. Configuration

Runtime defaults live in `config/*.yaml`. Relative paths resolve from the
repository root. Optional root `config.yaml` can override domain config.

Secrets are read from environment variables or `.env`.

Common variables:

- `SEMANTIC_SCHOLAR_API_KEY`
- LiteLLM provider credentials and routing variables
- `LITELLM_METADATA_SELECTION_MODEL`
- Langfuse variables when tracing is enabled

Infisical helper:

```bash
uv run victus-infisical-env export --env dev --path / --output .env
uv run victus-infisical-env run --env dev --path / -- victus-processing --help
```

Configuration contracts and stable path expectations live in
[Contracts](300-CONTRACTS.md).

## 5. Observability

There is no central logging or metrics service in this repository.

Operational inspection sources:

- CLI stdout/stderr;
- `data/runtime/03-pdf_processing/processing_status.jsonl`;
- `data/runtime/03-pdf_processing/{paper_id}/raw_batches/`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.md`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.processed.json`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.final.json`.

The claims CLI default pattern is `*/*.final.json`.

## 6. Failure and Recovery

- Rerun interrupted stages; completed artifacts are skipped where supported.
- Use `--skip-existing` for claim extraction when preserving previous outputs.
- Use force/overwrite flags only when intentionally regenerating artifacts.
- Treat status JSONL files as operational state.
- Do not remove `data/` artifacts during recovery unless cleanup is explicit.
- For git rollback, revert documentation or code changes only; do not treat user
  runtime data as disposable.

## 7. Troubleshooting

- Missing LiteLLM provider credentials: model-backed selection, PDF processing,
  or claims commands fail.
- Missing `SEMANTIC_SCHOLAR_API_KEY`: Semantic Scholar may run with stricter
  public rate limits.
- LLM 429/5xx/network errors: LiteLLM owns retries, fallbacks, provider routing,
  and quota behavior.
- Missing PDFs: ensure normalized PDFs exist under
  `data/runtime/02-pdfs/active/`.
- Unexpected CLI behavior: run `uv run victus-processing --help` and the smoke
  test before editing stage code.

## 8. Operational Boundaries

Operations owns:

- runtime execution workflows;
- configuration and secret-loading guidance;
- validation commands;
- observability and recovery guidance;
- runbook navigation.

Operations does not own:

- architecture reasoning;
- stable contracts and invariants;
- historical decisions;
- implementation walkthroughs.

## 9. Related Documentation

- [System Context](000-SYSTEM-CONTEXT.md)
- [Architecture](100-ARCHITECTURE.md)
- [Contracts](300-CONTRACTS.md)
- [CLI operations](operations/cli.md)
- [PDF processing operations](operations/pdf-processing.md)
- [Runbooks](operations/runbooks/)
