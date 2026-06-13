from __future__ import annotations

import argparse
import random
from pathlib import Path

from src.workspace import config as ctx
from src.workspace.pipeline_context import PipelineRunContext
from src.workspace.runs import config_hash, content_hash_file
from src.workspace.data_layout import create_data_layout
from src.application.bibliography_export import generate_bib_flow
from src.application.metadata_extraction import seed_dois
from src.application.pdf_intake import backfill_links_from_existing_artifacts, link_manual_pdf
from src.application.processing_state import refresh_processing_state
from src.application.pdf_processing.markdown import pdf_dir_to_markdown
from src.application.pdf_processing.pipeline import (
    load_pdf_processing_config,
    run_markdown_processing,
    run_pdf_processing,
    run_pdf_processing_dir,
)
from src.application.evidence_extraction.evidence import run_pdf_evidence, run_pdf_evidence_db, run_pdf_evidence_dir
from src.application.testing_pipeline.artifacts import copy_testing_markdown, copy_testing_source_pdf, iter_testing_pdf_paths
from src.infrastructure.llm.factory import build_llm_client
from src.infrastructure.prompts.factory import build_prompt_registry

run_metadata_exploration_flow = None

HELP_WIDTH = 120


CLI_DESCRIPTION = (
    "CLI para el procesamiento de papers del sistema Victus."
)


def _help_formatter(prog: str) -> argparse.HelpFormatter:
    return argparse.HelpFormatter(prog, width=HELP_WIDTH, max_help_position=34)


def _add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser], name: str, **kwargs) -> argparse.ArgumentParser:
    kwargs.setdefault("formatter_class", _help_formatter)
    return subparsers.add_parser(name, **kwargs)


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve()


def _optional_resolved(path: Path | None) -> Path | None:
    return _resolved(path) if path is not None else None


def _command_subparsers(parser: argparse.ArgumentParser, dest: str) -> argparse._SubParsersAction[argparse.ArgumentParser]:
    parser._positionals.title = "commands"
    return parser.add_subparsers(dest=dest, title="commands", metavar="COMMAND")


def _observability_dirs_for_output(output_path: Path) -> tuple[Path | None, Path | None, Path | None]:
    resolved = output_path.expanduser().resolve()
    try:
        resolved.relative_to(ctx.DATA_DIR.resolve())
    except ValueError:
        root = resolved.parent / ".victus-observability"
        return root / "lake", root / "runtime/runs", root / "registry"
    return ctx.DATA_LAKE_DIR, ctx.DATA_RUNTIME_RUNS_DIR, ctx.DATA_REGISTRY_DIR


def _pipeline_record_store():
    if not ctx.VICTUS_PIPELINE_POSTGRES_ENABLED:
        return None
    if not ctx.VICTUS_PIPELINE_POSTGRES_DSN.strip():
        raise SystemExit("ERROR: VICTUS_PIPELINE_POSTGRES_DSN is required when VICTUS_PIPELINE_POSTGRES_ENABLED=true.")
    from src.infrastructure.postgres.pipeline_store import PostgresPipelineRecordStore

    return PostgresPipelineRecordStore(ctx.VICTUS_PIPELINE_POSTGRES_DSN)


def cmd_metadata_explore(args: argparse.Namespace) -> None:
    global run_metadata_exploration_flow
    if run_metadata_exploration_flow is None:
        from src.application.metadata_extraction.stage import run_metadata_exploration_flow as loaded_run_metadata_exploration_flow

        run_metadata_exploration_flow = loaded_run_metadata_exploration_flow

    run_metadata_exploration_flow(
        mode=args.mode,
        llm_client=build_llm_client(),
        prompt_registry=build_prompt_registry(),
        prompt_label=ctx.PROMPT_LABEL,
    )


