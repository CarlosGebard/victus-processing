# Data Platform Restructure Plan

## Task Classification

- refactor
- storage
- database
- migration
- documentation
- data pipeline
- contract change
- observability

## Goal

Restructure `victus-processing` so the runtime data model, local files, and
future PostgreSQL integration follow the fundamental contracts and the target
layout under `data/`, with `PipelineRun` and `PipelineEvent` as the execution
audit backbone.

Target local layout:

```text
data/
  inputs/
    seeds/
      seed_dois.jsonl
      explored_seed_dois.jsonl
    generated_seed_dois/
      candidates_seed_dois.jsonl

  lake/
    papers.jsonl
    paper_candidates.jsonl
    paper_review_decisions.jsonl
    pdf_relations.jsonl
    structured_blocks.jsonl
    paper_classifications.jsonl
    experiment_maps.jsonl
    experiment_packets.jsonl
    canonical_evidence.jsonl
    pipeline_runs.jsonl
    pipeline_events.jsonl

  artifacts/
    pdfs/
      {paper_id}.pdf
    markdown/
      {paper_id}.md

  runtime/
    runs/
      {run_id}/
        manifest.json
        errors.jsonl

  debug/
    runs/
      {run_id}/
        {paper_id}/
          raw_batches.jsonl
          failed_batches.jsonl
          classifier_input.json

  registry/
    artifact_manifest.jsonl
    documents.jsonl
    links.jsonl

  testing/
    runs/
      {run_id}/
        manifest.json
        outputs/
        debug/
```

## Non-Goals

- Do not change prompt content or LLM behavior unless required by schema
  compatibility.
- Do not introduce a new dependency; `psycopg[binary]` is already present.
- Do not connect to the production PostgreSQL server until local JSONL behavior
  and schema mapping are validated.
- Do not delete or migrate existing user data automatically in the first pass.
- Do not rename public CLI commands unless a milestone explicitly requires it.
- Do not treat docs as implemented behavior until code and tests confirm them.

## Current State Observations

- `docs/contracts/fundamental/processing/README.md` already contains the target
  layout and identifies `data/lake/pipeline_runs.jsonl`,
  `data/lake/pipeline_events.jsonl`, and future PostgreSQL targets.
- `PipelineRun` requires one immutable `run_id` before any event is emitted.
- `PipelineEvent` is append-only, compact, and must reference `run_id`; large
  payloads belong in artifacts referenced by path or artifact id.
- `ArtifactManifest` points at `data/registry/artifact_manifest.jsonl` and
  future table `artifact_manifests`.
- `src/workspace/config.py` still defines many legacy constants:
  `data/runtime/01-candidates`, `data/runtime/02-pdfs`,
  `data/runtime/03-pdf_processing`, `data/runtime/04-evidence`,
  `data/papers`, `data/reports`, and `data/archive`.
- `config/storage.yaml`, `config/pdf_processing.yaml`, `config/processing.yaml`,
  and `config/testing.yaml` still point at legacy runtime directories.
- PDF processing currently writes per-paper files:
  `paper.md`, `raw_batches/*.json`, `paper.processed.json`,
  `paper.final.json`, and `processing_status.jsonl` under
  `data/runtime/03-pdf_processing`.
- Evidence extraction currently writes per-paper files:
  `paper.classifier_input.json`, `paper.classification.json`,
  `trimmed.json`, `experiment_map.json`, `experiment_packets.json`, and
  `canonical_evidence.json` under `data/runtime/04-evidence`.
- Testing currently writes directly under `data/testing/{paper_id}` instead of
  `data/testing/runs/{run_id}`.
- `src/workspace/artifacts.py` currently uses `data/registry/documents.jsonl`
  and `links.jsonl`, plus compatibility mirrors under `data/papers/{paper_id}`.
- There is no existing database/migration layer despite the `psycopg`
  dependency.
- Local contract cleanup removed duplicate object contracts. `data-layout.md`
  has been restored for the target layout, while `stage-handoffs.md` and
  `artifact-schemas.md` still need implementation-aligned path updates as
  stages migrate.

## Inconsistencies To Resolve Before Implementation

- The proposed `data/lake/*.jsonl` datasets are canonical, but current stages
  mostly produce nested per-paper JSON files. The plan must define whether each
  stage writes JSONL directly, writes per-run artifacts then promotes to JSONL,
  or does both.
- Fundamental `PaperClassification`, `ExperimentMap`, and `CanonicalEvidence`
  require richer canonical fields than some current local outputs, including
  `run_id`, `experiment_map_id`, and `canonical_evidence_id`.
- The target layout has `data/artifacts/markdown/{paper_id}.md`, but current
  processing writes Markdown under each processing output directory.
