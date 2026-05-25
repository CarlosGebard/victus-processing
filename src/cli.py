from __future__ import annotations

import argparse
from pathlib import Path

from src.workspace import config as ctx
from src.claims.stage import run_llm_to_claim_flow
from src.workspace.data_layout import create_data_layout
from src.pdf_extraction.json_to_bib import generate_bib_flow
from src.metadata import citation_exploration, gap_seed_dois, seed_dois
from src.pdf_extraction import normalize_from_relations
from src.pdf_processing.pipeline import load_pdf_processing_config, run_pdf_processing, run_pdf_processing_dir

run_metadata_exploration_flow = None


CLI_DESCRIPTION = (
    "CLI profesional para el pipeline de papers. "
    "Organizada por dominios: metadata, bib, pdfs, pdf-processing, claims, bridge y data-layout."
)


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def _optional_resolved(path: Path | None) -> Path | None:
    return _resolved(path) if path is not None else None


def cmd_metadata_explore(args: argparse.Namespace) -> None:
    global run_metadata_exploration_flow
    if run_metadata_exploration_flow is None:
        from src.metadata.stage import run_metadata_exploration_flow as loaded_run_metadata_exploration_flow

        run_metadata_exploration_flow = loaded_run_metadata_exploration_flow

    run_metadata_exploration_flow(mode=args.mode)


def cmd_metadata_from_doi(args: argparse.Namespace) -> None:
    try:
        output_path, status = citation_exploration.write_metadata_for_doi(
            args.doi,
            output_dir=_resolved(args.output_dir),
            overwrite=args.overwrite,
        )
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    if status == "skipped_existing":
        print(f"[SKIP EXISTING] {output_path}")
        return
    print(f"[OK] Metadata guardada en {output_path}")


def cmd_metadata_seed_dois(args: argparse.Namespace) -> None:
    if args.mode == "broad-nutrition":
        metadata_dir = ctx.METADATA_DIR.resolve()
        explored_dois_file = ctx.EXPLORATION_COMPLETED_SEED_DOI_FILE.resolve()
        terms_file = seed_dois.DEFAULT_TERMS_FILE.resolve()
        output_path = seed_dois.DEFAULT_OUTPUT_FILE.resolve()
        if not metadata_dir.exists():
            raise SystemExit(f"No existe metadata_dir: {metadata_dir}")
        if not terms_file.exists():
            raise SystemExit(f"No existe terms_file: {terms_file}")

        keywords = seed_dois.load_keyword_dictionary(terms_file)
        explored_dois = seed_dois.load_explored_dois(explored_dois_file)
        rows = seed_dois.collect_candidate_rows(
            metadata_dir,
            explored_dois=explored_dois,
            keywords=keywords,
            min_citations=max(0, int(args.min_citations)),
        )
        written = seed_dois.write_doi_output(rows, output_path, limit=max(0, int(args.limit)))

        print("Metadata seed DOI candidates")
        print(f"- metadata_dir:     {ctx.display_path(metadata_dir)}")
        print(f"- explored_dois:    {ctx.display_path(explored_dois_file)}")
        print(f"- terms_file:       {ctx.display_path(terms_file)}")
        print(f"- output:           {ctx.display_path(output_path)}")
        print(f"- min_citations:    {max(0, int(args.min_citations))}")
        print(f"- keywords_loaded:  {len(keywords)}")
        print(f"- candidates_found: {len(rows)}")
        print(f"- dois_written:     {written}")
        for row in rows[:10]:
            print(
                f"  - {row['doi']} | citations={row['citation_count']} | "
                f"matched={', '.join(row['matched_keywords'][:3])} | title={row['title']}"
            )
        return
    if args.mode == "dataset-gaps":
        papers_csv = ctx.PRE_INGESTION_PAPERS_CSV.resolve()
        unclassified_csv = (ctx.PRE_INGESTION_AUDIT_DIR / "unclassified_papers.csv").resolve()
        metadata_dir = ctx.METADATA_DIR.resolve()
        explored_dois_file = ctx.EXPLORATION_COMPLETED_SEED_DOI_FILE.resolve()
        topics_file = gap_seed_dois.DEFAULT_TOPICS_FILE.resolve()
        output_path = gap_seed_dois.DEFAULT_OUTPUT_FILE.resolve()
        if not papers_csv.exists():
            raise SystemExit(f"No existe papers_csv: {papers_csv}")
        if not metadata_dir.exists():
            raise SystemExit(f"No existe metadata_dir: {metadata_dir}")
        if not topics_file.exists():
            raise SystemExit(f"No existe topics_file: {topics_file}")

        topics = gap_seed_dois.load_gap_topics(topics_file)
        metadata_index = gap_seed_dois.load_metadata_index(metadata_dir)
        explored_dois = gap_seed_dois.load_explored_dois(explored_dois_file)
        papers_rows = gap_seed_dois.load_paper_rows(papers_csv)
        unclassified_rows = gap_seed_dois.load_paper_rows(unclassified_csv)
        rows = gap_seed_dois.collect_gap_seed_rows(
            papers_rows=papers_rows,
            unclassified_rows=unclassified_rows,
            metadata_index=metadata_index,
            explored_dois=explored_dois,
            topics=topics,
            min_citations=max(0, int(args.min_citations)),
        )
        written = gap_seed_dois.write_doi_output(rows, output_path, limit=max(0, int(args.limit)))

        print("Metadata gap seed DOI candidates")
        print(f"- papers_csv:        {ctx.display_path(papers_csv)}")
        print(f"- unclassified_csv:  {ctx.display_path(unclassified_csv)}")
        print(f"- metadata_dir:      {ctx.display_path(metadata_dir)}")
        print(f"- explored_dois:     {ctx.display_path(explored_dois_file)}")
        print(f"- topics_file:       {ctx.display_path(topics_file)}")
        print(f"- output:            {ctx.display_path(output_path)}")
        print(f"- min_citations:     {max(0, int(args.min_citations))}")
        print(f"- topics_loaded:     {len(topics)}")
        print(f"- candidates_found:  {len(rows)}")
        print(f"- dois_written:      {written}")
        for row in rows[:10]:
            print(
                f"  - {row['doi']} | citations={row['citation_count']} | "
                f"bucket={row['source_bucket']} | matched={', '.join(row['matched_topics'][:3])} | title={row['title']}"
            )
        return
    raise ValueError(f"Modo seed-dois no soportado: {args.mode}")


