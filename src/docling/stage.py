from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src import config as ctx
from src.artifacts import parse_document_from_pdf_name, refresh_registry_record
from src.pdf.stage import list_pdf_candidates


def run_docling_for_pdf(pdf_path: Path) -> dict[str, Path]:
    resolved_pdf_path = pdf_path.expanduser().resolve()
    document_id, doi, base_name = parse_document_from_pdf_name(resolved_pdf_path)
    record = refresh_registry_record(document_id, doi, base_name)
    stage_status = record.get("stage_status", {})

    if stage_status.get("completed"):
        print(f"[SKIP COMPLETE] {resolved_pdf_path.name}")
        return {}

    if stage_status.get("heuristics"):
        print(f"[SKIP HEURISTICS] {resolved_pdf_path.name}: ya existe salida heuristics")
        return {}

    runner = ctx.resolve_docling_v2_pipeline_runner()
    result = runner(
        input_pdf=resolved_pdf_path,
        output_root_dir=ctx.DOCLING_HEURISTICS_DIR,
        metadata_dir=ctx.METADATA_DIR,
        dotenv_path=ctx.ROOT_DIR / ".env",
        document_id=document_id,
        doi=doi,
        base_name=base_name,
    )
    output_dir = Path(result["output_dir"])
    docling_json = Path(result["json_path"])
    filtered_json = Path(result["filtered_json_path"])
    final_json = Path(result["final_json_path"])
    refresh_registry_record(document_id, doi, base_name)
    print(f"[OK] {resolved_pdf_path.name}")
    print(f"  - Output dir:    {ctx.display_path(output_dir)}")
    print(f"  - Docling JSON:  {ctx.display_path(docling_json)}")
    print(f"  - Filtered JSON: {ctx.display_path(filtered_json)}")
    print(f"  - Final JSON:    {ctx.display_path(final_json)}")
    return {
        "output_dir": output_dir,
        "json_path": docling_json,
        "filtered_json_path": filtered_json,
        "final_json_path": final_json,
    }


def run_docling_flow(runners: int = 1, pdf_path: Path | None = None) -> None:
    if runners < 1:
        raise ValueError("--runners debe ser >= 1")

    if pdf_path is not None:
        run_docling_for_pdf(pdf_path)
        return

    pdfs = list_pdf_candidates()
    if not pdfs:
        print(f"No hay PDFs en {ctx.display_path(ctx.DOCLING_INPUT_DIR)}.")
        return

    pending: list[Path] = []
    skipped_complete = 0
    skipped_existing_heuristics = 0

    for candidate in pdfs:
        document_id, doi, base_name = parse_document_from_pdf_name(candidate)
        record = refresh_registry_record(document_id, doi, base_name)
        stage_status = record.get("stage_status", {})

        if stage_status.get("completed"):
            print(f"[SKIP COMPLETE] {candidate.name}")
            skipped_complete += 1
            continue

        if stage_status.get("heuristics"):
            print(f"[SKIP HEURISTICS] {candidate.name}: ya existe salida heuristics")
            skipped_existing_heuristics += 1
            continue

        pending.append(candidate)

    if not pending:
        print("No hay PDFs pendientes para docling + heuristics.")
        print("\nResumen docling")
        print("- Procesados:              0")
        print(f"- Saltados completos:      {skipped_complete}")
        print(f"- Saltados por heuristics: {skipped_existing_heuristics}")
        print("- Fallidos:                0")
        return

    processed = 0
    failed = 0
    print(f"Pendientes docling: {len(pending)} PDFs")

    with ThreadPoolExecutor(max_workers=runners) as executor:
        futures = {executor.submit(run_docling_for_pdf, candidate): candidate for candidate in pending}
        for future in as_completed(futures):
            candidate = futures[future]
            try:
                future.result()
            except Exception as exc:
                failed += 1
                print(f"[FAIL] {candidate.name}: {exc}")
                continue
            processed += 1

    print("\nResumen docling")
    print(f"- Procesados:              {processed}")
    print(f"- Saltados completos:      {skipped_complete}")
    print(f"- Saltados por heuristics: {skipped_existing_heuristics}")
    print(f"- Fallidos:                {failed}")
