---
id: VICTUS-PROCESSING-CONTRACTS
title: Victus Processing Contracts
status: source-of-truth
updated_at: 2026-06-06
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
  bibliography, PDF normalization, PDF processing, trimming, experiment mapping,
  and canonical evidence extraction.
- [Artifact Schemas](contracts/artifact-schemas.md): durable JSON/JSONL shapes
  consumed or produced by the current pipeline.
- [Block](contracts/block.md): durable identity, ordering, context, and field
  semantics for processed and final paper blocks.
- [Experiment Map](contracts/experiment-map.md): experiment-scope grouping
  contract generated from trimmed blocks.
- [Canonical Evidence](contracts/canonical-evidence.md): normalized evidence
  record contract generated from experiment packets.
- [Paper Classification](contracts/paper-classification.md): classifier input,
  classification output, and primary-research evidence gate.
- [Testing Pipeline](contracts/testing-pipeline.md): per-paper testing workspace,
  Markdown reuse behavior, and testing artifact guarantees.

## Contract Scope

Contracts cover:

- local runtime artifact boundaries;
- stage handoff locations;
- stable identity terms;
- block identity and field-level semantics;
- required validation expectations;
- compatibility boundaries between processing stages;
- config and environment resolution that affects paths or models;
- public CLI command names used by operators and agents;
- schema-level expectations for current durable artifacts;
- experiment map and canonical evidence schema expectations.
- paper classification gate expectations.
- testing workspace artifact expectations.

Contracts do not cover:

- implementation details;
- operational procedures;
- architecture rationale;
- external vendor guarantees.
- downstream analytics schemas outside this repository;
- deprecated downstream extraction contracts.

## Status Rule

All documentation with `status: source-of-truth` is authoritative for agents as
of `updated_at: 2026-06-06`. If code and docs disagree, stop and reconcile the
contract before making behavior-changing edits.

## Related Documents

- [System Context](000-SYSTEM-CONTEXT.md)
- [Architecture](100-ARCHITECTURE.md)
- [Operations](200-OPERATIONS.md)