def cmd_bib_generate(args: argparse.Namespace) -> None:
    generate_bib_flow(
        _optional_resolved(args.output),
        _optional_resolved(args.input_csv),
    )


def cmd_pdfs_normalize(args: argparse.Namespace) -> None:
    relations_csv = _resolved(args.relations_csv) if args.relations_csv else normalize_from_relations._default_relations_csv_from_metadata_dir(ctx.METADATA_DIR)
    if relations_csv is None:
        raise FileNotFoundError("No se encontro doi_pdf_relations*.csv en data/reports o metadata.")
    raw_pdf_dir = _resolved(args.raw_dir) if args.raw_dir != ctx.RAW_PDF_DIR else ctx.resolve_available_raw_pdf_dir(ctx.RAW_PDF_DIR)

    copied, skipped = normalize_from_relations.sync_raw_pdfs_from_relations(
        raw_pdf_dir=raw_pdf_dir,
        input_dir=_resolved(args.input_dir),
        relations_csv=relations_csv,
        unmatched_dir=_resolved(args.unmatched_dir),
    )

    print("Sincronizacion raw_pdf -> normalized_pdfs via doi_pdf_relations.csv")
    print(f"- relations_csv: {ctx.display_path(relations_csv)}")
    if raw_pdf_dir != ctx.RAW_PDF_DIR:
        print(f"- raw_pdf_dir fallback: {ctx.display_path(raw_pdf_dir)}")
    print(f"- unmatched_pdf_dir: {ctx.display_path(_resolved(args.unmatched_dir))}")
    print(f"- Copiados: {copied}")
    print(f"- Omitidos: {skipped}")


