---
id: ADR-005
title: PostgreSQL-only evidence extraction
status: accepted
updated_at: 2026-06-19
owners:
  - victus-processing
related_docs:
  - docs/100-ARCHITECTURE.md
  - docs/operations/pipeline/evidence-extraction.md
---

# PostgreSQL-only Evidence Extraction

## Context

Evidence extraction previously preferred PostgreSQL inputs when enabled but
still accepted `paper.processed.json`, wrote intermediate and final JSON files,
and degraded database failures to a local outbox. This created two possible
sources of truth.

## Decision

Evidence extraction requires PostgreSQL. It reads `structured_papers`, keeps
classifier inputs, trimmed blocks, and experiment packets in memory, and writes
classifications, experiment maps, canonical evidence, and derived evidence to
the existing scientific-output tables. Persistence failures fail the command.

## Tradeoffs

- PostgreSQL becomes an operational prerequisite.
- Runtime evidence JSON is no longer available for inspection or recovery.
- Reruns use persisted rows and deterministic identifiers.
- PDF and Markdown artifacts remain filesystem-backed because the current
  schema does not represent them.

## Alternatives Considered

- Dual-write files and PostgreSQL: rejected because it preserves ambiguous
  authority and synchronization failure modes.
- Add tables for PDF and Markdown artifacts: rejected as outside this change
  and incompatible with the constraint to use current tables.

## Consequences

The evidence CLI no longer accepts filesystem input/output options. Operators
must enable PostgreSQL and use `--paper-id` for a targeted run. Database errors
are immediately visible and no scientific-output outbox is written locally.

## Related Documents

- [Architecture](../100-ARCHITECTURE.md)
- [Evidence extraction operations](../operations/pipeline/evidence-extraction.md)
