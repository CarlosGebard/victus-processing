# victus-processing

Estado documental: `source-of-truth` desde `2026-05-27`.

Pipeline local para convertir papers científicos en metadata, PDFs
normalizados, bloques estructurados y evidencia canónica.

## Qué Resuelve

- busca candidatos en Semantic Scholar
- guarda metadata canónica
- normaliza PDFs crudos
- procesa PDFs con Docling y heurísticas locales
- extrae evidencia canónica con modelos LLM via LiteLLM
- expone bridge para registry, storage y eventos Victus

## Uso Local

```bash
uv sync
uv run victus-processing --help
uv run victus-processing data-layout create
```

Flujo principal:

```bash
uv run victus-processing metadata-extraction explore --mode broad-nutrition
uv run victus-processing metadata-to-pdf normalize-pdfs
uv run victus-processing pdf-processing run
```


## Validar

```bash
uv run pytest tests/test_cli_smoke.py -q
```

## Leer Más

- [Contexto del sistema](000-SYSTEM-CONTEXT.md)
- [Arquitectura](100-ARCHITECTURE.md)
- [Contratos](300-CONTRACTS.md)
- [Contrato de layout](contracts/local/data-layout.md)
- [Contrato de configuración y CLI](contracts/local/configuration-and-cli.md)
- [Contrato de handoffs](contracts/local/stage-handoffs.md)
- [Contrato de schemas](contracts/local/artifact-schemas.md)
- [Contrato de StructuredBlock](contracts/fundamental/scientific/structured-block.md)
- [Contrato de ExperimentMap](contracts/fundamental/scientific/experiment-map.md)
- [Contrato de CanonicalEvidence](contracts/fundamental/scientific/canonical-evidence.md)
- [Operación](200-OPERATIONS.md)
- [CLI local](operations/cli.md)
- [Runbooks](operations/runbooks/)
