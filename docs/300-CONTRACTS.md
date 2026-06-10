---
id: VICTUS-PROCESSING-CONTRACTS
title: Victus Processing Contracts
status: source-of-truth
updated_at: 2026-06-10
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

## Contract Layout

Contracts are split by source and responsibility:

- `docs/contracts/fundamental/`: ecosystem-level contracts synchronized from
  `victus-docs`. These define shared Victus interfaces and preserve the central
  contract repository subdirectory layout.
- `docs/contracts/local/`: repository-local contracts maintained here. These
  define how `victus-processing` implements, stores, validates, and operates
  around the shared interfaces.

## Fundamental Contracts

- [Paper](contracts/fundamental/scientific/paper.md)
- [Structured Block](contracts/fundamental/scientific/structured-block.md)
- [Paper Classification](contracts/fundamental/scientific/paper-classification.md)
- [Experiment Map](contracts/fundamental/scientific/experiment-map.md)
- [Canonical Evidence](contracts/fundamental/scientific/canonical-evidence.md)
- [Pipeline Run](contracts/fundamental/scientific/pipeline-run.md)
- [Pipeline Event](contracts/fundamental/scientific/pipeline-event.md)
- [Storage Layout](contracts/fundamental/processing/README.md)
- [Artifact Manifest](contracts/fundamental/scientific/artifact-manifest.md)
- [Contracts Lock](contracts/fundamental/contracts.lock.json)

## Local Contracts

- [Data Layout](contracts/local/data-layout.md): stable local artifact
  locations, identities, stage inputs, stage outputs, and failure expectations.
- [Configuration and CLI](contracts/local/configuration-and-cli.md): config
  loading, environment precedence, CLI command surface, and public command
  guarantees.
- [Stage Handoffs](contracts/local/stage-handoffs.md): boundaries between
  metadata, bibliography, PDF normalization, PDF processing, trimming,
  experiment mapping, and canonical evidence extraction.
- [Artifact Schemas](contracts/local/artifact-schemas.md): durable JSON/JSONL
  shapes consumed or produced by the current pipeline.
- [Artifact Inventory](contracts/local/artifact-inventory.md): complete artifact
  list with the inputs consumed to create each artifact.
- [Testing Pipeline](contracts/local/testing-pipeline.md): per-paper testing
  workspace, Markdown reuse behavior, and testing artifact guarantees.

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
of `updated_at: 2026-06-10`. If code and docs disagree, stop and reconcile the
contract before making behavior-changing edits.

## Related Documents

- [System Context](000-SYSTEM-CONTEXT.md)
- [Architecture](100-ARCHITECTURE.md)
- [Operations](200-OPERATIONS.md)
