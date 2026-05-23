# PDF Processing

## Purpose

Scientific paper extraction as:

1. PDF -> Markdown with Microsoft MarkItDown.
2. Markdown batches -> JSON with Gemini.
3. Batch JSON merge -> final clean JSON.

## Inputs

- PDF file passed through CLI:

```bash
uv run victus-processing pdf-processing run
```

Single PDF:

```bash
uv run victus-processing pdf-processing run --pdf path/to/paper.pdf
```

PDF to Markdown only:

```bash
uv run python -m src.pdf_processing.markdown path/to/paper.pdf output/paper.md
```

Limit number of PDFs from the input directory:

```bash
uv run victus-processing pdf-processing run --limit 10
```

Process PDFs in parallel:

```bash
uv run victus-processing pdf-processing run --limit 10 --workers 3
```

Use MarkItDown LLM mode:

```bash
uv run victus-processing pdf-processing run --pdf path/to/paper.pdf --markitdown-use-llm
```

Limit processed Markdown batches:

```bash
uv run victus-processing pdf-processing run --pdf path/to/paper.pdf --max-batches 3
```

- Prompt templates:
  - `src/prompts/md_to_json_first.md`
  - `src/prompts/md_to_json_next.md`

- Runtime config:
  - `config/pdf_processing.yaml`

- Gemini API keys from environment:
  - `GEMINI_KEY_1`
  - `GEMINI_KEY_2`
  - `GEMINI_KEY_3`

Compatibility keys also work:

- `GEMINI_API_KEY`
- `GEMINI_API_KEYS1`, `GEMINI_API_KEYS2`, ...

## Outputs

Default output root:

```text
data/runtime/03-pdf_processing/
```

Per paper:

```text
data/runtime/03-pdf_processing/{pdf_stem}/
  {pdf_stem}.md
  raw_batches/
    batch_0001.json
    batch_0002.json
  {pdf_stem}.full.json
```

Shared quota state:

```text
data/runtime/quotas/gemini.sqlite3
```

Processing status log:

```text
data/runtime/03-pdf_processing/processing_status.jsonl
```

Record shape:

```json
{"paper_id":"00221...","status":"done|failed","error":null,"updated_at":"ISO-8601"}
```

The log is append-only. The latest record per `paper_id` is the current state.

## Final JSON Contract

`{paper_id}.full.json` shape:

```json
{
  "source_pdf": "path/to/paper.pdf",
  "metadata": {
    "title": null,
    "authors": [],
    "year": null,
    "doi": null
  },
  "sections": [
    {
      "order": 0,
      "title": "Introduction",
      "type": "introduction",
      "parent": null
    }
  ],
  "section_registry": [
    {
      "title": "Introduction",
      "type": "introduction",
      "parent": null
    }
  ],
  "blocks": [
    {
      "block_id": "introduction-0001",
      "order": 0,
      "section_path": ["Introduction"],
      "section_title": "Introduction",
      "section_type": "introduction",
      "content_kind": "paragraph",
      "text": "...",
      "quality": {
        "confidence": "high",
        "is_truncated": false,
        "is_duplicate": false
      }
    }
  ],
  "batch_states": [],
  "processing": {
    "model": "gemini-3.1-flash-lite",
    "markdown_batch_chars": 12000,
    "markdown_overlap_chars": 1200,
    "total_batches": 0,
    "created_at": "ISO-8601 timestamp"
  }
}
```

Only batch 1 contributes metadata. All batches contribute blocks and batch_state.
Duplicate overlap blocks are removed by normalized block signature while preserving order.

## Quota And Circuit Breaker

Per key defaults:

- 15 requests per minute
- 500 requests per day
- HTTP 429 cooldown: 60 seconds
- HTTP 5xx cooldown: 30 seconds
- network error cooldown: 30 seconds

State persists in SQLite, so quota/cooldown survives process restart.
