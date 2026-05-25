from __future__ import annotations

from pathlib import Path
import argparse
import json
from datetime import UTC, datetime

from typing import Any


def build_docling_converter() -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )


def validate_input_pdf(input_pdf: Path) -> None:
    if not input_pdf.exists():
        raise FileNotFoundError(f"No existe el archivo: {input_pdf}")
    if not input_pdf.is_file():
        raise ValueError(f"La ruta no es un archivo valido: {input_pdf}")
    if input_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"El archivo no es un PDF: {input_pdf}")


def pdf_to_markdown(pdf_path: Path, output_path: Path) -> str:
    validate_input_pdf(pdf_path)

    result = build_docling_converter().convert(str(pdf_path))
    document = getattr(result, "document", None)
    if document is None:
        raise RuntimeError("Docling no devolvio un documento valido.")

    markdown = document.export_to_markdown()
    if not isinstance(markdown, str) or not markdown.strip():
        raise RuntimeError(f"Docling produjo Markdown vacio para {pdf_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    return markdown


def pdf_output_markdown_path(output_dir: Path, pdf_path: Path) -> Path:
    return output_dir / pdf_path.stem / "paper.md"


def default_markdown_status_file(output_dir: Path) -> Path:
    return output_dir / "markdown_status.jsonl"


def iter_pdf_files(input_dir: Path) -> tuple[Path, ...]:
    if not input_dir.exists():
        raise FileNotFoundError(f"No existe el directorio: {input_dir}")
    if not input_dir.is_dir():
        raise ValueError(f"La ruta no es un directorio: {input_dir}")
    return tuple(sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"))


def load_markdown_status_index(status_file: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not status_file.exists():
        return index

    for line in status_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        paper_id = str(record.get("paper_id") or "")
        status = str(record.get("status") or "")
        if not paper_id or status not in {"done", "failed"}:
            continue
        index[paper_id] = record
    return index


def write_markdown_status(status_file: Path, index: dict[str, dict[str, Any]]) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(index.values(), key=lambda item: str(item.get("paper_id") or ""))
    content = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    status_file.write_text(content + ("\n" if content else ""), encoding="utf-8")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _markdown_status_record(
    *,
    paper_id: str,
    pdf_path: Path,
    markdown_output: Path,
    status: str,
    error: str | None = None,
    error_description: str | None = None,
) -> dict[str, Any]:
    return {
        "paper_id": paper_id,
        "stage": "docling_markdown",
        "status": status,
        "source_pdf": str(pdf_path),
        "output_markdown": str(markdown_output),
        "error": error,
        "error_description": error_description,
        "updated_at": _utc_now_iso(),
    }


def pdf_dir_to_markdown(
    input_dir: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
    skip_existing: bool = False,
    force: bool = False,
    status_file: Path | None = None,
) -> tuple[Path, ...]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1 when provided")

    pdfs = iter_pdf_files(input_dir)
    if limit is not None:
        pdfs = pdfs[:limit]

    resolved_status_file = status_file or default_markdown_status_file(output_dir)
    status_index = load_markdown_status_index(resolved_status_file)

    outputs: list[Path] = []
    for pdf_path in pdfs:
        markdown_output = pdf_output_markdown_path(output_dir, pdf_path)
        paper_id = pdf_path.stem
        status_record = status_index.get(paper_id) or {}
        if not force and status_record.get("status") == "done":
            print(f"[SKIP DONE] {paper_id}: {markdown_output}")
            outputs.append(markdown_output)
            continue
        if not force and skip_existing and markdown_output.exists():
            print(f"[SKIP EXISTING] {paper_id}: {markdown_output}")
            status_index[paper_id] = _markdown_status_record(
                paper_id=paper_id,
                pdf_path=pdf_path,
                markdown_output=markdown_output,
                status="done",
            )
            write_markdown_status(resolved_status_file, status_index)
            outputs.append(markdown_output)
            continue

        print(f"[DOCLING MARKDOWN] {paper_id}")
        try:
            pdf_to_markdown(pdf_path, markdown_output)
        except Exception as exc:
            status_index[paper_id] = _markdown_status_record(
                paper_id=paper_id,
                pdf_path=pdf_path,
                markdown_output=markdown_output,
                status="failed",
                error="docling_markdown_failed",
                error_description=f"{type(exc).__name__}: {exc}",
            )
            write_markdown_status(resolved_status_file, status_index)
            raise

        status_index[paper_id] = _markdown_status_record(
            paper_id=paper_id,
            pdf_path=pdf_path,
            markdown_output=markdown_output,
            status="done",
        )
        write_markdown_status(resolved_status_file, status_index)
        print(f"[WROTE] {markdown_output}")
        outputs.append(markdown_output)

    return tuple(outputs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert a PDF to Markdown using Docling.")
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    pdf_to_markdown(args.input_pdf.expanduser().resolve(), args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
