# victus-processing

Estado documental: `source-of-truth` desde `2026-05-27`.

Pipeline local para convertir papers científicos en metadata, PDFs
normalizados, bloques estructurados y evidencia canónica.

## Qué Resuelve

- busca candidatos en Semantic Scholar
- guarda metadata canónica
- linkea PDFs obtenidos manualmente
- procesa PDFs con Docling y heurísticas locales
- extrae evidencia canónica con modelos LLM via LiteLLM

## Uso Local

```bash
uv sync
uv run victus-processing --help
uv run victus-processing data-layout create
```

Flujo principal:

```bash
uv run victus-processing metadata-extraction explore --mode broad-nutrition
uv run victus-processing bibliography-export generate-bib
uv run victus-processing pdf-intake link --metadata-id meta:s2:example --pdf data/artifacts/intake/pdfs/example.pdf
uv run victus-processing pdf-processing run
```


## Validar

```bash
uv run pytest tests/test_cli_smoke.py -q
```

## Leer Más

Para tener la imagen completa de el projecto de victus visitar:
https://wiki.victus.fit/
