---
id: VICTUS-PROCESSING-CLAIMS-SCHEMA-CONTRACT
title: Victus Processing Claims Schema Contract
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
related_components:
  - src.application.claims.extraction
  - src.prompts.claims
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
tags:
  - contracts
  - claims
  - schemas
---

# Claims Schema Contract

## 1. Purpose

This contract defines the normalized claim object extracted from structured
paper content. It is the first contract agents should review before changing
claim extraction prompts, claim validation, downstream claim consumers, or
claim-related artifact schemas.

## 2. Scope

Covered:

- the required keys for each extracted claim;
- the scientific meaning of each claim field;
- allowed categorical values;
- nullability expectations;
- statistics subfields;
- validation expectations before writing successful claims output.

Not covered:

- full paper-processing schemas;
- provider API response envelopes;
- downstream analytics tables;
- ranking, retrieval, or scoring systems outside this repository.

## 3. Output Envelope

Claims extraction writes a JSON object with metadata and a list of claim
objects:

```json
{
  "metadata": {
    "model": "string",
    "source_final_json": "string",
    "claims_limit": 0,
    "estimated_input_tokens": 0
  },
  "claims": []
}
```

The `claims` array must contain only objects that satisfy this contract.

## 4. Claim Object Schema

Each claim object must include every key below:

```json
{
  "claim_text": "string",
  "claim_family": "primary_outcome | secondary_outcome | adherence_biomarker | safety | risk_association | other_empirical",
  "support_section": "section title or mixed",
  "population": "string or null",
  "subgroup": "string or null",
  "intervention_or_exposure": "string or null",
  "comparator": "string or null",
  "arm": "string or null",
  "comparison_type": "between_group | within_group | association | null",
  "outcome": "string or null",
  "direction": "increase | decrease | no_effect | association | difference | null",
  "units": "string or null",
  "baseline_value": "string or null",
  "followup_value": "string or null",
  "within_group_change": "string or null",
  "between_group_difference": "string or null",
  "dose": "string or null",
  "duration": "string or null",
  "timepoint": "string or null",
  "study_design": "string or null",
  "sample_size": "string or null",
  "keywords": ["string"],
  "statistics": {
    "p_value": "string or null",
    "confidence_interval": "string or null",
    "other": "string or null"
  },
  "evidence_span": "exact supporting sentence(s) or exact table/figure-related text copied verbatim from the provided content",
  "confidence": 0.0
}
```

## 5. Field Semantics

- `claim_text`: normalized, self-contained version of the finding.
- `claim_family`: scientific role of the claim within the paper.
- `support_section`: section that supports the claim, or `mixed` when support
  spans multiple sections.
- `population`: main population to which the finding applies.
- `subgroup`: narrower analytic subset of the population.
- `intervention_or_exposure`: intervention, exposure, dose group, condition, or
  factor being evaluated.
- `comparator`: explicit comparator for the claim, usually another group such
  as control.
- `arm`: measurement arm or study group from which the value comes.
- `comparison_type`: type of comparison represented by the claim.
- `outcome`: medical endpoint or measured variable.
- `direction`: direction of the finding.
- `units`: unit used for the outcome measurement.
- `baseline_value`: baseline or pre-intervention value.
- `followup_value`: explicitly reported follow-up value.
- `within_group_change`: change within the same group or arm.
- `between_group_difference`: difference between groups.
- `dose`: dose or exposure level.
- `duration`: experiment or intervention duration.
- `timepoint`: specific measurement or evaluation moment.
- `study_design`: study design, such as randomized, prospective, or
  cross-sectional.
- `sample_size`: number of participants or analytic sample size.
- `keywords`: retrieval-oriented keywords grounded in the source content.
- `statistics.p_value`: reported p-value.
- `statistics.confidence_interval`: reported confidence interval.
- `statistics.other`: other reported statistical support.
- `evidence_span`: exact supporting sentence, sentences, table text, or figure
  text copied from the provided content.
- `confidence`: numeric confidence that the claim is directly and completely
  supported by the provided content.

## 6. Required Value Constraints

- `claim_text`, `claim_family`, `support_section`, and `evidence_span` must be
  non-empty strings.
- `confidence` must be numeric.
- `keywords` must be a list.
- `statistics` must be an object.
- Nullable contextual fields must be present even when their value is `null`.
- `evidence_span` must be copied from the provided content and must not invent
  support text.

## 7. Allowed Values

`claim_family` values:

```text
primary_outcome
secondary_outcome
adherence_biomarker
safety
risk_association
other_empirical
```

`comparison_type` values:

```text
between_group
within_group
association
null
```

`direction` values:

```text
increase
decrease
no_effect
association
difference
null
```

## 8. Extraction Guarantees

- Claims must be empirical, health-related, atomic, and explicitly supported.
- Claims must not overgeneralize beyond the provided population, subgroup,
  comparator, timepoint, or study design.
- Numerical values, units, p-values, confidence intervals, and other statistics
  must preserve source fidelity.
- A comparator must be present only when the source explicitly reports one.
- Population and subgroup must not duplicate the same scope.
- Keywords must be grounded in the source and useful for retrieval.
- Claims with confidence below the extraction threshold must be excluded rather
  than written with low confidence.

## 9. Failure Expectations

- Model output that is not a JSON array must fail validation.
- Any claim missing a required key must fail validation.
- Empty `claim_text`, `claim_family`, `support_section`, or `evidence_span`
  must fail validation.
- Non-numeric `confidence`, non-list `keywords`, or non-object `statistics`
  must fail validation.
- Invalid claim arrays must not be written as successful claims output.
- Removing required fields requires an explicit contract update.

## 10. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Artifact Schemas](artifact-schemas.md)
- [Stage Handoffs](stage-handoffs.md)
