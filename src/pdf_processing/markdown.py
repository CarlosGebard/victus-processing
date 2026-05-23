from __future__ import annotations

from pathlib import Path
import argparse

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
