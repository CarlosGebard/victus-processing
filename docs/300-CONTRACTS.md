---
id: VICTUS-PROCESSING-CONTRACTS
title: Victus Processing Contracts
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
related_docs:
  - VICTUS-PROCESSING-SYSTEM-CONTEXT
  - VICTUS-PROCESSING-ARCHITECTURE
tags:
  - contracts
  - invariants
  - artifacts
---

# Contracts

This hub is the source of truth for stable guarantees that future changes must
preserve.

Contracts are high-trust documentation. Agents should treat them as
compatibility boundaries before changing paths, artifacts, identities, schemas,
or stage handoffs.

## Contract Documents

- [Data Layout](contracts/data-layout.md): stable local artifact locations,
  identities, stage inputs, stage outputs, and failure expectations.
- [Configuration and CLI](contracts/configuration-and-cli.md): config loading,
  environment precedence, CLI command surface, and public command guarantees.
- [Stage Handoffs](contracts/stage-handoffs.md): boundaries between metadata,
  bibliography, PDF normalization, PDF processing, and claims.
- [Artifact Schemas](contracts/artifact-schemas.md): durable JSON/JSONL shapes
  consumed or produced by the current pipeline.
- [Claims Schema](contracts/claims-schema.md): required claim fields, field
  semantics, allowed values, and validation expectations.

## Contract Scope

Contracts cover:

- local runtime artifact ownership;
- stage handoff locations;
- stable identity terms;
- required validation expectations;
- compatibility boundaries between processing stages;
- config and environment resolution that affects paths or models;
- public CLI command names used by operators and agents;
- schema-level expectations for current durable artifacts;
- claim extraction schema and field-level semantics.

Contracts do not cover:

- implementation details;
- operational procedures;
- architecture rationale;
- external vendor guarantees.
- downstream analytics schemas outside this repository.

## Status Rule

All documentation with `status: source-of-truth` is authoritative for agents as
of `updated_at: 2026-05-27`. If code and docs disagree, stop and reconcile the
contract before making behavior-changing edits.

## Related Documents

- [System Context](000-SYSTEM-CONTEXT.md)
- [Architecture](100-ARCHITECTURE.md)
- [Operations](200-OPERATIONS.md)
