# Contracts

## Local CLI

Entrypoint:

```bash
victus-processing
```

Path fallback:

```bash
python -m src.cli
```

Public command groups:

- `metadata`
- `bib`
- `pdfs`
- `pipeline`
- `claims`
- `bridge`
- `data-layout`

Stable validation commands:

```bash
victus-processing --help
victus-processing metadata --help
victus-processing claims --help
victus-processing bridge --help
victus-bridge --help
```

## Storage Paths

Defaults come from `config.yaml`.

| Purpose | Default path |
|---|---|
| metadata candidates | `data/candidates/active` |
| discarded candidates | `data/candidates/discarded` |
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

Bridge:

- `VICTUS_PG_DSN`
- `VICTUS_REDIS_URL`
- `VICTUS_S3_ENDPOINT`
- `VICTUS_S3_ACCESS_KEY`
- `VICTUS_S3_SECRET_KEY`
- `VICTUS_S3_BUCKET`
- `VICTUS_AWS_REGION`

Known statuses:

- processing: `pending`, `processing`, `completed`, `failed`
- RAG: `pending`, `indexed`, `error`
