---
id: VICTUS-CONTRACT-CANONICAL-EVIDENCE
contract_id: victus.scientific.canonical_evidence
title: CanonicalEvidence
status: draft
version: v1
owner: victus-processing
domain: scientific
contract_type: domain
stability: experimental
updated_at: 2026-06-09
---

# CanonicalEvidence Contract Documentation

## 1. Purpose

Represent a canonical, reusable, traceable scientific result extracted from one or more StructuredBlocks.

CanonicalEvidence exists to transform preserved scientific context into reusable evidence objects that can be retrieved, aggregated, ranked, compared, synthesized, and reasoned over across the Victus ecosystem.

CanonicalEvidence is a derived scientific artifact.

CanonicalEvidence replaces the legacy `Claim` contract concept. Victus does not
use `Claim` as a system contract.

CanonicalEvidence does not represent a paper, experiment, study summary,
document section, paragraph, table row, or downstream answer.

CanonicalEvidence represents a single explicit scientific result relation supported by source evidence.

## 2. Identity

### Identity Rules

* Canonical identifier: `canonical_evidence_id`
* `canonical_evidence_id` is globally unique inside Victus.
* `canonical_evidence_id` is immutable after creation.
* `canonical_evidence_id` is deterministic for the same source evidence,
  extraction rules, and contract-compatible extraction output.
* Downstream systems must reference evidence through `canonical_evidence_id`.
* Source paper identifiers and block identifiers are traceability metadata, not evidence identity.

### Ownership

CanonicalEvidence identity is owned by `victus-processing`.

Downstream retrieval, ranking, synthesis, and reasoning systems may consume evidence but must not modify evidence identity.

## 3. Schema

### JSON Schema

```json
{
  "canonical_evidence_id": "string",
  "paper_id": "string",
  "evidence_type": "between_group_result|within_group_change|association|correlation|dose_response|time_course|subgroup_result|mechanistic_result|null_result|adverse_effect|feasibility_result|descriptive_result|specificity_or_selectivity_result|other|unclear",
  "evidence_text": "string",
  "population": "string|null",
  "subgroup": "string|null",
  "organism": "human|animal|in_vitro|mixed|unclear|null",
  "intervention_or_exposure": "string|null",
  "comparator": "string|null",
  "outcomes": [
    "string"
  ],
  "direction": "increase|decrease|no_change|mixed|positive_association|negative_association|not_applicable|unclear",
  "timepoint": "string|null",
  "duration": "string|null",
  "dose": "string|null",
  "measurement_method": "string|null",
  "observations": [
    {
      "source_block_id": "string",
      "source_quote": "string",
      "observation_role": "primary_finding|quantitative_support|context_support|limitation_or_caution"
    }
  ],
  "quantitative_data": {
    "summary": "string|null",
    "values": [
      {
        "label": "string",
        "value": "string",
        "units": "string|null",
        "source_block_id": "string"
      }
    ]
  },
  "experiment_map_id": "string",
  "experiment_scope_id": "string",
  "source_block_ids": [
    "string"
  ]
}
```

## 4. Field Definitions

| Field                      | Type          | Description                                                 |
| -------------------------- | ------------- | ----------------------------------------------------------- |
| `canonical_evidence_id`    | String        | Canonical Victus identifier for the evidence object.        |
| `paper_id`                 | String        | Source paper identifier.                                    |
| `evidence_type`            | Enum          | Scientific result pattern represented by the evidence.      |
| `evidence_text`            | String        | Canonical description of the scientific result.             |
| `population`               | String|Null   | Population explicitly represented by the evidence.          |
| `subgroup`                 | String|Null   | Explicit subgroup associated with the evidence.             |
| `organism`                 | Enum          | Organism or experimental model.                             |
| `intervention_or_exposure` | String|Null   | Intervention, treatment, exposure, or condition.            |
| `comparator`               | String|Null   | Explicit comparison condition when reported.                |
| `outcomes`                 | Array[String] | Outcomes directly measured by the evidence.                 |
| `direction`                | Enum          | Direction of the reported result.                           |
| `timepoint`                | String|Null   | Explicit measurement timepoint.                             |
| `duration`                 | String|Null   | Explicit intervention or observation duration.              |
| `dose`                     | String|Null   | Explicit dose or exposure amount.                           |
| `measurement_method`       | String|Null   | Explicit measurement method when relevant.                  |
| `observations`             | Array         | Traceable supporting observations.                          |
| `quantitative_data`        | Object        | Preserved quantitative information supporting the evidence. |
| `experiment_map_id`        | String        | ExperimentMap identifier used to generate this evidence.    |
| `experiment_scope_id`      | String        | Experiment scope identifier used to generate this evidence. |
| `source_block_ids`         | Array[String] | Source StructuredBlocks supporting the evidence.            |

