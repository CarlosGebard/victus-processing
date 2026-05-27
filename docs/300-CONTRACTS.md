---
id: VICTUS-PROCESSING-CONTRACTS
title: Victus Processing Contracts
status: draft
updated_at: 2026-05-26
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

This hub defines stable guarantees that future changes must preserve.

Contracts are high-trust documentation. Agents should treat them as
compatibility boundaries before changing paths, artifacts, identities, schemas,
or stage handoffs.

## Contract Documents

- [Data Layout](contracts/data-layout.md): stable local artifact locations,
  identities, stage inputs, stage outputs, and failure expectations.

## Contract Scope

Contracts cover:

- local runtime artifact ownership;
- stage handoff locations;
- stable identity terms;
- required validation expectations;
- compatibility boundaries between processing stages.

Contracts do not cover:

- implementation details;
- operational procedures;
- architecture rationale;
- external vendor guarantees.

## Related Documents

- [System Context](000-SYSTEM-CONTEXT.md)
- [Architecture](100-ARCHITECTURE.md)
- [Operations](200-OPERATIONS.md)
