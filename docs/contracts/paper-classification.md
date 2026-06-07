---
id: VICTUS-PROCESSING-PAPER-CLASSIFICATION-CONTRACT
title: Victus Processing Paper Classification Contract
status: source-of-truth
updated_at: 2026-06-06
related_components:
  - src.application.evidence_extraction.evidence
  - src.application.evidence_extraction.llm_evidence
  - src.prompts.evidence_extraction.paper_classifier
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
  - VICTUS-PROCESSING-STAGE-HANDOFFS-CONTRACT
  - VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
tags:
  - contracts
  - paper-classification
  - evidence
---

# Paper Classification Contract

## 1. Purpose

This contract defines the paper-classification handoff between structured
PDF-processing output and evidence extraction.

## 2. Scope

Covered:

- `paper.classifier_input.json`;
- `paper.classification.json`;
- `evidence_skipped.json`;
- the primary-research gate before evidence extraction.

Not covered:

- classifier prompt wording;
- canonical evidence extraction schema;
- downstream analytics or ranking.

## 3. Guarantees

- Classification input is built from `paper.processed.json`.
- Classification input is not `trimmed.json`.
- Classification input contains only `metadata` and `blocks`.
- Classification input removes whole blocks by `section_type`; it does not
  rewrite, summarize, split, merge, or interpret block text.
- `paper_classifier` classifies the paper itself, not cited studies.
- Evidence extraction continues only when `paper_family` is `primary_research`.
- Non-primary papers write `evidence_skipped.json` and must not call experiment
  mapping or canonical evidence extraction.

## 4. Invariants

Classifier input excludes these section types:

```text
front_matter
references
acknowledgements
funding
disclosure
ethics
appendix
supplementary
```

Classifier input block objects must preserve these fields when present:

```text
block_id
paper_id
section_path
section_type
content_kind
text
```

`paper.classification.json` must contain:

```text
paper_family
paper_type
evidence_generation_mode
has_original_experiments
has_systematic_search
has_meta_analysis
classification_confidence
quality_flags
risk_flags
routing_evidence
reasoning_summary
```

Allowed `paper_family` values:

```text
primary_research
evidence_synthesis
methodological
case_based
opinion_or_theory
unknown
```

Allowed `evidence_generation_mode` values:

```text
generates_original_data
synthesizes_existing_evidence
proposes_method
reports_cases
argues_or_interprets
unclear
```

## 5. Inputs and Outputs

Input:

```text
data/runtime/03-pdf_processing/{paper_id}/paper.processed.json
```

Runtime evidence outputs:

```text
data/runtime/04-evidence/{paper_id}/paper.classifier_input.json
data/runtime/04-evidence/{paper_id}/paper.classification.json
data/runtime/04-evidence/{paper_id}/evidence_skipped.json
```

Testing outputs use the same filenames under:

```text
data/testing/{paper_id}/
```

`evidence_skipped.json` shape:

```text
{
  "paper_id": string,
  "reason": "non_primary_research",
  "paper_family": string,
  "paper_type": string,
  "evidence_generation_mode": string
}
```

## 6. Failure Expectations

- Invalid classifier JSON must fail the evidence stage.
- Missing required classifier fields must fail validation.
- Unknown `paper_family` or `evidence_generation_mode` values must fail
  validation.
- Non-primary classification is not a failure; it is a terminal skipped evidence
  outcome.

## 7. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Stage Handoffs](stage-handoffs.md)
- [Artifact Schemas](artifact-schemas.md)
- [Paper Classification Gate ADR](../adr/002-paper-classification-gate.md)
