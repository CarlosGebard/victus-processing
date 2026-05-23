# Architecture

## Boundary

This repo owns local paper processing:

```text
metadata -> bib -> raw_pdf -> input_pdfs -> docling + heuristics -> claims
```

This repo does not own analytics, deployment infrastructure, Qdrant, RAG indexing, or external PDF retrieval services.

## Components

- `src/cli.py`: local CLI entrypoint, parser, command routing, and handlers.
- `ops/scripts/bridge/`: Victus bridge package for registry, storage, and event integration.
- `ops/scripts/*.py`: manager scripts that do not belong to a narrower ops domain yet.
- `src/config.py`: config loading, `.env` loading, runtime paths.
- `src/metadata/stage.py, src/pdf/stage.py, src/docling/stage.py, src/claims/stage.py`: pipeline stage orchestration.
- `src/metadata/`: metadata discovery, selection, topic, and bibliography helpers.
- `src/pdf/`: PDF normalization and ingestion helpers.
- `src/docling/`: Docling and heuristic document processing.
- `src/claims/`: claim extraction helpers.
- `tests/`: validation.

## Data Flow

```text
data/inputs
  -> data/runtime/01-candidates/active
  -> data/papers/{paper_id}/raw/source.pdf
  -> data/papers/{paper_id}/metadata/source.json
  -> data/papers/{paper_id}/docling
  -> data/runtime/claims/{model}/{paper}.claims.json
```

