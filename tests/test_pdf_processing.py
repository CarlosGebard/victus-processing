from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from src.application.ports.llm import LLMRequest, LLMResponse
from src.application.pdf_processing.batching import MarkdownBatchingError, build_markdown_batches
from src.application.pdf_processing.llm_markdown import LLMMarkdownResponseError, parse_llm_json
from src.application.pdf_processing.markdown import load_markdown_status_index, pdf_dir_to_markdown
from src.application.pdf_processing.merge import merge_batch_outputs
from src.application.pdf_processing.models import MarkdownBatchOutput
from src.application.pdf_processing.models import PdfProcessingConfig
from src.application.pdf_processing.pipeline import _load_or_create_markdown, _write_llm_failure, run_markdown_processing, run_pdf_processing
from src.application.testing_pipeline.artifacts import collect_testing_artifacts, copy_testing_markdown


class FakeMarkdownLLM:
    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text=(
                '{"metadata":{"title":"Paper","authors":[],"year":null,"doi":null},'
                '"section_registry":[{"section_path":["Methods"],"original_title":"Methods",'
                '"canonical_title":"Methods","section_type":"methods","parent_path":[]}],'
                '"batch_index":1,'
                '"blocks":[{"section_path":["Methods"],"section_type":"methods",'
                '"content_kind":"paragraph","text":"Methods text."}],'
                '"batch_end":{"last_section_path":["Methods"],"last_section_title":"Methods",'
                '"last_section_type":"methods","tail_context":"Methods text."}}'
            )
        )


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
    assert "current_section" not in parsed
    assert "batch_warnings" not in parsed
    assert "local_id" not in parsed["blocks"][0]


def test_markdown_batch_output_drops_legacy_fields_from_model_output() -> None:
    parsed = MarkdownBatchOutput.model_validate(
        {
            "current_section": {"main": "methods"},
            "batch_warnings": {"possible_cut_table": False},
            "batch_index": 1,
            "blocks": [
                {
                    "local_id": None,
                    "section_path": ["Methods"],
                    "section_type": "methods",
                    "content_kind": "paragraph",
                    "text": "Text.",
                }
            ],
            "batch_end": {"last_section_path": ["Methods"]},
        }
    ).as_clean_dict()

    assert "current_section" not in parsed
    assert "batch_warnings" not in parsed
    assert "local_id" not in parsed["blocks"][0]


def test_parse_llm_json_accepts_json_wrapped_in_provider_text() -> None:
    parsed = parse_llm_json('Here is the JSON:\n{"batch_index": 1, "blocks": []}\nDone.')

    assert parsed == {"batch_index": 1, "blocks": []}


def test_parse_llm_json_preserves_raw_response_on_failure() -> None:
    raw_response = "not json"

    with pytest.raises(LLMMarkdownResponseError) as exc_info:
        parse_llm_json(raw_response)

    assert exc_info.value.response_text == raw_response


def test_write_llm_failure_includes_raw_response(tmp_path: Path) -> None:
    output = tmp_path / "batch_0002.failed.json"
    error = LLMMarkdownResponseError("LLM response is not valid JSON", response_text="not json")

    _write_llm_failure(output, batch_index=2, batch_start=10, batch_end=20, exc=error)

    assert '"batch_index": 2' in output.read_text(encoding="utf-8")
    assert '"response_text": "not json"' in output.read_text(encoding="utf-8")


def test_merge_batch_outputs_does_not_invent_quality(tmp_path: Path) -> None:
    config = PdfProcessingConfig(
        model="m",
        input_dir=tmp_path,
        output_dir=tmp_path,
        prompt_first_batch=tmp_path / "first.md",
        prompt_continuation_batch=tmp_path / "next.md",
    )

    merged = merge_batch_outputs(
        source_pdf=tmp_path / "paper.pdf",
        batches=[
            {
                "blocks": [
                    {
                        "section_path": ["Methods"],
                        "section_type": "methods",
                        "content_kind": "paragraph",
                        "text": "Text.",
                    }
                ]
            }
        ],
        config=config,
    )

    assert "quality" not in merged["blocks"][0]


