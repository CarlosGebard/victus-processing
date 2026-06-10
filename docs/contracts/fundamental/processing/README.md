# Processing Contracts

Processing contracts define operational registry, execution, artifact, and error
tracking guarantees for `victus-processing`.

These contracts support reproducibility, debugging, promotion, and coexistence of
multiple pipeline versions. They do not define scientific object schemas; those
live under [Scientific Contracts](../scientific/README.md).

## Contract Index

| Contract | Identifier | Status | Purpose |
|---|---|---|---|
| [Processing Papers](papers.md) | `victus.processing.papers@v1` | draft | Operational paper registry table |
| [Pipeline Runs](pipeline-runs.md) | `victus.processing.pipeline_runs@v1` | draft | Complete pipeline execution table |
| [Stage Runs](stage-runs.md) | `victus.processing.stage_runs@v1` | draft | Per-stage execution and debugging table |
| [Processing Artifacts](artifacts.md) | `victus.processing.artifacts@v1` | draft | External artifact registry table |
| [Processing Errors](processing-errors.md) | `victus.processing.processing_errors@v1` | draft | Traceable pipeline error table |

## Registry Flow

```text
papers
  -> pipeline_runs
  -> stage_runs
  -> artifacts
  -> processing_errors
```

`papers` tracks operational paper state. `pipeline_runs` tracks complete
executions for a paper. `stage_runs` tracks individual stage execution.
`artifacts` tracks externally stored produced or consumed objects.
`processing_errors` tracks failures without overloading stage state.

## Boundary

These contracts define PostgreSQL registry shape and operational relationships.
They do not store heavy JSON payloads, extracted scientific content, embeddings,
or model traces directly.

## Target Data Layout

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

Layout rules:

- `data/lake/` contains canonical datasets.
- `data/artifacts/` contains large or semi-large physical files.
- `data/runtime/` contains temporary execution state.
- `data/debug/` contains debugging evidence, not domain contracts.
- `data/registry/` contains indexes and compatibility records.
- `data/testing/` is isolated from real runtime state.

Names in this layout that do not yet have enough contract detail must not be
added as canonical contracts only because they appear here.
