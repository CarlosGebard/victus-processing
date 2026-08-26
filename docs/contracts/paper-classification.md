---
id: VICTUS-CONTRACT-PAPER-CLASSIFICATION
contract_id: victus.scientific.paper_classification
title: PaperClassification
status: draft
version: v1
owner: victus-processing
domain: scientific
contract_type: domain
stability: experimental
updated_at: 2026-06-19
---

# PaperClassification Contract Documentation

## 1. Purpose

Define the classification record that describes how a scientific paper generates
knowledge before evidence extraction.

`PaperClassification` decides whether a processed paper is eligible for
canonical evidence extraction. It does not extract evidence, evaluate scientific
quality, judge conclusions, rank papers, or interpret whether the paper is
correct.

## 2. Identity

### Identity Rules

- Canonical identifier: `paper_id` plus `run_id`
- A paper may have multiple classifications across runs.
- Classification output must be traceable to the run that produced it.
- `paper_id` links the classification to `Paper`.
- `run_id` links the classification to `PipelineRun`.

### Ownership

`PaperClassification` is owned by `victus-processing`.

## 3. Schema

### JSON Schema

```json
{
  "paper_id": "string",
  "run_id": "string",
  "paper_family": "primary_research|evidence_synthesis|methodological|case_based|opinion_or_theory|unknown",
  "paper_type": "string",
  "evidence_generation_mode": "generates_original_data|synthesizes_existing_evidence|proposes_method|reports_cases|argues_or_interprets|unclear",
  "has_original_experiments": true,
  "has_systematic_search": false,
  "has_meta_analysis": false,
  "classification_confidence": 0.95,
  "quality_flags": [],
  "risk_flags": [],
  "routing_evidence": [],
  "reasoning_summary": "Brief explanation supported by explicit evidence."
}
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `paper_id` | String | Classified paper. |
| `run_id` | String | Pipeline run that produced the classification. |
| `paper_family` | Enum | High-level paper family used for evidence routing. |
| `paper_type` | String | More specific paper type label. |
| `evidence_generation_mode` | Enum | How the paper generates or handles evidence. |
| `has_original_experiments` | Boolean | Whether the paper reports original experiments. |
| `has_systematic_search` | Boolean | Whether the paper reports a systematic search. |
| `has_meta_analysis` | Boolean | Whether the paper reports a meta-analysis. |
| `classification_confidence` | Number | Confidence in the classification. |
| `quality_flags` | Array | Non-routing quality flags. |
| `risk_flags` | Array | Risk flags relevant to downstream handling. |
| `routing_evidence` | Array | Explicit source evidence supporting the route. |
| `reasoning_summary` | String | Brief explanation grounded in explicit evidence. |

## 5. Responsibilities

### Required Responsibilities

`PaperClassification` must:

- classify the current paper, not cited studies or background literature
- decide whether evidence extraction may continue
- preserve routing evidence when available
- preserve enough audit information to reconstruct the decision
- support deterministic routing from a validated classification output

### Forbidden Responsibilities

`PaperClassification` must not:

- extract canonical evidence
- group result scopes
- build experiment packets
- rank paper quality
- decide whether conclusions are true
- evaluate clinical usefulness
- rewrite or summarize structured blocks
- use external knowledge

## 6. Validation Rules

- Required fields must be present.
- `paper_id` must reference an existing `Paper`.
- `run_id` must reference an existing `PipelineRun`.
- `paper_family` must use an allowed value.
- `evidence_generation_mode` must use an allowed value.
- `classification_confidence` must be numeric.
- `quality_flags`, `risk_flags`, and `routing_evidence` must be arrays.
- `reasoning_summary` must not be empty.
- A schema-invalid classification must not be used for routing.
- A non-primary paper must not be treated as failed.

### Allowed Paper Family Values

- `primary_research`
- `evidence_synthesis`
- `methodological`
- `case_based`
- `opinion_or_theory`
- `unknown`

### Allowed Evidence Generation Modes

- `generates_original_data`
- `synthesizes_existing_evidence`
- `proposes_method`
- `reports_cases`
- `argues_or_interprets`
- `unclear`

## 7. Lifecycle

### Created

Created after validated structured paper data is classified.

### Updated

Updated only through a new run or explicit migration. Existing classification
records should not be silently overwritten.

### Deleted

Not deleted under normal operation.

### Deprecated

Deprecated when superseded by a newer classification contract or promoted run.

## 8. Relationships

### Upstream Contracts

- `Paper`
- `StructuredBlock`
- `PipelineRun`

### Downstream Contracts

- `ExperimentMap`
- `PipelineEvent`

### References

- `PaperClassification.paper_id` -> `Paper.paper_id`
- `PaperClassification.run_id` -> `PipelineRun.run_id`
- `PipelineEvent.paper_id` -> `PaperClassification.paper_id`

## 9. Operational Notes

Target canonical dataset output:

```text
data/lake/paper_classifications.jsonl
```

Current runtime may still write:

```text
paper.classifier_input.json
paper.classification.json
evidence_skipped.json
```

`paper.classification.json` is the current per-paper runtime representation of
`PaperClassification`. `paper.classifier_input.json` is debug/audit input.
`evidence_skipped.json` is a runtime routing output, not a canonical scientific
artifact. Its durable information belongs in `PaperClassification` and
`PipelineEvent`.

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Backward-compatible additions such as nullable fields, additional flags, or
additional non-breaking routing evidence.

### Major

Breaking schema changes, identity changes, routing semantics changes, field
removals, or allowed-value meaning changes.
