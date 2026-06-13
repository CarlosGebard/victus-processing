# Processing Contracts

Processing contracts define operational registry, execution, artifact, and error
tracking guarantees for `victus-processing`.

These contracts support reproducibility, debugging, promotion, and coexistence of
multiple pipeline versions. They do not define scientific object schemas; those
live under [Scientific Contracts](../scientific/README.md).

## Contract Index

| Contract | Identifier | Status | Purpose |
|---|---|---|---|
| [Paper Processing State](../scientific/paper-processing-state.md) | `victus.scientific.paper_processing_state@v1` | active | Current operational dashboard row per paper |
| [Pipeline Runs](pipeline-runs.md) | `victus.processing.pipeline_runs@v1` | optional | Legacy/optional run observability |

## Registry Flow

```text
data/artifacts inputs
  -> scientific PostgreSQL tables
  -> paper_processing_state
```

`paper_processing_state` tracks current operational state. Scientific output
tables store processed results. Pipeline run/event tables are optional
observability and are not required for v1 operation.

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
    paper_candidates.jsonl
    paper_pdf_links.jsonl

    structured_blocks.jsonl
    paper_classifications.jsonl
    experiment_maps.jsonl
    experiment_packets.jsonl
    canonical_evidence.jsonl

    pipeline_runs.jsonl
    pipeline_events.jsonl

  artifacts/
    intake/
      pdfs/
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
