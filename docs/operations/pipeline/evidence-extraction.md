---
id: VICTUS-PROCESSING-PIPELINE-EVIDENCE-EXTRACTION
title: Evidence Extraction Pipeline
status: source-of-truth
updated_at: 2026-06-19
tags:
  - operations
  - pipeline
  - evidence-extraction
---

# Evidence Extraction

Purpose: classify structured papers, map study/experiment scopes, build packets,
extract canonical evidence, and derive traceable general-evidence/RAG handoff
artifacts.

Commands:

```bash
uv run victus-processing evidence-extraction run
uv run victus-processing evidence-extraction run --skip-existing --limit 20
uv run victus-processing evidence-derivation build
uv run victus-processing evidence-derivation build --input data/runtime/04-evidence/{paper_id}/canonical_evidence.json --llm-conclusions --language es
```

Inputs:

- StructuredBlock rows produced by PDF processing;
- paper classifier, experiment mapper, and canonical evidence prompts;
- LiteLLM provider credentials and routing configuration.

Outputs:

- local per-paper evidence artifacts under `data/runtime/04-evidence/{paper_id}/`;
- `paper_classifications` PostgreSQL rows;
- `experiment_maps` PostgreSQL rows for primary-research papers;
- `canonical_evidence` PostgreSQL rows after extraction;
- `general_evidence_artifacts.json`, containing exposure/outcome registries,
  evidence projections, deterministic ranks, and general evidence;
- `rag_export.json`, containing only `general_evidence` and `evidence_support`
  document payloads for another repository to index;
- `paper_processing_state` refresh shows the next missing stage.

`evidence-derivation build` is the post-canonical command. It reads
`canonical_evidence.json` plus sibling `experiment_map.json`, then writes
`general_evidence_artifacts.json` and `rag_export.json`. Use
`--llm-conclusions` only when conclusion text should be generated with the
controlled GeneralEvidence prompt; counts, ranks, consensus, and recommendation
use remain deterministic.

This repository does not implement vector indexing, retrieval, Qdrant, or RAG
serving. It only prepares the JSON handoff payloads.

Design notes:

- The mapper owns `study_design` because design describes the study/scope
  context, not an extracted result.
- `CanonicalEvidence` remains paper-level extracted evidence and does not store
  rank, registry IDs, projection IDs, or general evidence IDs.
- Exposure and outcome registries are separate because exposure concepts and
  outcome concepts have different type systems and should not be merged by
  shared wording.
- Evidence ranking is deterministic policy code so counts, caveats, and RAG use
  are reproducible and auditable.
- `GeneralEvidence` aggregates by study/paper support units so one paper with
  many extracted rows cannot dominate the balance.
- LLMs may help normalize registry wording or write conclusion text, but must
  not decide ranks, support counts, dominant direction, consensus, or
  recommendation use.

Migration notes:

- Legacy `intervention_or_exposure` maps to `raw_exposure`.
- Legacy `outcomes` maps to `raw_outcomes`.
- Legacy `direction: no_change` maps to `effect_direction: no_effect`;
  association directions map to increase/decrease for compatibility.
- PostgreSQL stores the normalized value in
  `canonical_evidence.effect_direction`.

Validation:

```bash
uv run victus-processing evidence-extraction --help
uv run victus-processing evidence-extraction run --help
```
