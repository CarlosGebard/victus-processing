#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from src.workspace import config as ctx


DEFAULT_INPUT_JSONL = ctx.DATA_LAKE_DIR / "paper_metadata.jsonl"
DEFAULT_OUTPUT_BIB = ctx.DATA_LAKE_DIR / "paper_metadata.bib"


def citekey_from_metadata_id(metadata_id: str, used_keys: set[str]) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "_", metadata_id).strip("_") or "paper"
    key = base
    counter = 1
    while key in used_keys:
        key = f"{base}_{counter}"
        counter += 1
    used_keys.add(key)
    return key


def paper_metadata_to_doi_bibtex_entry(record: dict[str, Any], used_keys: set[str]) -> str | None:
    screening = record.get("domain_screening") if isinstance(record.get("domain_screening"), dict) else {}
    if screening.get("decision") != "keep":
        return None

    source_metadata = record.get("source_metadata") if isinstance(record.get("source_metadata"), dict) else {}
    doi = str(source_metadata.get("doi") or "").strip()
    if not doi:
        return None

    citekey = citekey_from_metadata_id(str(record.get("metadata_id") or doi), used_keys)
    return "\n".join(
        [
            f"@article{{{citekey},",
            f"  doi = {{{doi}}}",
            "}",
        ]
    )


def generate_bib_from_paper_metadata_jsonl(input_jsonl: Path, output_bib: Path) -> tuple[int, int]:
    used_keys: set[str] = set()
    entries: list[str] = []
    skipped = 0

    if not input_jsonl.exists():
        raise FileNotFoundError(f"No existe input_jsonl: {input_jsonl}")

    for raw_line in input_jsonl.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(payload, dict):
            skipped += 1
            continue
        entry = paper_metadata_to_doi_bibtex_entry(payload, used_keys)
        if entry:
            entries.append(entry)
        else:
            skipped += 1

    output_bib.parent.mkdir(parents=True, exist_ok=True)
    output_bib.write_text("\n\n".join(entries), encoding="utf-8")
    return len(entries), skipped


def generate_bib_flow(
    output_file: Path | None = None,
    input_jsonl: Path = DEFAULT_INPUT_JSONL,
) -> None:
    target = output_file or DEFAULT_OUTPUT_BIB
    entries, skipped = generate_bib_from_paper_metadata_jsonl(input_jsonl, target)

    print("BibTeX generado")
    print(f"- Entradas: {entries}")
    print(f"- Omitidos: {skipped}")
    print(f"- Archivo:  {ctx.display_path(target)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convierte paper_metadata JSONL keep a BibTeX DOI-only")
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=DEFAULT_INPUT_JSONL,
        help=f"Paper metadata JSONL canonical (default: {DEFAULT_INPUT_JSONL})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Archivo .bib de salida (default: {DEFAULT_OUTPUT_BIB})",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    target = args.output or DEFAULT_OUTPUT_BIB
    entries, skipped = generate_bib_from_paper_metadata_jsonl(args.input_jsonl, target)
    print(f"Generated {entries} BibTeX entries")
    print(f"Skipped {skipped} records")
    print(f"Output -> {target}")


if __name__ == "__main__":
    main()