def test_run_markdown_processing_uses_existing_paper_md(tmp_path: Path) -> None:
    paper_dir = tmp_path / "processing" / "paper-1"
    paper_dir.mkdir(parents=True)
    markdown_path = paper_dir / "paper.md"
    markdown_path.write_text("# Paper\n\n## Methods\n\nMethods text.", encoding="utf-8")
    config = PdfProcessingConfig(
        model="m",
        input_dir=tmp_path / "active",
        output_dir=tmp_path / "processing",
        prompt_first_batch=tmp_path / "first.md",
        prompt_continuation_batch=tmp_path / "next.md",
        markdown_batch_chars=10,
        markdown_batch_soft_limit_chars=100,
        markdown_batch_hard_limit_chars=200,
    )
    config.prompt_first_batch.write_text("Return JSON.", encoding="utf-8")
    config.prompt_continuation_batch.write_text("Return JSON.", encoding="utf-8")

    output = run_markdown_processing(markdown_path, config=config, llm_client=FakeMarkdownLLM())

    assert output == paper_dir / "paper.final.json"
    assert (paper_dir / "paper.processed.json").exists()


def test_run_pdf_processing_writes_markdown_batch_debug_when_requested(monkeypatch, tmp_path: Path) -> None:
    pdf_path = tmp_path / "active" / "paper-1.pdf"
    pdf_path.parent.mkdir()
    pdf_path.write_bytes(b"%PDF-1.4\n")
    config = PdfProcessingConfig(
        model="m",
        input_dir=tmp_path / "active",
        output_dir=tmp_path / "testing",
        prompt_first_batch=tmp_path / "first.md",
        prompt_continuation_batch=tmp_path / "next.md",
        markdown_batch_chars=10,
        markdown_batch_soft_limit_chars=100,
        markdown_batch_hard_limit_chars=200,
    )
    config.prompt_first_batch.write_text("Return JSON.", encoding="utf-8")
    config.prompt_continuation_batch.write_text("Return JSON.", encoding="utf-8")

    def fake_pdf_to_markdown(pdf_path: Path, output_path: Path) -> str:
        markdown = "# Paper\n\n## Methods\n\nMethods text."
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        return markdown

    monkeypatch.setattr(
        "src.application.pdf_processing.pipeline.pdf_to_markdown",
        fake_pdf_to_markdown,
    )

    output = run_pdf_processing(
        pdf_path,
        config=config,
        llm_client=FakeMarkdownLLM(),
        markdown_batches_dir=tmp_path / "testing" / "paper-1" / "markdown_batches",
    )

    assert output == tmp_path / "testing" / "paper-1" / "paper.final.json"
    assert (tmp_path / "testing" / "paper-1" / "markdown_batches" / "batch_0001.md").read_text(encoding="utf-8").startswith("# Paper")
    metadata = (tmp_path / "testing" / "paper-1" / "markdown_batches" / "batch_0001.json").read_text(encoding="utf-8")
    assert '"batch_index": 1' in metadata
    assert '"chars":' in metadata
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


def test_collect_testing_artifacts_copies_existing_pdf_and_markdown(tmp_path: Path) -> None:
    pdf_dir = tmp_path / "active"
    markdown_dir = tmp_path / "processing"
    output_dir = tmp_path / "testing"
    pdf_dir.mkdir()
    paper_dir = markdown_dir / "paper-1"
    paper_dir.mkdir(parents=True)
    (pdf_dir / "paper-1.pdf").write_bytes(b"%PDF-1.4\n")
    (pdf_dir / "missing-markdown.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_dir / "paper.md").write_text("# Paper 1\n", encoding="utf-8")

    result = collect_testing_artifacts(
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        output_dir=output_dir,
    )

    assert [item.paper_id for item in result.copied] == ["paper-1"]
    assert [(item.paper_id, item.reason) for item in result.skipped] == [("missing-markdown", "missing_markdown")]
    assert (output_dir / "paper-1" / "source.pdf").read_bytes() == b"%PDF-1.4\n"
    assert (output_dir / "paper-1" / "paper.md").read_text(encoding="utf-8") == "# Paper 1\n"


def test_copy_testing_markdown_copies_existing_markdown(tmp_path: Path) -> None:
    markdown_dir = tmp_path / "processing"
    output_dir = tmp_path / "testing"
    source_dir = markdown_dir / "paper-1"
    source_dir.mkdir(parents=True)
    (source_dir / "paper.md").write_text("# Existing Markdown\n", encoding="utf-8")

    output = copy_testing_markdown(markdown_dir, output_dir, "paper-1")

    assert output == output_dir.resolve() / "paper-1" / "paper.md"
    assert output.read_text(encoding="utf-8") == "# Existing Markdown\n"


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