def cmd_metadata_from_doi(args: argparse.Namespace) -> None:
    from src.application.metadata_extraction import citation_exploration

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
        metadata_file = (ctx.DATA_LAKE_DIR / "paper_metadata.jsonl").resolve()
        explored_dois_file = ctx.EXPLORATION_COMPLETED_SEED_DOI_FILE.resolve()
        terms_file = seed_dois.DEFAULT_TERMS_FILE.resolve()
        output_path = seed_dois.DEFAULT_OUTPUT_FILE.resolve()
        if not metadata_file.exists():
            raise SystemExit(f"No existe metadata_file: {metadata_file}")
        if not terms_file.exists():
            raise SystemExit(f"No existe terms_file: {terms_file}")
        context = _start_seed_context(args, output_path)
        attempt = context.stage_attempt(stage="seed.load")
        attempt.event(
            event_type="stage_started",
            severity="info",
            status="started",
            message="Seed DOI generation started",
            action="stage.started",
            metadata={"mode": args.mode},
        )

        keywords = seed_dois.load_keyword_dictionary(terms_file)
        explored_dois = seed_dois.load_explored_dois(explored_dois_file)
        rows = seed_dois.collect_candidate_rows(
            metadata_file,
            explored_dois=explored_dois,
            keywords=keywords,
            min_citations=max(0, int(args.min_citations)),
        )
        written = seed_dois.write_doi_output(rows, output_path, limit=max(0, int(args.limit)))
        if output_path.exists():
            artifact = attempt.register_artifact(
                artifact_type="seed-dois",
                artifact_version="v1",
                storage_uri=ctx.display_path(output_path),
                storage_backend="local_fs",
                content_format="jsonl",
                size_bytes=output_path.stat().st_size,
                checksum=content_hash_file(output_path),
                contract_version="seed-dois:v1",
                metadata={"written": written, "candidates_found": len(rows)},
            )
            attempt.event(
                event_type="artifact_created",
                severity="info",
                status="succeeded",
                message="Seed DOI output written",
                action="artifact.created",
                artifact_id=artifact["artifact_id"],
                artifact_path=ctx.display_path(output_path),
                contract_version="seed-dois:v1",
                metadata={"written": written},
            )
        attempt.event(
            event_type="stage_succeeded",
            severity="info",
            status="succeeded",
            message="Seed DOI generation completed",
            action="stage.succeeded",
            metadata={"written": written, "candidates_found": len(rows)},
        )
        context.finish(status="succeeded", summary={"written": written, "candidates_found": len(rows)})

        print("Metadata seed DOI candidates")
        print(f"- metadata_file:    {ctx.display_path(metadata_file)}")
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
    raise ValueError(f"Modo seed-dois no soportado: {args.mode}")


def _start_seed_context(args: argparse.Namespace, output_path: Path) -> PipelineRunContext:
    lake_dir, runtime_runs_dir, registry_dir = _observability_dirs_for_output(output_path)
    return PipelineRunContext.start(
        pipeline_name="seed-dois",
        pipeline_version="v1",
        execution_mode="stage_only",
        process_name="victus.processing.seed_ingestion",
        input_scope={"mode": args.mode, "limit": int(args.limit), "min_citations": int(args.min_citations)},
        config_hash=config_hash(
            {
                "pipeline_name": "seed-dois",
                "pipeline_version": "v1",
                "stage": "seed.load",
                "flags": {"mode": args.mode, "limit": int(args.limit), "min_citations": int(args.min_citations)},
                "schema_versions": {"event": "pipeline-event:v1"},
                "contract_versions": {"seed-dois": "seed-dois:v1"},
            }
        ),
        lake_dir=lake_dir,
        runtime_runs_dir=runtime_runs_dir,
        registry_dir=registry_dir,
        record_store=_pipeline_record_store(),
    )


def cmd_bib_generate(args: argparse.Namespace) -> None:
    generate_bib_flow(
        _optional_resolved(args.output),
        _resolved(args.input_jsonl),
    )


def cmd_pdf_intake_link(args: argparse.Namespace) -> None:
    link = link_manual_pdf(
        metadata_id=args.metadata_id,
        source_pdf=_resolved(args.pdf),
        metadata_file=_resolved(args.metadata_file),
        artifact_dir=_resolved(args.artifact_dir),
        links_file=_resolved(args.links_file),
        move=not args.copy,
        overwrite=args.overwrite,
    )

    print("PDF linkeado")
    print(f"- metadata_id:       {link.metadata_id}")
    print(f"- paper_id:          {link.paper_id}")
    print(f"- doi:               {link.doi or ''}")
    print(f"- source_pdf_path:   {link.source_pdf_path}")
    print(f"- artifact_pdf_path: {link.artifact_pdf_path}")
    print(f"- links_file:        {ctx.display_path(_resolved(args.links_file))}")


