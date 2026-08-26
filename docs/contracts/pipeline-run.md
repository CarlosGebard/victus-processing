---
id: VICTUS-CONTRACT-PIPELINE-RUN
contract_id: victus.orchestration.pipeline_run
title: PipelineRun
status: draft
version: v1
owner: victus-processing
domain: orchestration
contract_type: orchestration
stability: experimental
updated_at: 2026-06-19
---

# PipelineRun Contract Documentation

## 1. Purpose

Define the canonical execution record for one Victus processing run.

`PipelineRun` identifies, tracks, audits, resumes, and supports reasoning about
one execution of the processing pipeline. It represents execution state, not
scientific content.

## 2. Identity

### Identity Rules

- Canonical identifier: `run_id`
- `run_id` is globally unique inside Victus.
- `run_id` is immutable after creation.
- `run_id` must be generated before any process event is emitted.
- All events, artifacts, and stage outcomes created during the execution must
  reference the same `run_id`.

### Ownership

`PipelineRun` is owned by `victus-processing`.

## 3. Schema

### JSON Schema

```json
{
  "run_id": "string",
  "pipeline_name": "string",
  "pipeline_version": "string",
  "execution_mode": "single_paper|batch|stage_only|testing|backfill|replay",
  "status": "pending|running|succeeded|failed|partially_succeeded|cancelled",
  "input_scope": {},
  "started_at": "datetime",
  "ended_at": "datetime|null",
  "created_by": "string|null",
  "summary": {},
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `run_id` | String | Unique identifier for this execution. |
| `pipeline_name` | String | Name of the pipeline being executed. |
| `pipeline_version` | String | Version or git reference of the pipeline code or contract set used for this run. |
| `execution_mode` | Enum | Execution scope. |
| `status` | Enum | Current run status. |
| `input_scope` | Object | Structured description of what the run was asked to process. |
| `started_at` | Datetime | Run start timestamp. |
| `ended_at` | Datetime / Null | Run end timestamp. |
| `created_by` | String / Null | Actor or process that created the run. |
| `summary` | Object | Materialized operational counters produced by the run. |
| `created_at` | Datetime | Run creation timestamp. |
| `updated_at` | Datetime | Last run update timestamp. |

## 5. Responsibilities

### Required Responsibilities

`PipelineRun` must record:

- what was executed
- when execution started and ended
- which pipeline version was used
- which input scope was selected
- current execution status
- terminal result when available
- summary counters for processed, skipped, failed, and successful items

### Forbidden Responsibilities

`PipelineRun` must not store:

- paper metadata as canonical scientific data
- structured blocks
- canonical evidence
- embeddings
- raw LLM responses
- full prompts
- full exception traces
- storage payloads
- PDF or Markdown content

## 6. Validation Rules

- Required fields must be present.
- `run_id` must be unique and immutable.
- `execution_mode` must be one of the allowed values.
- `status` must be one of the allowed values.
- `input_scope` and `summary` must be objects.
- A run must not be marked `succeeded` if required terminal artifacts are
  missing or schema-invalid.
- A failed run must emit at least one failure `PipelineEvent`.

### Allowed Execution Modes

- `single_paper`
- `batch`
- `stage_only`
- `testing`
- `backfill`
- `replay`

### Allowed Status Values

- `pending`
- `running`
- `succeeded`
- `failed`
- `partially_succeeded`
- `cancelled`

## 7. Lifecycle

### Created

Created before execution starts and before any event is emitted.

### Updated

Updated as execution starts, progresses, ends, fails, partially succeeds, or is
cancelled.

### Deleted

Not deleted under normal operation.

### Deprecated

Deprecated only by future contract version or run model migration.

## 8. Relationships

### Upstream Contracts

None.

### Downstream Contracts

- `PipelineEvent`
- `ArtifactManifest`

### References

- `PipelineEvent.run_id` -> `PipelineRun.run_id`
- `ArtifactManifest.run_id` -> `PipelineRun.run_id`

## 9. Operational Notes

Durable JSONL target:

```text
data/lake/pipeline_runs.jsonl
```

PostgreSQL stores paper-scoped stage attempts in `paper_pipeline_state`; it does
not duplicate complete `PipelineRun` records.

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Backward-compatible additions such as nullable fields, additional summary
counters, or additional execution modes.

### Major

Breaking schema changes, identity changes, status meaning changes, field
removals, or semantic meaning changes.
