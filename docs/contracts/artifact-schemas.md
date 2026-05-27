---
id: VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
title: Victus Processing Artifact Schemas Contract
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
related_components:
  - src.pdf_processing.models
  - src.pdf_processing.pipeline
  - src.claims.extraction
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

Each Gemini batch result must validate against the current batch model shape:

```text
metadata?: object
current_section: object
section_registry: list[object]
updated_section_registry: list[object]
batch_index: integer
blocks: list[object]
batch_end: object
batch_warnings: object
```

Block objects contain:

```text
local_id?: string
order: integer
section_path: list[string]
section_type: string
content_kind: string
text: string
```

Raw batch files are written as debug envelopes:

```text
{
  "batch_index": integer,
  "start_char": integer,
  "end_char": integer,
  "result": { batch output object }
}
```

## 4. PDF-Processing Final Output

The canonical final output is:

```text
data/runtime/03-pdf_processing/{paper_id}/paper.processed.json
```

It is produced by merging validated batch outputs. Claims extraction expects a
JSON object with a top-level `sections` list. When present, `paper`, `title`,
`paper_title`, and `trace` are used as context for claims prompts.

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
