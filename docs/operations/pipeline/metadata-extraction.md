---
id: VICTUS-PROCESSING-METADATA-EXTRACTION
title: Metadata Extraction
status: source-of-truth
version: v1
updated_at: 2026-06-11
related_components:
  - src.application.metadata_extraction
  - src.application.bibliography_export
tags:
  - metadata-extraction
  - operations
  - contracts
---

# Metadata Extraction

## Purpose

Discover candidate papers, screen them by title, and maintain the canonical
metadata lake at `data/lake/paper_metadata.jsonl`.

## Commands

```bash
uv run victus-processing metadata-extraction explore --mode broad-nutrition
uv run victus-processing metadata-extraction from-doi --doi 10.1000/demo
uv run victus-processing metadata-extraction seed-dois --mode broad-nutrition --limit 200
uv run python -m ops.scripts.data.refresh_paper_metadata_from_dois --limit 10
```

## Flow

1. Load a seed DOI queue or a single DOI argument.
2. Fetch seed/citation metadata from Semantic Scholar.
3. Skip candidates already present in `paper_metadata.jsonl`.
4. For exploration, send candidate titles only to the LLM selector.
5. Write kept metadata directly to `data/lake/paper_metadata.jsonl`.

## Inputs

- exploration config;
- seed DOI queues;
- `data/lake/paper_metadata.jsonl`, when present;
- Semantic Scholar API access.

## Outputs

- `data/lake/paper_metadata.jsonl`;
- optional `data/lake/paper_metadata.s2_refreshed.jsonl`;
- DOI seed queues for configured profiles.

`metadata-extraction from-doi` appends or upserts one normalized record directly
in `data/lake/paper_metadata.jsonl`.

## LLM Selection Contract

`metadata-extraction explore` sends only:

```json
{
  "candidates": [
    {
      "id": "cand_001",
      "title": "Paper title"
    }
  ]
}
```

The LLM must return:

```json
{
  "decisions": [
    {
      "id": "cand_001",
      "decision": "keep | drop | uncertain",
      "reason": "short reason grounded in the title"
    }
  ]
}
```

Abstracts are not sent to the LLM selector.

## paper_metadata.jsonl Contract

Each line is a JSON object:

```json
{
  "metadata_id": "meta:s2:{source_paper_id} | meta:openalex:{document_id} | meta:crossref:{doi}",
  "source_metadata": {
    "source": "semantic_scholar | openalex",
    "source_paper_id": "string | null",
    "doi": "string | null",
    "arxiv": "string | null",
    "title": "string",
    "year": "integer | null",
    "citation_count": "integer | null",
    "pdf_url": "string | null",
    "authors": ["string"]
  },
  "schema_version": "v1",
  "discovery": {
    "seed_papers": ["doi"],
    "is_seed_paper": "boolean"
  },
  "domain_screening": {
    "decision": "keep | drop | uncertain",
    "model": "string | null"
  },
  "created_at": "ISO-8601 UTC timestamp",
  "updated_at": "ISO-8601 UTC timestamp"
}
```

Required fields:

- `metadata_id`;
- `source_metadata.title`;
- `schema_version`;
- `domain_screening.decision`;
- `created_at`;
- `updated_at`.

Rules:

- `schema_version` must be `v1`;
- `domain_screening.decision` must be `keep`, `drop`, or `uncertain`;
- DOI values must be normalized lowercase text;
- abstracts must not be stored in `paper_metadata.jsonl`;
- titles must not be used as identity or dedupe keys.

## Dedupe Rules

`metadata-extraction explore` skips candidates when:

- `source_metadata.source_paper_id` matches the Semantic Scholar `paperId`;
- or `source_metadata.doi` matches the candidate DOI.

Only `data/lake/paper_metadata.jsonl` is used for metadata dedupe.

## Validation

```bash
uv run victus-processing metadata-extraction --help
uv run victus-processing metadata-extraction explore --help
uv run pytest tests/test_cli_smoke.py -q
```
