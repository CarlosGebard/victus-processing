---
id: VICTUS-POSTGRES-SCIENTIFIC-STATE-RUNBOOK
title: PostgreSQL Scientific State Runbook
status: source-of-truth
updated_at: 2026-06-19
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

This runbook covers the simplified PostgreSQL integration. The active tables
are:

- `paper_pipeline_state`
- `paper_processing_state`
- `structured_papers`
- `structured_blocks`
- `paper_classifications`
- `experiment_maps`
- `canonical_evidence`

PostgreSQL is the active query/export sink for scientific outputs and
paper state. Detailed events and artifact manifests remain local JSON records.

## Setup

Apply the active schema migration:

```bash
psql "$DATABASE_URL" -f ops/sql/005_simplified_postgres_schema.sql
```

Migration 005 drops and recreates every pipeline table except
`structured_papers`. Back up any other PostgreSQL data that must be retained
before applying it. Do not interrupt the migration after it acquires the
`structured_papers` lock; all destructive work runs in one transaction. On a
new database the migration creates `structured_papers` before acquiring the
lock.

`DATABASE_URL` should be injected through the normal secret path, preferably
Infisical for real environments.

## Validation

Confirm the active tables exist:

```bash
psql "$DATABASE_URL" -c '\d paper_processing_state'
psql "$DATABASE_URL" -c '\d paper_pipeline_state'
psql "$DATABASE_URL" -c '\d structured_papers'
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

Use repeated `--table` flags to export a subset or include
`paper_pipeline_state` and `structured_papers`.

Create a self-contained judge review sample with random papers, their canonical
evidence, a manifest, and matching PDFs:

```bash
uv run victus-canonical-evidence-sample \
  --limit 5 \
  --seed judge-001 \
  --output-dir data/reports/exports/judge-samples/judge-001
```

All files for that review are written under the chosen `--output-dir`.

## Boundaries

PostgreSQL stores final scientific output records and paper processing state.
It does not store:

- PDFs;
- Markdown;
- raw LLM responses;
- raw batch artifacts.

Large payloads must remain in artifacts or scientific output rows designed for
that payload.
