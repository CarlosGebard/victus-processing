---
id: VICTUS-CONTRACT-PIPELINE-EVENT
contract_id: victus.orchestration.pipeline_event
title: PipelineEvent
status: draft
version: v1
owner: victus-processing
domain: orchestration
contract_type: orchestration
stability: experimental
updated_at: 2026-06-19
---

# PipelineEvent Contract Documentation

## 1. Purpose

Define the canonical event record emitted by Victus processing stages.

`PipelineEvent` makes pipeline execution observable, auditable, debuggable, and
replayable. It records what happened during execution without storing scientific
payloads.

## 2. Identity

### Identity Rules

- Canonical identifier: `event_id`
- `event_id` is globally unique inside Victus.
- `event_id` is immutable after creation.
- Every event must reference one `run_id`.
- Events are append-only and must not be rewritten except through explicit
  migration tooling.

### Ownership

`PipelineEvent` is owned by `victus-processing`.

## 3. Schema

### JSON Schema

```json
{
  "event_id": "string",
  "run_id": "string",
  "timestamp": "datetime",
  "process_name": "string",
  "stage": "string",
  "event_type": "stage_started|stage_succeeded|stage_failed|artifact_created|artifact_validated|artifact_invalid|routing_decision|skipped|warning|retry_scheduled|retry_exhausted",
  "severity": "debug|info|warning|error|critical",
  "status": "started|succeeded|failed|skipped|warning",
  "paper_id": "string|null",
  "artifact_id": "string|null",
  "artifact_path": "string|null",
  "message": "string",
  "metadata": {}
}
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `event_id` | String | Unique identifier for the event. |
| `run_id` | String | Identifier of the parent PipelineRun. |
| `timestamp` | Datetime | Time when the event was emitted. |
| `process_name` | String | Name of the process that emitted the event. |
| `stage` | String | Coarser pipeline stage. |
| `event_type` | Enum | Machine-readable event type. |
| `severity` | Enum | Operational severity. |
| `status` | Enum | Simplified event outcome. |
| `paper_id` | String / Null | Paper affected by the event. |
| `artifact_id` | String / Null | Artifact affected by the event. |
| `artifact_path` | String / Null | Physical path for the artifact when relevant. |
| `message` | String | Short human-readable description. |
| `metadata` | Object | Small structured diagnostic payload. |

## 5. Responsibilities

### Required Responsibilities

`PipelineEvent` must record:

- which run emitted the event
- which process emitted the event
- which paper or artifact the event concerns
- what happened
- whether the event represents progress, success, warning, skip, or failure
- relevant paths or artifact identifiers
- compact diagnostic metadata

### Forbidden Responsibilities

`PipelineEvent` must not store:

- full PDF content
- full Markdown content
- full structured blocks
- full canonical evidence
- full raw LLM responses
- large stack traces
- embeddings
- scientific conclusions as payload

Large payloads must be stored as artifacts and referenced by path or artifact
identifier.

## 6. Validation Rules

- Required fields must be present.
- `event_id` must be unique and immutable.
- `run_id` must reference one `PipelineRun`.
- `event_type`, `severity`, and `status` must use allowed values.
- `message` must not be empty.
- `metadata` must be an object.
- Expected skips must not be emitted as failures.
- Events must be compact and append-only.

### Allowed Event Types

- `stage_started`
- `stage_succeeded`
- `stage_failed`
- `artifact_created`
- `artifact_validated`
- `artifact_invalid`
- `routing_decision`
- `skipped`
- `warning`
- `retry_scheduled`
- `retry_exhausted`

### Allowed Severity Values

- `debug`
- `info`
- `warning`
- `error`
- `critical`

### Allowed Status Values

- `started`
- `succeeded`
- `failed`
- `skipped`
- `warning`

## 7. Lifecycle

### Created

Created when a process emits an execution event.

### Updated

Events are append-only and should not be materially updated.

### Deleted

Not deleted under normal operation.

### Deprecated

Deprecated only by future contract version or event taxonomy migration.

## 8. Relationships

### Upstream Contracts

- `PipelineRun`

### Downstream Contracts

- `ArtifactManifest`

### References

- `PipelineEvent.run_id` -> `PipelineRun.run_id`
- `PipelineEvent.paper_id` -> `Paper.paper_id`
- `PipelineEvent.artifact_id` -> `ArtifactManifest.artifact_id`

## 9. Operational Notes

Durable JSONL target:

```text
data/lake/pipeline_events.jsonl
```

PostgreSQL stores lifecycle state in `paper_pipeline_state`; it does not
duplicate the full local event stream.

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Backward-compatible additions such as nullable fields, new event types, or
additional metadata guidance.

### Major

Breaking schema changes, identity changes, event meaning changes, field
removals, or semantic meaning changes.
