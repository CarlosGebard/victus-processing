---
id: VICTUS-PROCESSING-PDF-PROCESSING-OPERATIONS
title: Victus Processing PDF Processing Operations
status: source-of-truth
updated_at: 2026-05-28
owners:
  - architecture
tags:
  - operations
  - pdf-processing
  - gemini
---

# PDF Processing Operations

PDF processing converts active PDFs into Markdown and structured paper JSON.

Runtime sequence:

```text
PDF -> Docling Markdown -> Markdown batches -> Gemini JSON -> merged JSON
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

Operational inputs:

- active PDFs under `data/runtime/02-pdfs/active/`;
- prompts under `src/prompts/`;
- runtime defaults in `config/pdf_processing.yaml`;
- Gemini credentials from `GEMINI_KEY*`.

Batching behavior:

- Markdown is split into structural units before LLM calls.
- The default target, soft limit, and hard limit are 6000, 9000, and 14000
  characters.
- Structural unit kinds include headings, paragraphs, tables, references,
  captions, code blocks, and lists.
- Headings open a new batch when the current batch is at least half the target
  size.
- The batcher avoids ending a batch with a trailing heading when it can carry
  that heading into the next batch.
- Tables, captions, and code blocks are not split internally. Oversized
  paragraphs, lists, and references may be split only at blank-line or line
  boundaries.
- Each batch carries compact context: previous section path, last heading, last
  300 characters, and whether an oversized unit had to be split.

Prompt and registry behavior:

- Prompts live under `src/prompts/md_to_json_first.md` and
  `src/prompts/md_to_json_next.md`.
- Continuation batches receive the accumulated section registry from prior
  batches.
- Current prompt registry entries use `original_title`, `canonical_title`,
  `section_type`, and `parent`.
- Legacy registry entries with `title` and `type` are still accepted.

Final block contract:

- Final `block_id` is deterministic: `{paper_hash}:b{order}`.
- Final `content_hash` is SHA-256 over normalized block text.
- `global_block_id` and `global_id` are not part of the current final block
  contract.
- `retrieval_exclude: true` marks frontmatter or publisher noise that should not
  be used for retrieval.

Operational outputs:

- `data/runtime/03-pdf_processing/{paper_id}/paper.md`;
- `data/runtime/03-pdf_processing/{paper_id}/raw_batches/`;
- `data/runtime/03-pdf_processing/{paper_id}/paper.processed.json`;
- `data/runtime/03-pdf_processing/processing_status.jsonl`;
- `data/runtime/quotas/gemini.sqlite3`.

Claims handoff:

- current PDF-processing writes `paper.processed.json`;
- `claims extract` defaults to `*/*.final.json` for compatibility;
- use `--pattern "*/paper.processed.json"` when extracting claims from current
  PDF-processing outputs.

Quota behavior:

- request limits are configured in `config/pdf_processing.yaml`;
- 429, 5xx, and network failures place keys in cooldown;
- quota/cooldown state survives process restarts through SQLite.

Testing notes:

- `data/testing/e2e_prompt_current/` contains the latest four-paper run using
  the current prompts and default batching.
- `data/testing/e2e_contract_batch_10k_12k_20k/` contains a comparison run using
  target 10000, soft limit 12000, and hard limit 20000.
- Test runs exclude the `01aadd...` paper by convention for this audit set.
- Gemini quota can require retrying failed papers after cooldown; successful
  partial outputs are preserved by paper directory.

Related: [Operations](../200-OPERATIONS.md),
[Data Layout Contract](../contracts/data-layout.md).
