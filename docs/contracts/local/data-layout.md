---
id: VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
title: Victus Processing Data Layout Contract
status: source-of-truth
updated_at: 2026-06-11
related_components:
  - src.workspace.config
  - src.workspace.data_layout
  - src.workspace.runs
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - contracts
  - data-layout
  - storage
---

# Data Layout Contract

## 1. Purpose

This contract governs local filesystem layout for `victus-processing`.

The layout follows the fundamental processing contract and separates canonical
datasets, physical artifacts, run state, debug payloads, registries, and testing
runs.

## 2. Scope

Covered:

- local `data/` directories;
- canonical JSONL lake files;
- physical PDF and Markdown artifact locations;
- run-scoped runtime and debug files;
- registry JSONL files;
- testing run isolation.

Not covered:

- PostgreSQL DDL;
- object-store bucket layout;
- prompt text;
- downstream RAG or analytics storage.

## 3. Canonical Layout

```text
data/
  inputs/
    seeds/
      seed_dois.jsonl
      explored_seed_dois.jsonl
    generated_seed_dois/
      candidates_seed_dois.jsonl

  lake/
    paper_metadata.jsonl
    paper_candidates.jsonl
    paper_pdf_links.jsonl
    structured_blocks.jsonl
    paper_classifications.jsonl
    experiment_maps.jsonl
    experiment_packets.jsonl
    canonical_evidence.jsonl
    pipeline_runs.jsonl
    pipeline_events.jsonl
    paper_stage_state.jsonl

  artifacts/
    intake/
      pdfs/
    pdfs/
      {paper_id}.pdf
    markdown/
      {paper_id}.md
    victus-data/
      papers/{paper_id}/original.pdf
      markdown/{paper_id}/paper.md
      structured-blocks/{paper_id}/blocks.json
      paper-classification/{paper_id}/classification.json
      experiment-maps/{paper_id}/experiment_map.json
      evidence-packets/{paper_id}/evidence_packets.json
      canonical-evidence/{paper_id}/canonical_evidence.json
    victus-ops/
      runs/{run_id}/run.json
      events/{run_id}/events.jsonl
      manifests/{run_id}/manifest.json
      errors/{run_id}/errors.jsonl
      debug/{run_id}/{paper_id}/...

  runtime/
    runs/
      {run_id}/
        manifest.json
        errors.jsonl
    outbox/
      postgres_pipeline_records.jsonl

  debug/
    runs/
      {run_id}/
        {paper_id}/
          raw_batches.jsonl
          failed_batches.jsonl
          classifier_input.json

  registry/
    artifact_manifest.jsonl
    artifact_registry.jsonl
    documents.jsonl
    links.jsonl

  testing/
    runs/
      {run_id}/
        manifest.json
        outputs/
        debug/
```

## 4. Guarantees

- `data/lake/` stores canonical local JSONL datasets.
- `data/lake/paper_metadata.jsonl` is the canonical metadata index and dedupe
  source for metadata exploration reruns.
- `data/artifacts/intake/pdfs/` is a manual staging area for PDFs obtained
  outside this repository.
- `data/lake/paper_pdf_links.jsonl` stores the append-only metadata-to-PDF
  links created during manual PDF intake.
- `data/artifacts/` stores physical payloads such as PDFs and Markdown.
- `data/artifacts/victus-data/` stores one primary file per paper per stage for
  this phase; do not introduce raw/bronze/silver/gold tiers yet.
- `data/artifacts/victus-ops/` stores compact operational artifacts by run when
  filesystem storage is used instead of object storage.
- `data/runtime/runs/{run_id}/` stores compact execution state.
- `data/runtime/outbox/` stores local delivery records for secondary sinks such
  as PostgreSQL.
- `data/debug/runs/{run_id}/` stores debug payloads that are useful for audit
  but are not canonical domain records.
- `data/registry/` stores artifact manifests and compatibility indexes.
- `data/testing/runs/{run_id}/` isolates testing execution from production lake
  outputs unless a command explicitly promotes records.
- `run_id` must exist before a `PipelineEvent` is emitted.
- `PipelineRun` and `PipelineEvent` are append-only audit records.
- `paper_stage_state.jsonl` stores current operational state by `paper_id` and
  `stage`; consumers must treat the latest record per natural key as current.
- Large payloads must be stored as artifacts or debug files and referenced from
  events or manifests; they must not be embedded in `PipelineEvent`.

## 5. Archived Legacy Inputs

Legacy runtime outputs were archived under:

```text
data/legacy/archive/{date}/
```

New writes must target the canonical layout. Legacy paths may be read only by
explicit recovery or migration tooling.

## 6. Related Documents

- [Contracts](../../300-CONTRACTS.md)
- [Artifact Schemas](artifact-schemas.md)
- [Artifact Inventory](artifact-inventory.md)
- [Stage Handoffs](stage-handoffs.md)
- [PipelineRun](../fundamental/scientific/pipeline-run.md)
- [PipelineEvent](../fundamental/scientific/pipeline-event.md)
- [ArtifactManifest](../fundamental/scientific/artifact-manifest.md)
