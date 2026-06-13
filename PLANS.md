# Structured Paper DB Flow

## Goal
Persist the full processed paper as `structured_paper`, classify from database payloads, and persist evidence-ready blocks only after primary-research classification.

## Scope
- Add `structured_papers` and `evidence_blocks` persistence.
- Remove useless source PDF path from processed payloads.
- Keep local JSON artifacts for compatibility.
- Move processing state from `has_structured_blocks` to `has_structured_paper` / `has_evidence_blocks`.

## Assumptions
- `paper_id` is the canonical identifier for the PDF/paper.
- `structured_blocks` remains legacy/indexable storage and is not the new stage gate.

## Steps
1. Add store APIs and PostgreSQL tables for `structured_papers` and `evidence_blocks`.
2. Persist `structured_paper` from PDF/Markdown processing.
3. Classify from DB payloads when a store is available; keep file fallback.
4. Persist and consume `evidence_blocks` after primary-research classification.
5. Update processing-state facts and docs/tests.

## Validation
- `uv run pytest`
- CLI smoke help tests

## Risks
- Existing DBs need the updated SQL migration applied before DB-backed runs.