def cmd_pdf_intake_backfill_links(args: argparse.Namespace) -> None:
    written, skipped = backfill_links_from_existing_artifacts(
        metadata_file=_resolved(args.metadata_file),
        legacy_links_file=_resolved(args.legacy_links_file),
        artifact_dir=_resolved(args.artifact_dir),
        links_file=_resolved(args.links_file),
        overwrite=args.overwrite,
    )
    print("paper_pdf_links.jsonl generado")
    print(f"- Escritos:   {written}")
    print(f"- Omitidos:   {skipped}")
    print(f"- links_file: {ctx.display_path(_resolved(args.links_file))}")


def cmd_pdf_processing_run(args: argparse.Namespace) -> None:
    if args.pdf and args.markdown:
        raise SystemExit("ERROR: use --pdf or --markdown, not both.")
    common_kwargs = {
        "output_dir": _optional_resolved(args.output_dir),
        "prompt_first_batch": _optional_resolved(args.prompt_first_batch),
        "prompt_continuation_batch": _optional_resolved(args.prompt_continuation_batch),
        "force_markdown": args.force_markdown,
        "max_batches": args.max_batches,
        "llm_client": build_llm_client(),
        "prompt_registry": build_prompt_registry(),
        "prompt_label": ctx.PROMPT_LABEL,
        "output_store": _pipeline_record_store(),
    }
    if args.markdown:
        output_path = run_markdown_processing(_resolved(args.markdown), **common_kwargs)
        print(f"[OK] Markdown processing output: {ctx.display_path(output_path)}")
        return
    if args.pdf:
        output_path = run_pdf_processing(_resolved(args.pdf), **common_kwargs)
        print(f"[OK] PDF processing output: {ctx.display_path(output_path)}")
        return
    outputs = run_pdf_processing_dir(_resolved(args.input_dir), limit=args.limit, workers=args.workers, **common_kwargs)
    print(f"[OK] PDF processing outputs: {len(outputs)}")
    for output_path in outputs:
        print(f"- {ctx.display_path(output_path)}")


def cmd_pdf_processing_json_from_markdown(args: argparse.Namespace) -> None:
    if args.markdown and args.input_dir:
        raise SystemExit("ERROR: use --markdown or --input-dir, not both.")
    common_kwargs = {
        "output_dir": _optional_resolved(args.output_dir),
        "prompt_first_batch": _optional_resolved(args.prompt_first_batch),
        "prompt_continuation_batch": _optional_resolved(args.prompt_continuation_batch),
        "max_batches": args.max_batches,
        "llm_client": build_llm_client(),
        "prompt_registry": build_prompt_registry(),
        "prompt_label": ctx.PROMPT_LABEL,
        "output_store": _pipeline_record_store(),
    }
    if args.markdown:
        output_path = run_markdown_processing(
            _resolved(args.markdown),
            paper_id=args.paper_id,
            **common_kwargs,
        )
        print(f"[OK] Markdown JSON output: {ctx.display_path(output_path)}")
        return

    input_dir = _resolved(args.input_dir)
    markdown_paths = sorted(input_dir.glob("*.md"))
    if args.shuffle:
        rng = random.Random(args.seed)
        rng.shuffle(markdown_paths)
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("ERROR: --limit must be >= 1.")
        markdown_paths = markdown_paths[: args.limit]

    outputs = []
    for markdown_path in markdown_paths:
        outputs.append(run_markdown_processing(markdown_path, **common_kwargs))
    print(f"[OK] Markdown JSON outputs: {len(outputs)}")
    for output_path in outputs:
        print(f"- {ctx.display_path(output_path)}")


def cmd_pdf_processing_markdown(args: argparse.Namespace) -> None:
    outputs = pdf_dir_to_markdown(
        _resolved(args.input_dir),
        _resolved(args.output_dir),
        limit=args.limit,
        skip_existing=args.skip_existing,
        force=args.force,
        max_pages=args.max_pages,
        status_file=_optional_resolved(args.status_file),
    )
    print(f"[OK] Markdown outputs: {len(outputs)}")
    for output_path in outputs:
        print(f"- {ctx.display_path(output_path)}")


