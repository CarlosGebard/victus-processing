---
id: VICTUS-PIPELINE-ACTION-OBSERVABILITY-PLAN
title: Pipeline Action Observability Plan
status: draft
updated_at: 2026-06-10
related_docs:
  - VICTUS-PROCESSING-OPERATIONS
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - operations
  - observability
  - pipeline-runs
  - pipeline-events
  - paper-stage-state
  - artifact-registry
---

# Pipeline Action Observability Plan

## Goal

Make pipeline execution auditable without turning the event stream into the
query model.

The observability model separates:

- immutable audit history;
- queryable current operational state;
- canonical artifact indexing;
- PostgreSQL synchronization safety.

PostgreSQL must not store large payloads. Large JSON documents, model inputs,
model outputs, PDFs, markdown files, debug batches, and extracted content stay
in lake files, artifacts, debug files, or object storage. PostgreSQL only stores
compact operational records and references.

Langfuse must not become part of core domain logic. If Langfuse is used, it is
an external trace provider referenced through `trace_ref`, not a source of truth
for pipeline state.

## Operational Model

### Immutable Audit Records

`PipelineRun` and `PipelineEvent` are append/audit records.

They answer:

- what happened;
- when it happened;
- which run, stage, attempt, paper, or artifact was involved;
- why a routing decision, skip, retry, validation, or failure occurred.

They do not answer current-state queries directly. Operators may replay them for
debugging, but production-style status queries should use state tables/files.

### Current Operational State

`PaperStageState` is the queryable current state per `paper_id` and `stage`.

It answers:

- what is the current status of this paper in this stage;
- which attempt is current;
- which run last updated it;
- whether the stage can be resumed, skipped, retried, or inspected;
- where the latest error summary or artifact reference is.

Expected local file:

- `data/lake/paper_stage_state.jsonl`

Expected PostgreSQL table:

- `paper_stage_state`

This record is upserted by natural key:

- `paper_id`
- `stage`

### Canonical Artifact Index

`ArtifactRegistry` is the canonical index of produced artifacts.

It answers:

- which artifacts exist;
- which run/stage/attempt produced them;
- which paper they belong to;
- where they are stored;
- which contract and schema version they claim;
- whether they are current, superseded, discarded, or invalid.

Expected local file:

- `data/registry/artifact_manifest.jsonl`

Expected PostgreSQL table:

- `artifact_registry`

The current implementation already has artifact manifest support in
`src/workspace/runs.py`. The next iteration should align naming around
`ArtifactRegistry` while keeping compatibility with the existing
`artifact_manifest.jsonl` file.

## Action Boundary

Instrument only meaningful operational actions:

- state changes;
- routing decisions;
- validations;
- principal artifact creation;
- intentional skips;
- retries;
- failures.

Do not instrument every micro-action. Do not emit events for tight-loop
internals, every helper call, every file stat, every row parse, every log line,
or every small transformation.

The event stream should be useful for operators. It should not become a verbose
debug trace.

## Required Fields

### PipelineRun

`PipelineRun` remains append-only. A run start and terminal update may both be
written as audit records.

Required or recommended fields:

- `run_id`
- `pipeline_name`
- `pipeline_version`
- `execution_mode`
- `status`
- `input_scope`
- `started_at`
- `ended_at`
- `created_by`
- `summary`
- `config_hash`
- `schema_version`
- `trace_ref`
- `created_at`
- `updated_at`

Field notes:

- `config_hash` identifies the effective runtime configuration.
- `schema_version` identifies the record shape for compatibility.
- `trace_ref` may point to Langfuse or another trace system, but core logic must
  not depend on that provider.

### PipelineEvent

`PipelineEvent` remains append-only and compact.

Required or recommended fields:

- `event_id`
- `run_id`
- `stage_attempt_id`
- `attempt_number`
- `idempotency_key`
- `timestamp`
- `process_name`
- `stage`
- `event_type`
- `severity`
- `status`
- `paper_id`
- `artifact_id`
- `artifact_path`
- `contract_version`
- `schema_version`
- `trace_ref`
- `message`
- `metadata`

Field notes:

