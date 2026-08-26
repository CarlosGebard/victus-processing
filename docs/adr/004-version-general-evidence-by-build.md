---
id: ADR-004
title: Version GeneralEvidence by corpus build
status: accepted
updated_at: 2026-06-19
owners:
  - victus-processing
related_docs:
  - docs/contracts/local/evidence-derivation-storage.md
---

# Version GeneralEvidence by Corpus Build

## Context

GeneralEvidence aggregates support across papers. Per-paper derivation cannot
produce valid corpus-level paper counts or consensus, and replacing rows in
place would make prior results irreproducible.

## Decision

Directory derivation creates one corpus build. `build_id` participates in
EvidenceProjection and GeneralEvidence identities, and all rows for one build
are persisted atomically. Single-paper derivation remains available as a
one-paper build.

## Tradeoffs

- Builds are reproducible and may coexist.
- Re-running the same build replaces that build atomically.
- Storage grows with retained builds.
- Registry concepts remain stable across builds and are upserted independently.

## Consequences

Consumers must select a build explicitly when comparing or exporting derived
evidence. RAG export remains a generated JSON artifact rather than a table.

