# Data Layout
Local `data/` mirrors Seaweed keys for processed papers and keeps candidates/runtime separate.
## Tree
```text
data/
  candidates/
    active/{document_id}/
    discarded/{document_id}/
  papers/
    {paper_id}/
  registry/
  inputs/
    seeds/
    rules/
    imports/
  runtime/
    pdf_retrieval/
    tmp/
    logs/
    queues/
  reports/
    audits/
    exports/
  archive/
    legacy/
    experiments/


```
## Identity
- `document_id`: pre-PDF identity.
- `paper_id`: SHA256 of `raw/source.pdf`.
- Pre-PDF records live under `data/candidates`.
- Post-PDF canonical artifacts live under `data/papers/{paper_id}`.
## Current Contract
- `data/papers/{paper_id}` mirrors Seaweed key prefix `papers/{paper_id}`.
- `data/candidates` stores pre-PDF metadata.
- `data/runtime` stores temporary or unresolved files only.
## Active Paths
| Purpose | Path |
|---|---|
| metadata candidates | `data/candidates/active` |
| discarded candidates | `data/candidates/discarded` |
| registry | `data/registry` |
| papers | `data/papers/{paper_id}` |
| paper raw PDF | `data/papers/{paper_id}/raw/source.pdf` |
| paper metadata | `data/papers/{paper_id}/metadata/source.json` |
| paper docling | `data/papers/{paper_id}/docling/*.json` |
| paper claims | `data/papers/{paper_id}/claims/claims.json` |
| unresolved PDFs | `data/runtime/pdf_retrieval/unmapped_raw` |
| seed DOIs | `data/inputs/seeds` |
| rules | `data/inputs/rules` |
| imports | `data/inputs/imports` |
## Seaweed Mirror Target
```text
data/papers/{paper_id}/raw/source.pdf
data/papers/{paper_id}/metadata/source.json
data/papers/{paper_id}/docling/final.json
data/papers/{paper_id}/claims/claims.json
```
Remote keys:
```text
papers/{paper_id}/raw/source.pdf
papers/{paper_id}/metadata/source.json
papers/{paper_id}/docling/final.json
papers/{paper_id}/claims/claims.json
```
## Discard Rule
- Discard before PDF: `data/candidates/discarded/{document_id}`.
- Discard after PDF: `data/papers/{paper_id}/manifests/discard.json`.
- Global index: `data/registry/discards.jsonl`.
## Migration State
- Raw and normalized mapped PDFs were mirrored into `data/papers/{paper_id}`.
- Metadata and Docling were linked through `data/registry/links.jsonl`.
- Archive claims with links were moved into `data/papers/{paper_id}/claims`.
- Unmapped raw PDFs remain under `data/runtime/pdf_retrieval/unmapped_raw`.
## CLI
```bash
victus-processing data-layout create --dry-run
```
