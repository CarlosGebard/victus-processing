"""Evidence extraction application pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run_pdf_evidence(input_path: Path, **kwargs: Any) -> Path:
    from src.application.evidence_extraction.evidence import run_pdf_evidence as _run_pdf_evidence

    return _run_pdf_evidence(input_path, **kwargs)


__all__ = ["run_pdf_evidence"]
