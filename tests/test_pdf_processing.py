from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from src.application.pdf_processing.batching import MarkdownBatchingError, build_markdown_batches
from src.application.pdf_processing.markdown import load_markdown_status_index, pdf_dir_to_markdown
from src.application.pdf_processing.models import MarkdownBatchOutput
from src.application.pdf_processing.pipeline import _load_or_create_markdown


def test_build_markdown_batches_groups_structural_units_by_soft_limit() -> None:
    markdown = "\n\n".join(
        [
            "# Paper",
            "## Section 1",
            "a" * 80,
            "## Section 2",
            "b" * 80,
            "## Section 3",
            "c" * 40,
        ]
    )

    batches = build_markdown_batches(markdown, min_chars=90, soft_limit_chars=120, hard_limit_chars=180)

    assert len(batches) == 3
    assert batches[0].index == 1
    assert batches[1].start_char >= batches[0].end_char
    assert "## Section 2" not in batches[0].text
    assert batches[1].text.startswith("## Section 2")
    assert batches[1].previous_section_path == ("Paper", "Section 1")
    assert batches[1].last_300_chars == batches[0].text[-300:]


def test_build_markdown_batches_opens_batch_with_heading_after_half_target() -> None:
    markdown = "\n\n".join(
        [
            "# Paper",
            "a" * 60,
            "## Results",
            "b" * 60,
        ]
    )

    batches = build_markdown_batches(markdown, min_chars=100, soft_limit_chars=140, hard_limit_chars=200)

    assert len(batches) == 2
    assert not batches[0].text.endswith("## Results")
    assert batches[1].text.startswith("## Results")


def test_build_markdown_batches_moves_trailing_heading_when_hard_limit_closes() -> None:
    markdown = "\n\n".join(
        [
            "# Paper",
            "a" * 50,
            "## " + ("Results " * 12),
            "b" * 20,
        ]
    )

    batches = build_markdown_batches(markdown, min_chars=130, soft_limit_chars=135, hard_limit_chars=140)

    assert len(batches) == 2
    assert not batches[0].text.endswith("Results ")
    assert batches[1].text.startswith("## Results")


def test_build_markdown_batches_preserves_complete_table_and_list_units() -> None:
    markdown = "\n\n".join(
        [
            "# Paper",
            "Intro paragraph " + ("a" * 70),
            "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |",
            "- item one\n- item two\n- item three",
            "Final paragraph " + ("z" * 20),
        ]
    )

    batches = build_markdown_batches(markdown, min_chars=80, soft_limit_chars=120, hard_limit_chars=180)

    assert len(batches) >= 2
    all_batch_text = "\n---BATCH---\n".join(batch.text for batch in batches)
    assert "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |" in all_batch_text
    assert "- item one\n- item two\n- item three" in all_batch_text
    assert not any(batch.text.endswith("| A | B |") for batch in batches)
    assert not any(batch.text.endswith("- item one") for batch in batches)


def test_build_markdown_batches_splits_oversized_paragraph_by_safe_sub_rules() -> None:
    markdown = "# Paper\n\n" + "\n".join(["a" * 40 for _ in range(8)])

    batches = build_markdown_batches(markdown, min_chars=70, soft_limit_chars=100, hard_limit_chars=140)

    assert len(batches) >= 3
    assert any(batch.oversized_unit for batch in batches)
    assert all(len(batch.text) <= 140 for batch in batches)


def test_build_markdown_batches_raises_for_oversized_table() -> None:
    markdown = "# Paper\n\n" + "\n".join(["| " + ("a" * 80) + " |" for _ in range(4)])

    with pytest.raises(MarkdownBatchingError):
        build_markdown_batches(markdown, min_chars=70, soft_limit_chars=100, hard_limit_chars=140)


def test_markdown_batch_output_accepts_new_section_registry_contract_without_slug() -> None:
    parsed = MarkdownBatchOutput.model_validate(
        {
            "section_registry": [
                {
                    "original_title": "1. INTRODUCTION",
                    "canonical_title": "Introduction",
                    "section_type": "introduction",
                    "parent": None,
                }
            ],
            "blocks": [{"section_path": ["Introduction"], "section_type": "introduction", "content_kind": "paragraph", "text": "Text."}],
        }
    ).as_clean_dict()

    assert parsed["section_registry"][0]["title"] == "Introduction"
    assert parsed["section_registry"][0]["type"] == "introduction"
def test_pdf_dir_to_markdown_records_done_and_skips_from_status(monkeypatch, tmp_path: Path) -> None:
    input_dir = tmp_path / "active"
    output_dir = tmp_path / "processing"
    input_dir.mkdir()
    pdf_path = input_dir / "paper-1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    calls: list[Path] = []

    def fake_pdf_to_markdown(pdf_path: Path, output_path: Path) -> str:
        calls.append(pdf_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# Paper\n", encoding="utf-8")
        return "# Paper\n"

    monkeypatch.setattr("src.application.pdf_processing.markdown.pdf_to_markdown", fake_pdf_to_markdown)
    monkeypatch.setattr("src.application.pdf_processing.markdown.get_pdf_page_count", lambda pdf_path: 12)

    outputs = pdf_dir_to_markdown(input_dir, output_dir)
    skipped_outputs = pdf_dir_to_markdown(input_dir, output_dir)

    assert outputs == skipped_outputs == (output_dir / "paper-1" / "paper.md",)
    assert calls == [pdf_path]
    status = load_markdown_status_index(output_dir / "markdown_status.jsonl")
    assert status["paper-1"]["stage"] == "docling_markdown"
    assert status["paper-1"]["status"] == "done"


def test_pdf_dir_to_markdown_marks_over_page_limit_failed(monkeypatch, tmp_path: Path) -> None:
    input_dir = tmp_path / "active"
    output_dir = tmp_path / "processing"
    input_dir.mkdir()
    pdf_path = input_dir / "large.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    calls: list[Path] = []

    monkeypatch.setattr("src.application.pdf_processing.markdown.get_pdf_page_count", lambda pdf_path: 130)
    monkeypatch.setattr(
        "src.application.pdf_processing.markdown.pdf_to_markdown",
        lambda pdf_path, output_path: calls.append(pdf_path) or "# Paper\n",
    )

    outputs = pdf_dir_to_markdown(input_dir, output_dir, max_pages=100)

    assert outputs == ()
    assert calls == []
    status = load_markdown_status_index(output_dir / "markdown_status.jsonl")
    assert status["large"]["status"] == "failed"
    assert status["large"]["error"] == "pdf_page_limit_exceeded"
    assert status["large"]["page_count"] == 130

def test_docling_markdown_conversion_can_run_concurrently(monkeypatch, tmp_path: Path) -> None:
    def slow_pdf_to_markdown(pdf_path: Path, output_path: Path) -> str:
        time.sleep(0.2)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"# {pdf_path.stem}", encoding="utf-8")
        return f"# {pdf_path.stem}"

    monkeypatch.setattr("src.application.pdf_processing.pipeline.pdf_to_markdown", slow_pdf_to_markdown)

    async def run() -> list[str]:
        return await asyncio.gather(
            _load_or_create_markdown(tmp_path / "one.pdf", tmp_path / "one" / "paper.md", force_markdown=True),
            _load_or_create_markdown(tmp_path / "two.pdf", tmp_path / "two" / "paper.md", force_markdown=True),
        )

    start = time.perf_counter()
    results = asyncio.run(run())
    elapsed = time.perf_counter() - start

    assert results == ["# one", "# two"]
    assert elapsed < 0.35
