---
id: VICTUS-PROCESSING-CONTRACTS
title: Victus Processing Contracts
status: source-of-truth
updated_at: 2026-06-19
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
- `docs/contracts/local/`: repository-specific contracts owned here.

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
- [Metadata Extraction](operations/pipeline/metadata-extraction.md): operation, LLM selection
  contract, `paper_metadata.jsonl` schema, and dedupe rules.
- [Stage Handoffs](contracts/local/stage-handoffs.md): boundaries between
  metadata, bibliography export, manual PDF intake, PDF processing, trimming,
  experiment mapping, and canonical evidence extraction.
- [Artifact Schemas](contracts/local/artifact-schemas.md): durable JSON/JSONL
  shapes consumed or produced by the current pipeline.
- [Artifact Inventory](contracts/local/artifact-inventory.md): complete artifact
  list with the inputs consumed to create each artifact.
- [Paper Pipeline State](contracts/local/paper-pipeline-state.md): PostgreSQL
  lifecycle state for one paper stage attempt.
- [Paper Processing State](contracts/fundamental/scientific/paper-processing-state.md): derived
  PostgreSQL dashboard state by paper.

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
- schema-level expectations for current durable artifacts and PostgreSQL state;
- experiment map and canonical evidence schema expectations.
- paper classification gate expectations.
- testing workspace artifact expectations.

Contracts do not cover:

- implementation details;
- operational procedures;
- architecture rationale;
- external vendor guarantees.
- downstream analytics schemas outside this repository.

## Status Rule

Documentation with `status: source-of-truth` is authoritative as of its own
`updated_at` value. If code and docs disagree, stop and reconcile the contract
before making behavior-changing edits.

## Related Documents

- [System Context](000-SYSTEM-CONTEXT.md)
- [Architecture](100-ARCHITECTURE.md)
- [Operations](200-OPERATIONS.md)
