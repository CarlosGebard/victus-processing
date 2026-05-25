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
- active PDFs: `data/runtime/02-pdfs/active`
- PDF processing output: `data/runtime/03-pdf_processing`
- claims: `data/runtime/04-claims_by_model/{model}/{paper}.claims.json`
- unmapped raw PDFs: `data/registry/unmapped_pdfs.jsonl`
- registry: `data/registry`

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
    02-pdfs/
      active/
    03-pdf_processing/
    04-claims_by_model/
      {model}/
    quotas/
  papers/
    {paper_id}/
      raw/
      metadata/
      docling/
      claims/
  registry/
    links.jsonl
    papers.jsonl
    unmapped_pdfs.jsonl
  inputs/
    generated_seed_dois/
    seeds/
    rules/
  reports/
    audits/


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