def cmd_pdf_processing_run(args: argparse.Namespace) -> None:
    common_kwargs = {
        "output_dir": _optional_resolved(args.output_dir),
        "prompt_first_batch": _optional_resolved(args.prompt_first_batch),
        "prompt_continuation_batch": _optional_resolved(args.prompt_continuation_batch),
        "force_markdown": args.force_markdown,
        "max_batches": args.max_batches,
    }
    if args.pdf:
        output_path = run_pdf_processing(_resolved(args.pdf), **common_kwargs)
        print(f"[OK] PDF processing output: {ctx.display_path(output_path)}")
        return
    outputs = run_pdf_processing_dir(_resolved(args.input_dir), limit=args.limit, workers=args.workers, **common_kwargs)
    print(f"[OK] PDF processing outputs: {len(outputs)}")
    for output_path in outputs:
        print(f"- {ctx.display_path(output_path)}")


def cmd_claims_extract(args: argparse.Namespace) -> None:
    run_llm_to_claim_flow(
        input_path=args.input,
        output_path=args.output,
        model=args.model,
        max_claims=args.max_claims,
        temperature=args.temperature,
        pattern=args.pattern,
        auto_approve_max_tokens=(
            ctx.LLM_CLAIMS_AUTO_APPROVE_MAX_TOKENS if args.auto_approve_under_7000_tokens else None
        ),
        skip_existing=args.skip_existing,
    )


def cmd_data_layout_create(args: argparse.Namespace) -> None:
    created_dirs = tuple(ctx.get_data_layout_dirs()) if args.dry_run else create_data_layout()
    print("Data layout dry-run" if args.dry_run else "Data layout ensured")
    for directory in created_dirs:
        print(f"- {ctx.display_path(directory)}")


def _add_shared_claims_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=f"Modelo (default config llm_to_claim.model: {ctx.LLM_CLAIMS_MODEL})",
    )
    parser.add_argument(
        "--max-claims",
        type=int,
        default=None,
        help="Fixed max claims override (default auto: base 10 + extras)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help=f"Temperature (default config llm_to_claim.temperature: {ctx.LLM_CLAIMS_TEMPERATURE})",
    )


def _add_metadata_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    default_exploration_mode = str((ctx.CONFIG.get("exploration") or {}).get("mode", "broad-nutrition"))
    metadata_parser = subparsers.add_parser(
        "metadata",
        help="Operaciones de metadata, exploracion y seeds",
        description=(
            "Grupo de metadata. Incluye exploracion de papers, alta puntual desde DOI "
            "y generacion de seed DOIs."
        ),
    )
    metadata_subparsers = metadata_parser.add_subparsers(dest="metadata_command")

    metadata_explore_parser = metadata_subparsers.add_parser(
        "explore",
        help="Explora candidatos y guarda metadata canónica",
        description=(
            "Explora candidatos desde seed DOIs y guarda metadata en "
            f"{ctx.display_path(ctx.METADATA_DIR)}."
        ),
    )
    metadata_explore_parser.add_argument(
        "--mode",
        choices=["broad-nutrition", "dataset-gaps"],
        default=default_exploration_mode,
        help=(
            "Perfil de exploracion. "
            "broad-nutrition hace barrido amplio de nutricion; "
            "dataset-gaps prioriza gaps del dataset. "
            "Ambos consumen la cola configurada en exploration.seed_doi_file. "
            f"Default config exploration.mode: {default_exploration_mode}."
        ),
    )
    metadata_explore_parser.set_defaults(handler=cmd_metadata_explore)

    metadata_from_doi_parser = metadata_subparsers.add_parser(
        "from-doi",
        help="Crea un metadata JSON canónico desde un DOI",
    )
    metadata_from_doi_parser.add_argument("--doi", type=str, required=True, help="DOI del paper")
    metadata_from_doi_parser.add_argument(
        "--output-dir",
        type=Path,
        default=ctx.METADATA_DIR,
        help=f"Directorio de salida metadata (default: {ctx.display_path(ctx.METADATA_DIR)})",
    )
    metadata_from_doi_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescribe el metadata si ya existe",
    )
    metadata_from_doi_parser.set_defaults(handler=cmd_metadata_from_doi)

    metadata_seed_dois_parser = metadata_subparsers.add_parser(
        "seed-dois",
        help="Genera seed DOIs usando perfil broad-nutrition o dataset-gaps",
    )
    metadata_seed_dois_parser.add_argument(
        "--mode",
        choices=["broad-nutrition", "dataset-gaps"],
        default="broad-nutrition",
        help=(
            "Perfil de generacion de seeds. "
            "broad-nutrition usa metadata local + diccionario de keywords; "
            "dataset-gaps usa pre-ingestion + topics de gaps. "
            "Cada modo usa sus defaults configurados."
        ),
    )
    metadata_seed_dois_parser.add_argument(
        "--min-citations",
        type=int,
        default=seed_dois.DEFAULT_MIN_CITATIONS,
        help="Citas minimas requeridas para exportar un DOI.",
    )
    metadata_seed_dois_parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Cantidad maxima de DOIs a escribir.",
    )
    metadata_seed_dois_parser.set_defaults(handler=cmd_metadata_seed_dois)


