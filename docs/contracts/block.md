---
id: VICTUS-PROCESSING-BLOCK-CONTRACT
title: Victus Processing Block Contract
status: source-of-truth
updated_at: 2026-06-03
related_components:
  - src.application.pdf_processing.processed_paper_contract
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
tags:
  - contracts
  - blocks
  - pdf-processing
---

# Block Contract

## 1. Purpose

This contract defines the durable meaning of a `block` in processed, trimmed,
experiment-map, and canonical-evidence handoff artifacts.

A block is the smallest stable textual unit used by the pipeline to preserve a
paper's documentary address, semantic text identity, order, context, and content
kind.

## 2. Scope

Covered:

- `blocks` in `paper.processed.json`;
- `blocks` in `paper.final.json`;
- `blocks` in trimmed evidence inputs;
- field-level meaning required by downstream stages.

Not covered:

- raw Markdown batching internals;
- downstream analytics schemas;
- canonical evidence output schemas.

## 3. Required Fields

Each processed or final block must include:

```text
block_id: "{paper_hash}:b{order}"
paper_id: string
content_hash: sha256(normalized_text)
order: integer
section_path: list[string]
section_type: string
content_kind: string
text: string
```

## 4. Field Semantics

- `block_id` identifies the textual origin inside the paper. It is the
  documentary address of the block.
- `paper_id` identifies the post-PDF paper associated with the block.
- `content_hash` identifies the normalized text content. It enables change,
  duplicate, and re-processing detection.
- `order` preserves the documentary sequence of the paper.
- `section_path` preserves the contextual hierarchy that contains the block.
- `section_type` identifies the scientific function of the block, such as
  `methods`, `results`, `discussion`, or `conclusion`.
- `content_kind` identifies the content form, such as paragraph, table, figure
  caption, equation, reference, or metadata.
- `text` contains the original semantic unit represented by the block.

In short:

```text
block_id = documentary address
content_hash = semantic-textual identity
```

## 5. Identity Guarantees

`block_id` is deterministic within a processed paper. It uses
`{paper_hash}:b{order}` and is recomputed after final block repair and ordering.

`content_hash` is computed from normalized block text using:

```text
Unicode NFKC normalization
ligature cleanup
lowercase
whitespace collapse
trim
sha256(UTF-8 bytes)
```

Blocks are the active units of information and localization after trimming.
Downstream evidence stages must use block identifiers and block fields for
traceability, not `sections`, `section_registry`, `updated_section_registry`,
or `batch_end`.

Blocks must not rely on `global_block_id` or `global_id`; those fields are not
part of the current block contract.

## 6. Downstream Use

Trimming preserves block text and removes irrelevant blocks by `section_type`.
Experiment maps reference blocks through `source_block_ids`. Canonical evidence
records reference blocks through object-level `source_block_ids`, observation
`source_block_id` fields, and quantitative value `source_block_id` fields.

## 6. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Artifact Schemas](artifact-schemas.md)
- [Experiment Map](experiment-map.md)
- [Canonical Evidence](canonical-evidence.md)
