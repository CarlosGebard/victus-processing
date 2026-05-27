---
id: VICTUS-PROCESSING-SYSTEM-CONTEXT
title: Victus Processing System Context
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
---

# System Context

## 1. Purpose

`victus-processing` exists to turn scientific-paper inputs into local,
inspectable processing artifacts for the Victus ecosystem.

It owns the local workflow from paper metadata and PDFs to structured paper
outputs and extracted claims. The repository is optimized for reproducible
batch processing, explicit artifact ownership, and agent-readable documentation.

## 2. System Goals

- Keep paper-processing stages explicit and reproducible.
- Preserve stable local artifacts between stages.
- Make repository boundaries clear for humans and AI agents.
- Prefer operationally simple workflows over hidden orchestration.
- Keep model-mediated outputs traceable to inputs, prompts, and configuration.
- Separate onboarding, architecture, operations, contracts, and decisions.

Non-goals:

- serve analytics products;
- host RAG/vector indexing;
- own deployment infrastructure;
- replace external paper retrieval services;
- guarantee external API availability or model behavior.

## 3. Repository Scope

This repository owns:

- `victus-processing` CLI commands;
- local `data/` runtime layout;
- metadata discovery and candidate state;
- PDF normalization into active processing inputs;
- Docling/Gemini PDF-processing artifacts;
- OpenAI claim extraction outputs;
- local contracts for artifacts, paths, and stage handoffs.

This repository does not own:

- analytics dashboards or downstream products;
- production infrastructure;
- vector stores or query-serving systems;
- external PDF download services;
- external vendor billing, limits, or uptime.

## 4. Documentation Map

Primary hubs:

- [Architecture](100-ARCHITECTURE.md): system design, components, data architecture,
  quality attributes, decisions, and invariants.
- [Operations](200-OPERATIONS.md): configuration, daily commands, validation,
  troubleshooting, and rollback notes.
- [Contracts](300-CONTRACTS.md): storage paths, environment variables, data layout,
  and identity contracts.
- [Contract details](contracts/): source-of-truth contracts for data layout,
  configuration/CLI, stage handoffs, artifact schemas, and claims schema.
- [CLI operations](operations/cli.md): command groups and common command flow.
- [PDF processing operations](operations/pdf-processing.md): runtime details
  specific to PDF-processing flow.
- [Runbooks](operations/runbooks/): task-specific operational procedures.

Planned documentation structure:

- `000-SYSTEM-CONTEXT.md`: repository orientation and documentation map.
- `100-ARCHITECTURE.md`: architecture hub.
- `200-OPERATIONS.md`: operations hub.
- `300-DECISIONS.md`: decisions hub.
- module folders under `docs/`: deeper focused documentation.

## 5. Core Concepts

- **Paper:** scientific publication processed by the pipeline.
- **Metadata candidate:** pre-PDF paper record discovered or fetched by DOI.
- **Document ID:** identity used before a PDF is normalized.
- **Paper ID:** identity used for post-PDF processing artifacts.
- **Stage:** explicit processing step invoked by CLI command.
- **Artifact:** durable file produced or consumed by a stage.
- **Active PDF:** normalized PDF ready for PDF processing.
- **Structured paper JSON:** merged extracted paper representation.
- **Claim:** validated empirical statement extracted from structured paper JSON.
- **Runtime layout:** local directory structure under `data/`.
- **Bridge:** optional integration surface for Victus infrastructure.

## 6. Repository Structure

```text
src/        -> pipeline code and CLI implementation
config/     -> runtime defaults and stage configuration
docs/       -> system, architecture, operations, and contract documentation
tests/      -> validation for CLI, prompts, and processing behavior
ops/        -> operational helper scripts
data/       -> local runtime artifacts, ignored or environment-specific
```

## 7. Design Principles

- **Explicit stages:** processing should be visible through commands and files.
- **Stable artifacts:** stage handoffs should use predictable paths and names.
- **Low hidden state:** important state should be inspectable on disk.
- **Restartable workflow:** interrupted runs should resume from existing outputs.
- **Contract-first docs:** paths, identities, and invariants must be documented.
- **Agent-safe navigation:** docs should tell agents where to look before code.
- **Separation of concerns:** README, context, architecture, operations,
  contracts, and decisions each have distinct jobs.
