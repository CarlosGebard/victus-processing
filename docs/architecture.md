# Architecture

## Boundary

This repo owns local paper processing:

```text
metadata -> bib -> pdfs -> pdf_processing -> claims
```

This repo does not own analytics, deployment infrastructure, Qdrant, RAG indexing, or external PDF retrieval services.

## Components

- `src/cli.py`: local CLI entrypoint, parser, command routing, and handlers.
- `ops/scripts/bridge/`: Victus bridge package for registry, storage, and event integration.
- `ops/scripts/*.py`: manager scripts that do not belong to a narrower ops domain yet.
- `src/workspace/config.py`: config loading, `.env` loading, runtime paths.
- `src/metadata/stage.py`, `src/pdf_extraction/stage.py`, `src/pdf_processing/pipeline.py`, `src/claims/stage.py`: pipeline stage orchestration.
- `src/metadata/`: metadata discovery, citation exploration, and paper selection helpers.
- `src/pdf_extraction/json_to_bib.py`: exports metadata JSON/CSV records to BibTeX.
- `src/pdf_extraction/`: PDF normalization and BibTeX export helpers.
- `src/pdf_processing/`: Docling Markdown conversion, LLM PDF extraction, and merge helpers.
- `src/claims/`: claim extraction helpers.
- `tests/`: validation.

## Data Flow

```text
data/inputs
  -> data/runtime/01-candidates/active
  -> data/papers/{paper_id}/raw/source.pdf
  -> data/papers/{paper_id}/metadata/source.json
  -> data/papers/{paper_id}/docling
  -> data/runtime/04-claims_by_model/{model}/{paper}.claims.json
```
