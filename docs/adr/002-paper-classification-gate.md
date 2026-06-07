---
id: ADR-002-PAPER-CLASSIFICATION-GATE
title: Paper Classification Gate Before Evidence Extraction
status: accepted
updated_at: 2026-06-06
related_docs:
  - VICTUS-PROCESSING-PAPER-CLASSIFICATION-CONTRACT
  - VICTUS-PROCESSING-STAGE-HANDOFFS-CONTRACT
  - VICTUS-PROCESSING-ARTIFACT-SCHEMAS-CONTRACT
tags:
  - adr
  - evidence
  - classification
---

# Paper Classification Gate Before Evidence Extraction

## 1. Context

Canonical evidence extraction is intended for primary research papers. Running
mapper and evidence extraction on reviews, methods papers, commentaries, or
other non-primary papers creates low-value artifacts and can confuse downstream
routing.

The existing evidence stage trimmed directly to methods, results, discussion,
and conclusion before mapping experiments. That trim is appropriate for evidence
extraction but too narrow for classifying the paper family.

## 2. Decision

The evidence stage now creates `paper.classifier_input.json` from
`paper.processed.json` before evidence trimming.

Classifier input removes only administrative sections:
`front_matter`, `references`, `acknowledgements`, `funding`, `disclosure`,
`ethics`, `appendix`, and `supplementary`.

The `paper_classifier` prompt produces `paper.classification.json`.
Only papers with `paper_family: primary_research` continue to evidence
trimming, experiment mapping, experiment packet construction, and canonical
evidence extraction.

Non-primary papers write `evidence_skipped.json` and stop before trimming.

## 3. Tradeoffs

Positive:

- Prevents non-primary papers from entering primary-research evidence
  extraction.
- Keeps classification input separate from evidence trimming.
- Produces explicit skip artifacts instead of silent no-op behavior.

Negative:

- Adds one LLM call per paper before evidence extraction.
- Evidence output paths may contain `evidence_skipped.json` instead of
  `canonical_evidence.json`.
- Classification failures now block evidence extraction.

## 4. Alternatives Considered

- Reuse `trimmed.json` for classification.
  Rejected because trimmed evidence input removes too much context for reliable
  paper-family classification.
- Classify during Markdown batching.
  Rejected because classification should happen after the full structured paper
  is available.
- Run evidence extraction for all paper families and filter downstream.
  Rejected because it wastes model calls and creates misleading artifacts for
  non-primary papers.

## 5. Consequences

Downstream consumers must treat `evidence_skipped.json` as a valid terminal
evidence-stage outcome for non-primary papers.

Future evidence-stage changes must preserve the separation between classifier
input and evidence-trimmed input.

## 6. Related Documents

- [Paper Classification](../contracts/paper-classification.md)
- [Stage Handoffs](../contracts/stage-handoffs.md)
- [Artifact Schemas](../contracts/artifact-schemas.md)
