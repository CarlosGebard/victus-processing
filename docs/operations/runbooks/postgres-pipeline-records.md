---
id: VICTUS-POSTGRES-PIPELINE-RECORDS-RUNBOOK
title: PostgreSQL Pipeline Records Runbook
status: draft
updated_at: 2026-06-10
related_components:
  - src.infrastructure.postgres.pipeline_store
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - operations
  - postgres
  - pipeline-runs
  - pipeline-events
---

# PostgreSQL Pipeline Records

This runbook covers the v1 PostgreSQL integration scope only:

- `pipeline_runs`
- `pipeline_events`
- `paper_stage_states`
- `artifact_registry`

JSONL artifacts and object payloads are out of scope for this integration path.
They are expected to move through S3/Seaweed-backed storage later.

Local JSONL remains the first durable write. PostgreSQL is a secondary query
sink and must be synchronized through a local outbox when enabled.

## Setup

Apply the v1 schema:

```bash
psql "$DATABASE_URL" -f ops/sql/001_pipeline_runs_events.sql
```

`DATABASE_URL` should be injected through the normal secret path, preferably
Infisical for real environments.

## Validation

Confirm the tables exist:

```bash
psql "$DATABASE_URL" -c '\d pipeline_runs'
psql "$DATABASE_URL" -c '\d pipeline_events'
psql "$DATABASE_URL" -c '\d paper_stage_states'
psql "$DATABASE_URL" -c '\d artifact_registry'
```

Run the maintained smoke validation:

```bash
uv run pytest tests/test_cli_smoke.py -q
```

## Local Outbox

When PostgreSQL dual-write is enabled, failed deliveries must be retained in:

```text
data/runtime/outbox/postgres_pipeline_records.jsonl
```

Outbox records must be compact and idempotent. They may reference local payloads
such as `data/lake/pipeline_events.jsonl#evt_...`, but they must not embed
large payloads.

Delivery rules:

- write local JSONL first;
- append or keep an outbox record before retrying PostgreSQL;
- mark delivery only after PostgreSQL confirms;
- retry by `idempotency_key`;
- upsert `pipeline_runs` by `run_id`;
- insert or dedupe `pipeline_events` by `event_id` or `idempotency_key`.

The replay command is:

```bash
uv run python -m ops.scripts.sync_postgres_outbox
```

## Boundaries

PostgreSQL v1 stores orchestration records only. It does not store:

- PDFs;
- Markdown;
- raw LLM responses;
- JSONL lake payloads;
- canonical evidence payload files;
- artifact payloads.

Large payloads must remain outside `pipeline_events`; events should reference
paths or artifact ids when available.