def _add_bib_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    bib_parser = subparsers.add_parser(
        "bib",
        help="Operaciones de bibliografia",
        description="Genera bibliografia BibTeX desde metadata canonica o desde CSV auxiliar.",
    )
    bib_subparsers = bib_parser.add_subparsers(dest="bib_command")

    bib_generate_parser = bib_subparsers.add_parser(
        "generate",
        help="Genera un archivo .bib",
    )
    bib_generate_parser.add_argument("--output", type=Path, default=None, help="Ruta opcional del archivo .bib")
    bib_generate_parser.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help="CSV opcional como fuente, por ejemplo data/reports/exports/missing_pdf_items.csv",
    )
    bib_generate_parser.set_defaults(handler=cmd_bib_generate)


def _add_pdfs_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    pdfs_parser = subparsers.add_parser(
        "pdfs",
        help="Operaciones sobre PDFs crudos y normalizados",
    )
    pdfs_subparsers = pdfs_parser.add_subparsers(dest="pdfs_command")

    pdfs_normalize_parser = pdfs_subparsers.add_parser(
        "normalize",
        help=(
            "Normaliza raw PDFs hacia nombres DOI-first usando doi_pdf_relations*.csv "
            f"({ctx.display_path(ctx.RAW_PDF_DIR)} -> {ctx.display_path(ctx.DOCLING_INPUT_DIR)})"
        ),
        description=(
            "Normaliza raw PDFs hacia nombres DOI-first usando doi_pdf_relations*.csv "
            f"({ctx.display_path(ctx.RAW_PDF_DIR)} -> {ctx.display_path(ctx.DOCLING_INPUT_DIR)})"
        ),
    )
    pdfs_normalize_parser.add_argument(
        "--raw-dir",
        type=Path,
        default=ctx.RAW_PDF_DIR,
        help=f"Directorio fuente de PDFs crudos (default: {ctx.display_path(ctx.RAW_PDF_DIR)})",
    )
    pdfs_normalize_parser.add_argument(
        "--input-dir",
        type=Path,
        default=ctx.DOCLING_INPUT_DIR,
        help=f"Directorio destino normalizado (default: {ctx.display_path(ctx.DOCLING_INPUT_DIR)})",
    )
    pdfs_normalize_parser.add_argument(
        "--unmatched-dir",
        type=Path,
        default=ctx.UNMATCHED_PDF_DIR,
        help=f"Destino para PDFs sin DOI resuelto (default: {ctx.display_path(ctx.UNMATCHED_PDF_DIR)})",
    )
    pdfs_normalize_parser.add_argument(
        "--relations-csv",
        type=Path,
        default=None,
        help="CSV doi_pdf_relations explicito. Si no se indica, usa el ultimo encontrado en data/reports.",
    )
    pdfs_normalize_parser.set_defaults(handler=cmd_pdfs_normalize)


