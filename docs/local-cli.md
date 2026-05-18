# Local CLI Contract
CLI local de `victus-processing`. Orquesta metadata, PDFs, claims, bridge y layout desde una entrada estable.
## Entry Points
```bash
victus-processing --help
python -m src.cli --help
```
## Boundaries
Owns:
- parser `argparse`
- grupos y flags públicos
- routing hacia stage modules dentro de cada dominio (`src.metadata.stage`, `src.pdf.stage`, `src.docling.stage`, `src.claims.stage`)
- routing hacia módulos en `ops/scripts/*`
- wrapper local hacia bridge
Does not own:
- config runtime: `src/config.py`
- lógica de dominio: `src/metadata`, `src/pdf`, `src/docling`, `src/claims`
- contratos bridge: `ops/scripts/bridge`
- storage/DB/event bus bridge
## Groups
| Grupo | Propósito |
|---|---|
| `metadata` | exploración, alta desde DOI, seed DOI candidates |
| `bib` | generación BibTeX |
| `pdfs` | normalización raw PDF -> input PDFs |
| `docling` | ejecución Docling/heuristics sobre PDFs normalizados |
| `claims` | extracción LLM claims desde `*.final.json` |
| `bridge` | wrapper a CLI bridge |
| `data-layout` | bootstrap explícito de estructura `data/` |
## Commands
```bash
victus-processing metadata explore [--mode broad-nutrition|dataset-gaps]
victus-processing metadata from-doi --doi DOI [--output-dir DIR] [--overwrite]
victus-processing metadata seed-dois [--mode broad-nutrition|dataset-gaps] [--metadata-dir DIR] [--explored-dois FILE] [--output FILE] [--min-citations N] [--limit N] [--terms-file FILE] [--papers-csv FILE] [--unclassified-csv FILE] [--topics-file FILE]
victus-processing bib generate [--output FILE] [--input-csv FILE]
victus-processing pdfs normalize [--raw-dir DIR] [--input-dir DIR] [--unmatched-dir DIR] [--relations-csv FILE]
victus-processing docling run [--runners N]
victus-processing claims extract [--input PATH] [--output PATH] [--model MODEL] [--max-claims N] [--temperature FLOAT] [--pattern GLOB] [--auto-approve-under-7000-tokens] [--skip-existing]
victus-processing bridge <bridge-command>
victus-processing data-layout create [--dry-run]
```
## Contracts
### Paths
- CLI resuelve `Path` con `expanduser().resolve()` para comandos locales que reciben archivos/dirs.
- Defaults salen de `src/config.py`.
- `pdfs normalize` usa fallback para raw PDFs vía `ctx.resolve_available_raw_pdf_dir(...)`.
- Layout activo documentado en `docs/data-layout/`.
- Artifacts procesados viven en `data/papers/{paper_id}`.
### Metadata
- `metadata explore` llama `run_metadata_exploration_flow(mode=...)`.
- El modo sale de `--mode`; si no se pasa, usa `exploration.mode` en `config.yaml`.
- `metadata from-doi` usa Semantic Scholar session y escribe metadata canónica.
- `metadata seed-dois` tiene dos modos: `broad-nutrition` y `dataset-gaps`.
### Docling
- `docling run` llama `run_docling_flow(runners=N, pdf_path=None)`.
- `--pdf` permite procesar un PDF normalizado puntual.
### Claims
- `claims extract` llama `run_llm_to_claim_flow(...)`.
- `--auto-approve-under-7000-tokens` usa límite desde config.
- `--skip-existing` evita outputs ya existentes.
### Bridge
- `bridge` delega parser a `victus_ingest_bridge.cli.configure_parser`.
- Comandos bridge mantienen contrato propio en `ops/scripts/bridge/README.md` y `docs/contracts/bridge-processing-changes/`.
## Side Effects
| Comando | Escribe |
|---|---|
| `metadata explore` | metadata canónica configurada |
| `metadata from-doi` | JSON metadata |
| `metadata seed-dois` | txt de DOIs |
| `bib generate` | `.bib` si output aplica |
| `pdfs normalize` | PDFs normalizados y unmatched |
| `docling run` | artifacts Docling/heuristics |
| `claims extract` | `data/runtime/claims/{model}/{paper}.claims.json` |
| `data-layout create` | directorios `data/` |
| `bridge ...` | depende de bridge command |
## Env
- Pipeline/claims pueden requerir `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_METADATA_SELECTION_MODEL`.
- Metadata DOI puede requerir `SEMANTIC_SCHOLAR_API_KEY`.
- Bridge requiere env bridge: `VICTUS_PG_DSN`, `VICTUS_REDIS_URL`, `VICTUS_S3_ENDPOINT`, `VICTUS_S3_ACCESS_KEY`, `VICTUS_S3_SECRET_KEY`.
## Operational Notes
- Usar `victus-processing <group> --help` para flags exactas.
- Preferir entrypoint instalado `victus-processing`.
- Usar fallback path solo en desarrollo local.
- No correr comandos con side effects sin revisar defaults de `src/config.py`.
## Minimal Check
```bash
victus-processing --help
```
