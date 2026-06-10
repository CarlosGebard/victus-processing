---
id: VICTUS-PROCESSING-PDF-PROCESSING-OPERATIONS
title: Victus Processing PDF Processing Operations
status: source-of-truth
updated_at: 2026-06-05
tags:
  - operations
  - pdf-processing
  - llm
---

# PDF Processing Operations

PDF processing converts active PDFs into Markdown and structured block JSON.
Evidence extraction and testing are separate public pipeline interfaces.

Runtime sequence:

```text
PDF -> Docling Markdown -> Markdown batches -> LLM JSON -> merged block JSON
  -> processed-paper contract enforcement -> paper.processed.json
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

Next stages:

- [Evidence extraction](pipelines/evidence-extraction.md)
- [Testing pipeline](pipelines/testing-pipeline.md)

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

- Prompts live under `src/prompts/pdf_processing/markdown_first_batch.md` and
  `src/prompts/pdf_processing/markdown_continuation_batch.md`.
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
  [StructuredBlock Contract](../contracts/fundamental/scientific/structured-block.md).
- Evidence trimming keeps only methods, results, discussion, and conclusion.
- The evidence-stage handoff contains only `metadata-extraction` and `blocks`.
- Blocks are the unit of downstream information and localization.

Operational outputs:

- `data/runtime/03-pdf_processing/{paper_id}/paper.md`;
- `data/runtime/03-pdf_processing/{paper_id}/raw_batches/`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.processed.json`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.final.json`;
- `data/runtime/03-pdf_processing/processing_status.jsonl`.

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
[Data Layout Contract](../contracts/local/data-layout.md),
[Evidence extraction](pipelines/evidence-extraction.md),
[Testing pipeline](pipelines/testing-pipeline.md).
