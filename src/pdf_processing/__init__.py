"""Gemini-based PDF Markdown extraction pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run_pdf_processing(pdf_path: Path, **kwargs: Any) -> Path:
    from src.pdf_processing.pipeline import run_pdf_processing as _run_pdf_processing

    return _run_pdf_processing(pdf_path, **kwargs)


__all__ = ["run_pdf_processing"]