def _add_pdf_processing_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    defaults = load_pdf_processing_config()
    pdf_processing_parser = subparsers.add_parser(
        "pdf-processing",
        help="Docling Markdown y extraccion Gemini desde PDFs cientificos",
    )
    pdf_processing_subparsers = pdf_processing_parser.add_subparsers(dest="pdf_processing_command")

    run_parser = pdf_processing_subparsers.add_parser(
        "run",
        help="Convierte PDF con Docling, procesa batches con Gemini y genera paper.processed.json",
    )
    run_parser.add_argument("--pdf", type=Path, default=None, help="PDF cientifico puntual de entrada")
    run_parser.add_argument(
        "--input-dir",
        type=Path,
        default=defaults.input_dir,
        help=f"Directorio de PDFs de entrada (default: {ctx.display_path(defaults.input_dir)})",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad maxima de PDFs a procesar desde --input-dir",
    )
    run_parser.add_argument(
        "--workers",
        type=int,
        default=defaults.workers,
        help=f"PDFs a procesar en paralelo (default: {defaults.workers})",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Directorio runtime de salida (default: {ctx.display_path(defaults.output_dir)})",
    )
    run_parser.add_argument("--prompt-first-batch", type=Path, default=None, help="Prompt alternativo para primer batch")
    run_parser.add_argument(
        "--prompt-continuation-batch",
        type=Path,
        default=None,
        help="Prompt alternativo para batches de continuacion",
    )
    run_parser.add_argument("--force-markdown", action="store_true", help="Regenera Markdown Docling existente")
    run_parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Cantidad maxima de batches Markdown a procesar para este PDF",
    )
    run_parser.set_defaults(handler=cmd_pdf_processing_run)


def _add_claims_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    claims_parser = subparsers.add_parser(
        "claims",
        help="Extraccion de claims desde *.final.json",
    )
    claims_subparsers = claims_parser.add_subparsers(dest="claims_command")

    claims_extract_parser = claims_subparsers.add_parser(
        "extract",
        help=(
            f"Extrae claims desde {ctx.display_path(ctx.CLAIMS_INPUT_DIR)} "
            f"hacia {ctx.display_path(ctx.CLAIMS_OUTPUT_DIR)}"
        ),
    )
    claims_extract_parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Archivo final JSON o directorio de entrada (default config llm_to_claim.input_dir)",
    )
    claims_extract_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Archivo/directorio de salida (default config llm_to_claim.output_dir)",
    )
    _add_shared_claims_args(claims_extract_parser)
    claims_extract_parser.add_argument(
        "--pattern",
        type=str,
        default="*/*.final.json",
        help="Glob pattern cuando --input es directorio",
    )
    claims_extract_parser.add_argument(
        "--auto-approve-under-7000-tokens",
        action="store_true",
        help=(
            "Procesa automaticamente solo archivos con estimated_input_tokens "
            f"menor a {ctx.LLM_CLAIMS_AUTO_APPROVE_MAX_TOKENS}"
        ),
    )
    claims_extract_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Salta archivos cuyo *.claims.json de salida ya existe",
    )
    claims_extract_parser.set_defaults(handler=cmd_claims_extract)


def _add_data_layout_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    data_layout_parser = subparsers.add_parser(
        "data-layout",
        help="Bootstrap explícito del layout canonico de data/",
    )
    data_layout_subparsers = data_layout_parser.add_subparsers(dest="data_layout_command")

    data_layout_create_parser = data_layout_subparsers.add_parser(
        "create",
        help="Crea de forma explícita la estructura canonica de directorios bajo data/",
        description="Crea de forma explícita la estructura canonica de directorios bajo data/",
    )
    data_layout_create_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los directorios requeridos sin crearlos.",
    )
    data_layout_create_parser.set_defaults(handler=cmd_data_layout_create)

def _add_bridge_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    bridge_parser = subparsers.add_parser(
        "bridge",
        help="Comunicacion con registry, storage y eventos Victus",
        description=(
            "Comandos de integracion para registrar PDFs, publicar artifacts/eventos, "
            "marcar stages y consultar estado en la infraestructura Victus."
        ),
    )
    try:
        from ops.scripts.bridge.victus_ingest_bridge import cli as bridge_cli
    except ModuleNotFoundError:
        bridge_parser.set_defaults(
            handler=lambda args: (_ for _ in ()).throw(
                SystemExit("Bridge CLI no esta disponible en ops/scripts/bridge.")
            )
        )
        return

    bridge_cli.configure_parser(bridge_parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=CLI_DESCRIPTION)
    subparsers = parser.add_subparsers(dest="command")

    _add_metadata_group(subparsers)
    _add_bib_group(subparsers)
    _add_pdfs_group(subparsers)
    _add_pdf_processing_group(subparsers)
    _add_claims_group(subparsers)
    _add_bridge_group(subparsers)
    _add_data_layout_group(subparsers)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return

    handler(args)


if __name__ == "__main__":
    main()
