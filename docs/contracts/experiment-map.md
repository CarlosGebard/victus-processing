---
id: VICTUS-CONTRACT-EXPERIMENT-MAP
contract_id: victus.scientific.experiment_map
title: ExperimentMap
status: draft
version: v1
owner: victus-processing
domain: scientific
contract_type: domain
stability: experimental
updated_at: 2026-06-17
---

# ExperimentMap Contract Documentation

## 1. Purpose

Represent the deterministic mapping between StructuredBlocks and coherent result-centered scientific contexts.

ExperimentMap exists to group preserved scientific blocks into scopes that can be consumed by downstream evidence extraction.

Despite the name, an experiment scope does not necessarily represent a whole experiment, whole study, whole protocol, whole trial, whole cohort, or whole paper.

An experiment scope represents a coherent result-centered context supported by source blocks.

ExperimentMap is a derived mapping artifact.

ExperimentMap does not extract evidence, infer findings, normalize scientific findings, rank evidence, or generate conclusions.

Its responsibility is block grouping plus minimal methodological scope context
needed by downstream evidence derivation.

## 2. Identity

### Identity Rules

* Canonical identifier: `experiment_map_id`
* `experiment_map_id` is globally unique inside Victus.
* `experiment_map_id` is immutable after creation.
* `experiment_map_id` is deterministic for the same Paper, StructuredBlock
  inputs, mapping rules, and contract-compatible mapping output.
* Downstream artifacts must reference this contract through `experiment_map_id` when the full mapping artifact must be traced.
* Each scope must have an `experiment_scope_id`.
* `experiment_scope_id` is deterministic and supports traceability, audit,
  regeneration, debugging, and internal references.
* Individual scopes do not represent stable scientific entities.
* Source block identifiers are traceability references, not ExperimentMap identity.

### Ownership

ExperimentMap identity is owned by `victus-processing`.

Downstream extraction workflows may consume ExperimentMap but must not modify its identity or reinterpret its grouping as experimental truth.

## 3. Schema

### JSON Schema