- The target layout has `debug/runs/{run_id}/{paper_id}/raw_batches.jsonl`,
  while current raw batches are separate JSON files under `raw_batches/`.
- The target layout has `runtime/runs/{run_id}/errors.jsonl`, while current
  failures are mixed into `processing_status.jsonl` or CLI output.
- `data/lake/pdf_relations.jsonl` replaces scattered CSV/relation behavior, but
  current metadata-to-PDF normalization still searches for
  `doi_pdf_relations*.csv`.
- `data/testing/runs/{run_id}/outputs/` needs a decision: mirror the new lake
  filenames, preserve per-paper folders for review, or do both.
- PostgreSQL table contracts for processing records are referenced in the
  fundamental `processing/README.md`, but the actual contract files for
  `papers.md`, `pipeline-runs.md`, `stage-runs.md`, `artifacts.md`, and
  `processing-errors.md` are not currently synchronized into this repository.

## Likely Touch Points

- `src/workspace/config.py`
- `src/workspace/data_layout.py`
- `src/workspace/artifacts.py`
- `src/application/metadata_extraction/*`
- `src/application/metadata_to_pdf/*`
- `src/application/pdf_processing/pipeline.py`
- `src/application/pdf_processing/status.py`
- `src/application/evidence_extraction/evidence.py`
- `src/application/testing_pipeline/artifacts.py`
- `src/cli.py`
- `config/*.yaml`
- `tests/test_cli_smoke.py`
- `tests/test_pdf_processing.py`
- `tests/test_evidence_extraction.py`
- new tests for run/event/artifact stores
- `docs/contracts/local/`
- `docs/operations/`

## Milestones

### 1. Contract And Layout Baseline

Purpose: make the local contract surface explicit before changing runtime
behavior.

Status: in progress.

Completed:

- Recreate or replace `docs/contracts/local/data-layout.md` for the new layout.
- Update `artifact-inventory.md` to describe lake/artifacts/runtime/debug/testing
  boundaries.
- Add canonical layout constants and `data-layout` directory coverage in
  `src.workspace.config`.

Remaining:

- Update `stage-handoffs.md` and `artifact-schemas.md` once stage write paths
  actually move.
- Decide and document which datasets are canonical JSONL and which files are
  debug or physical artifacts.
- Add an ADR because this is an architecture/storage migration.

Likely touch points:

- `docs/contracts/local/data-layout.md`
- `docs/contracts/local/stage-handoffs.md`
- `docs/contracts/local/artifact-schemas.md`
- `docs/contracts/local/artifact-inventory.md`
- `docs/300-CONTRACTS.md`
- `docs/adr/`

Validation commands:

```bash
uv run contracts validate
rg -n "data/runtime/0|data/testing/\\{paper_id\\}|data/contracts/local/data-layout|\\(data-layout.md\\)" docs
```

Blockers/dependencies:

- Confirm whether fundamental processing table contracts should be synchronized
  as standalone files, not only via `processing/README.md`.

### 2. Run And Event Core

Purpose: introduce `run_id`, `PipelineRun`, and `PipelineEvent` as reusable
local primitives before moving stage outputs.

Status: in progress.

Completed:

- Add a small orchestration/audit module that creates `run_id`.
- Append `PipelineRun` records to `data/lake/pipeline_runs.jsonl`.
- Append `PipelineEvent` records to `data/lake/pipeline_events.jsonl`.
- Write `data/runtime/runs/{run_id}/manifest.json`.
- Write `data/runtime/runs/{run_id}/errors.jsonl` for compact failures.
- Add ArtifactManifest JSONL registration helper.

Remaining:

- Integrate the run/event core into CLI stage execution.
- Keep events compact; large payloads remain file artifacts.

Likely touch points:

- new `src/workspace/runs.py` or `src/application/orchestration/*`
- `src/cli.py`
- `src/workspace/config.py`
- `tests/`

Validation commands:

```bash
uv run pytest tests/test_cli_smoke.py -q
uv run pytest -q tests/test_*run* tests/test_*event*
uv run victus-processing data-layout --dry-run
```

Rollback/recovery:

- This milestone should be additive. Existing stage outputs remain supported
  while run/event files are introduced.

### 3. Data Layout Configuration Migration

Purpose: centralize new paths and stop encoding legacy paths as defaults.

Expected outcome:

- `get_data_layout_dirs()` creates the target layout.
- Config defaults point to `data/lake`, `data/artifacts`, `data/runtime/runs`,
  `data/debug/runs`, `data/registry`, and `data/testing/runs`.
- Legacy constants are either removed or clearly marked compatibility-only.
- No automatic deletion of old `data/runtime/01-*`, `02-*`, `03-*`, or `04-*`.

Likely touch points:

- `src/workspace/config.py`
- `src/workspace/data_layout.py`
- `config/storage.yaml`
- `config/pdf_processing.yaml`
- `config/processing.yaml`
- `config/testing.yaml`
- tests that monkeypatch old constants

Validation commands:

```bash
uv run victus-processing data-layout --dry-run
uv run pytest tests/test_cli_smoke.py tests/test_pdf_processing.py tests/test_evidence_extraction.py -q
```

### 4. Metadata Lake Promotion

Purpose: move metadata candidate state from nested runtime files into lake
datasets.

Expected outcome:

- DOI seeds remain under `data/inputs/`.
- Candidate metadata lands in `data/lake/paper_candidates.jsonl`.
- Accepted papers land in `data/lake/papers.jsonl`.
- Review decisions land in `data/lake/paper_review_decisions.jsonl`.
- Existing metadata CLI behavior remains usable through adapters if needed.

Likely touch points:

- `src/application/metadata_extraction/*`
- `src/application/metadata_to_pdf/json_to_bib.py`
- `src/workspace/artifacts.py`
- metadata tests

Validation commands:

```bash
uv run pytest tests/test_cli_smoke.py -q
uv run victus-processing metadata-extraction --help
```

Blockers/dependencies:

- Define canonical `paper_id` derivation for `papers.jsonl` versus current DOI
  slug/base-name behavior.

### 5. PDF Relations And Physical Artifacts

Purpose: separate canonical relation data from physical PDFs and Markdown.

Expected outcome:

- PDF relation records land in `data/lake/pdf_relations.jsonl`.
- Active PDFs are stored as `data/artifacts/pdfs/{paper_id}.pdf`.
- Markdown is stored as `data/artifacts/markdown/{paper_id}.md`.
- Metadata-to-PDF no longer depends primarily on `doi_pdf_relations*.csv`.
- `ArtifactManifest` records are emitted to
  `data/registry/artifact_manifest.jsonl`.

Likely touch points:

- `src/application/metadata_to_pdf/normalization.py`
- `src/application/metadata_to_pdf/normalize_from_relations.py`
- `src/workspace/artifacts.py`
- `docs/contracts/fundamental/scientific/artifact-manifest.md`
- tests for PDF normalization and artifact paths

