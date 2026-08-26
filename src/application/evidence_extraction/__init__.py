"""Evidence extraction application pipeline."""

from __future__ import annotations

from typing import Any


def run_pdf_evidence(paper_id: str, **kwargs: Any) -> str:
    from src.application.evidence_extraction.evidence import run_pdf_evidence as _run_pdf_evidence

    return _run_pdf_evidence(paper_id, **kwargs)


__all__ = ["run_pdf_evidence"]
