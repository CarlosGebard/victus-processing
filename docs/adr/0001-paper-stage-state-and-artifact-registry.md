# 0001. Paper Stage State And Artifact Registry

Date: 2026-06-10

## Status

Accepted

## Context

The pipeline needs auditability and current operational queries without turning
the event stream into mutable state.

Large artifacts are stored in filesystem or S3-like storage. Local JSONL is the
first durable write. PostgreSQL is an optional operational index and registry.

## Decision

- `PipelineRun` records executions.
- `PipelineEvent` records immutable history.
- `PaperStageState` records current state per `(paper_id, stage)`.
- `ArtifactRegistry` is the canonical global index of produced artifacts.
- `artifact_manifest.jsonl` remains a local manifest by run.
- PostgreSQL stores compact indexes and registry records only.
- Storage holds large artifacts and payloads.
- Local JSONL remains the v1 durable write.
- PostgreSQL dual-write failures write local outbox records and do not
  automatically fail the pipeline.

## Consequences

- Operators query current state from `paper_stage_states`, not events.
- Operators audit history from `pipeline_events`.
- Replay can repair PostgreSQL after transient failures.
- No workers, queues, daemons, or extra infrastructure are required for v1.