def cmd_pdf_processing_evidence(args: argparse.Namespace) -> None:
    output_store = _pipeline_record_store()
    common_kwargs = {
        "output_dir": _optional_resolved(args.output_dir),
        "model": args.model,
        "skip_existing": args.skip_existing,
        "llm_client": build_llm_client(),
        "prompt_registry": build_prompt_registry(),
        "prompt_label": ctx.PROMPT_LABEL,
        "output_store": output_store,
    }
    if args.from_db:
        if output_store is None:
            raise SystemExit("ERROR: --from-db requires VICTUS_PIPELINE_POSTGRES_ENABLED=true.")
        outputs = run_pdf_evidence_db(
            store=output_store,
            paper_id=args.paper_id,
            limit=args.limit,
            **{key: value for key, value in common_kwargs.items() if key != "output_store"},
        )
        print(f"[OK] Evidence outputs from DB: {len(outputs)}")
        for output_path in outputs:
            print(f"- {ctx.display_path(output_path)}")
        return
    if args.input.is_file():
        output_path = run_pdf_evidence(_resolved(args.input), **common_kwargs)
        print(f"[OK] Evidence output: {ctx.display_path(output_path)}")
        return
    outputs = run_pdf_evidence_dir(
        _resolved(args.input),
        pattern=args.pattern,
        limit=args.limit,
        **common_kwargs,
    )
    print(f"[OK] Evidence outputs: {len(outputs)}")
    for output_path in outputs:
        print(f"- {ctx.display_path(output_path)}")


def cmd_pdf_processing_testing(args: argparse.Namespace) -> None:
    output_dir = _resolved(args.output_dir)
    pdf_paths = iter_testing_pdf_paths(
        pdf_dir=_resolved(args.pdf_dir),
        paper_ids=tuple(args.paper_id or ()),
        limit=args.limit,
    )
    llm_client = build_llm_client()
    prompt_registry = build_prompt_registry()

    print("Testing pipeline")
    print(f"- output_dir: {ctx.display_path(output_dir)}")
    print(f"- papers:     {len(pdf_paths)}")
    for pdf_path in pdf_paths:
        paper_id = pdf_path.stem
        source_pdf = copy_testing_source_pdf(pdf_path, output_dir, overwrite=args.overwrite_source)
        print(f"[TESTING SOURCE] {paper_id}: {ctx.display_path(source_pdf)}")
        paper_dir = output_dir / paper_id
        common_processing_kwargs = {
            "output_dir": output_dir,
            "prompt_first_batch": _optional_resolved(args.prompt_first_batch),
            "prompt_continuation_batch": _optional_resolved(args.prompt_continuation_batch),
            "force_markdown": args.force_markdown,
            "max_batches": args.max_batches,
            "llm_client": llm_client,
            "prompt_registry": prompt_registry,
            "prompt_label": ctx.PROMPT_LABEL,
            "output_store": _pipeline_record_store(),
        }
        if args.reuse_markdown:
            markdown_path = copy_testing_markdown(
                _resolved(args.markdown_dir),
                output_dir,
                paper_id,
                overwrite=args.overwrite_markdown,
            )
            print(f"[TESTING MARKDOWN SOURCE] {paper_id}: {ctx.display_path(markdown_path)}")
            final_output = run_markdown_processing(markdown_path, **common_processing_kwargs)
        else:
            final_output = run_pdf_processing(
                pdf_path,
                **common_processing_kwargs,
            )
        processed_output = paper_dir / "paper.processed.json"
        evidence_input = processed_output if processed_output.exists() else final_output
        evidence_output = run_pdf_evidence(
            evidence_input,
            output_dir=output_dir,
            model=args.evidence_model,
            skip_existing=args.skip_existing_evidence,
            llm_client=llm_client,
            prompt_registry=prompt_registry,
            prompt_label=ctx.PROMPT_LABEL,
            output_store=_pipeline_record_store(),
        )
        print(f"[TESTING DONE] {paper_id}: {ctx.display_path(evidence_output)}")


def cmd_data_layout_create(args: argparse.Namespace) -> None:
    created_dirs = tuple(ctx.get_data_layout_dirs()) if args.dry_run else create_data_layout()
    print("Data layout dry-run" if args.dry_run else "Data layout ensured")
    for directory in created_dirs:
        print(f"- {ctx.display_path(directory)}")


def cmd_processing_state_refresh(args: argparse.Namespace) -> None:
    try:
        records = refresh_processing_state(
            data_dir=_resolved(args.data_dir),
            store=_pipeline_record_store(),
            csv_output=_optional_resolved(args.csv),
            pipeline_version=args.pipeline_version,
            config_hash=args.config_hash,
        )
    except Exception as exc:
        if type(exc).__name__ == "UndefinedTable":
            raise SystemExit(
                "ERROR: faltan tablas PostgreSQL. Aplica las migraciones en orden:\n"
                "  psql \"$DATABASE_URL\" -f ops/sql/001_pipeline_runs_events.sql\n"
                "  psql \"$DATABASE_URL\" -f ops/sql/002_scientific_outputs.sql\n"
                "  psql \"$DATABASE_URL\" -f ops/sql/003_paper_processing_state.sql\n"
                "  psql \"$DATABASE_URL\" -f ops/sql/004_structured_paper_evidence_blocks.sql"
            ) from exc
        raise
    print("Paper processing state refreshed")
    print(f"- papers: {len(records)}")
    if args.csv:
        print(f"- csv:    {ctx.display_path(_resolved(args.csv))}")


