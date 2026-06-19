---
id: VICTUS-CONTRACT-PAPER-PIPELINE-STATE
title: Paper Pipeline State
status: source-of-truth
version: v1
owner: victus-processing
contract_type: database
updated_at: 2026-06-19
---

# Paper Pipeline State

## Purpose

`paper_pipeline_state` stores the latest lifecycle state for one paper stage
attempt. Detailed events remain in local `pipeline_events.jsonl`.

## Identity

- Primary key: `pipeline_state_id`, derived from the stage-attempt identity.
- `(paper_id, run_id, stage, attempt_number)` must be unique.

## Required Responsibilities

- Record stage status, attempt number, run context, timestamps, compact errors,
  and an optional artifact path.
- Support derivation of `paper_processing_state`.

## Forbidden Responsibilities

- It must not store complete event history, scientific payloads, prompts, model
  responses, PDFs, or Markdown.

## Validation

- `paper_id`, `stage`, `run_id`, pipeline metadata, and `updated_at` are required.
- `attempt_number` must be greater than zero.
- Status must be `pending`, `running`, `succeeded`, `failed`, `skipped`,
  `blocked`, or `warning`.
- Terminal attempts may set `ended_at`; the first start sets `started_at`.

## Lifecycle

Lifecycle events and explicit stage-state updates upsert the same attempt row.
Rows are rebuilt only by an explicitly destructive schema reset.

## Relationships

`paper_processing_state` summarizes these rows by `paper_id`. Scientific tables
use logical paper identifiers rather than foreign keys to this operational
table.

## Schema

The executable schema is
[`ops/sql/005_simplified_postgres_schema.sql`](../../../ops/sql/005_simplified_postgres_schema.sql).

