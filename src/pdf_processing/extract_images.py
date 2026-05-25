from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import fitz


DEFAULT_INPUT = Path("data/testing")
DEFAULT_OUTPUT = Path("data/testing/extracted_images")


def iter_pdfs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {input_path}")
        return [input_path]
    if input_path.is_dir():
        return sorted(path for path in input_path.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")
    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def extract_images_from_pdf(pdf_path: Path, output_dir: Path) -> dict[str, Any]:
    pdf_path = pdf_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    paper_output_dir = output_dir / pdf_path.stem
    paper_output_dir.mkdir(parents=True, exist_ok=True)

    extracted: list[dict[str, Any]] = []
    seen_xrefs: set[int] = set()

    with fitz.open(pdf_path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            for image_index, image_info in enumerate(page.get_images(full=True), start=1):
                xref = int(image_info[0])
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)

                image = document.extract_image(xref)
                extension = str(image.get("ext") or "bin").lower()
                image_bytes = image.get("image")
                if not isinstance(image_bytes, bytes) or not image_bytes:
                    continue

                filename = f"page-{page_index + 1:04d}_image-{image_index:03d}_xref-{xref}.{extension}"
                image_path = paper_output_dir / filename
                image_path.write_bytes(image_bytes)

                extracted.append(
                    {
                        "page": page_index + 1,
                        "image_index": image_index,
                        "xref": xref,
                        "width": image.get("width"),
                        "height": image.get("height"),
                        "colorspace": image.get("colorspace"),
                        "extension": extension,
                        "path": str(image_path),
                    }
                )

    manifest = {
        "source_pdf": str(pdf_path),
        "output_dir": str(paper_output_dir),
        "image_count": len(extracted),
        "images": extracted,
    }
    (paper_output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract embedded images from PDF files.")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help="PDF file or directory containing PDFs. Defaults to data/testing.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory where extracted images will be written.",
    )
    args = parser.parse_args()

    pdfs = iter_pdfs(args.input.expanduser())
    if not pdfs:
        print(f"No PDF files found in {args.input}")
        return 0

    total_images = 0
    for pdf_path in pdfs:
        manifest = extract_images_from_pdf(pdf_path, args.output_dir)
        total_images += int(manifest["image_count"])
        print(f"{pdf_path}: extracted {manifest['image_count']} images -> {manifest['output_dir']}")

    print(f"Done. PDFs={len(pdfs)} images={total_images}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