def _add_metadata_extraction_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    default_exploration_mode = str((ctx.CONFIG.get("exploration") or {}).get("mode", "broad-nutrition"))
    metadata_parser = _add_parser(
        subparsers,
        "metadata-extraction",
        help="Extrae metadata, explora candidatos y genera seeds",
        description=(
            "Grupo de metadata. Incluye exploracion de papers, alta puntual desde DOI "
            "y generacion de seed DOIs."
        ),
    )
    metadata_subparsers = _command_subparsers(metadata_parser, "metadata_command")

    metadata_explore_parser = _add_parser(
        metadata_subparsers,
        "explore",
        help="Explora candidatos a partir de seed-dois y guarda metadata",
        description=(
            "Explora candidatos desde seed DOIs y guarda metadata en "
            "data/lake/paper_metadata.jsonl."
        ),
    )
    metadata_explore_parser.add_argument(
        "--mode",
        choices=["broad-nutrition"],
        default=default_exploration_mode,
        help=(
            "Perfil de exploracion. "
            "broad-nutrition hace barrido amplio de nutricion y consume la cola configurada "
            "en exploration.seed_doi_file. "
            f"Default config exploration.mode: {default_exploration_mode}."
        ),
    )
    metadata_explore_parser.set_defaults(handler=cmd_metadata_explore)

    metadata_from_doi_parser = _add_parser(
        metadata_subparsers,
        "from-doi",
        help="Crea un metadata desde un DOI",
    )
    metadata_from_doi_parser.add_argument("--doi", type=str, required=True, help="DOI del paper")
    metadata_from_doi_parser.add_argument(
        "--output-dir",
        type=Path,
        default=ctx.DATA_LAKE_DIR / "paper_metadata.jsonl",
        help="Archivo JSONL de salida metadata (default: data/lake/paper_metadata.jsonl)",
    )
    metadata_from_doi_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescribe el metadata si ya existe",
    )
    metadata_from_doi_parser.set_defaults(handler=cmd_metadata_from_doi)

    metadata_seed_dois_parser = _add_parser(
        metadata_subparsers,
        "seed-dois",
        help="Genera seed DOIs usando perfil broad-nutrition",
    )
    metadata_seed_dois_parser.add_argument(
        "--mode",
        choices=["broad-nutrition"],
        default="broad-nutrition",
        help=(
            "Perfil de generacion de seeds. "
            "broad-nutrition usa metadata local + diccionario de keywords."
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


def _add_bibliography_export_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    bibliography_parser = _add_parser(
        subparsers,
        "bibliography-export",
        help="Genera bibliografia BibTeX desde metadata canonical",
        description="Exporta data/lake/paper_metadata.jsonl a un BibTeX DOI-only para flujos externos como Zotero.",
    )
    bibliography_subparsers = _command_subparsers(bibliography_parser, "bibliography_export_command")

    bib_generate_parser = _add_parser(
        bibliography_subparsers,
        "generate-bib",
        help="Genera un archivo .bib",
    )
    bib_generate_parser.add_argument("--output", type=Path, default=None, help="Ruta opcional del archivo .bib")
    bib_generate_parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=ctx.DATA_LAKE_DIR / "paper_metadata.jsonl",
        help="Paper metadata JSONL canonical para generar BibTeX DOI-only.",
    )
    bib_generate_parser.set_defaults(handler=cmd_bib_generate)

def _add_pdf_intake_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    pdf_intake_parser = _add_parser(
        subparsers,
        "pdf-intake",
        help="Linkea PDFs obtenidos manualmente con metadata canonical",
        description=(
            "Toma PDFs desde artifacts/intake, los mueve a artifacts/pdfs con paper_id hasheado "
            "y registra data/lake/paper_pdf_links.jsonl."
        ),
    )
    pdf_intake_subparsers = _command_subparsers(pdf_intake_parser, "pdf_intake_command")

    link_parser = _add_parser(
        pdf_intake_subparsers,
        "link",
        help="Mueve un PDF manual a artifacts/pdfs y registra su vínculo",
    )
    link_parser.add_argument("--metadata-id", required=True, help="metadata_id existente en paper_metadata.jsonl.")
    link_parser.add_argument(
        "--pdf",
        type=Path,
        required=True,
        help=f"PDF fuente, normalmente bajo {ctx.display_path(ctx.DATA_ARTIFACTS_INTAKE_PDFS_DIR)}.",
    )
    link_parser.add_argument(
        "--metadata-file",
        type=Path,
        default=ctx.DATA_LAKE_DIR / "paper_metadata.jsonl",
        help="JSONL canonical de metadata.",
    )
    link_parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=ctx.DATA_ARTIFACTS_PDFS_DIR,
        help=f"Destino de PDFs canonicales (default: {ctx.display_path(ctx.DATA_ARTIFACTS_PDFS_DIR)}).",
    )
    link_parser.add_argument(
        "--links-file",
        type=Path,
        default=ctx.DATA_LAKE_PAPER_PDF_LINKS_FILE,
        help=f"JSONL de vinculos metadata/PDF (default: {ctx.display_path(ctx.DATA_LAKE_PAPER_PDF_LINKS_FILE)}).",
    )
    link_parser.add_argument("--copy", action="store_true", help="Copia el PDF en vez de moverlo desde intake.")
    link_parser.add_argument("--overwrite", action="store_true", help="Sobrescribe el PDF artifact si ya existe.")
    link_parser.set_defaults(handler=cmd_pdf_intake_link)

    backfill_parser = _add_parser(
        pdf_intake_subparsers,
        "backfill-links",
        help="Genera paper_pdf_links.jsonl desde PDFs artifact existentes y links legacy",
    )
    backfill_parser.add_argument(
        "--metadata-file",
        type=Path,
        default=ctx.DATA_LAKE_DIR / "paper_metadata.jsonl",
        help="JSONL canonical de metadata.",
    )
    backfill_parser.add_argument(
        "--legacy-links-file",
        type=Path,
        default=ctx.DATA_LAKE_DIR / "links.jsonl",
        help="JSONL legacy con paper_id y DOI.",
    )
    backfill_parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=ctx.DATA_ARTIFACTS_PDFS_DIR,
        help=f"Directorio de PDFs artifact existentes (default: {ctx.display_path(ctx.DATA_ARTIFACTS_PDFS_DIR)}).",
    )
    backfill_parser.add_argument(
        "--links-file",
        type=Path,
        default=ctx.DATA_LAKE_PAPER_PDF_LINKS_FILE,
        help=f"JSONL de salida (default: {ctx.display_path(ctx.DATA_LAKE_PAPER_PDF_LINKS_FILE)}).",
    )
    backfill_parser.add_argument("--overwrite", action="store_true", help="Sobrescribe links_file si ya existe.")
    backfill_parser.set_defaults(handler=cmd_pdf_intake_backfill_links)


