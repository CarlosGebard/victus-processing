# victus-processing

Pipeline local para convertir papers científicos en metadata, PDFs
normalizados, artefactos estructurados y claims.

## Qué Resuelve

- busca candidatos en Semantic Scholar
- guarda metadata canónica
- normaliza PDFs crudos
- procesa PDFs con Docling y heurísticas locales
- extrae claims con modelos OpenAI
- expone bridge para registry, storage y eventos Victus

## Uso Local

```bash
uv sync
uv run victus-processing --help
uv run victus-processing data-layout create
```

Flujo principal:

```bash
uv run victus-processing metadata explore --mode broad-nutrition
uv run victus-processing pdfs normalize
uv run victus-processing pdf-processing run
uv run victus-processing claims extract --skip-existing
```

## Validar

```bash
uv run pytest tests/test_cli_smoke.py -q
```

## Leer Más

- [Contexto del sistema](000-SYSTEM-CONTEXT.md)
- [Arquitectura](100-ARCHITECTURE.md)
- [Contratos](300-CONTRACTS.md)
- [Operación](200-OPERATIONS.md)
- [CLI local](operations/cli.md)
- [Runbooks](operations/runbooks/)
