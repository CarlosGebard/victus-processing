---
id: VICTUS-PROCESSING-ARTIFACT-INVENTORY-CONTRACT
title: Victus Processing Artifact Inventory Contract
status: source-of-truth
updated_at: 2026-06-10
related_components:
  - src.application.metadata_extraction
  - src.application.bibliography_export
  - src.application.pdf_intake
  - src.application.pdf_processing
  - src.application.evidence_extraction
  - src.application.testing_pipeline
  - src.workspace.artifacts
  - src.workspace.runs
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
  - VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
tags:
  - contracts
  - artifacts
  - audit
---

# Artifact Inventory Contract

## 1. Purpose

This contract lists durable local artifacts recognized by
`victus-processing`.

The inventory separates canonical records from physical artifacts and debug
payloads so the same model can later be mirrored into PostgreSQL.

## 2. Canonical Lake Records

| Artifact | Purpose |
| --- | --- |
| `data/lake/paper_candidates.jsonl` | Candidate paper metadata before acceptance. |
| `data/lake/paper_pdf_links.jsonl` | Manual and backfilled metadata-to-PDF link records: `metadata_id`, `paper_id`, `doi`, `source_pdf_path`, `artifact_pdf_path`, `linked_at`, and `link_method`. |
| `data/lake/structured_blocks.jsonl` | StructuredBlock records promoted from PDF processing. |
| `data/lake/paper_classifications.jsonl` | PaperClassification records. |
| `data/lake/experiment_maps.jsonl` | ExperimentMap records. |
| `data/lake/experiment_packets.jsonl` | Deterministic packet records used for evidence extraction. |
| `data/lake/canonical_evidence.jsonl` | CanonicalEvidence records. |
| `data/lake/pipeline_runs.jsonl` | Optional legacy PipelineRun execution records. |
| `data/lake/pipeline_events.jsonl` | Optional legacy PipelineEvent append-only execution events. |
| `data/lake/paper_stage_state.jsonl` | Optional legacy state per paper and stage. |

## 3. Physical Artifacts

| Artifact | Purpose |
| --- | --- |
| `data/artifacts/pdfs/{paper_id}.pdf` | Normalized source PDF for processing. |
| `data/artifacts/markdown/{paper_id}.md` | Markdown generated from the source PDF or imported for processing. |
| `data/artifacts/victus-data/papers/{paper_id}/original.pdf` | General storage path for original paper PDF. |
| `data/artifacts/victus-data/markdown/{paper_id}/paper.md` | General storage path for paper markdown. |
| `data/artifacts/victus-data/structured-blocks/{paper_id}/blocks.json` | Structured blocks artifact. |
| `data/artifacts/victus-data/paper-classification/{paper_id}/classification.json` | Paper classification artifact. |
| `data/artifacts/victus-data/experiment-maps/{paper_id}/experiment_map.json` | Experiment map artifact. |
| `data/artifacts/victus-data/evidence-packets/{paper_id}/evidence_packets.json` | Evidence packet artifact. |
| `data/artifacts/victus-data/canonical-evidence/{paper_id}/canonical_evidence.json` | Canonical evidence artifact. |

Physical artifacts must be registered in
`data/registry/artifact_manifest.jsonl` when produced by a tracked run.

## 4. Runtime And Debug Artifacts

| Artifact | Purpose |
| --- | --- |
| `data/runtime/runs/{run_id}/manifest.json` | Compact run manifest matching PipelineRun identity. |
| `data/runtime/runs/{run_id}/errors.jsonl` | Compact run failures and recovery notes. |
| `data/runtime/outbox/postgres_pipeline_records.jsonl` | Local outbox for PostgreSQL dual-write delivery records. |
| `data/debug/runs/{run_id}/{paper_id}/raw_batches.jsonl` | Raw successful LLM batch debug envelopes. |
| `data/debug/runs/{run_id}/{paper_id}/failed_batches.jsonl` | Failed LLM batch debug envelopes. |
| `data/debug/runs/{run_id}/{paper_id}/classifier_input.json` | Paper classifier debug input. |

Debug artifacts are inspectable evidence for operators. They are not canonical
scientific records.

## 5. Registry Artifacts

| Artifact | Purpose |
| --- | --- |
| `data/registry/artifact_manifest.jsonl` | ArtifactRegistry/ArtifactManifest records for physical artifacts. |
| `data/registry/artifact_registry.jsonl` | Optional legacy global artifact index. |
| `data/registry/documents.jsonl` | Compatibility document index. |
| `data/registry/links.jsonl` | Compatibility document-to-paper links. |

## 6. Testing Artifacts

| Artifact | Purpose |
| --- | --- |
| `data/testing/runs/{run_id}/manifest.json` | Testing run manifest. |
| `data/testing/runs/{run_id}/outputs/` | Testing outputs isolated from production lake records. |
| `data/testing/runs/{run_id}/debug/` | Testing debug payloads. |

Testing runs must not write production lake records unless a command explicitly
promotes them.

## 7. Archived Legacy Inputs

Legacy runtime outputs were archived under:

```text
data/legacy/archive/{date}/
```

New writes should target the canonical layout. Archive reads should be explicit
recovery or migration operations.

## 8. Related Documents

- [Data Layout](data-layout.md)
- [Artifact Schemas](artifact-schemas.md)
- [Stage Handoffs](stage-handoffs.md)
- [PipelineRun](../fundamental/scientific/pipeline-run.md)
- [PipelineEvent](../fundamental/scientific/pipeline-event.md)
- [ArtifactManifest](../fundamental/scientific/artifact-manifest.md)
