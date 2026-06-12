---
id: VICTUS-DATA-LAYOUT-MIGRATION-RUNBOOK
title: Data Layout Migration Runbook
status: draft
updated_at: 2026-06-10
related_components:
  - ops.scripts.data.migrate_data_layout
related_docs:
  - VICTUS-PROCESSING-DATA-LAYOUT-CONTRACT
tags:
  - operations
  - data-layout
  - migration
---

# Data Layout Migration

Use this runbook to audit or copy legacy `data/` files into the target data
layout.

The migration script is conservative. It does not delete files. It reports:

- non-conflicting copies;
- conflicts where the target exists with different content;
- unresolved legacy files that need a manual decision.

## Dry Run

```bash
uv run python -m ops.scripts.data.migrate_data_layout --limit 40
```

Write a full JSON report:

```bash
uv run python -m ops.scripts.data.migrate_data_layout \
  --report /tmp/victus-data-layout-migration-report.json
```

## Apply Non-Conflicting Copies

Only run this after reviewing the dry-run output:

```bash
uv run python -m ops.scripts.data.migrate_data_layout --apply
```

The command refuses to apply if conflicts exist.

## Current Copy Targets

- `data/runtime/02-pdfs/active/*.pdf` -> `data/artifacts/pdfs/*.pdf`
- `data/runtime/03-pdf_processing/{paper_id}/paper.md` ->
  `data/artifacts/markdown/{paper_id}.md`

## Manual Decision Categories

- `legacy_paper_bundle_needs_manual_classification`: old `data/papers/` bundle
  content. Decide whether it is obsolete or should be converted into lake
  records/artifacts.
- `needs_debug_raw_batches_jsonl_conversion`: old batch JSON files that need
  conversion to `debug/runs/{run_id}/{paper_id}/raw_batches.jsonl`.
- `needs_debug_failed_batches_jsonl_conversion`: old failed batch files that
  need conversion to `debug/runs/{run_id}/{paper_id}/failed_batches.jsonl`.
- `needs_lake_evidence_jsonl_promotion`: old evidence JSON files that need
  conversion into lake records.
- `needs_structured_blocks_jsonl_promotion`: old `paper.processed.json` output
  that needs conversion into `structured_blocks.jsonl`.
- `compatibility_output_not_in_new_layout`: old `paper.final.json`
  compatibility output.
- `legacy_testing_layout`: old `data/testing/{paper_id}` or root testing files.
- `no_target_in_current_contract`: data that has no destination in the current
  contract.

## Validation

```bash
uv run pytest tests/test_cli_smoke.py -q
uv run contracts validate
```
