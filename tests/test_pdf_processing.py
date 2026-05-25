from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from src.pdf_processing.batching import MarkdownBatchingError, build_markdown_batches
from src.pdf_processing.gemini import load_gemini_api_keys
from src.pdf_processing.markdown import load_markdown_status_index, pdf_dir_to_markdown
from src.pdf_processing.merge import merge_batch_outputs
from src.pdf_processing.models import PdfProcessingConfig
from src.pdf_processing.pipeline import _load_or_create_markdown
from src.pdf_processing.quota import GeminiKeyScheduler, SQLiteQuotaRepository


def test_build_markdown_batches_cuts_before_level_two_heading() -> None:
    markdown = "\n\n".join(
        [
            "# Paper",
            "## Section 1\n" + ("a" * 120),
            "## Section 2\n" + ("b" * 120),
            "## Section 3\n" + ("c" * 40),
        ]
    )

    batches = build_markdown_batches(markdown, min_chars=100, hard_limit_chars=180)

    assert len(batches) == 3
    assert batches[0].index == 1
    assert batches[1].start_char > batches[0].end_char
    assert "## Section 2" not in batches[0].text
    assert batches[1].text.startswith("## Section 2")


def test_build_markdown_batches_falls_back_to_block_cut_when_heading_is_missing() -> None:
    markdown = "\n\n".join(
        [
            "# Paper",
            "a" * 80,
            "b" * 80,
            "c" * 80,
            "d" * 20,
        ]
    )

    batches = build_markdown_batches(markdown, min_chars=100, hard_limit_chars=180)

    assert len(batches) == 2
    assert batches[0].text.endswith("b" * 80)
    assert batches[1].text.startswith("c" * 80)


def test_build_markdown_batches_raises_when_no_safe_cut_exists_before_hard_limit() -> None:
    markdown = "a" * 250

    with pytest.raises(MarkdownBatchingError):
        build_markdown_batches(markdown, min_chars=100, hard_limit_chars=180)


def test_merge_uses_first_batch_metadata_dedupes_and_preserves_order(tmp_path) -> None:
    config = PdfProcessingConfig(
        model="gemini-3.1-flash-lite",
        input_dir=tmp_path / "input",
        output_dir=tmp_path,
        prompt_first_batch=Path("first.md"),
        prompt_continuation_batch=Path("next.md"),
        markdown_batch_chars=1000,
    )
    repeated_block = {
        "local_id": "intro-1",
        "section_path": ["Intro"],
        "section_type": "introduction",
        "content_kind": "paragraph",
        "text": "Same¶ paragraph_X_.",
    }

    merged = merge_batch_outputs(
        source_pdf=Path("paper.pdf"),
        batches=[
            {
                "metadata": {"title": "Paper¶ Title_X_", "authors": ["A"], "abstract": None, "doi": None, "journal": None, "year": None},
                "section_registry": [{"title": "Intro", "type": "introduction", "parent": None}],
                "blocks": [
                    repeated_block,
                    {
                        "local_id": "intro-table",
                        "section_path": ["Intro"],
                        "section_type": "introduction",
                        "content_kind": "table",
                        "text": "| A¶ | B |\n|---|---|\n| 1_X_ | 2 |",
                    },
                ],
                "batch_end": {"tail_context": "Same paragraph."},
                "batch_warnings": {"possible_cut_table": False, "possible_cut_list": False, "possible_cut_reference": False, "reason": None},
            },
            {
                "metadata": {"title": "Ignored"},
                "updated_section_registry": [{"title": "Methods", "type": "methods", "parent": None}],
                "blocks": [
                    repeated_block,
                    {
                        "local_id": "intro-2",
                        "section_path": ["Intro"],
                        "section_type": "introduction",
                        "content_kind": "paragraph",
                        "text": "New.",
                    },
                ],
                "batch_end": {"tail_context": "New."},
                "batch_warnings": {"possible_cut_table": False, "possible_cut_list": False, "possible_cut_reference": False, "reason": None},
            },
        ],
        config=config,
    )

    assert merged["metadata"]["title"] == "Paper Title"
    assert merged["sections"] == [
        {"order": 0, "title": "Intro", "type": "introduction", "parent": None},
        {"order": 1, "title": "Methods", "type": "methods", "parent": None},
    ]
    assert merged["section_registry"] == [
        {"title": "Intro", "type": "introduction", "parent": None},
        {"title": "Methods", "type": "methods", "parent": None},
    ]
    assert merged["blocks"] == [
        {
            "block_id": "intro-1",
            "order": 0,
            "section_path": ["Intro"],
            "section_title": "Intro",
            "section_type": "introduction",
            "content_kind": "paragraph",
            "text": "Same paragraph.",
            "quality": {"confidence": "medium", "is_truncated": False, "is_duplicate": False},
        },
        {
            "block_id": "intro-table",
            "order": 1,
            "section_path": ["Intro"],
            "section_title": "Intro",
            "section_type": "introduction",
            "content_kind": "table",
            "text": "| A | B |\n|---|---|\n| 1 | 2 |",
            "quality": {"confidence": "medium", "is_truncated": False, "is_duplicate": False},
        },
        {
            "block_id": "intro-2",
            "order": 2,
            "section_path": ["Intro"],
            "section_title": "Intro",
            "section_type": "introduction",
            "content_kind": "paragraph",
            "text": "New.",
            "quality": {"confidence": "medium", "is_truncated": False, "is_duplicate": False},
        },
    ]
    assert merged["batch_ends"] == [{"tail_context": "Same paragraph."}, {"tail_context": "New."}]


