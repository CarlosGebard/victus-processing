---
id: VICTUS-PROCESSING-PDF-PROCESSING-OPERATIONS
title: Victus Processing PDF Processing Operations
status: source-of-truth
updated_at: 2026-06-05
owners:
  - architecture
tags:
  - operations
  - pdf-processing
  - llm
---

# PDF Processing Operations

PDF processing converts active PDFs into Markdown and structured block JSON.

Runtime sequence:

```text
PDF -> Docling Markdown -> Markdown batches -> LLM JSON -> merged block JSON
  -> processed-paper contract enforcement -> paper.processed.json
  -> evidence trimming -> experiment map -> experiment packets
  -> canonical evidence
```

Run all active PDFs:

```bash
uv run victus-processing pdf-processing run
```

Run one PDF:

```bash
uv run victus-processing pdf-processing run --pdf path/to/paper.pdf
```

Limit work:

```bash
uv run victus-processing pdf-processing run --limit 10
uv run victus-processing pdf-processing run --pdf path/to/paper.pdf --max-batches 3
```

Run Markdown-only conversion:

```bash
uv run victus-processing pdf-processing markdown --skip-existing
```

Generate evidence artifacts from processed paper JSON:

```bash
uv run victus-processing pdf-processing evidence
uv run victus-processing pdf-processing evidence --input data/runtime/03-pdf_processing/{paper_id}/paper.processed.json
```

Run the complete testing pipeline in per-paper review folders:

```bash
uv run victus-processing pdf-processing testing
uv run victus-processing pdf-processing testing --paper-id {paper_id}
uv run victus-processing pdf-processing testing --paper-id {paper_id} --reuse-markdown
```

Operational inputs:

- active PDFs under `data/runtime/02-pdfs/active/`;
- prompts under `src/prompts/`;
- runtime defaults in `config/pdf_processing.yaml`;
- LiteLLM provider credentials and routing configuration.

Batching behavior:

- Markdown is split before LLM calls so each request preserves local scientific
  continuity while staying below model-safe size limits.
- Current defaults in `config/pdf_processing.yaml` are:

```text
target: 10000 characters
soft limit: 14000 characters
hard limit: 20000 characters
max output tokens: provider/model default (`max_tokens: null`)
```

- The batcher first parses Markdown into structural units. Unit kinds include
  headings, paragraphs, tables, references, captions, code blocks, and lists.
- Units are appended to the current batch until the target is reached. The soft
  limit allows a coherent unit to stay intact instead of forcing an early split.
- The hard limit is the strict safety boundary. A batch must not exceed it
  unless an unsplittable unit itself is too large, in which case processing
  fails rather than silently damaging the artifact.
- Headings are treated as section transitions. A heading opens a new batch when
  the current batch is already at least half the target size.
- The batcher avoids ending a batch with a trailing heading. If possible, that
  heading is carried into the next batch so the following content keeps its
  section context.
- Tables, captions, and code blocks are high-value structural artifacts and are
  not split internally.
- Oversized paragraphs, lists, and references may be split only at blank-line or
  line boundaries.
- Each batch carries compact structural context for the prompt: previous section
  path, last heading, last 300 characters, and whether an oversized unit had to
  be split.
- `pdf_processing.max_tokens` controls the output budget for local Markdown
  extraction prompts. Use `null` to avoid sending an explicit LiteLLM
  `max_tokens` limit and rely on the provider/model limit. Truncated model
  output is recorded as `raw_batches/batch_XXXX.failed.json`.
- The previous 300-character tail is used only for continuity and overlap
  removal. It is not a downstream evidence artifact.

Prompt and batch-continuity behavior:

- Prompts live under `src/prompts/md_to_json_first.md` and
  `src/prompts/md_to_json_next.md`.
- Continuation batches receive accumulated `section_registry` and
  `batch_end` state from prior batches.
- Current prompt registry entries use `original_title`, `canonical_title`,
  `section_type`, and parent-path fields.
- Legacy registry entries with `title` and `type` are still accepted.
- `section_registry`, `updated_section_registry`, and `batch_end` are internal
  batch-continuity state only. They are obsolete after trimming and must not be
  used as downstream scientific localization contracts.

Final block behavior:

- `paper.final.json` blocks preserve the
  [Block Contract](../contracts/block.md).
- Evidence trimming keeps only methods, results, discussion, and conclusion.
- The evidence-stage handoff contains only `metadata` and `blocks`.
- Blocks are the unit of downstream information and localization.

Operational outputs:

- `data/runtime/03-pdf_processing/{paper_id}/paper.md`;
- `data/runtime/03-pdf_processing/{paper_id}/raw_batches/`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.processed.json`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.final.json`;
- `data/runtime/03-pdf_processing/processing_status.jsonl`.

Testing pipeline outputs:

- `data/testing/{paper_id}/source.pdf`;
- `data/testing/{paper_id}/paper.md`;
- `data/testing/{paper_id}/markdown_batches/`;
- `data/testing/{paper_id}/raw_batches/`;
- `data/testing/{paper_id}/paper.processed.json`;
- `data/testing/{paper_id}/paper.final.json`;
- `data/testing/{paper_id}/paper.classifier_input.json`;
- `data/testing/{paper_id}/paper.classification.json`;
- `data/testing/{paper_id}/evidence_skipped.json` for non-primary papers;
- `data/testing/{paper_id}/trimmed.json`;
- `data/testing/{paper_id}/experiment_map.json`;
- `data/testing/{paper_id}/experiment_packets.json`;
- `data/testing/{paper_id}/canonical_evidence.json`.

Evidence handoff:

- current PDF-processing writes compatibility `paper.final.json`;
- the active evidence pipeline first builds `paper.classifier_input.json`;
- `paper_classifier` writes `paper.classification.json`;
- only `primary_research` papers continue to evidence extraction;
- non-primary papers write `evidence_skipped.json` and stop before trimming;
- primary papers then produce trimmed `metadata + blocks`;
- experiment scope mapping consumes blocks and maps scopes to block ids;
- experiment packet construction deterministically expands each scope into the
  exact block packet for one extraction pass;
- canonical evidence extraction consumes one experiment packet per LLM call.

Evidence outputs:

- `data/runtime/04-evidence/{paper_id}/trimmed.json`;
- `data/runtime/04-evidence/{paper_id}/experiment_map.json`;
- `data/runtime/04-evidence/{paper_id}/experiment_packets.json`;
- `data/runtime/04-evidence/{paper_id}/canonical_evidence.json`.

LLM behavior:

- provider credentials, routing, retries, fallbacks, and quota behavior are
  handled by LiteLLM outside the application pipeline.

Testing notes:

- `data/testing/e2e_prompt_current/` contains the latest four-paper run using
  the current prompts and default batching.
- `data/testing/e2e_contract_batch_10k_12k_20k/` contains a comparison run using
  target 10000, soft limit 12000, and hard limit 20000.
- Test runs exclude the `01aadd...` paper by convention for this audit set.
- successful partial outputs are preserved by paper directory.

Related: [Operations](../200-OPERATIONS.md),
[Data Layout Contract](../contracts/data-layout.md).
