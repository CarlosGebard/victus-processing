---
id: VICTUS-POSTGRES-SCIENTIFIC-STATE-RUNBOOK
title: PostgreSQL Scientific State Runbook
status: source-of-truth
updated_at: 2026-06-13
related_components:
  - src.infrastructure.postgres.pipeline_store
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - operations
  - postgres
  - processing-state
  - scientific-outputs
---

# PostgreSQL Scientific State

This runbook covers the v1 PostgreSQL integration scope. The active operational
tables are:

- `paper_processing_state`
- `structured_papers`
- `evidence_blocks`
- `structured_blocks`
- `paper_classifications`
- `experiment_maps`
- `canonical_evidence`

Legacy/optional observability tables may still exist:

- `pipeline_runs`
- `pipeline_events`
- `paper_stage_states`
- `artifact_registry`

PostgreSQL is the active query/export sink for scientific outputs and
`paper_processing_state`.

## Setup

Apply the v1 schema:

```bash
psql "$DATABASE_URL" -f ops/sql/001_pipeline_runs_events.sql
psql "$DATABASE_URL" -f ops/sql/002_scientific_outputs.sql
psql "$DATABASE_URL" -f ops/sql/003_paper_processing_state.sql
psql "$DATABASE_URL" -f ops/sql/004_structured_paper_evidence_blocks.sql
```

`DATABASE_URL` should be injected through the normal secret path, preferably
Infisical for real environments.

## Validation

Confirm the active tables exist:

```bash
psql "$DATABASE_URL" -c '\d paper_processing_state'
psql "$DATABASE_URL" -c '\d structured_papers'
psql "$DATABASE_URL" -c '\d evidence_blocks'
psql "$DATABASE_URL" -c '\d structured_blocks'
psql "$DATABASE_URL" -c '\d paper_classifications'
psql "$DATABASE_URL" -c '\d experiment_maps'
psql "$DATABASE_URL" -c '\d canonical_evidence'
```

Run the maintained smoke validation:

```bash
uv run pytest tests/test_cli_smoke.py -q
```

## Local Outbox

When PostgreSQL writes fail, failed deliveries must be retained in:

```text
data/runtime/outbox/postgres_pipeline_records.jsonl
```

Outbox records must be compact and idempotent. They may reference local payloads
but they must not embed large payloads.

Delivery rules:

- append or keep an outbox record before retrying PostgreSQL;
- retry by `idempotency_key`;
- upsert scientific outputs by their canonical ids or paper/run key.

The replay command is:

```bash
uv run python -m ops.scripts.sync_postgres_outbox
```

## Table Exports

Export scientific output tables to CSV and Parquet:

```bash
uv run victus-postgres-export --output-dir data/reports/exports/postgres
```

Equivalent module form:

```bash
uv run python -m ops.scripts.export_postgres_tables --format csv --format parquet
```

By default this exports:

- `paper_processing_state`
- `structured_blocks`
- `paper_classifications`
- `experiment_maps`
- `canonical_evidence`

Use repeated `--table` flags to export a subset or include orchestration tables.

## Boundaries

PostgreSQL v1 stores final scientific output records and paper processing state.
It does not store:

- PDFs;
- Markdown;
- raw LLM responses;
- raw batch artifacts.

Large payloads must remain in artifacts or scientific output rows designed for
that payload.
