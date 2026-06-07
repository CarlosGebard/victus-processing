---
id: VICTUS-PROCESSING-CANONICAL-EVIDENCE-CONTRACT
title: Victus Processing Canonical Evidence Contract
status: source-of-truth
updated_at: 2026-06-06
related_components:
  - src.prompts.evidence_extraction.canonical_evidence_extractor
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - contracts
  - evidence
  - canonical-evidence
---

# Canonical Evidence Contract

## 1. Purpose

This contract defines normalized scientific evidence records extracted from one
experiment packet at a time.

Canonical Evidence is the first active stage that extracts normalized evidence.

## 2. Scope

Covered:

- canonical evidence object schema;
- evidence field semantics;
- source block and quote-level observation grounding;
- validation expectations.

Not covered:

- recommendations;
- final conclusions;
- cross-paper synthesis;
- study-quality ranking;
- downstream retrieval or reasoning outputs.

## 3. Inputs

`canonical_evidence_extractor` consumes:

```json
{
  "experiment_packet": {
    "source_block_ids": [],
    "blocks": []
  }
}
```

Each call processes exactly one experiment packet. The persisted
`canonical_evidence.json` aggregates validated outputs from all packet calls.

## 4. Output Envelope

```json
{
  "canonical_evidence": []
}
```

The prompt output envelope contains `canonical_evidence`. Runtime aggregation
may include `unextracted_packet_items` for compatibility, but prompt producers
and schema consumers must not require it.

The persisted output does not add `paper_id`, `experiment_id`, `packet_id`,
`canonical_evidence_id`, or `local_evidence_index`.

## 5. Canonical Evidence Object

Each canonical evidence object must include:

```json
{
  "evidence_type": "between_group_result|within_group_change|association|correlation|dose_response|time_course|subgroup_result|mechanistic_result|null_result|adverse_effect|feasibility_result|descriptive_result|specificity_or_selectivity_result|other|unclear",
  "evidence_text": "string",
  "population": "string|null",
  "subgroup": "string|null",
  "organism": "human|animal|in_vitro|mixed|unclear|null",
  "intervention_or_exposure": "string|null",
  "comparator": "string|null",
  "outcomes": ["string"],
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
  "source_block_ids": ["string"]
}
```

## 6. Invariants

- Each evidence object represents one reusable scientific result relation inside
  one experiment packet.
- One packet may produce zero, one, or many evidence objects.
- Evidence must be explicitly supported by one or more source blocks and one or
  more observations.
- Evidence must not be created unless at least one observation anchors the core
  finding with an exact `source_quote`.
- Evidence `source_block_ids`, observation `source_block_id`, and quantitative
  value `source_block_id` values must be subsets of the current packet
  `source_block_ids`.
- Every populated field must be explicitly supported by the current packet.
- Missing nullable fields remain `null`.
- Uncertain enum fields use `unclear`.
- Numerical values, units, signs, p-values, confidence intervals, effect sizes,
  ratios, deviations, sample counts, tests, and statistics must preserve source
  wording.
- Evidence extraction must not create recommendations, final conclusions, causal
  interpretations not present in the source, or external knowledge.

## 7. Observation And Source Semantics

`source_block_ids` is the complete block support set for the evidence object.

`observations` are quote-level anchors. Each observation must copy one concise
verbatim quote from one provided block and assign one `observation_role`.

Allowed observation roles:

- `primary_finding`;
- `quantitative_support`;
- `context_support`;
- `limitation_or_caution`.

Discussion blocks may provide secondary support, but they must not override
methods, results, tables, or figures.

## 8. Failure Expectations

- Invalid JSON must fail validation.
- Unknown source block ids must fail validation.
- Evidence without `source_block_ids` must fail validation.
- Evidence without one or more observations must fail validation.
- Observations without a valid `source_block_id`, non-empty `source_quote`, or
  valid `observation_role` must fail validation.
- Invalid enum values must fail validation.
- Invalid canonical evidence arrays must not be written as successful outputs.

## 9. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Stage Handoffs](stage-handoffs.md)
- [Artifact Schemas](artifact-schemas.md)
- [Block](block.md)
- [Experiment Map](experiment-map.md)
