# Contracts

## Storage Paths

Defaults come from `config.yaml`.

| Purpose | Default path |
|---|---|
| metadata candidates | `data/runtime/01_candidates/active` |
| discarded candidates | `data/runtime/01_candidates/discarded` |
| paper mirror | `data/papers/{paper_id}` |
| raw PDF | `data/papers/{paper_id}/raw/source.pdf` |
| metadata | `data/papers/{paper_id}/metadata/source.json` |
| Docling + heuristics | `data/papers/{paper_id}/docling/` |
| claims | `data/runtime/claims/{model}/{paper}.claims.json` |
| unmapped raw PDFs | `data/runtime/pdf_retrieval/unmapped_raw` |
| registry | `data/registry` |
| testing | `data/archive/experiments/testing_1` |

## Env Vars

Pipeline:

- `SEMANTIC_SCHOLAR_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_METADATA_SELECTION_MODEL`