def _add_pdf_processing_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    defaults = load_pdf_processing_config()
    pdf_processing_parser = _add_parser(
        subparsers,
        "pdf-processing",
        help="Docling Markdown y extraccion LLM desde PDFs cientificos",
    )
    pdf_processing_subparsers = _command_subparsers(pdf_processing_parser, "pdf_processing_command")

    run_parser = _add_parser(
        pdf_processing_subparsers,
        "run",
        help="Convierte PDF con Docling, procesa batches con LLM y genera paper.final.json",
    )
    run_parser.add_argument("--pdf", type=Path, default=None, help="PDF cientifico puntual de entrada")
    run_parser.add_argument("--markdown", type=Path, default=None, help="paper.md puntual de entrada")
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

    json_from_markdown_parser = _add_parser(
        pdf_processing_subparsers,
        "json-from-markdown",
        help="Convierte un Markdown artifact a paper.processed.json y paper.final.json",
        description=(
            "Procesa un Markdown existente con el flujo LLM de estructuracion. "
            "Acepta un Markdown puntual o todos los .md de data/artifacts/markdown."
        ),
    )
    json_from_markdown_parser.add_argument("--markdown", type=Path, default=None, help="Markdown fuente puntual")
    json_from_markdown_parser.add_argument(
        "--input-dir",
        type=Path,
        default=ctx.DATA_ARTIFACTS_MARKDOWN_DIR,
        help=f"Directorio de Markdown artifacts (default: {ctx.display_path(ctx.DATA_ARTIFACTS_MARKDOWN_DIR)})",
    )
    json_from_markdown_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad maxima de Markdown files a procesar desde --input-dir",
    )
    json_from_markdown_parser.add_argument(
        "--shuffle",
        action="store_true",
        help="Procesa los Markdown de --input-dir en orden aleatorio",
    )
    json_from_markdown_parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed opcional para reproducir el orden aleatorio de --shuffle",
    )
    json_from_markdown_parser.add_argument(
        "--paper-id",
        default=None,
        help="Paper id explicito. Si se omite, usa el stem del Markdown o el directorio padre de paper.md.",
    )
    json_from_markdown_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Directorio de salida estructurada (default: {ctx.display_path(defaults.output_dir)})",
    )
    json_from_markdown_parser.add_argument(
        "--prompt-first-batch",
        type=Path,
        default=None,
        help="Prompt alternativo para primer batch",
    )
    json_from_markdown_parser.add_argument(
        "--prompt-continuation-batch",
        type=Path,
        default=None,
        help="Prompt alternativo para batches de continuacion",
    )
    json_from_markdown_parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Cantidad maxima de batches Markdown a procesar",
    )
    json_from_markdown_parser.set_defaults(handler=cmd_pdf_processing_json_from_markdown)

    markdown_parser = _add_parser(
        pdf_processing_subparsers,
        "markdown",
        help="Convierte los PDFs artifact a paper.md usando solo Docling",
        description=(
            "Convierte PDFs a Markdown con Docling sin ejecutar batching ni LLM. "
            "Por defecto lee data/artifacts/pdfs y escribe en el output_dir configurado."
        ),
    )
    markdown_parser.add_argument(
        "--input-dir",
        type=Path,
        default=defaults.input_dir,
        help=f"Directorio de PDFs de entrada (default: {ctx.display_path(defaults.input_dir)})",
    )
    markdown_parser.add_argument(
        "--output-dir",
        type=Path,
        default=defaults.output_dir,
        help=f"Directorio de salida Markdown (default: {ctx.display_path(defaults.output_dir)})",
    )
    markdown_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad maxima de PDFs a convertir.",
    )
    markdown_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Marca como done y no regenera paper.md cuando ya existe.",
    )
    markdown_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenera aunque markdown_status.jsonl tenga status done.",
    )
    markdown_parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        help="Marca failed y salta PDFs con mas paginas que este limite (default: 100).",
    )
    markdown_parser.add_argument(
        "--status-file",
        type=Path,
        default=None,
        help=(
            "JSONL de estado para saltar papers done "
            "(default: <output-dir>/markdown_status.jsonl)."
        ),
    )
    markdown_parser.set_defaults(handler=cmd_pdf_processing_markdown)

