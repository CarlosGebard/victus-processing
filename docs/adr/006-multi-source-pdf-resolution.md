---
id: ADR-006
title: Multi-source DOI-to-PDF resolution
status: accepted
updated_at: 2026-06-19
owners:
  - victus-processing
related_docs:
  - docs/contracts/local/metadata-to-pdf-resolution.md
  - docs/operations/pipeline/pdf-intake.md
---

# Multi-source DOI-to-PDF Resolution

## Context

Unpaywall alone does not cover every legally accessible PDF. Independent
provider scripts would duplicate retry state and could mark a paper complete
before all providers were attempted.

## Decision

Use one ordered resolver: metadata URL, Unpaywall, Europe PMC/PMC, then CORE.
Provider failures are isolated. The first valid PDF is promoted; otherwise the
best landing or PDF URL is retained. One final status record contains all
provider attempts.

The existing `unpaywall_pdf_status.jsonl` filename remains for compatibility,
but its semantic role becomes multi-source resolution history.

## Tradeoffs

- Coverage and traceability improve without adding state files.
- The compatibility filename no longer describes the complete contents.
- CORE requires optional credentials and has independent quota constraints.
- External URLs remain hints; only PDF-signature validation permits promotion.

## Alternatives Considered

- One status JSONL per provider: rejected because reconciliation and resume
  semantics become ambiguous.
- Parallel provider calls: rejected because they spend quota after an earlier
  source has already produced a valid PDF.
- Rename the existing status file immediately: rejected to avoid breaking
  current operations and historical data.

## Consequences

Consumers must use `source`, `resolution_status`, and `attempts`, not infer the
provider from the filename. A future major migration may rename the file after
existing data and operators are migrated.

## Related Documents

- [Resolution contract](../contracts/local/metadata-to-pdf-resolution.md)
- [PDF intake operations](../operations/pipeline/pdf-intake.md)
