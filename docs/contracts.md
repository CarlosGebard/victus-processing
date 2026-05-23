# Contracts

## Storage Paths

Defaults come from domain-specific files under `config/`. The root `config.yaml`
is reserved for compatibility overrides and is merged after `config/*.yaml`.

- metadata candidates: `data/runtime/01-candidates/active`
- discarded candidates: `data/runtime/01-candidates/discarded`
- reviewed candidate index: `data/runtime/01-candidates/reviewed.jsonl`
- paper mirror: `data/papers/{paper_id}`
- raw PDF: `data/papers/{paper_id}/raw/source.pdf`
- metadata: `data/papers/{paper_id}/metadata/source.json`
- Docling + heuristics: `data/papers/{paper_id}/docling/`
- claims: `data/runtime/claims/{model}/{paper}.claims.json`
- unmapped raw PDFs: `data/runtime/pdf_retrieval/unmapped_raw`
- registry: `data/registry`
- testing: `data/archive/experiments/testing_1`

## Env Vars

Pipeline:

- `SEMANTIC_SCHOLAR_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_METADATA_SELECTION_MODEL`
- `GEMINI_KEY_1`
- `GEMINI_KEY_2`
- `GEMINI_KEY_3`

## PDF Processing

Gemini-based PDF extraction is documented in `docs/pdf_processing.md`.

# Data Layout
## Tree
```text
data/
  runtime/
    01-candidates/
      reviewed.jsonl
      active/
        {document_id}.metadata.json
      discarded/
        discarded.jsonl
    pdf_retrieval/
    tmp/
    logs/
    queues/
  papers/
    {paper_id}/
  registry/
  inputs/
    seeds/
    rules/
    imports/
  reports/
    audits/
    exports/
  archive/
    legacy/
    experiments/


```
## Identity
- `document_id`: pre-PDF identity.
- `paper_id`: SHA256 of `raw/source.pdf`.
- Pre-PDF records live under `data/runtime/01-candidates`.
- Active and discarded candidate records include `created_at`.
- `reviewed.jsonl` indexes active and discarded DOIs for fast lookup.
- `reviewed.jsonl` uses `dataset_nutrition` or `dataset_gap`.
- Post-PDF canonical artifacts live under `data/papers/{paper_id}`.
## Current Contract
- `data/papers/{paper_id}` mirrors Seaweed key prefix `papers/{paper_id}`.
- `data/runtime/01-candidates` stores pre-PDF metadata review state.