def _add_evidence_extraction_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    defaults = load_pdf_processing_config()
    evidence_parser = _add_parser(
        subparsers,
        "evidence-extraction",
        help="Genera Canonical Evidence a partir de JSON estructurado.",
    )
    evidence_subparsers = _command_subparsers(evidence_parser, "evidence_extraction_command")
    run_parser = _add_parser(
        evidence_subparsers,
        "run",
        help="Genera artifacts de evidencia desde paper.processed.json",
    )
    run_parser.add_argument(
        "--input",
        type=Path,
        default=defaults.output_dir,
        help=(
            "Archivo paper.processed.json o directorio de artefactos PDF-processing "
            f"(default: {ctx.display_path(defaults.output_dir)})"
        ),
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Directorio de evidencia (default: {ctx.display_path(ctx.EVIDENCE_OUTPUT_DIR)})",
    )
    run_parser.add_argument(
        "--pattern",
        default="*/paper.processed.json",
        help='Patron glob cuando --input es directorio (default: "*/paper.processed.json")',
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad maxima de papers a procesar cuando --input es directorio",
    )
    run_parser.add_argument(
        "--from-db",
        action="store_true",
        help="Consume structured_papers desde PostgreSQL en vez de paper.processed.json",
    )
    run_parser.add_argument(
        "--paper-id",
        default=None,
        help="Paper puntual para --from-db",
    )
    run_parser.add_argument("--model", default=None, help="Modelo LLM alternativo para evidence")
    run_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Salta papers con canonical_evidence.json existente",
    )
    run_parser.set_defaults(handler=cmd_pdf_processing_evidence)

