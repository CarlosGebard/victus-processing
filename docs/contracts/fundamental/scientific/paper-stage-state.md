---
id: victus.scientific.paper_stage_state
title: PaperStageState
version: v1
status: draft
owner: victus-processing
updated_at: 2026-06-19
---

# PaperStageState Contract Documentation

## Purpose

`PaperStageState` stores the current operational state for one paper in one
pipeline stage.

It is the local current-state model. It is not the event history or the
PostgreSQL operational contract.

## Storage

Local durable write:

```text
data/lake/paper_stage_state.jsonl
```

## Identity

There must be one current state per:

- `paper_id`
- `stage`

Local JSONL may contain multiple records for the same key. Consumers must treat
the latest record as current.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `paper_id` | String | Yes | Paper identifier. |
| `stage` | String | Yes | Strict pipeline stage name. |
| `status` | String | Yes | Current stage status. |
| `run_id` | String | No | Latest run that updated this state. |
| `artifact_id` | String | No | Primary artifact linked to this state. |
| `artifact_path` | String | No | Storage path or URI for the primary artifact. |
| `error_code` | String | No | Compact machine-readable failure code. |
| `error_message` | String | No | Compact operator-readable failure summary. |
| `attempt_count` | Integer | Yes | Number of attempts observed for this paper/stage. |
| `updated_at` | Timestamp | Yes | Last state transition timestamp. |

## Allowed Status Values

- `pending`
- `running`
- `succeeded`
- `failed`
- `skipped`
- `blocked`

## Guarantees

- `PipelineEvent` remains the immutable history.
- `PaperStageState` is the current-state index.
- State updates must not embed large payloads.
- Large debug payloads, extracted content, model inputs, and model outputs must
  stay in filesystem or object storage and be referenced by path.

PostgreSQL lifecycle state is defined separately by `paper_pipeline_state`.
