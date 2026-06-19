# PostgreSQL Simplification — Completed

## Goal

Provide one clean PostgreSQL schema for scientific outputs and paper-scoped
pipeline state while preserving `structured_papers` during migration.

## Delivered

- `paper_pipeline_state` stores one row per paper stage attempt.
- `paper_processing_state` is the derived dashboard projection.
- Scientific outputs use dedicated tables aligned with current contracts.
- Trimmed evidence blocks are derived in memory.
- Detailed run events and artifact manifests remain local JSON/JSONL artifacts.
- Migration 005 is the standalone schema entrypoint for new and existing
  databases.

## Validation

- Migration applied successfully on 2026-06-19.
- All 109 `structured_papers` rows were preserved.
- Target tables and canonical-evidence query columns were verified.
- Repository test result: `38 passed`.
