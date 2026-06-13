---
id: VICTUS-PROCESSING-OPERATIONS
title: Victus Processing Operations
status: active
updated_at: 2026-06-13
version: v1.0.0
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

These operations describe the `v1.0.0` processing baseline.

## 1. Operational Overview

`victus-processing` is operated as a local CLI-driven batch pipeline. Operators
run explicit stages, inspect local artifacts, and rerun failed or incomplete
work from persisted state.

Primary operational responsibilities:

- prepare local runtime directories;
- configure API credentials for selected stages;
- run metadata, PDF, PDF-processing, and evidence stages;
- inspect status artifacts and CLI output;
- preserve local `data/` artifacts unless cleanup is intentional.

## 2. Runtime Environments

- **Local development:** primary supported runtime. Uses `uv`, local files, and
  environment variables or `.env`.
- **CI validation:** focused smoke tests for CLI availability and command
  routing.
- **Container runtime:** Dockerfile exists, but no production deployment flow is
  defined in this repository.

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
uv run victus-processing metadata-extraction explore --mode broad-nutrition
uv run victus-processing bibliography-export generate-bib
uv run victus-processing pdf-intake link --metadata-id meta:s2:example --pdf data/artifacts/intake/pdfs/example.pdf
uv run victus-processing pdf-processing run
uv run victus-processing evidence-extraction run
```

Run a single DOI metadata fetch:

```bash
uv run victus-processing metadata-extraction from-doi --doi 10.1000/demo
```

This writes directly to `data/lake/paper_metadata.jsonl`.

Run smoke validation:

```bash
uv run pytest tests/test_cli_smoke.py -q
```

More CLI detail: [CLI operations](operations/cli.md).

PDF-processing detail: [PDF processing operations](operations/pdf-processing.md).

## 4. Configuration

Runtime defaults live in `config/*.yaml`. Relative paths resolve from the
repository root. Optional root `config.yaml` can override domain config.

Secrets are read from environment variables. `.env` is only a local fallback;
prefer Infisical injection for real runs.

Common variables:

- `SEMANTIC_SCHOLAR_API_KEY`
- `LITELLM_PROXY_API_BASE`
- `LITELLM_PROXY_API_KEY` or legacy `LITELLM_KEY`
- `LITELLM_METADATA_SELECTION_MODEL`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`
- `PROMPT_LABEL`
- `PROMPTS_LOCAL_DIR`
- `DEFAULT_LLM_MODEL`

Infisical helper:

```bash
uv run victus-infisical-env export --env dev --path / --output .env
uv run victus-infisical-env run --env dev --path / -- victus-processing --help
```

Prompt Management:

- Langfuse Prompt Management is the primary prompt source when Langfuse
  credentials are injected.
- Local markdown prompts under `src/prompts/` are fallback prompts.
- Local prompt defaults do not set `max_tokens`; explicit stage config or remote
  prompt config must provide output-token limits.
- LiteLLM remains the execution adapter and does not fetch prompts.

Configuration contracts and stable path expectations live in
[Contracts](300-CONTRACTS.md).

## 5. Observability

There is no central logging or metrics service in this repository.

Operational inspection sources:

- CLI stdout/stderr;
- `paper_processing_state` for per-paper progress;
- `structured_blocks`, `paper_classifications`, `experiment_maps`, and
  `canonical_evidence` for processed outputs;
- `data/reports/exports/paper_processing_state.csv` for quick spreadsheet
  inspection.

## 6. Failure and Recovery

- Rerun interrupted stages; completed artifacts are skipped where supported.
- Preserve existing evidence outputs unless an explicit force or overwrite
  behavior is implemented and requested.
- Use force/overwrite flags only when intentionally regenerating artifacts.
- Treat status JSONL files as operational state.
- Do not remove `data/` artifacts during recovery unless cleanup is explicit.
- For git rollback, revert documentation or code changes only; do not treat user
  runtime data as disposable.

## 7. Troubleshooting

- Missing LiteLLM provider credentials: model-backed selection, PDF processing,
  or evidence commands fail.
- Missing `SEMANTIC_SCHOLAR_API_KEY`: Semantic Scholar may run with stricter
  public rate limits.
- LLM 429/5xx/network errors: LiteLLM handles retries, fallbacks, provider routing,
  and quota behavior.
- Missing PDFs: ensure linked PDF artifacts exist under
  `data/artifacts/pdfs/`.
- Unexpected CLI behavior: run `uv run victus-processing --help` and the smoke
  test before editing stage code.

## 8. Operational Boundaries

Operations covers:

- runtime execution workflows;
- configuration and secret-loading guidance;
- validation commands;
- observability and recovery guidance;
- runbook navigation.

Operations does not cover:

- architecture reasoning;
- stable contracts and invariants;
- historical decisions;
- implementation walkthroughs.

## 9. Related Documentation

- [System Context](000-SYSTEM-CONTEXT.md)
- [Architecture](100-ARCHITECTURE.md)
- [Contracts](300-CONTRACTS.md)
- [CLI operations](operations/cli.md)
- [Contract synchronization](operations/contracts-sync.md)
- [PDF processing operations](operations/pdf-processing.md)
- [Pipeline runbooks](operations/pipeline/)
- [Runbooks](operations/runbooks/)
- [PostgreSQL pipeline records](operations/runbooks/postgres-pipeline-records.md)
- [Data layout migration](operations/runbooks/data-layout-migration.md)
