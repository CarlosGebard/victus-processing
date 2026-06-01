---
id: VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
title: Victus Processing Artifact Schemas Contract
status: source-of-truth
updated_at: 2026-05-28
owners:
  - architecture
related_components:
  - src.application.pdf_processing.models
  - src.application.pdf_processing.pipeline
  - src.application.pdf_processing.processed_paper_contract
  - src.application.claims.extraction
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
- PDF-processing raw batch files;
- PDF-processing final structured paper files;
- status JSONL files;
- claims output files;
- registry JSONL records.

Not covered:

- full external API response schemas;
- downstream analytics schemas;
- prompt text content.

## 3. PDF-Processing Batch Output

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

## 4. PDF-Processing Processed and Final Outputs

The normalized processed output is:

```text
data/runtime/03-pdf_processing/{paper_id}/paper.processed.json
```

It is produced by merging validated batch outputs and enforcing the
processed-paper contract.

The canonical final output is derived from `paper.processed.json`:

```text
data/runtime/03-pdf_processing/{paper_id}/paper.final.json
```

Claims extraction should consume `paper.final.json`. It expects a JSON object
with a top-level `sections` list. When present, `paper`, `title`,
`paper_title`, and `trace` are used as context for claims prompts.

Processed and final `blocks` are normalized by the processed-paper contract.
Each block must include:

```text
block_id: "{paper_hash}:b{order}"
content_hash: sha256(normalized_text)
order: integer
section_path: list[string]
section_type: string
content_kind: string
text: string
```

`block_id` is the operational block identity. It is deterministic within a
processed paper and is recomputed after final block repair and ordering.

`content_hash` is the real content identity. It is computed from normalized
block text using:

```text
Unicode NFKC normalization
ligature cleanup
lowercase
whitespace collapse
trim
sha256(UTF-8 bytes)
```

Blocks must not rely on `global_block_id` or `global_id`; those fields are not
part of the current block contract.

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

Final trimming keeps only these section types:

```text
abstract
methods
results
discussion
conclusion
supplementary
```

Final trimming removes top-level `section_registry`, `batch_warnings`, and
`processing`. It also removes block quality flags `is_truncated` and
`is_duplicate` when present.

## 5. Status JSONL

PDF-processing status records are append-oriented JSONL. Current durable fields:

```text
paper_id: string
status: "done" | "failed"
error?: string | null
error_description?: string
```

Status files are operational state. Future changes may add fields, but must not
remove the meaning of `paper_id`, `status`, or `error`.

## 6. Claims Output

Claims output is a JSON object:

```text
{
  "metadata": {
    "model": string,
    "source_final_json": string,
    "claims_limit": integer,
    "estimated_input_tokens": integer
  },
  "claims": [ claim objects ]
}
```

The canonical claim object schema, field semantics, allowed values, and
validation rules live in [Claims Schema](claims-schema.md).

## 7. Registry Records

`data/registry/documents.jsonl` is keyed by normalized DOI. Records may contain:

```text
document_id: string
doi: string
base_name: string
updated_at: ISO datetime string
paths: object mapping artifact role to path string
stage_status: object mapping stage name to boolean
claims_runs?: list[object]
```

Registry writes must preserve DOI normalization and deterministic ordering by
DOI and document ID.

## 8. Failure Expectations

- Invalid JSON must not be treated as a successful artifact.
- Invalid claim arrays must not be written as successful claims output.
- New optional fields may be added compatibly.
- Removing required fields requires an explicit contract update.

## 9. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Data Layout](data-layout.md)
- [Stage Handoffs](stage-handoffs.md)
- [Claims Schema](claims-schema.md)
