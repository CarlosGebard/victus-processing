---
id: VICTUS-CONTRACT-PAPER-PROCESSING-STATE
contract_id: victus.scientific.paper_processing_state
title: PaperProcessingState
status: active
version: v1
owner: victus-processing
domain: scientific
contract_type: operational-state
stability: foundation
updated_at: 2026-06-13
---

# PaperProcessingState Contract Documentation

## 1. Purpose

`PaperProcessingState` is the current operational dashboard row for one paper.

It answers what exists, what has succeeded, what should run next, and whether a
paper is ready for export.

## 2. Identity

### Identity Rules

- Canonical identifier: `paper_id`.
- One current row exists per paper.
- The row is mutable and reflects the latest refresh.
- Runtime file paths must not be used as processing-state identity.

### Ownership

`PaperProcessingState` is owned by `victus-processing`.

## 3. Schema

```sql
CREATE TABLE paper_processing_state (
    paper_id TEXT PRIMARY KEY,
    overall_status TEXT NOT NULL,
    current_stage TEXT NOT NULL,
    last_successful_stage TEXT,
    next_stage TEXT,
    active_pipeline_run_id TEXT,
    pipeline_version TEXT NOT NULL,
    config_hash TEXT,
    is_processable BOOLEAN NOT NULL DEFAULT TRUE,
    is_complete BOOLEAN NOT NULL DEFAULT FALSE,
    is_ready_for_export BOOLEAN NOT NULL DEFAULT FALSE,
    is_exported BOOLEAN NOT NULL DEFAULT FALSE,
    blocked_reason TEXT,
    last_error_code TEXT,
    last_error_message TEXT,
    locked_by TEXT,
    locked_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `paper_id` | Text | Paper identifier used across artifacts and scientific tables. |
| `overall_status` | Text | Current aggregate status for the paper. |
| `current_stage` | Text | Stage currently required or represented by the row. |
| `last_successful_stage` | Text, nullable | Last stage known to have completed successfully. |
| `next_stage` | Text, nullable | Next stage an operator should run. |
| `active_pipeline_run_id` | Text, nullable | Optional active run id when a runner owns the paper. |
| `pipeline_version` | Text | Processing version used to derive the row. |
| `config_hash` | Text, nullable | Optional config hash for the current processing context. |
| `is_processable` | Boolean | Whether the paper has enough inputs to continue. |
| `is_complete` | Boolean | Whether processing is complete for v1. |
| `is_ready_for_export` | Boolean | Whether downstream CSV/Parquet export can consume the paper. |
| `is_exported` | Boolean | Whether export has been marked complete. |
| `blocked_reason` | Text, nullable | Human-readable reason the paper cannot continue. |
| `last_error_code` | Text, nullable | Last machine-readable error code. |
| `last_error_message` | Text, nullable | Last human-readable error message. |
| `locked_by` | Text, nullable | Optional worker lock owner. |
| `locked_until` | Timestamptz, nullable | Optional worker lock expiry. |
| `created_at` | Timestamptz | Row creation timestamp. |
| `updated_at` | Timestamptz | Last refresh timestamp. |

## 5. Responsibilities

### Required Responsibilities

`PaperProcessingState` must:

- reflect physical inputs under `data/artifacts`;
- reflect processed outputs from PostgreSQL scientific tables;
- identify the next missing processing stage;
- support CSV/Parquet operational dashboards;
- remain cheap to refresh.

### Forbidden Responsibilities

`PaperProcessingState` must not:

- store StructuredBlock or CanonicalEvidence payloads;
- infer scientific meaning;
- use runtime directories as source of truth;
- replace the scientific output tables;
- store full run event history.

## 6. Validation Rules

- `paper_id`, `overall_status`, `current_stage`, and `pipeline_version` are required.
- `next_stage` must be null when `is_complete=true`.
- `is_ready_for_export=true` requires either completed evidence extraction or a
  terminal non-primary classification.
- `is_processable=false` requires `blocked_reason`.

### Allowed Stage Values

- `input.discovery`
- `pdf.markdown`
- `pdf.process`
- `classification.classify`
- `evidence.map`
- `evidence.extract`
- `export.ready`

## 7. Lifecycle

### Created

Created by `victus-processing processing-state refresh`.

### Updated

Updated by refresh after inputs or PostgreSQL scientific output tables change.

### Deleted

Rows are not deleted under normal operation.

## 8. Relationships

### Upstream Contracts

- `Paper`
- `StructuredBlock`
- `PaperClassification`
- `ExperimentMap`
- `CanonicalEvidence`

### Downstream Contracts

- CSV and Parquet exports.

### References

- `paper_processing_state.paper_id` logically references paper ids present in
  inputs or scientific output tables.

## 9. Operational Notes

Refresh command:

```bash
uv run victus-processing processing-state refresh --csv data/reports/exports/paper_processing_state.csv
```