```json
{
  "experiment_map_id": "string",
  "paper_id": "string",
  "experiment_scopes": [
    {
      "experiment_scope_id": "string",
      "study_id": "string",
      "source_block_ids": [
        "string"
      ],
      "study_design": "rct|prospective_cohort|retrospective_cohort|case_control|cross_sectional|meta_analysis|systematic_review|animal_experiment|in_vitro|mechanistic_experiment|descriptive_microbiome|method_validation|unclear",
      "study_role_in_paper": "main_study|secondary_analysis|subgroup_analysis|sensitivity_analysis|mechanistic_substudy|external_meta_analysis|method_validation|unclear"
    }
  ],
  "unmapped_block_ids": [
    "string"
  ]
}
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `experiment_map_id` | String | Canonical Victus identifier for the mapping artifact. |
| `paper_id` | String | Source Paper identifier. |
| `experiment_scopes` | Array[Object] | Result-centered block groups used as downstream evidence extraction contexts. |
| `experiment_scopes[].experiment_scope_id` | String | Deterministic identifier for the scope within the mapping artifact. |
| `experiment_scopes[].study_id` | String | Study/scope identifier used by CanonicalEvidence. May equal `experiment_scope_id` for compatibility. |
| `experiment_scopes[].source_block_ids` | Array[String] | StructuredBlock identifiers belonging to the same coherent result-centered context. |
| `experiment_scopes[].study_design` | Enum | Methodological design for the mapped scope. Use `unclear` when uncertain. |
| `experiment_scopes[].study_role_in_paper` | Enum | Role of the mapped scope within the paper. Use `unclear` when uncertain. |
| `unmapped_block_ids` | Array[String] | StructuredBlock identifiers not directly required for any result-centered scope. |

## 5. Responsibilities

### Required Responsibilities

ExperimentMap must:

* group StructuredBlocks into coherent result-centered contexts
* preserve traceability through `source_block_ids`
* keep result families separate when they represent different measurement or analytical contexts
* attach directly required method blocks only after result anchors are identified
* leave unrelated, generic, or unsupported blocks unmapped
* preserve `study_id`, `study_design`, and `study_role_in_paper` for downstream traceability
* support downstream CanonicalEvidence extraction

### Forbidden Responsibilities

ExperimentMap must not store:

* extracted evidence
* canonical evidence
* claims
* population extraction
* intervention extraction
* comparator extraction
* outcome extraction
* direction extraction
* statistics extraction
* evidence roles
* assertion types
* scientific conclusions
* evidence ranks
* exposure IDs or outcome IDs
* retrieval scores
* embeddings
* pipeline execution state

ExperimentMap must not infer outcomes, populations, findings, or claims that are not explicitly supported by source blocks.

ExperimentMap must not use methods blocks to merge otherwise separate result-centered contexts.

## 6. Validation Rules

* Required fields must be present.
* `experiment_map_id` must be unique and immutable.
* `experiment_map_id` must be deterministic for the same Paper,
  StructuredBlock inputs, mapping rules, and contract-compatible mapping output.
* `paper_id` must reference an existing Paper.
* Every scope must include an `experiment_scope_id`.
* Every scope must include a `study_id`; it may equal `experiment_scope_id`.
* `experiment_scope_id` must be deterministic within the mapping artifact.
* `study_design` must use the allowed enum and should be `unclear` when not
  directly supported by the mapped blocks.
* `study_role_in_paper` must use the allowed enum and should be `unclear` when
  not directly supported by the mapped blocks.
* Every `source_block_ids` value must reference an existing StructuredBlock.
* Every `unmapped_block_ids` value must reference an existing StructuredBlock.
* A block id must not appear more than once inside the same scope.
* A scope must contain at least one `source_block_id`.
* Empty scopes must not be emitted.
* Unknown block ids must not be invented.
* Blocks must be grouped only by evidence present in the provided StructuredBlocks.

### Scope Boundary Rules

* A scope must be centered on explicit current-study result anchors.
* Result subsections are strong scope boundaries.
* Different measurement families should produce separate scopes.
* Different analytical contexts should produce separate scopes.
* Different validation or manipulation-check analyses should produce separate scopes.
* Different datasets, cohorts, organisms, model systems, phases, or protocols should produce separate scopes when they create different result-centered contexts.
* Shared participants, cohort, intervention, comparator arms, protocol, statistical model, or broad research question are not sufficient reasons to merge scopes.

### Mapping Rules

* Method blocks are contextual support, not scope anchors.
* Discussion blocks are low-priority support.
* Generic methods may remain unmapped.
* Generic discussion may remain unmapped.
* Tables and figures belong to the result family they support.
* Tables must not be split into one scope per row.
* Figures must not be split into one scope per panel.
* A block may appear in multiple scopes only when it directly supports multiple result-centered contexts.

## 7. Lifecycle

### Created

ExperimentMap is created after StructuredBlock generation and before CanonicalEvidence extraction.

Typical sources:

* StructuredBlock collections from a processed Paper
* deterministic experiment scope mapping workflow

### Updated

ExperimentMap may be regenerated when block structuring, mapping rules, prompts,
or contract versions change.

Regenerated versions must coexist with prior versions unless an explicit
promotion or migration decision supersedes them.

### Deleted

ExperimentMap may be deleted when the source paper is removed or when regeneration supersedes the artifact.

### Deprecated

ExperimentMap versions may be deprecated when replaced by a newer contract version or mapping strategy.

## 8. Relationships

### Upstream Contracts

* `Paper`
* `StructuredBlock`

### Downstream Contracts

* `CanonicalEvidence`

### References

* `ExperimentMap.paper_id` -> `Paper.paper_id`
* `ExperimentMap.experiment_scopes[].source_block_ids[]` -> `StructuredBlock.block_id`
* `ExperimentMap.unmapped_block_ids[]` -> `StructuredBlock.block_id`
* `CanonicalEvidence.source_block_ids[]` -> `StructuredBlock.block_id`

## 9. Operational Notes

ExperimentMap is a lightweight grouping artifact.

It should remain minimal, deterministic, and independent from downstream
ranking, aggregation, and retrieval design.

ExperimentMap should not become a hidden experiment model.

The name `experiment_scope` is operational, not ontological.

`study_id` is a downstream traceability handle, not a claim that the scope is a
complete trial, cohort, experiment, or paper-level study.

`study_design` belongs here because it describes the methodological context of
the scope. It does not belong in CanonicalEvidence, EvidenceProjection rank
inputs except as copied context, or GeneralEvidence aggregation outputs as a
source-of-truth field.

A single paper may produce zero, one, or many scopes.

A single study, cohort, intervention, or protocol may produce many scopes.

A single scope may produce zero, one, or many CanonicalEvidence objects.

Storage paths, object-store keys, database rows, pipeline runs, and prompt executions must not be treated as ExperimentMap identity.

Pipeline, parser, model, and prompt versions belong in a separate provenance
contract such as `ProcessingProvenance` or `ExtractionRun`, not in ExperimentMap.

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Backward-compatible additions such as optional metadata fields or additional validation guidance.

### Major

Breaking schema changes, identity changes, field removals, or semantic changes to scope boundary guarantees.
