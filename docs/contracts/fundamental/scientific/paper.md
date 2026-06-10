---
id: VICTUS-CONTRACT-PAPER
contract_id: victus.scientific.paper
title: Paper
status: active
version: v1
owner: victus-processing
domain: scientific
contract_type: domain
stability: foundation
updated_at: 2026-06-09
---

# Paper Contract Documentation

## 1. Purpose

Represent the canonical scientific publication identity used throughout Victus.

`Paper` provides a stable, traceable, reusable reference to a scientific
publication independently of processing pipelines, storage systems, extraction
stages, retrieval systems, or downstream evidence generation.

`Paper` is the root scientific artifact from which all other scientific objects
originate.

## 2. Identity

### Identity Rules

- Canonical identifier: `paper_id`
- `paper_id` is globally unique inside Victus.
- `paper_id` is immutable after creation.
- `paper_id` is deterministic for the same canonical publication identity.
- All downstream scientific artifacts must reference `Paper` through `paper_id`.
- External identifiers such as DOI, PMID, PMCID, and arXiv ID are metadata
  identifiers, not Victus identity.
- External identifiers may support deduplication, but must not replace
  `paper_id`.
- DOI may be used for deduplication, reconciliation, and identity resolution,
  but it must not become the mandatory primary identifier for `Paper`.
- Legacy operational identifiers, including active PDF filename stems, are not
  canonical scientific `paper_id` values.

### Ownership

`Paper` is owned by the metadata ingestion layer.

Metadata enrichment workflows may update bibliographic fields, but must not
change the identity of the object.

## 3. Schema

### JSON Schema

```json
{
  "paper_id": "string",
  "title": "string",
  "publication_year": "integer | null",
  "doi": "string | null",
  "pmid": "string | null",
  "pmcid": "string | null",
  "arxiv_id": "string | null",
  "source_url": "string | null",
  "authors": [
    {
      "name": "string"
    }
  ],
  "journal": "string | null",
  "language": "string | null",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## 4. Field Definitions

| Field | Type | Description |
|---|---|---|
| `paper_id` | String | Canonical Victus identifier for the publication. |
| `title` | String | Canonical publication title. |
| `publication_year` | Integer / Null | Publication year when available. |
| `doi` | String / Null | Digital Object Identifier when available. |
| `pmid` | String / Null | PubMed identifier when available. |
| `pmcid` | String / Null | PubMed Central identifier when available. |
| `arxiv_id` | String / Null | arXiv identifier when available. |
| `source_url` | String / Null | External source URL or publication landing page. |
| `authors` | List of Objects | Ordered list of publication authors. |
| `authors.name` | String | Author display name from the metadata source. |
| `journal` | String / Null | Journal, conference, publisher, or publication venue. |
| `language` | String / Null | Detected or declared publication language. |
| `created_at` | Timestamp | Object creation timestamp inside Victus. |
| `updated_at` | Timestamp | Last object update timestamp. |

## 5. Responsibilities

### Required Responsibilities

`Paper` must:

- identify one scientific publication
- preserve core bibliographic metadata
- provide stable traceability for downstream objects
- support metadata enrichment and deduplication
- remain independent from processing pipeline versions
- maintain explicit provenance links from pre-PDF operational identifiers, such
  as `document_id`, to canonical `paper_id`

### Forbidden Responsibilities

`Paper` must not store:

- extracted content
- structured blocks
- paper classification
- evidence
- claims
- embeddings
- retrieval chunks
- pipeline state
- audit logs
- storage paths as identity
- generated summaries or conclusions

`Paper` must not infer scientific meaning.

## 6. Validation Rules

- `paper_id`, `title`, `authors`, `created_at`, and `updated_at` are required.
- `paper_id` must be unique and immutable.
- `paper_id` must be deterministic for the same canonical publication identity.
- `title` must not be empty.
- `authors` must always be a list.
- Author names must not be empty when present.
- Nullable fields must use `null`.
- Empty strings must be normalized to `null`.
- Unknown values must not be invented.
- External identifiers must preserve source formatting.
- `created_at` must be set once.
- `updated_at` must change when the object is modified.

## 7. Lifecycle

### Created

Created after successful metadata ingestion or extraction.

Typical sources:

- DOI
- PubMed
- PubMed Central
- Crossref
- Semantic Scholar
- arXiv
- manual ingestion

### Updated

Updated only when bibliographic metadata is enriched or corrected.

### Deleted

Not deleted under normal operation.

### Deprecated

Deprecated only when confirmed as a duplicate of another canonical `Paper`.

## 8. Relationships

### Upstream Contracts

None.

`Paper` is a root contract.

### Downstream Contracts

- `StructuredBlock`
- `ExperimentMap`
- `CanonicalEvidence`
- `Embedding`

### References

- `StructuredBlock.paper_id` -> `Paper.paper_id`
- `ExperimentMap.paper_id` -> `Paper.paper_id`
- `CanonicalEvidence.paper_id` -> `Paper.paper_id`
- `Embedding.paper_id` -> `Paper.paper_id`

## 9. Operational Notes

`Paper` should be small, stable, frequently reused, and inexpensive to load.

`Paper` is suitable for PostgreSQL storage as a canonical metadata table.

Object storage paths may reference `paper_id`, but must not define publication
identity.

Downstream artifacts may be regenerated without modifying `Paper`.

`paper.md`, `paper.processed.json`, and `paper.final.json` are operational
pipeline artifacts. They may implement or carry `StructuredBlock` data, but they
are not canonical scientific contracts.

Pipeline, parser, model, and prompt versions belong in a separate provenance
contract such as `ProcessingProvenance` or `ExtractionRun`, not in `Paper`.

## 10. Versioning

### Patch

Documentation clarification or validation wording refinement.

### Minor

Additive nullable fields or additive external identifiers.

### Major

Breaking schema changes, identity changes, field removals, or semantic meaning
changes.
