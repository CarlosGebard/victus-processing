---
id: VICTUS-PROCESSING-ARCHITECTURE
title: Victus Processing Architecture
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
related_docs:
  - VICTUS-PROCESSING-SYSTEM-CONTEXT
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-OPERATIONS
tags:
  - architecture
  - batch-processing
  - artifact-pipeline
---

# Architecture

## 1. Architectural Overview

`victus-processing` is a local, file-oriented batch-processing pipeline exposed
through a Python CLI.

The system shape is:

```text
CLI command
  -> domain stage
  -> local artifacts under data/
  -> optional external API call
  -> next stage input
```

The architecture favors explicit stage boundaries and durable local artifacts.
Each stage can be inspected independently because handoffs are represented by
files, not hidden in memory or remote services.

## 2. Major Components

### CLI Router

- **Path:** `src/cli.py`
- **Responsibility:** public command surface and command routing.
- **Inputs:** user arguments.
- **Outputs:** invoked stage behavior and CLI status output.
- **Dependencies:** domain modules.
- **Boundary:** owns command grouping, not stage internals.

### Workspace Configuration

- **Path:** `src/workspace/`
- **Responsibility:** repository paths, config loading, `.env` loading, and
  canonical data layout helpers.
- **Inputs:** `config/*.yaml`, optional `config.yaml`, environment variables.
- **Outputs:** resolved paths and runtime constants.
- **Dependencies:** local filesystem.
- **Boundary:** owns resolution, not business processing.

### Metadata Stage

- **Path:** `src/metadata/`
- **Responsibility:** discover, fetch, classify, and store paper metadata
  candidates.
- **Inputs:** seed DOI queues, DOI arguments, Semantic Scholar responses.
- **Outputs:** metadata JSON, reviewed indexes, discarded indexes.
- **Dependencies:** Semantic Scholar API, OpenAI metadata selection.
- **Boundary:** owns pre-PDF candidate state.

### PDF Extraction and Normalization

- **Path:** `src/pdf_extraction/`
- **Responsibility:** generate bibliography outputs and normalize raw PDFs into
  active pipeline inputs.
- **Inputs:** metadata records, relation CSV files, raw PDFs.
- **Outputs:** BibTeX artifacts and active PDFs.
- **Dependencies:** local filesystem.
- **Boundary:** owns conversion into PDF-processing inputs.

### PDF Processing Stage

- **Path:** `src/pdf_processing/`
- **Responsibility:** convert active PDFs into Markdown, split Markdown into
  batches, call Gemini, validate batch outputs, and merge structured paper JSON.
- **Inputs:** active PDFs, prompt files, PDF-processing config.
- **Outputs:** Markdown, raw batch JSON, merged structured paper JSON, status.
- **Dependencies:** Docling, Gemini API, SQLite quota state.
- **Boundary:** owns post-PDF structured paper artifacts.

### Claims Stage

- **Path:** `src/claims/`
- **Responsibility:** extract validated empirical claims from structured paper
  JSON.
- **Inputs:** structured paper JSON, claim prompt, model configuration.
- **Outputs:** model-specific claims JSON.
- **Dependencies:** OpenAI API.
- **Boundary:** owns claim extraction outputs, not downstream analytics.

### Prompt Assets

- **Path:** `src/prompts/`
- **Responsibility:** store model instructions used by LLM-mediated stages.
- **Inputs:** repository-authored prompt text.
- **Outputs:** prompt content consumed by metadata, PDF-processing, and claims.
- **Dependencies:** none.
- **Boundary:** prompts shape behavior but do not execute stages directly.

## 3. System Boundaries

Internal boundaries:

- CLI routing is separated from stage execution.
- Configuration/path resolution is separated from processing logic.
- Metadata is pre-PDF state.
- PDF-processing is post-PDF structured extraction.
- Claims are downstream derived outputs.
- Prompts are separate artifacts consumed by model-mediated stages.

External boundaries:

- Semantic Scholar provides metadata and citation graph data.
- OpenAI provides metadata-selection and claim-extraction model responses.
- Gemini provides structured extraction from Markdown batches.
- Optional Victus bridge integrations are outside the core local pipeline.
- Analytics, RAG indexing, vector stores, and production deployment are outside
  this repository.

## 4. Runtime Flow

High-level runtime sequence:

```text
seed DOI or DOI argument
  -> metadata stage
  -> metadata candidate artifacts
  -> raw PDF availability
  -> PDF normalization
  -> active PDF
  -> PDF processing
  -> structured paper JSON
  -> claims extraction
  -> claims JSON
```

The CLI is the orchestrating boundary. It does not run every stage
automatically; operators and agents select the stage to execute.

## 5. Artifact or Data Flow

Main artifact movement:

```text
data/inputs/
  -> data/runtime/01-candidates/
  -> data/runtime/02-pdfs/active/
  -> data/runtime/03-pdf_processing/
  -> data/runtime/04-claims_by_model/
```

Artifact roles:

- `data/inputs/`: seed queues, rules, and imports.
- `data/runtime/01-candidates/`: pre-PDF metadata state.
- `data/runtime/02-pdfs/active/`: normalized PDFs ready for processing.
- `data/runtime/03-pdf_processing/`: Markdown, raw batches, merged paper JSON,
  and processing status.
- `data/runtime/04-claims_by_model/`: extracted claims grouped by model.
- `data/runtime/quotas/`: Gemini quota and cooldown state.

Detailed path, handoff, configuration, CLI, and schema contracts live in
[Contracts](300-CONTRACTS.md).

## 6. Quality Attributes

- **Inspectability:** stage state is visible as local files.
- **Reproducibility:** commands consume stable inputs and write stable outputs.
- **Recoverability:** stages can resume from existing artifacts and status.
- **Operational transparency:** expensive model-mediated stages are explicit.
- **Composability:** stages can be run independently or chained by operators.
- **Local-first execution:** the core workflow does not require deployment
  infrastructure.
- **Agent readability:** docs, prompts, config, and artifacts are discoverable
  without requiring hidden service context.

## 7. External Dependencies

- **Semantic Scholar API:** metadata and citation exploration.
- **OpenAI API:** metadata selection and claim extraction.
- **Gemini API:** structured extraction from Markdown batches.
- **Docling:** local PDF-to-Markdown conversion.
- **SQLite:** local Gemini key scheduling and quota persistence.
- **Local filesystem:** primary durable state store.
- **Optional Victus infrastructure:** bridge-facing registry, object storage,
  events, Postgres, Redis, or S3-compatible services.

## 8. Documentation Links

- [System Context](000-SYSTEM-CONTEXT.md)
- [Contracts](300-CONTRACTS.md)
- [Operations](200-OPERATIONS.md)
- [CLI operations](operations/cli.md)
- [PDF processing operations](operations/pdf-processing.md)
- [Runbooks](operations/runbooks/)