Validation commands:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_pdf_processing.py -q
uv run victus-processing metadata-to-pdf --help
```

### 6. PDF Processing Output Reshape

Purpose: promote structured blocks to the lake and move batch/debug data under
run-scoped debug paths.

Expected outcome:

- Structured blocks append to `data/lake/structured_blocks.jsonl`.
- Generated Markdown is read/written through `data/artifacts/markdown/`.
- Raw LLM batches are written to
  `data/debug/runs/{run_id}/{paper_id}/raw_batches.jsonl`.
- Failed LLM batches are written to
  `data/debug/runs/{run_id}/{paper_id}/failed_batches.jsonl`.
- Stage success/failure emits `PipelineEvent` records instead of relying on
  `processing_status.jsonl`.

Likely touch points:

- `src/application/pdf_processing/pipeline.py`
- `src/application/pdf_processing/status.py`
- `src/application/pdf_processing/merge.py`
- `src/application/pdf_processing/processed_paper_contract.py`
- `tests/test_pdf_processing.py`

Validation commands:

```bash
uv run pytest tests/test_pdf_processing.py tests/test_cli_smoke.py -q
```

Rollback/recovery:

- Keep read compatibility for old per-paper `paper.processed.json` until the
  migration path is validated.

### 7. Evidence Output Promotion

Purpose: align evidence outputs with fundamental scientific contracts.

Expected outcome:

- Paper classifications append to `data/lake/paper_classifications.jsonl`.
- Experiment maps append to `data/lake/experiment_maps.jsonl`.
- Experiment packets append to `data/lake/experiment_packets.jsonl`.
- Canonical evidence appends to `data/lake/canonical_evidence.jsonl`.
- Classifier input moves to
  `data/debug/runs/{run_id}/{paper_id}/classifier_input.json`.
- Output records include required contract identifiers where possible:
  `run_id`, `paper_id`, `experiment_map_id`, `experiment_scope_id`,
  `canonical_evidence_id`.
- Non-primary routing emits `PipelineEvent` with `routing_decision` or
  `skipped`.

Likely touch points:

- `src/application/evidence_extraction/evidence.py`
- `src/application/evidence_extraction/llm_evidence.py`
- prompts only if required to obtain missing fields
- `tests/test_evidence_extraction.py`

Validation commands:

```bash
uv run pytest tests/test_evidence_extraction.py tests/test_cli_smoke.py -q
```

Blockers/dependencies:

- Decide whether IDs such as `experiment_map_id` and `canonical_evidence_id`
  are generated deterministically in code after LLM output or requested from the
  prompt and then validated. Prefer deterministic code generation.

### 8. Testing Run Layout

Purpose: isolate testing artifacts by run while preserving review ergonomics.

Expected outcome:

- Testing writes to `data/testing/runs/{run_id}/`.
- `manifest.json` records selected papers, source artifact paths, prompt label,
  and execution mode `testing`.
- Outputs and debug files follow a documented layout under `outputs/` and
  `debug/`.
- Testing emits `PipelineRun` and `PipelineEvent` records without polluting
  production lake records unless explicitly requested.

Likely touch points:

- `src/application/testing_pipeline/artifacts.py`
- `src/cli.py`
- `config/testing.yaml`
- `tests/test_cli_smoke.py`
- `tests/test_pdf_processing.py`

Validation commands:

```bash
uv run pytest tests/test_cli_smoke.py tests/test_pdf_processing.py -q
uv run victus-processing testing-pipeline run --help
```

Open question:

- Should testing write separate testing lake files inside `outputs/`, or reuse
  production lake schema with an execution mode flag?

### 9. PostgreSQL Adapter Preparation

Purpose: prepare the v1 server integration for orchestration records only.

Expected outcome:

- Add a repository/storage interface for `PipelineRun` and `PipelineEvent`
  records.
- Keep JSONL as the local/default backend.
- Add optional PostgreSQL backend gated by env/config.
- Define table DDL or migrations for `pipeline_runs` and `pipeline_events`
  only.
- Use upsert/append semantics compatible with the JSONL contracts.
- Do not implement JSONL/object storage in Postgres. JSONL/object payloads are
  planned for S3/Seaweed.
- Do not implement `artifact_manifests` in Postgres for v1.

Likely touch points:

- new `src/infrastructure/storage/` or `src/infrastructure/postgres/`
- config for database URL/secret source
- operations runbook for local JSONL vs PostgreSQL mode
- tests with fake repository or optional integration tests

Validation commands:

```bash
uv run pytest -q
uv run victus-processing data-layout --dry-run
```

Blockers/dependencies:

- Need connection details and secret-loading convention for the PostgreSQL
  server.
- Need decision on migration tooling. If no dependency is allowed, use plain SQL
  files plus a small `psycopg` runner.

### 10. Migration And Compatibility Tooling

Purpose: make old data readable and promotable without destructive moves.

Expected outcome:

- Add a dry-run migration command that scans legacy runtime paths and reports
  what can be promoted.
- Add an explicit migration command only after dry-run output is validated.
- Preserve old files by default.
- Write migration events to `pipeline_events.jsonl` with execution mode
  `backfill` or `replay`.

Likely touch points:

- new `ops/scripts/data/` migration script or CLI subcommand
- `src/workspace/artifacts.py`
- tests with temporary legacy layouts
- operations runbook

Validation commands:

```bash
uv run pytest -q
uv run victus-processing data-layout --dry-run
```

Rollback/recovery:

- Migration must be copy/promote-first, not move/delete-first.
- Any destructive cleanup requires a separate explicit task.

### 11. Documentation And Operations Finalization

Purpose: make docs match implemented behavior after code migration.

Expected outcome:

- Update `docs/200-OPERATIONS.md`.
- Update pipeline operation docs under `docs/operations/pipelines/`.
- Update contracts hub and local contracts.
- Add or update runbook for JSONL/PostgreSQL synchronization and migration.
- Remove stale references to legacy paths only after compatibility is decided.

Likely touch points:

- `docs/200-OPERATIONS.md`
- `docs/operations/`
- `docs/contracts/local/`
- `docs/adr/`

Validation commands:

```bash
uv run contracts validate
rg -n "data/runtime/01-candidates|data/runtime/02-pdfs|data/runtime/03-pdf_processing|data/runtime/04-evidence|data/testing/\\{paper_id\\}" docs src config tests
uv run pytest -q
```

## Initial Validation Set

Run after each milestone that touches code:

```bash
uv run pytest tests/test_cli_smoke.py -q
uv run pytest tests/test_pdf_processing.py tests/test_evidence_extraction.py -q
uv run contracts validate
```

Run before claiming the full migration complete:

```bash
uv run pytest -q
uv run victus-processing data-layout --dry-run
uv run contracts validate
```

## Open Questions

- Should `data/lake/*.jsonl` be the canonical local source even after PostgreSQL
  is enabled, or should PostgreSQL become authoritative with JSONL as export?
- Should `paper_id` continue to be the active PDF filename stem, or should it be
  generated from the fundamental `Paper` identity contract?
- Should testing runs ever write into production lake files, or stay fully under
  `data/testing/runs/{run_id}`?
- Should the fundamental processing table contracts be synchronized as separate
  files before implementing PostgreSQL tables?
- Which migration tool style do you want for Postgres: plain SQL files plus a
  small runner, or a migration framework?
