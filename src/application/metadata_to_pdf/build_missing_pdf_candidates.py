from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.application.metadata_to_pdf.common import (
    doi_from_metadata_record,
    iter_jsonl,
    linked_metadata_ids_and_dois,
    paper_id_from_metadata_id,
    pdf_url_from_metadata_record,
    should_keep_metadata_record,
    title_from_metadata_record,
    utc_now_iso,
    write_jsonl,
)


DEFAULT_METADATA_FILE = Path("data/lake/paper_metadata.jsonl")
DEFAULT_LINKS_FILE = Path("data/lake/paper_pdf_links.jsonl")
DEFAULT_OUTPUT_FILE = Path("data/lake/papers_missing_pdfs.jsonl")


def build_missing_pdf_candidates(
    *,
    metadata_file: Path = DEFAULT_METADATA_FILE,
    links_file: Path = DEFAULT_LINKS_FILE,
    output_file: Path = DEFAULT_OUTPUT_FILE,
    keep_only: bool = True,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    linked_metadata_ids, linked_dois = linked_metadata_ids_and_dois(links_file)
    records: list[dict[str, Any]] = []
    created_at = utc_now_iso()

    for metadata_record in iter_jsonl(metadata_file):
        metadata_id = str(metadata_record.get("metadata_id") or "").strip()
        if not metadata_id:
            continue
        if keep_only and not should_keep_metadata_record(metadata_record):
            continue

        doi = doi_from_metadata_record(metadata_record)
        has_link = metadata_id in linked_metadata_ids or (doi is not None and doi in linked_dois)
        if has_link:
            continue

        records.append(
            {
                "metadata_id": metadata_id,
                "paper_id": paper_id_from_metadata_id(metadata_id),
                "doi": doi,
                "title": title_from_metadata_record(metadata_record),
                "metadata_pdf_url": pdf_url_from_metadata_record(metadata_record),
                "missing_pdf_reason": "no_matching_record_in_paper_pdf_links",
                "created_at": created_at,
            }
        )
        if limit is not None and len(records) >= limit:
            break

    write_jsonl(output_file, records)
    return records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a JSONL list of metadata records that do not have a linked PDF yet."
    )
    parser.add_argument("--metadata-file", type=Path, default=DEFAULT_METADATA_FILE)
    parser.add_argument("--links-file", type=Path, default=DEFAULT_LINKS_FILE)
    parser.add_argument("--output-file", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--include-non-keep",
        action="store_true",
        help="Include records whose domain_screening decision is not keep.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    records = build_missing_pdf_candidates(
        metadata_file=args.metadata_file,
        links_file=args.links_file,
        output_file=args.output_file,
        keep_only=not args.include_non_keep,
        limit=args.limit,
    )
    print(f"Missing PDF candidates written: {len(records)}")
    print(f"Output: {args.output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