def _add_testing_pipeline_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    defaults = load_pdf_processing_config()
    testing_parser = _add_parser(
        subparsers,
        "testing-pipeline",
        help="Ejecuta PDF-processing completo en data/testing/<paper_id>",
        description=(
            "Ejecuta el flujo completo de testing por paper: copia source.pdf, "
            "crea paper.md con Docling, estructura con LLM y genera evidence."
        ),
    )
    testing_subparsers = _command_subparsers(testing_parser, "testing_pipeline_command")
    run_parser = _add_parser(
        testing_subparsers,
        "run",
        help="Ejecuta el pipeline completo en data/testing/<paper_id>",
    )
    run_parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=defaults.input_dir,
        help=f"Directorio de PDFs fuente (default: {ctx.display_path(defaults.input_dir)})",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=ctx.TESTING_ROOT_DIR,
        help=f"Directorio testing destino (default: {ctx.display_path(ctx.TESTING_ROOT_DIR)})",
    )
    run_parser.add_argument(
        "--markdown-dir",
        type=Path,
        default=defaults.output_dir,
        help=f"Directorio con <paper_id>/paper.md para --reuse-markdown (default: {ctx.display_path(defaults.output_dir)})",
    )
    run_parser.add_argument(
        "--paper-id",
        action="append",
        default=None,
        help="Paper puntual a procesar. Puede repetirse. Si se omite, usa todos los PDFs de --pdf-dir.",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cantidad maxima de papers a procesar cuando no se especifica --paper-id.",
    )
    run_parser.add_argument(
        "--overwrite-source",
        action="store_true",
        help="Sobrescribe source.pdf existente en testing.",
    )
    run_parser.add_argument(
        "--reuse-markdown",
        action="store_true",
        help="Copia paper.md existente desde --markdown-dir y evita ejecutar Docling.",
    )
    run_parser.add_argument(
        "--overwrite-markdown",
        action="store_true",
        help="Sobrescribe paper.md existente en testing cuando se usa --reuse-markdown.",
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
    run_parser.add_argument("--evidence-model", default=None, help="Modelo LLM alternativo para evidence")
    run_parser.add_argument(
        "--skip-existing-evidence",
        action="store_true",
        help="Salta papers con canonical_evidence.json existente",
    )
    run_parser.set_defaults(handler=cmd_pdf_processing_testing)


def _add_data_layout_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    data_layout_parser = _add_parser(
        subparsers,
        "data-layout",
        help="Bootstrap explícito del layout canonico de data/",
    )
    data_layout_subparsers = _command_subparsers(data_layout_parser, "data_layout_command")

    data_layout_create_parser = _add_parser(
        data_layout_subparsers,
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


def _add_processing_state_group(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    processing_state_parser = _add_parser(
        subparsers,
        "processing-state",
        help="Actualiza estado operacional por paper desde data/",
    )
    processing_state_subparsers = _command_subparsers(processing_state_parser, "processing_state_command")

    refresh_parser = _add_parser(
        processing_state_subparsers,
        "refresh",
        help="Escanea data/ y actualiza paper_processing_state",
        description=(
            "Deriva el estado actual por paper desde PDFs/Markdown en data/artifacts "
            "y las tablas PostgreSQL de outputs procesados."
        ),
    )
    refresh_parser.add_argument(
        "--data-dir",
        type=Path,
        default=ctx.DATA_DIR,
        help=f"Directorio data a escanear (default: {ctx.display_path(ctx.DATA_DIR)})",
    )
    refresh_parser.add_argument(
        "--csv",
        type=Path,
        default=ctx.DATA_REPORTS_EXPORTS_DIR / "paper_processing_state.csv",
        help="CSV local de inspeccion rapida.",
    )
    refresh_parser.add_argument("--pipeline-version", default="v1")
    refresh_parser.add_argument("--config-hash", default=None)
    refresh_parser.set_defaults(handler=cmd_processing_state_refresh)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=CLI_DESCRIPTION,
        formatter_class=_help_formatter,
    )
    subparsers = _command_subparsers(parser, "command")

    _add_metadata_extraction_group(subparsers)
    _add_bibliography_export_group(subparsers)
    _add_pdf_intake_group(subparsers)
    _add_pdf_processing_group(subparsers)
    _add_evidence_extraction_group(subparsers)
    _add_testing_pipeline_group(subparsers)
    _add_processing_state_group(subparsers)
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
