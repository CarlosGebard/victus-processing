"""Canonical multi-source metadata-to-PDF resolver entrypoint."""

from src.application.metadata_to_pdf.fetch_unpaywall_pdfs import (
    build_parser,
    main,
    resolve_missing_pdfs,
)

__all__ = ["build_parser", "main", "resolve_missing_pdfs"]


if __name__ == "__main__":
    raise SystemExit(main())
