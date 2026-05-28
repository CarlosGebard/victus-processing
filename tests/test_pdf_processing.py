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
from src.pdf_processing.models import MarkdownBatchOutput
from src.pdf_processing.processed_paper_contract import enforce_processed_paper_contract
from src.pdf_processing.pipeline import _load_or_create_markdown
from src.pdf_processing.quota import GeminiKeyScheduler, SQLiteQuotaRepository


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


def test_enforce_processed_paper_contract_repairs_ids_sections_frontmatter_and_splits() -> None:
    payload = {
        "source_pdf": "/tmp/paper-a.pdf",
        "blocks": [
            {
                "block_id": "b2",
                "order": 2,
                "section_path": ["2. Results"],
                "section_title": "2. Results",
                "section_type": "results",
                "content_kind": "paragraph",
                "text": "The intervention improved glucose and",
            },
            {
                "block_id": "b3",
                "order": 3,
                "section_path": ["2. Results"],
                "section_title": "Results",
                "section_type": "results",
                "content_kind": "paragraph",
                "text": "reduced insulin resistance.",
            },
            {
                "block_id": "b1",
                "order": 1,
                "section_path": ["Frontmatter"],
                "section_title": "Open Access",
                "section_type": "frontmatter",
                "content_kind": "paragraph",
                "text": "Open Access article under copyright notice.",
            },
        ],
    }

    normalized = enforce_processed_paper_contract(payload)

    assert [block["order"] for block in normalized["blocks"]] == [0, 1]
    assert normalized["blocks"][0]["retrieval_exclude"] is True
    assert normalized["blocks"][0]["block_id"] == "paper-a:b0"
    assert len(normalized["blocks"][1]["content_hash"]) == 64
    assert normalized["blocks"][1]["text"] == "The intervention improved glucose and reduced insulin resistance."
    assert normalized["blocks"][1]["section_title"] == "Results"
    assert normalized["blocks"][1]["section_slug"] == "results"
    assert set(normalized["blocks"][1]).issuperset(
        {
            "block_id",
            "content_hash",
            "section_path",
            "section_type",
            "content_kind",
            "text",
            "retrieval_exclude",
        }
    )


def test_enforce_processed_paper_contract_patches_section_ontology() -> None:
    payload = {
        "source_pdf": "paper.pdf",
        "blocks": [
            {
                "block_id": "b1",
                "order": 0,
                "section_path": ["Statistical analysis"],
                "section_title": "Statistical analysis",
                "section_type": "methods",
                "content_kind": "paragraph",
                "text": "Analyses used mixed models.",
            },
            {
                "block_id": "b2",
                "order": 1,
                "section_path": ["Data availability"],
                "section_title": "Data availability",
                "section_type": "unknown",
                "content_kind": "paragraph",
                "text": "Data are available from the repository.",
            },
        ],
    }

    normalized = enforce_processed_paper_contract(payload)

    assert normalized["blocks"][0]["section_type"] == "statistical_analysis"
    assert normalized["blocks"][1]["section_type"] == "dataset"
    assert normalized["blocks"][1]["retrieval_exclude"] is True


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
    assert merged["section_registry"][0] == {
        "title": "Intro",
        "type": "introduction",
        "original_title": "Intro",
        "canonical_title": "Intro",
        "section_type": "introduction",
        "parent": None,
    }
    assert merged["section_registry"][1]["title"] == "Methods"
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
    monkeypatch.setattr("src.pdf_processing.markdown.get_pdf_page_count", lambda pdf_path: 12)

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

    monkeypatch.setattr("src.pdf_processing.markdown.get_pdf_page_count", lambda pdf_path: 130)
    monkeypatch.setattr(
        "src.pdf_processing.markdown.pdf_to_markdown",
        lambda pdf_path, output_path: calls.append(pdf_path) or "# Paper\n",
    )

    outputs = pdf_dir_to_markdown(input_dir, output_dir, max_pages=100)

    assert outputs == ()
    assert calls == []
    status = load_markdown_status_index(output_dir / "markdown_status.jsonl")
    assert status["large"]["status"] == "failed"
    assert status["large"]["error"] == "pdf_page_limit_exceeded"
    assert status["large"]["page_count"] == 130


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
