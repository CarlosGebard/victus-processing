from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from src.application.evidence_extraction import evidence


ROOT = Path(__file__).resolve().parents[1]


class FakeStore:
    def __init__(self, *, existing: bool = False) -> None:
        self.classification: dict[str, Any] | None = None
        self.existing = existing

    def fetch_structured_paper_ids(self, limit: int | None = None) -> list[str]:
        paper_ids = ["paper_1"]
        return paper_ids[:limit] if limit is not None else paper_ids

    def fetch_structured_paper(self, paper_id: str) -> dict[str, Any] | None:
        return {
            "paper_id": paper_id,
            "metadata": {},
            "blocks": [
                {
                    "block_id": "block_1",
                    "paper_id": paper_id,
                    "section_path": ["Introduction"],
                    "section_type": "introduction",
                    "content_kind": "paragraph",
                    "text": "Background text.",
                }
            ],
        }

    def has_canonical_evidence(self, paper_id: str) -> bool:
        return self.existing

    def upsert_paper_classification(self, record: dict[str, Any]) -> None:
        self.classification = record


def test_evidence_extraction_reads_postgres_and_writes_no_local_artifacts(monkeypatch, tmp_path) -> None:
    async def fake_classify(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {
            "paper_family": "opinion_or_theory",
            "paper_type": "narrative_review",
            "evidence_generation_mode": "argues_or_interprets",
            "has_original_experiments": False,
            "has_systematic_search": False,
            "has_meta_analysis": False,
            "classification_confidence": 0.9,
            "quality_flags": [],
            "risk_flags": [],
            "routing_evidence": [],
            "reasoning_summary": "No original experiments.",
        }

    monkeypatch.setattr(evidence, "classify_paper", fake_classify)
    monkeypatch.chdir(tmp_path)
    store = FakeStore()
    progress_events: list[tuple[str, dict[str, Any]]] = []

    result = asyncio.run(
        evidence.run_pdf_evidence_async(
            "paper_1",
            llm_client=object(),
            output_store=store,
            progress=lambda event, details: progress_events.append((event, details)),
        )
    )

    assert result == "paper_1"
    assert store.classification is not None
    assert [event for event, _ in progress_events] == ["classified", "done"]
    assert progress_events[-1][1]["reason"] == "non_primary_research"
    assert list(tmp_path.iterdir()) == []


def test_evidence_batch_reports_indexed_start_and_skip_events() -> None:
    progress_events: list[tuple[str, dict[str, Any]]] = []

    result = asyncio.run(
        evidence.run_pdf_evidence_db_async(
            store=FakeStore(existing=True),
            skip_existing=True,
            llm_client=object(),
            progress=lambda event, details: progress_events.append((event, details)),
        )
    )

    assert result == ["paper_1"]
    assert [event for event, _ in progress_events] == ["start", "skip"]
    assert progress_events[0][1] == {"index": 1, "total": 1, "paper_id": "paper_1"}
    assert progress_events[1][1]["reason"] == "existing"


def test_evidence_extraction_requires_postgres_store() -> None:
    try:
        asyncio.run(evidence.run_pdf_evidence_async("paper_1", llm_client=object()))
    except RuntimeError as exc:
        assert str(exc) == "PostgreSQL scientific output store is required"
    else:
        raise AssertionError("Expected PostgreSQL store requirement")


def test_canonical_evidence_prompt_separates_evidence_and_assertion_types() -> None:
    prompt = (
        ROOT / "src/prompts/evidence_extraction/canonical_evidence_extractor.md"
    ).read_text(encoding="utf-8")

    assert "Use `association` or `correlation`" not in prompt
    assert "Use `null_result`" not in prompt
    assert "Use `mechanistic_result` only" not in prompt
    assert "Never place an `assertion_type` value" in prompt
