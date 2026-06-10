---
id: victus.scientific.artifact_registry
title: ArtifactRegistry
version: v1
status: draft
owner: victus-processing
---

# ArtifactRegistry Contract Documentation

## Purpose

`ArtifactRegistry` is the canonical global index of produced artifacts.

It records where artifacts are stored, which run produced them, which stage they
belong to, and whether the artifact is valid for downstream use.

`artifact_manifest.jsonl` remains the local manifest by run. `ArtifactRegistry`
is the global query index.

## Storage

Local durable write:

```text
data/registry/artifact_registry.jsonl
```

PostgreSQL table:

```text
artifact_registry
```

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `artifact_id` | String | Yes | Stable artifact identifier. |
| `paper_id` | String | No | Paper identifier when the artifact is paper-scoped. |
| `artifact_kind` | String | Yes | Artifact category. |
| `stage` | String | Yes | Strict pipeline stage name that produced the artifact. |
| `artifact_path` | String | Yes | Filesystem path or object storage URI. |
| `content_hash` | String | No | Content hash, usually `sha256:<hex>`. |
| `schema_version` | String | No | Artifact schema version. |
| `contract_version` | String | No | Contract version, such as `structured-blocks:v1`. |
| `producer_run_id` | String | Yes | PipelineRun that produced the artifact. |
| `validation_status` | String | Yes | Validation state. |
| `created_at` | Timestamp | Yes | Artifact registration timestamp. |

## Validation Status Values

- `valid`
- `invalid`
- `pending`
- `unknown`

## Artifact Kinds

Initial kinds:

- `pdf`
- `markdown`
- `structured-blocks`
- `paper-classification`
- `experiment-map`
- `evidence-packets`
- `canonical-evidence`

## Guarantees

- PostgreSQL stores index records only.
- Artifact content stays in filesystem or object storage.
- Registry records must not embed PDF, markdown, extracted text, model inputs,
  model outputs, or large evidence payloads.
- `producer_run_id` links the artifact to `PipelineRun`.
- `stage` links the artifact to the producing stage.

## PostgreSQL Shape

```sql
CREATE TABLE IF NOT EXISTS artifact_registry (
  artifact_id TEXT PRIMARY KEY,
  paper_id TEXT,
  artifact_kind TEXT NOT NULL,
  stage TEXT NOT NULL,
  artifact_path TEXT NOT NULL,
  content_hash TEXT,
  schema_version TEXT,
  contract_version TEXT,
  producer_run_id TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
