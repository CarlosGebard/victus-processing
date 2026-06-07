---
id: VICTUS-PROCESSING-STAGE-HANDOFFS-CONTRACT
title: Victus Processing Stage Handoffs Contract
status: source-of-truth
updated_at: 2026-06-06
related_components:
  - src.application.metadata_extraction
  - src.application.metadata_to_pdf
  - src.application.pdf_processing
  - src.application.evidence_extraction
  - src.application.ports.llm
  - src.infrastructure.llm
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - contracts
  - stages
  - handoffs
---

# Stage Handoffs Contract

## 1. Purpose

This contract defines the stable boundaries between processing stages. Agents
must preserve these handoffs before changing stage internals.

## 2. Scope

Covered stages:

- metadata;
- bibliography;
- PDF normalization;
- PDF-processing Markdown and LLM extraction;
- trimming;
- experiment scope mapping;
- canonical evidence extraction.

Not covered:

- external retrieval service guarantees;
- downstream analytics or indexing;
- production deployment orchestration.

## 3. Guarantees

- Stages communicate through durable local files, not hidden process memory.
- Each stage may be run independently through the CLI.
- A stage may skip completed artifacts when a final output already exists.
- Stage handoff paths are repository-relative unless explicitly configured
  otherwise.
- Model-mediated stages retain enough local output for inspection after a run.

## 4. Handoff Map

```text
data/inputs/seeds/*.jsonl or --doi
  -> metadata JSON under data/runtime/01-candidates/active/
  -> optional BibTeX and relation/audit reports
  -> active PDFs under data/runtime/02-pdfs/active/
  -> data/runtime/03-pdf_processing/{paper_id}/paper.md
  -> data/runtime/03-pdf_processing/{paper_id}/raw_batches/*.json
  -> data/runtime/03-pdf_processing/{paper_id}/paper.processed.json
  -> data/runtime/03-pdf_processing/{paper_id}/paper.final.json
  -> data/runtime/04-evidence/{paper_id}/trimmed.json
  -> data/runtime/04-evidence/{paper_id}/experiment_map.json
  -> data/runtime/04-evidence/{paper_id}/canonical_evidence.json
```

## 5. Stage Contracts

### Metadata

- Inputs are DOI seed queues or a single DOI argument.
- Outputs are metadata records and reviewed/discarded candidate state.
- The stage covers pre-PDF candidate state only.
- `document_id` must not be treated as the post-PDF `paper_id` unless a
  specific compatibility path explicitly maps it.

### Bibliography

- Inputs are metadata JSON files or an explicit CSV.
- Output is a BibTeX file.
- The command is a derived export and must not mutate candidate state.

### PDF Normalization

- Inputs are raw PDFs plus DOI/PDF relation data.
- Outputs are normalized active PDFs.
- PDFs without resolved DOI relation belong in the configured unmatched
  location.
- Downstream `paper_id` is derived from active PDF filename stem.

### PDF Processing

- Inputs are active PDFs, Markdown prompts, an injected LLM client, and
  `pdf_processing` config.
- Outputs are `paper.md`, raw LLM batch JSON, `paper.processed.json`,
  `paper.final.json`, and status JSONL.
- `paper.md` is generated with Docling and may be reused unless forced.
- Raw batch files must be written before final merge so partial model output can
  be inspected.
- `section_registry`, `updated_section_registry`, and `batch_end` are internal
  batch-continuity artifacts only. They must not be treated as downstream
  scientific localization contracts.
- Final success requires a merged structured JSON file, processed-paper contract
  enforcement, trimmed block handoff, and a done status.
- Final downstream localization is through block identifiers and block fields.
- Final `paper.final.json` blocks must preserve the [Block](block.md)
  contract and should be treated as a compatibility name until the evidence
  artifact names are implemented.

### Paper Classification

- Inputs are structured paper metadata and blocks.
- Output is `paper.classifier_input.json` plus `paper.classification.json`.
- Classifier input removes whole blocks by `section_type`; it does not rewrite,
  summarize, split, merge, or interpret block text.
- Excluded section types are `front_matter`, `references`,
  `acknowledgements`, `funding`, `disclosure`, `ethics`, `appendix`, and
  `supplementary`.
- `paper_classifier` classifies how the paper itself generates knowledge.
- Evidence extraction continues only for `paper_family: primary_research`.
- Non-primary papers write `evidence_skipped.json` and must not call experiment
  mapping or canonical evidence extraction.

### Trimming

- Inputs are structured paper metadata and blocks.
- Outputs contain only `metadata-extraction` and `blocks`.
- Trimming removes whole blocks by `section_type`; it does not rewrite,
  summarize, split, merge, or interpret block text.
- Preserved section types are `methods`, `results`, `discussion`, and
  `conclusion`.
- `section_registry`, `updated_section_registry`, `batch_end`, sections,
  warnings, and processing state are obsolete after trimming and must not
  continue downstream.

### Experiment Scope Mapping

- Inputs are trimmed `blocks` only.
- Output is an experiment map generated by `results_scope_mapper`.
- The map groups related blocks into broad experiment scopes using block
  identifiers.
- Each experiment scope defines one canonical extraction packet through its
  `source_block_ids`.
- The map does not consume metadata, paper title, section registry, or external
  knowledge.
- The map does not extract evidence, infer results, or populate population,
  intervention, comparator, outcome, direction, dose, duration, or statistics.
- The mapper output only requires `source_block_ids` per scope; optional scope
  metadata may be preserved for compatibility but must not be required by
  downstream schema consumers.

### Experiment Packet Construction

- Inputs are trimmed `metadata-extraction` and `blocks`, plus the validated
  `experiment_map`.
- Output is `experiment_packets.json`.
- Packet construction is deterministic and does not call an LLM.
- Each packet contains one scope and exactly the blocks referenced by that
  scope's `source_block_ids`.
- A block may appear in multiple packets when the experiment map includes it in
  multiple scopes.
- Canonical extraction must not use blocks outside the current packet.

### Canonical Evidence

- Inputs are one experiment packet per LLM call.
- Output is canonical evidence generated by `canonical_evidence_extractor`.
- Canonical evidence is the first active stage that extracts normalized
  evidence.
- The final `canonical_evidence.json` aggregates validated canonical outputs
  from all packets.
- Evidence validation must happen before writing a successful output file.

## 6. Failure Expectations

- A failed stage must not be represented as a successful final artifact.
- PDF-processing classified errors include `docling_failed`,
  `batching_failed`, `llm_failed`, or `processing_failed`.
- Directory-level PDF-processing continues other pending PDFs when one PDF
  fails.
- Provider retry, fallback, and quota behavior is handled by LiteLLM.
- Evidence extraction records per-file failures in CLI output and continues
  through remaining input files when supported.

## 7. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Data Layout](data-layout.md)
- [Artifact Schemas](artifact-schemas.md)
- [Block](block.md)
- [Paper Classification](paper-classification.md)
- [Experiment Map](experiment-map.md)
- [Canonical Evidence](canonical-evidence.md)
- [PDF processing operations](../operations/pdf-processing.md)