def test_gemini_key_scheduler_rotates_keys_round_robin(tmp_path) -> None:
    async def run() -> list[str]:
        scheduler = GeminiKeyScheduler(
            SQLiteQuotaRepository(tmp_path / "quota.sqlite3"),
            requests_per_minute=100,
            requests_per_day=100,
        )
        api_keys = {
            "GEMINI_KEY_1": "key-1",
            "GEMINI_KEY_2": "key-2",
            "GEMINI_KEY_3": "key-3",
        }
        selected = []
        for _ in range(5):
            key_id, _api_key = await scheduler.acquire_key(api_keys)
            selected.append(key_id)
        return selected

    assert asyncio.run(run()) == [
        "GEMINI_KEY_1",
        "GEMINI_KEY_2",
        "GEMINI_KEY_3",
        "GEMINI_KEY_1",
        "GEMINI_KEY_2",
    ]


def test_gemini_key_loader_accepts_descriptive_gemini_key_names() -> None:
    assert load_gemini_api_keys(
        {
            "GEMINI_KEY_CARLOS_MAIN": "main",
            "GEMINI_KEY_BACKUP_FAST": "backup",
            "GEMINI_API_KEY": "legacy",
            "OTHER": "ignored",
        }
    ) == {
        "GEMINI_KEY_BACKUP_FAST": "backup",
        "GEMINI_KEY_CARLOS_MAIN": "main",
    }


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

    monkeypatch.setattr("src.pdf_processing.markdown.pdf_to_markdown", fake_pdf_to_markdown)

    outputs = pdf_dir_to_markdown(input_dir, output_dir)
    skipped_outputs = pdf_dir_to_markdown(input_dir, output_dir)

    assert outputs == skipped_outputs == (output_dir / "paper-1" / "paper.md",)
    assert calls == [pdf_path]
    status = load_markdown_status_index(output_dir / "markdown_status.jsonl")
    assert status["paper-1"]["stage"] == "docling_markdown"
    assert status["paper-1"]["status"] == "done"


def test_gemini_key_scheduler_handles_variable_key_sets(tmp_path) -> None:
    async def run() -> list[str]:
        scheduler = GeminiKeyScheduler(
            SQLiteQuotaRepository(tmp_path / "quota.sqlite3"),
            requests_per_minute=100,
            requests_per_day=100,
        )
        selected = []
        for keys in (
            {"GEMINI_KEY_ALPHA": "a", "GEMINI_KEY_BRAVO": "b", "GEMINI_KEY_CHARLIE": "c"},
            {"GEMINI_KEY_ALPHA": "a", "GEMINI_KEY_CHARLIE": "c"},
            {"GEMINI_KEY_ALPHA": "a", "GEMINI_KEY_BRAVO": "b", "GEMINI_KEY_CHARLIE": "c"},
        ):
            key_id, _api_key = await scheduler.acquire_key(keys)
            selected.append(key_id)
        return selected

    assert asyncio.run(run()) == [
        "GEMINI_KEY_ALPHA",
        "GEMINI_KEY_CHARLIE",
        "GEMINI_KEY_ALPHA",
    ]


def test_docling_markdown_conversion_can_run_concurrently(monkeypatch, tmp_path: Path) -> None:
    def slow_pdf_to_markdown(pdf_path: Path, output_path: Path) -> str:
        time.sleep(0.2)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(f"# {pdf_path.stem}", encoding="utf-8")
        return f"# {pdf_path.stem}"

    monkeypatch.setattr("src.pdf_processing.pipeline.pdf_to_markdown", slow_pdf_to_markdown)

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
