---
id: VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
title: Victus Processing Artifact Schemas Contract
status: source-of-truth
updated_at: 2026-06-19
related_components:
  - src.application.bibliography_export
  - src.application.pdf_intake
  - src.application.pdf_processing.models
  - src.application.pdf_processing.pipeline
  - src.application.pdf_processing.processed_paper_contract
  - src.application.evidence_extraction
  - src.workspace.artifacts
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - contracts
  - schemas
  - artifacts
---

# Artifact Schemas Contract

## 1. Purpose

This contract defines durable JSON and JSONL artifact shapes currently produced
or consumed by the pipeline.

## 2. Scope

Covered:

- metadata candidate files;
- manual PDF intake link records;
- PDF-processing raw batch files;
- PDF-processing final structured paper files;
- status JSONL files;
- evidence output files;
- registry JSONL records.

Not covered:

- full external API response schemas;
- downstream analytics schemas;
- prompt text content.

PostgreSQL may store final scientific output records as a secondary query sink.
The local JSON/JSONL artifacts documented here remain the handoff and audit
source for the pipeline.

## 3. Paper PDF Link Records

The canonical manual PDF intake link dataset is:

```text
data/lake/paper_pdf_links.jsonl
```

Each JSONL line uses the minimal link shape:

```text
metadata_id: string
paper_id: string
doi: string | null
source_pdf_path: string
artifact_pdf_path: string
linked_at: string
link_method: "manual_intake"
```

Field rules:

- `metadata_id` must exist in `data/lake/paper_metadata.jsonl`.
- `paper_id` identifies the canonical PDF artifact. New manual intake derives
  it from `metadata_id`; backfilled records preserve the existing artifact
  filename stem.
- `doi` is copied from the metadata record when available and normalized.
- `source_pdf_path` is the original manual intake PDF path when available.
  Backfilled records may use the artifact path when no earlier source path is
  observable.
- `artifact_pdf_path` is the promoted PDF artifact path under
  `data/artifacts/pdfs/`.
- `linked_at` is an ISO-8601 UTC timestamp.
- `link_method` must be `manual_intake`.

Validation rules:

- `metadata_id`, `paper_id`, `source_pdf_path`, `artifact_pdf_path`,
  `linked_at`, and `link_method` are required.
- `doi` may be null only when metadata has no DOI.
- `artifact_pdf_path` must point under `data/artifacts/pdfs/`.
- `link_method` must equal `manual_intake`.
- Records are append-oriented. Corrections should be made by regenerating or
  appending corrected links, not by changing PDF-processing outputs.

Forbidden fields in this canonical link record:

- external provider response payloads;
- citation counts;
- title matching scores or heuristics;
- run/event state;
- PDF processing or evidence extraction outputs.

## 4. PDF-Processing Batch Output

Each LLM batch result must validate against the current prompt schema.

First-batch results use:

```text
metadata: object
document_semantics: object
current_section: object
section_registry: list[object]
batch_index: integer
blocks: list[object]
batch_end: object
batch_warnings: object
```

Continuation-batch results use:

```text
current_section: object
updated_section_registry: list[object]
batch_index: integer
blocks: list[object]
batch_end: object
batch_warnings: object
```

Batch block objects contain:

```text
section_path: list[string]
section_type: string
content_kind: string
text: string
```

`section_registry` and `updated_section_registry` use the current prompt
contract:

```text
original_title: string
canonical_title: string
section_type: string
parent?: string | null
```

For compatibility, the pipeline also accepts legacy `title` and `type` fields.
When batch outputs are normalized internally, `title` is derived from
`canonical_title`, then `original_title`, then legacy `title`; `type` is derived
from `section_type`, then legacy `type`.

Raw batch files are written as debug envelopes:

```text
{
  "batch_index": integer,
  "start_char": integer,
  "end_char": integer,
  "result": { batch output object }
}
```

`section_registry`, `updated_section_registry`, and `batch_end` are batch-local
technical state. They may be retained in raw batch artifacts for inspection and
continuity, but they are obsolete after trimming and must not continue into
experiment mapping or canonical evidence extraction.

## 5. PDF-Processing Processed and Final Outputs

The normalized processed output is persisted as `structured_blocks` rows in
PostgreSQL after merging validated batch outputs and enforcing the
processed-paper contract.

The active evidence pipeline consumes trimmed metadata and blocks, not
top-level `sections`. `sections` may exist in compatibility artifacts for
legacy consumers, but it is not a downstream localization contract.

Persisted StructuredBlock rows are normalized by the processed-paper contract.
Block field semantics, identity guarantees, and required fields live in
[StructuredBlock](../fundamental/scientific/structured-block.md).

Prompt-defined `section_type` values must be in this canonical set:

```text
front_matter
abstract
introduction
related_work
methods
results
discussion
conclusion
references
appendix
supplementary
acknowledgements
funding
disclosure
ethics
unknown
```

Prompt-defined `content_kind` values must be in this canonical set:

```text
paragraph
table
table_row
figure_caption
equation
reference
metadata
```

The post-merge contract layer may normalize known aliases into the canonical
sets, for example `frontmatter` to `front_matter`, `publisher_note` to
`disclosure`, and `author_contributions` to `acknowledgements`.

Processed block repair joins adjacent blocks in the same section when a block
ends with an obvious incomplete ending (`and`, `of`, `with`, `,`, `;`, `(`) or
lacks terminal punctuation.