- `stage_attempt_id` identifies one concrete attempt for one stage.
- `attempt_number` is monotonic per `paper_id` and `stage`.
- `idempotency_key` makes reruns and dual writes deduplicable.
- `contract_version` identifies the contract used by the event or artifact.
- `schema_version` identifies the event record shape.
- `metadata` must stay compact and JSON-serializable.

### PaperStageState

`PaperStageState` is mutable/current state. Locally, it can be represented as
append JSONL with consumers taking the latest record per natural key. In
PostgreSQL, it should be an upsert table.

Required or recommended fields:

- `paper_id`
- `stage`
- `stage_attempt_id`
- `attempt_number`
- `run_id`
- `status`
- `last_event_id`
- `last_transition_at`
- `started_at`
- `ended_at`
- `retry_count`
- `idempotency_key`
- `contract_version`
- `schema_version`
- `config_hash`
- `trace_ref`
- `primary_artifact_id`
- `error_summary`
- `updated_at`

Allowed state statuses should be small and operational:

- `pending`
- `running`
- `succeeded`
- `failed`
- `skipped`
- `retry_scheduled`
- `blocked`

### ArtifactRegistry

`ArtifactRegistry` is the canonical artifact index. It should reference
artifacts, not embed them.

Required or recommended fields:

- `artifact_id`
- `artifact_type`
- `artifact_version`
- `paper_id`
- `run_id`
- `stage`
- `stage_attempt_id`
- `storage_uri`
- `storage_backend`
- `content_format`
- `checksum`
- `size_bytes`
- `status`
- `contract_version`
- `schema_version`
- `config_hash`
- `trace_ref`
- `created_at`
- `updated_at`
- `metadata`

Allowed artifact statuses:

- `current`
- `superseded`
- `discarded`
- `invalid`

## Naming Convention

`process_name` and `stage` must be strict, stable identifiers.

Format:

- lowercase ASCII;
- dot-separated namespaces;
- no spaces;
- no free-form labels;
- no runtime values;
- no paper IDs, run IDs, timestamps, or provider names inside the name.

`process_name` format:

```text
victus.processing.<workflow>
```

Allowed initial `process_name` values:

- `victus.processing.data_layout_migration`
- `victus.processing.seed_ingestion`
- `victus.processing.candidate_discovery`
- `victus.processing.candidate_review`
- `victus.processing.pdf_acquisition`
- `victus.processing.pdf_normalization`
- `victus.processing.pdf_processing`
- `victus.processing.paper_classification`
- `victus.processing.evidence_extraction`
- `victus.processing.artifact_registration`

`stage` format:

```text
<workflow>.<stage>
```

Allowed initial `stage` values:

- `data_layout.plan`
- `data_layout.copy`
- `data_layout.conflict_detection`
- `data_layout.unresolved_detection`
- `data_layout.report`
- `seed.load`
- `seed.validate`
- `candidate.discover`
- `candidate.review`
- `pdf.acquire`
- `pdf.normalize`
- `pdf.process`
- `classification.classify`
- `evidence.extract`
- `artifact.register`

Adding a new name requires updating this runbook and the validation tests before
it is used in runtime code.

## Event Volume Policy

Events must describe operationally meaningful transitions.

### Principal Artifact Events

Emit one artifact event per principal artifact when the artifact is important to
paper-level recovery or audit.

Principal artifacts include:

- PDF;
- markdown;
- structured blocks;
- paper classification;
- experiment map;
- experiment packets;
- canonical evidence;
- registry records.

Use `artifact_created`, `artifact_validated`, or `artifact_invalid`.

### Aggregate Batch Events

Use aggregate events for high-volume batch operations where per-item events do
not improve recovery.

Examples:

- copied 4,106 PDFs;
- skipped 3,209 existing markdown files;
- detected 23 unresolved legacy paths;
- validated 10 contracts;
- processed 1,000 candidate rows.

Aggregate events should include counts and report paths in compact `metadata`.
They must not embed large item lists.

### Not Events

Do not emit events for:

- every file stat;
- every line read from JSONL;
- every internal function call;
- every prompt token;
- every model chunk;
- every debug batch;
- every unchanged artifact observed during a scan.

## Local Outbox Policy

