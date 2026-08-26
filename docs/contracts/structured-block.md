---
id: VICTUS-CONTRACT-STRUCTUREDBLOCK
contract_id: victus.scientific.structured_block
title: StructuredBlock
status: active
version: v1
owner: victus-processing
domain: scientific
contract_type: domain
stability: foundation
updated_at: 2026-06-09
---

# StructuredBlock Contract Documentation

## 1. Purpose

Represent the smallest preserved scientific context unit extracted from a source
paper.

StructuredBlock exists to preserve scientific content while maintaining local
semantic coherence, document structure, content ordering, and traceability to the
original publication.

StructuredBlock is a derived artifact created during paper processing.

StructuredBlock replaces the legacy `Section Block` terminology. New
documentation must use `StructuredBlock`; `Section Block` should be treated as
legacy wording only.

StructuredBlock does not represent evidence, experiments, conclusions,
scientific meaning, or extracted knowledge.

Its sole responsibility is preservation.

## 2. Identity

### Identity Rules

* Canonical identifier: `block_id`
* `block_id` is globally unique inside Victus.
* `block_id` is immutable after creation.
* `block_id` is deterministic for the same source paper, block order, and
  contract-compatible structuring output.
* Downstream artifacts must reference StructuredBlock through `block_id`.
* Source paper identifiers are traceability metadata, not block identity.
* `content_hash` identifies normalized block text content for change detection
  and audit.

### Ownership

StructuredBlock identity is owned by `victus-processing`.

Downstream workflows may consume blocks but must not modify block identity.

## 3. Schema

### JSON Schema

```json
{
  "block_id": "string",
  "paper_id": "string",
  "content_hash": "string",
  "order": "integer",
  "section_path": [
    "string"
  ],
  "section_type": "string",
  "content_kind": "string",
  "text": "string"
}
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `block_id` | String | Canonical Victus identifier for the block. |
| `paper_id` | String | Source Paper identifier. |
| `content_hash` | String | Deterministic hash of normalized block text used for content change detection. |
| `order` | Integer | Stable document order of the block within the processed paper. |
| `section_path` | Array[String] | Hierarchical document location where the block appears. |
| `section_type` | String | Canonical scientific section classification. |
| `content_kind` | String | Structural content type preserved from the paper. |
| `text` | String | Full preserved textual content of the block. |

## 5. Responsibilities

### Required Responsibilities

StructuredBlock must:

* preserve scientific source content
* preserve document ordering
* preserve local semantic coherence
* preserve section hierarchy
* preserve traceability to the source paper
* preserve content structure such as paragraphs, tables, captions, equations, and lists

### Forbidden Responsibilities

StructuredBlock must not store:

* extracted evidence
* canonical evidence
* claims
* embeddings
* experiment definitions
* experiment boundaries
* scientific conclusions
* retrieval scores
* ranking metadata
* pipeline execution state

StructuredBlock must not infer scientific meaning beyond what is explicitly present in the source content.

## 6. Validation Rules

* Required fields must be present.
* `block_id` must be unique and immutable.
* `block_id` must be deterministic for the same source paper, block order, and
  contract-compatible structuring output.
* `paper_id` must reference an existing Paper.
* `content_hash` must be derived from normalized block text.
* `order` must preserve document ordering within the source paper.
* `section_path` must contain at least one element.
* `text` must not be empty.
* Unknown values must not be invented.
* Block content must originate from the source document.

### Coherence Rules

* A block must represent a single coherent scientific context whenever possible.
* A block must not merge unrelated scientific content.
* A block may be large when necessary to preserve context.
* Tables must not be fragmented.
* Figure captions must not be fragmented.
* Evidence chains should remain intact whenever possible.

## 7. Lifecycle

### Created

StructuredBlock is created during document ingestion and scientific document structuring.

Typical sources:

* PDF-derived content
* Markdown-derived content

### Updated

StructuredBlock may be regenerated if document parsing or structuring logic
changes.

Regenerated versions must coexist with prior versions unless an explicit
promotion or migration decision supersedes them.

### Deleted

StructuredBlock may be deleted only if its parent paper is removed from Victus.

### Deprecated

StructuredBlock versions may be deprecated when superseded by a newer contract version.

## 8. Relationships

### Upstream Contracts

* `Paper`

### Downstream Contracts

* `ExperimentMap`
* `CanonicalEvidence`

### References

* `StructuredBlock.paper_id` -> `Paper.paper_id`
* `ExperimentMap.source_block_ids[]` -> `StructuredBlock.block_id`
* `CanonicalEvidence.source_block_ids[]` -> `StructuredBlock.block_id`

## 9. Operational Notes

StructuredBlock is the primary preserved scientific context object used
throughout the offline evidence pipeline.

StructuredBlock should remain stable and reusable across multiple downstream workflows.

Storage location, file paths, databases, object stores, vector stores, and processing systems must not be treated as block identity.

`paper.final.json` may be a repository-local implementation of
`StructuredBlock[]`, but it is not a separate canonical scientific contract.

StructuredBlock regeneration must produce equivalent scientific content
preservation for the same source document and contract version.

Pipeline, parser, model, and prompt versions belong in a separate provenance
contract such as `ProcessingProvenance` or `ExtractionRun`, not in
StructuredBlock.

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Backward-compatible additions such as optional metadata fields.

### Major

Changes to identity rules, schema structure, preservation guarantees, or contract semantics.