Paper classifier input is built from `structured_papers.payload` before
evidence trimming and is persisted as `paper.classifier_input.json`.
`paper.processed.json` remains a local compatibility artifact.

## 6. Evidence Derivation Outputs

Per-paper evidence extraction writes durable local JSON artifacts under:

```text
data/runtime/04-evidence/{paper_id}/
```

The derived evidence bundle is:

```text
general_evidence_artifacts.json
```

It contains:

```text
exposure_registry: list[object]
outcome_registry: list[object]
evidence_projections: list[object]
general_evidence: list[object]
rag_export: object
```

`EvidenceProjection` is derived from one `CanonicalEvidence` record plus one
normalized exposure/outcome pair. It may fan out one canonical record into
multiple projections when multiple outcomes are present.

`GeneralEvidence` is derived from grouped projections. Its support counts are
based primarily on paper/study support units, not raw evidence row count.

The RAG handoff artifact is:

```text
rag_export.json
```

It contains document payloads only:

```text
documents: list[object]
documents[].document_type: "general_evidence" | "evidence_support"
documents[].id: string
documents[].payload: object
```

`general_evidence` documents are emitted only for active, recommendable,
non-insufficient GeneralEvidence. `evidence_support` documents are emitted only
for accepted A/B projections with primary or supporting RAG use.

This artifact is a downstream handoff. It is not a vector index, retrieval
store, Qdrant collection, or serving API.

It excludes whole blocks with these section types:

```text
front_matter
references
acknowledgements
funding
disclosure
ethics
appendix
supplementary
```

It outputs only:

```text
metadata: object
blocks: list[object]
```

`paper.classification.json` is generated by `paper_classifier` from
`paper.classifier_input.json`. Evidence extraction continues only when
`paper_family` is `primary_research`. Non-primary papers write
`evidence_skipped.json` instead of `trimmed.json`.

Evidence trimming keeps only these section types:

```text
methods
results
discussion
conclusion
```

Evidence trimming outputs only:

```text
metadata: object
blocks: list[object]
```

For `primary_research` papers, trimmed blocks are derived in memory for
experiment mapping. They are not a durable PostgreSQL artifact.

It removes top-level `sections`, `section_registry`,
`updated_section_registry`, `batch_end`, `batch_ends`, `batch_warnings`, and
`processing`. It also removes block quality flags `is_truncated` and
`is_duplicate` when present.

## 6. Status JSONL

PDF-processing status records are append-oriented JSONL. Current durable fields:

```text
paper_id: string
status: "done" | "failed"
error?: string | null
error_description?: string
```

Status files are operational state. Future changes may add fields, but must not
remove the meaning of `paper_id`, `status`, or `error`.

## 6. Experiment Map Output

Experiment map output is generated by `results_scope_mapper` from trimmed
blocks.

Prompt output shape:

```text
{
  "experiment_scopes": [
    {
      "source_block_ids": list[string]
    }
  ],
  "unmapped_block_ids": list[string]
}
```

Legacy `scope_label`, `scope_kind`, and `scope_basis` fields must be ignored
when present in mapper output. They must not be persisted in
`experiment_map.json` or copied into `experiment_packets.json`.

## 7. Experiment Packets Output

Experiment packets are built deterministically from `trimmed.json` and
`experiment_map.json`.

Persisted shape:

```text
{
  "experiment_packets": [
    {
      "scope_index": integer,
      "source_block_ids": list[string],
      "blocks": list[block]
    }
  ]
}
```

Packet blocks must be exactly the blocks referenced by `source_block_ids`, in
the same order. `experiment_packets.json` is the direct input unit for
canonical evidence extraction.

The mapper itself must not extract evidence or infer scientific results.

## 8. Canonical Evidence Output

Canonical evidence output is generated by `canonical_evidence_extractor` from
one experiment packet per extraction call. The persisted
`canonical_evidence.json` aggregates validated outputs from all packets.

```text
{
  "canonical_evidence": [ canonical evidence objects ]
}
```

Runtime aggregation may include `unextracted_packet_items` for compatibility.
Prompt producers and Pydantic models for canonical prompt output must not require
that field.

The canonical evidence object schema, field semantics, allowed values, and
validation rules live in
[Canonical Evidence](../fundamental/scientific/canonical-evidence.md).

## 9. Registry Records

`data/registry/documents.jsonl` is keyed by normalized DOI. Records may contain:

```text
document_id: string
doi: string
base_name: string
updated_at: ISO datetime string
paths: object mapping artifact role to path string
stage_status: object mapping stage name to boolean
evidence_runs?: list[object]
```

Registry writes must preserve DOI normalization and deterministic ordering by
DOI and document ID.

## 10. Failure Expectations

- Invalid JSON must not be treated as a successful artifact.
- Invalid canonical evidence arrays must not be written as successful evidence
  output.
- New optional fields may be added compatibly.
- Removing required fields requires an explicit contract update.

## 11. Related Documents

- [Contracts](../../300-CONTRACTS.md)
- [Data Layout](data-layout.md)
- [Stage Handoffs](stage-handoffs.md)
- [StructuredBlock](../fundamental/scientific/structured-block.md)
- [Paper Classification](../fundamental/scientific/paper-classification.md)
- [Experiment Map](../fundamental/scientific/experiment-map.md)
- [Canonical Evidence](../fundamental/scientific/canonical-evidence.md)