## 5. Responsibilities

### Required Responsibilities

CanonicalEvidence must:

* represent a single scientific result relation
* preserve traceability to source blocks
* preserve explicit scientific findings
* preserve quantitative findings when reported
* preserve null findings when reported
* preserve specificity and selectivity findings when reported
* preserve scientific context necessary to interpret the result
* support retrieval and evidence synthesis workflows

### Forbidden Responsibilities

CanonicalEvidence must not store:

* paper summaries
* experiment summaries
* section summaries
* study quality scores
* retrieval scores
* embeddings
* ranking metadata
* user-facing conclusions
* aggregated scientific consensus
* claim-level synthesis
* generated recommendations
* medical advice

CanonicalEvidence must not infer findings that are not explicitly supported by source content.

CanonicalEvidence must not merge independent scientific result relations into a single evidence object.

## 6. Validation Rules

* Required fields must be present.
* `canonical_evidence_id` must be unique and immutable.
* `canonical_evidence_id` must be deterministic for the same source evidence,
  extraction rules, and contract-compatible extraction output.
* `paper_id` must reference an existing Paper.
* `experiment_map_id` must reference an existing ExperimentMap.
* `experiment_scope_id` must reference an existing ExperimentMap scope.
* `source_block_ids` must reference existing StructuredBlocks.
* `evidence_text` must not be empty.
* Every evidence object must be traceable to at least one source block.
* Observations must originate from cited source blocks.
* Quantitative values must not be invented.
* Unknown values must not be inferred.

### Evidence Boundary Rules

* One CanonicalEvidence represents one scientific result relation.
* A CanonicalEvidence is not a paragraph.
* A CanonicalEvidence is not a table row.
* A CanonicalEvidence is not an experiment.
* A CanonicalEvidence is not a study summary.
* Multiple findings may be extracted from the same source blocks.
* Independent findings must be represented as separate evidence objects.

## 7. Lifecycle

### Created

CanonicalEvidence is created during evidence extraction from StructuredBlocks grouped through ExperimentMap.

Typical sources:

* StructuredBlock
* ExperimentMap

### Updated

CanonicalEvidence may be regenerated when extraction logic, prompts, or contract
versions change.

Regenerated versions must coexist with prior versions unless an explicit
promotion or migration decision supersedes them.

### Deleted

CanonicalEvidence may be deleted when the source paper is removed or when regeneration supersedes the object.

### Deprecated

CanonicalEvidence versions may be deprecated when replaced by a newer contract version.

## 8. Relationships

### Upstream Contracts

* `Paper`
* `StructuredBlock`
* `ExperimentMap`

### Downstream Contracts

* `Embedding`
* `Retrieval`
* `Agent Reasoning`
* `User Answer`

### References

* `CanonicalEvidence.paper_id` -> `Paper.paper_id`
* `CanonicalEvidence.experiment_map_id` -> `ExperimentMap.experiment_map_id`
* `CanonicalEvidence.experiment_scope_id` -> `ExperimentMap.experiment_scopes[].experiment_scope_id`
* `CanonicalEvidence.source_block_ids[]` -> `StructuredBlock.block_id`

## 9. Operational Notes

CanonicalEvidence is the primary scientific knowledge unit used by retrieval and reasoning systems.

Evidence objects should remain reusable independently of specific retrieval architectures, ranking systems, vector stores, databases, or agent workflows.

Multiple CanonicalEvidence objects may originate from the same experiment scope.

A single experiment scope may generate zero, one, or many CanonicalEvidence objects.

CanonicalEvidence regeneration must preserve traceability and scientific meaning while allowing extraction quality improvements across contract versions.

Victus-RAG indexes CanonicalEvidence, not Claim.

Pipeline, parser, model, and prompt versions belong in a separate provenance
contract such as `ProcessingProvenance` or `ExtractionRun`, not in
CanonicalEvidence.

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Backward-compatible additions such as optional metadata fields or additional evidence classifications.

### Major

Breaking schema changes, identity changes, evidence semantics changes, field removals, or modifications to evidence boundary guarantees.
