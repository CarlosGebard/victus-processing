---
id: VICTUS-CONTRACT-PAPER-PROCESSING-STATE
contract_id: victus.scientific.paper_processing_state
title: PaperProcessingState
status: active
version: v1
owner: victus-processing
domain: orchestration
contract_type: operational-state
stability: foundation
updated_at: 2026-06-19
---

# PaperProcessingState

## Purpose

`paper_processing_state` is the derived PostgreSQL dashboard row for one paper.
It answers what exists, what should run next, and whether the paper is complete
or ready for export.

## Identity

`paper_id` is the primary key. Exactly one mutable row exists per paper.

## Fields

| Field | Type | Description |
|---|---|---|
| `paper_id` | Text | Paper identifier. |
| `overall_status` | Text | Aggregate processing status. |
| `current_stage` | Text | Current or required stage. |
| `last_successful_stage` | Text, nullable | Last completed stage. |
| `next_stage` | Text, nullable | Next operator action. |
| `is_processable` | Boolean | Whether required inputs exist. |
| `is_complete` | Boolean | Whether the applicable processing path is complete. |
| `is_ready_for_export` | Boolean | Whether downstream export may consume the paper. |
| `is_exported` | Boolean | Whether export is marked complete. |
| `blocked_reason` | Text, nullable | Reason processing cannot continue. |
| `last_error_code` | Text, nullable | Latest compact error code. |
| `last_error_message` | Text, nullable | Latest operator-readable error. |
| `has_pdf` | Boolean | Whether the normalized PDF exists. |
| `has_markdown` | Boolean | Whether Markdown exists. |
| `has_structured_paper` | Boolean | Whether the structured paper row exists. |
| `has_structured_blocks` | Boolean | Whether structured block rows exist. |
| `has_paper_classification` | Boolean | Whether a classification row exists. |
| `has_experiment_map` | Boolean | Whether an experiment map exists. |
| `has_canonical_evidence` | Boolean | Whether canonical evidence exists. |
| `paper_family` | Text, nullable | Latest paper family. |
| `updated_at` | Timestamptz | Last projection refresh. |

## Responsibilities

The row must remain cheap to rebuild from filesystem inputs, scientific tables,
and `paper_pipeline_state`. It must not store scientific payloads, attempt
history, complete events, prompts, or model responses.

## Validation

- `paper_id`, `overall_status`, `current_stage`, and `updated_at` are required.
- `next_stage` must be null when `is_complete` is true.
- `is_ready_for_export` requires completed evidence extraction or a terminal
  non-primary classification.
- `is_processable=false` requires `blocked_reason`.

## Lifecycle

`victus-processing processing-state refresh` upserts rows. Rows may be rebuilt
at any time and are not deleted during normal operation.

## Relationships

The projection reads `paper_pipeline_state`, `structured_papers`,
`structured_blocks`, `paper_classifications`, `experiment_maps`, and
`canonical_evidence` through logical `paper_id` relationships.

## Schema

The executable schema is
[`ops/sql/005_simplified_postgres_schema.sql`](../../../../ops/sql/005_simplified_postgres_schema.sql).
