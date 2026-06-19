---
id: ADR-003
title: Simplify PostgreSQL pipeline state
status: accepted
updated_at: 2026-06-19
owners:
  - victus-processing
related_docs:
  - docs/postgres-schema.mermaid.md
  - docs/operations/runbooks/postgres-pipeline-records.md
---

# Simplify PostgreSQL Pipeline State

## Context

PostgreSQL duplicated operational facts across run, event, stage-state, artifact,
and trimmed-block tables. The pipeline already retains detailed run events and
artifact manifests as local JSON artifacts, while scientific query consumers
need stable output rows and a fast per-paper state projection.

## Decision

PostgreSQL stores one `paper_pipeline_state` row per paper, run, stage, and
attempt; `paper_processing_state` remains the current-state projection.
Scientific outputs remain separate tables. Trimmed evidence blocks are derived
from the structured paper and are not persisted. Local run/event and artifact
records remain the detailed operational source.

The transition resets every PostgreSQL pipeline table except
`structured_papers`, whose rows are preserved because rebuilding them is
expensive.

## Tradeoffs

- PostgreSQL becomes simpler to query and operate.
- Detailed event history remains local rather than relational.
- Applying the reset migration discards non-structured-paper PostgreSQL data.
- Post-structure stages must rerun to repopulate scientific outputs.

## Alternatives Considered

Keeping and backfilling all legacy tables was rejected because their duplicated
roles are the source of the operational complexity. Persisting trimmed blocks
as a second block table was rejected because trimming is deterministic.

## Consequences

New PostgreSQL integrations must use `paper_pipeline_state`; they must not add
writes to the removed tables. A future object-storage requirement may justify a
focused storage manifest, but the former generic artifact registry is not the
default.

## Related Documents

- [PostgreSQL schema](../postgres-schema.mermaid.md)
- [PostgreSQL runbook](../operations/runbooks/postgres-pipeline-records.md)