Local JSONL is the first durable write. PostgreSQL dual-write is secondary.

When PostgreSQL is configured:

1. Write the local JSONL record first.
2. Write an outbox entry before or with the local record.
3. Attempt the PostgreSQL write.
4. Mark the outbox entry as delivered only after PostgreSQL confirms.
5. If PostgreSQL fails, keep the outbox entry pending and emit a compact warning
   event locally.

Expected local outbox file:

- `data/runtime/outbox/postgres_pipeline_records.jsonl`

Outbox fields:

- `outbox_id`
- `record_type`
- `record_id`
- `idempotency_key`
- `target`
- `status`
- `attempt_count`
- `last_attempt_at`
- `last_error`
- `payload_ref`
- `created_at`
- `updated_at`

Allowed outbox statuses:

- `pending`
- `delivered`
- `failed`

Outbox replay must be idempotent:

- `pipeline_runs` upsert by `run_id`;
- `pipeline_events` insert by `event_id` or dedupe by `idempotency_key`;
- `paper_stage_state` upsert by `paper_id` and `stage`;
- `artifact_registry` upsert by `artifact_id`.

PostgreSQL outages must not cause large payloads to be copied into PostgreSQL.
The outbox may keep compact payloads or local payload references only.

## PostgreSQL Scope

V1 PostgreSQL scope:

- `pipeline_runs`
- `pipeline_events`
- `artifact_registry`
- `paper_stage_states`

Local outbox replay is manual and intentionally does not require workers,
queues, daemons, or extra infrastructure.

Never store these directly in PostgreSQL:

- PDFs;
- markdown content;
- model raw inputs;
- model raw outputs;
- raw batches;
- extracted full text;
- large evidence payloads;
- full lake JSONL payloads.

## Implemented Baseline

The current baseline includes:

- contracts for `PaperStageState` and `ArtifactRegistry`;
- local writers for runs, events, paper stage state, artifact registry, and
  PostgreSQL outbox records;
- PostgreSQL DDL and adapter methods for `pipeline_runs`, `pipeline_events`,
  `paper_stage_states`, and `artifact_registry`;
- manual outbox replay through `uv run python -m ops.scripts.sync_postgres_outbox`;
- `PipelineRunContext` for compact instrumentation;
- initial instrumentation for data layout migration and seed DOI generation.

Remaining rollout should focus on applying `PipelineRunContext` to the next
pipeline stages in small batches.

## Files Involved

Core implementation:

- `src/workspace/runs.py`
- `src/workspace/config.py`
- `src/workspace/pipeline_context.py`
- `src/infrastructure/postgres/pipeline_store.py`

Operational scripts:

- `ops/scripts/data/migrate_data_layout.py`

Database:

- `ops/sql/001_pipeline_runs_events.sql`

Documentation:

- `docs/200-OPERATIONS.md`
- `docs/operations/runbooks/pipeline-action-observability-plan.md`
- `docs/operations/runbooks/postgres-pipeline-records.md`
- `docs/contracts/local/data-layout.md`
- `docs/contracts/local/artifact-inventory.md`
- `docs/contracts/fundamental/scientific/pipeline-run.md`
- `docs/contracts/fundamental/scientific/pipeline-event.md`
- `docs/contracts/fundamental/scientific/artifact-manifest.md`
- `docs/contracts/fundamental/scientific/paper-stage-state.md`
- `docs/contracts/fundamental/scientific/artifact-registry.md`

Maintained smoke validation:

- `tests/test_cli_smoke.py`

## Risks

- Treating events as state will make queries expensive and ambiguous. Use
  `PaperStageState` for current status.
- Too many events will make operations noisy. Use principal artifact events and
  aggregate batch events.
- PostgreSQL must not become payload storage. Store references only.
- Langfuse coupling would make observability provider-specific. Keep it behind
  `trace_ref`.
- Without an outbox, PostgreSQL dual-write failures can silently lose index
  records.

## Suggested Rollout

1. Instrument candidate discovery.
2. Instrument PDF acquisition and markdown generation.
3. Instrument structured blocks and paper classification.
4. Instrument experiment map, evidence packets, and canonical evidence.
5. Promote legacy runtime artifacts into the new storage layout or archive them.
