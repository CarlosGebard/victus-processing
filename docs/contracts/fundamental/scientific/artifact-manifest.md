---
id: VICTUS-CONTRACT-ARTIFACT-MANIFEST
contract_id: victus.storage.artifact_manifest
title: ArtifactManifest
status: draft
version: v1
owner: victus-processing
domain: storage
contract_type: storage
stability: experimental
updated_at: 2026-06-09
---

# ArtifactManifest Contract Documentation

## 1. Purpose

Define the canonical registry record used to locate, identify, and trace
physical artifacts produced by Victus.

`ArtifactManifest` separates domain objects from storage implementation. It
provides artifact identity, lineage, ownership, and storage location without
embedding artifact payloads.

## 2. Identity

### Identity Rules

- Canonical identifier: `artifact_id`
- `artifact_id` is globally unique inside Victus.
- `artifact_id` is immutable after creation.
- Storage locations may change without changing `artifact_id`.
- Directory structure, bucket layout, and database table names must not define
  artifact identity.

### Ownership

`ArtifactManifest` is owned by `victus-processing`.

## 3. Schema

### JSON Schema

```json
{
  "artifact_id": "string",
  "artifact_type": "string",
  "artifact_version": "string",
  "paper_id": "string|null",
  "run_id": "string",
  "storage_uri": "string",
  "storage_backend": "string",
  "content_format": "string",
  "checksum": "string|null",
  "size_bytes": 0,
  "created_at": "datetime",
  "metadata": {}
}
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `artifact_id` | String | Stable artifact identifier. |
| `artifact_type` | String | Domain or operational object represented by the artifact. |
| `artifact_version` | String | Version of the artifact schema or contract. |
| `paper_id` | String / Null | Owning paper when applicable. |
| `run_id` | String | PipelineRun responsible for creating the artifact. |
| `storage_uri` | String | Physical artifact location. |
| `storage_backend` | String | Storage technology, such as `local_fs`, `s3`, `seaweedfs`, `postgres`, or `parquet`. |
| `content_format` | String | Serialization format, such as `pdf`, `md`, `json`, `jsonl`, or `parquet`. |
| `checksum` | String / Null | Optional content hash. |
| `size_bytes` | Integer | Physical artifact size in bytes. |
| `created_at` | Datetime | Artifact manifest creation timestamp. |
| `metadata` | Object | Small implementation metadata. |

## 5. Responsibilities

### Required Responsibilities

`ArtifactManifest` must:

- record artifact identity
- record artifact type and version
- record storage location and backend
- preserve producing run lineage
- preserve owning paper when applicable
- support artifact audit and lookup

### Forbidden Responsibilities

`ArtifactManifest` must not store:

- full artifact payloads
- structured block content
- canonical evidence content
- Markdown content
- PDF content
- embeddings
- prompts
- raw LLM responses

## 6. Validation Rules

- `artifact_id`, `artifact_type`, `artifact_version`, `run_id`,
  `storage_uri`, `storage_backend`, `content_format`, `size_bytes`, and
  `created_at` are required.
- `artifact_id` must be stable after creation.
- `paper_id` may be `null` for global artifacts.
- `storage_uri` must not be empty.
- `size_bytes` must be non-negative.
- `metadata` must be an object.
- Schema-invalid artifacts must not receive successful manifests.
- A missing storage location must fail manifest creation.

## 7. Lifecycle

### Created

Created after a persisted artifact is successfully produced or registered.

### Updated

Updated only for manifest metadata that does not change artifact identity.

### Deleted

Deleted artifacts should preserve manifest history when auditability is
required.

### Deprecated

Deprecated when the artifact remains traceable but should no longer be used.

## 8. Relationships

### Upstream Contracts

- `PipelineRun`
- `PipelineEvent`

### Downstream Contracts

None.

### References

- `ArtifactManifest.run_id` -> `PipelineRun.run_id`
- `ArtifactManifest.paper_id` -> `Paper.paper_id`
- `PipelineEvent.artifact_id` -> `ArtifactManifest.artifact_id`

## 9. Operational Notes

Initial JSONL target:

```text
data/registry/artifact_manifest.jsonl
```

Future database target:

```text
artifact_manifests
```

Recommended indexes:

- `artifact_id`
- `artifact_type`
- `paper_id`
- `run_id`
- `created_at`

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Backward-compatible additions such as nullable fields, optional metadata, or
additional artifact classifications.

### Major

Breaking schema changes, identity changes, field removals, or semantic meaning
changes.
