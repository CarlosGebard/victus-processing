from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import src.cli as cli
from ops.scripts.data.refresh_paper_metadata_from_dois import refresh_paper_metadata
from src.application.bibliography_export import generate_bib_from_paper_metadata_jsonl
from src.application.metadata_extraction import citation_exploration
from src.application.metadata_extraction.paper_selector import PaperCandidate, classify_papers_with_llm
from src.application.ports.llm import LLMRequest, LLMResponse
from src.application.pdf_intake import link_manual_pdf, paper_id_from_metadata_id
from src.application.processing_state import build_processing_state_records
from src.application.scientific_output_store import (
    persist_evidence_blocks,
    persist_structured_blocks,
    persist_structured_paper,
    stable_experiment_map_id,
)


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "src.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("metadata-extraction", "seed-dois", "--help"),
        ("bibliography-export", "generate-bib", "--help"),
        ("pdf-intake", "link", "--help"),
        ("pdf-intake", "backfill-links", "--help"),
        ("pdf-processing", "run", "--help"),
        ("pdf-processing", "json-from-markdown", "--help"),
        ("evidence-extraction", "run", "--help"),
        ("processing-state", "refresh", "--help"),
        ("data-layout", "create", "--help"),
    ],
)
def test_cli_core_help_commands_are_available(args: tuple[str, ...]) -> None:
    result = run_cli(*args)

    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_metadata_seed_dois_reads_paper_metadata_jsonl(tmp_path: Path) -> None:
    metadata_file = tmp_path / "paper_metadata.jsonl"
    metadata_file.write_text(
        json.dumps(
            {
                "source_metadata": {
                    "doi": "10.1000/example",
                    "title": "Precision nutrition responses",
                    "citation_count": 250,
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rows = cli.seed_dois.collect_candidate_rows(
        metadata_file,
        explored_dois=set(),
        keywords=["nutrition"],
        min_citations=100,
    )

    assert [row["doi"] for row in rows] == ["10.1000/example"]


def test_metadata_selector_sends_single_json_input_request() -> None:
    class FakeLLMClient:
        def __init__(self) -> None:
            self.request: LLMRequest | None = None

        def complete(self, request: LLMRequest) -> LLMResponse:
            self.request = request
            return LLMResponse(
                text=json.dumps(
                    {
                        "decisions": [
                            {
                                "id": "cand_001",
                                "decision": "keep",
                                "reason": "nutrition topic",
                            }
                        ]
                    }
                )
            )

    client = FakeLLMClient()

    decisions, _raw = classify_papers_with_llm(
        candidates=[
            PaperCandidate(
                id="cand_001",
                title="Diet quality and metabolic health",
                abstract_preview="Adults with different dietary patterns were compared.",
            )
        ],
        model="test-model",
        client=client,
    )

    assert decisions == [{"id": "cand_001", "decision": "keep", "reason": "nutrition topic"}]
    assert client.request is not None
    assert client.request.operation == "metadata_extraction.paper_selector"
    assert len(client.request.messages) == 1
    assert client.request.messages[0]["role"] == "user"
    assert "# INPUT" in client.request.messages[0]["content"]
    assert '"candidates": [' in client.request.messages[0]["content"]
    assert '"title": "Diet quality and metabolic health"' in client.request.messages[0]["content"]
    assert "abstract_preview" not in client.request.messages[0]["content"]
    assert client.request.response_format == {
        "type": "json_schema",
        "json_schema": {
            "name": "paper_selection_decisions",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "decisions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "decision": {"type": "string", "enum": ["keep", "drop", "uncertain"]},
                                "reason": {"type": "string"},
                            },
                            "required": ["id", "decision", "reason"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["decisions"],
                "additionalProperties": False,
            },
        },
    }


def test_default_local_prompt_registry_finds_metadata_selector() -> None:
    from src.infrastructure.prompts.factory import build_prompt_registry

    prompt = build_prompt_registry().get("metadata_extraction/paper_selector")

    assert prompt.source == "local"
    assert "paper-selection agent" in prompt.template.lower()


def test_metadata_explore_skips_papers_from_lake_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lake_file = tmp_path / "paper_metadata.jsonl"
    lake_file.write_text(
        json.dumps(
            {
                "source_metadata": {
                    "source_paper_id": "s2paper123",
                    "doi": "10.1000/example",
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(citation_exploration, "paper_metadata_lake_file", lake_file)
    citation_exploration._collect_lake_paper_metadata_ids_cached.cache_clear()

    assert citation_exploration._paper_storage_state({"paperId": "s2paper123", "externalIds": {}}) == "kept"
    assert citation_exploration._paper_storage_state(
        {"paperId": "other", "externalIds": {"DOI": "10.1000/example"}}
    ) == "kept"


def test_metadata_from_doi_writes_directly_to_lake_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = tmp_path / "paper_metadata.jsonl"

    monkeypatch.setattr(
        citation_exploration,
        "fetch_paper_by_doi",
        lambda doi: {
            "paperId": "s2paper123",
            "title": "Seed paper",
            "year": 2025,
            "citationCount": 7,
            "externalIds": {"DOI": doi},
            "openAccessPdf": {"url": "https://example.test/paper.pdf"},
            "authors": [{"name": "Ada Lovelace"}],
        },
    )

    path, status = citation_exploration.write_metadata_for_doi("10.1000/EXAMPLE", output_dir=output)

    assert path == output
    assert status == "written"
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["metadata_id"] == "meta:s2:s2paper123"
    assert rows[0]["source_metadata"]["doi"] == "10.1000/example"


def test_metadata_save_paper_writes_directly_to_lake_jsonl(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lake_file = tmp_path / "paper_metadata.jsonl"
    monkeypatch.setattr(citation_exploration, "paper_metadata_lake_file", lake_file)

    citation_exploration.save_paper(
        {
            "paperId": "s2paper123",
            "title": "Explored paper",
            "year": 2025,
            "citationCount": 7,
            "externalIds": {"DOI": "10.1000/example"},
            "openAccessPdf": {"url": "https://example.test/paper.pdf"},
            "authors": [{"name": "Ada Lovelace"}],
        },
        parent=None,
        seed_doi="10.1000/seed",
    )

    rows = [json.loads(line) for line in lake_file.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["metadata_id"] == "meta:s2:s2paper123"
    assert rows[0]["domain_screening"]["decision"] == "keep"


def test_refresh_paper_metadata_from_dois_uses_semantic_scholar_paper_id(tmp_path: Path) -> None:
    class FakeClient:
        def fetch_by_doi(self, doi: str) -> dict[str, object]:
            assert doi == "10.1000/example"
            return {
                "paperId": "s2paper123",
                "title": "Fresh title",
                "year": 2025,
                "citationCount": 42,
                "externalIds": {"DOI": "10.1000/example", "ArXiv": "2501.00001"},
                "openAccessPdf": {"url": "https://example.test/fresh.pdf"},
                "authors": [{"name": "Ada Lovelace"}],
            }

    input_file = tmp_path / "paper_metadata.jsonl"
    output_file = tmp_path / "paper_metadata.s2_refreshed.jsonl"
    input_file.write_text(
        json.dumps(
            {
                "metadata_id": "meta:crossref:10.1000/example",
                "source_metadata": {"doi": "10.1000/example"},
                "discovery": {"seed_papers": ["10.1000/seed"], "is_seed_paper": False},
                "domain_screening": {"decision": "keep", "model": None},
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "schema_version": "v1",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    summary = refresh_paper_metadata(input_file=input_file, output_file=output_file, client=FakeClient())

    rows = [json.loads(line) for line in output_file.read_text(encoding="utf-8").splitlines()]
    assert summary.refreshed == 1
    assert rows[0]["metadata_id"] == "meta:s2:s2paper123"
    assert rows[0]["domain_screening"] == {"decision": "keep", "model": "gpt-4o"}
    assert rows[0]["source_metadata"]["source_paper_id"] == "s2paper123"
    assert rows[0]["source_metadata"]["citation_count"] == 42
    assert list(rows[0]) == [
        "metadata_id",
        "source_metadata",
        "schema_version",
        "discovery",
        "domain_screening",
        "created_at",
        "updated_at",
    ]
    assert list(rows[0]["source_metadata"])[-1] == "authors"


def test_generate_bib_from_paper_metadata_jsonl_writes_keep_doi_only(tmp_path: Path) -> None:
    input_jsonl = tmp_path / "paper_metadata.jsonl"
    output_bib = tmp_path / "paper_metadata.bib"
    rows = [
        {
            "metadata_id": "meta:s2:abc123",
            "source_metadata": {"doi": "10.1000/keep"},
            "domain_screening": {"decision": "keep"},
        },
        {
            "metadata_id": "meta:s2:def456",
            "source_metadata": {"doi": "10.1000/drop"},
            "domain_screening": {"decision": "drop"},
        },
        {
            "metadata_id": "meta:s2:ghi789",
            "source_metadata": {"doi": ""},
            "domain_screening": {"decision": "keep"},
        },
    ]
    input_jsonl.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    entries, skipped = generate_bib_from_paper_metadata_jsonl(input_jsonl, output_bib)

    assert entries == 1
    assert skipped == 2
    assert output_bib.read_text(encoding="utf-8") == "@article{meta_s2_abc123,\n  doi = {10.1000/keep}\n}"


def test_pdf_intake_links_manual_pdf_to_hashed_paper_id(tmp_path: Path) -> None:
    metadata_file = tmp_path / "paper_metadata.jsonl"
    source_pdf = tmp_path / "intake" / "paper.pdf"
    artifact_dir = tmp_path / "artifacts" / "pdfs"
    links_file = tmp_path / "lake" / "paper_pdf_links.jsonl"
    metadata_id = "meta:s2:abc123"
    metadata_file.write_text(
        json.dumps(
            {
                "metadata_id": metadata_id,
                "source_metadata": {"doi": "https://doi.org/10.1000/Example"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    source_pdf.parent.mkdir(parents=True)
    source_pdf.write_bytes(b"%PDF-1.4\n")

    link = link_manual_pdf(
        metadata_id=metadata_id,
        source_pdf=source_pdf,
        metadata_file=metadata_file,
        artifact_dir=artifact_dir,
        links_file=links_file,
        linked_at="2026-06-11T00:00:00Z",
    )

    expected_paper_id = paper_id_from_metadata_id(metadata_id)
    artifact_pdf = artifact_dir / f"{expected_paper_id}.pdf"
    assert not source_pdf.exists()
    assert artifact_pdf.read_bytes() == b"%PDF-1.4\n"
    assert link.paper_id == expected_paper_id
    assert link.doi == "10.1000/example"
    rows = [json.loads(line) for line in links_file.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "artifact_pdf_path": str(artifact_pdf),
            "doi": "10.1000/example",
            "linked_at": "2026-06-11T00:00:00Z",
            "link_method": "manual_intake",
            "metadata_id": metadata_id,
            "paper_id": expected_paper_id,
            "source_pdf_path": str(source_pdf),
        }
    ]


def test_pdf_intake_backfills_existing_artifact_links(tmp_path: Path) -> None:
    from src.application.pdf_intake import backfill_links_from_existing_artifacts

    metadata_file = tmp_path / "paper_metadata.jsonl"
    legacy_links_file = tmp_path / "links.jsonl"
    artifact_dir = tmp_path / "artifacts" / "pdfs"
    links_file = tmp_path / "paper_pdf_links.jsonl"
    paper_id = "a" * 64
    artifact_pdf = artifact_dir / f"{paper_id}.pdf"
    artifact_dir.mkdir(parents=True)
    artifact_pdf.write_bytes(b"%PDF-1.4\n")
    metadata_file.write_text(
        json.dumps(
            {
                "metadata_id": "meta:s2:abc123",
                "source_metadata": {"doi": "10.1000/example"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    legacy_links_file.write_text(
        json.dumps({"paper_id": paper_id, "doi": "10.1000/example"}) + "\n",
        encoding="utf-8",
    )

    written, skipped = backfill_links_from_existing_artifacts(
        metadata_file=metadata_file,
        legacy_links_file=legacy_links_file,
        artifact_dir=artifact_dir,
        links_file=links_file,
        linked_at="2026-06-11T00:00:00Z",
    )

    assert (written, skipped) == (1, 0)
    assert [json.loads(line) for line in links_file.read_text(encoding="utf-8").splitlines()] == [
        {
            "artifact_pdf_path": str(artifact_pdf),
            "doi": "10.1000/example",
            "linked_at": "2026-06-11T00:00:00Z",
            "link_method": "manual_intake",
            "metadata_id": "meta:s2:abc123",
            "paper_id": paper_id,
            "source_pdf_path": str(artifact_pdf),
        }
    ]


def test_scientific_output_store_persists_structured_blocks_payload() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.record: dict[str, object] | None = None

        def upsert_structured_blocks(self, record: dict[str, object]) -> None:
            self.record = record

    store = FakeStore()
    block = {
        "block_id": "block_1",
        "paper_id": "paper_1",
        "content_hash": "hash_1",
        "order": 1,
        "section_path": ["Results"],
        "section_type": "results",
        "content_kind": "paragraph",
        "text": "Result text.",
    }

    persist_structured_blocks(store, paper_id="paper_1", blocks=[block], producer_run_id="run_1")

    assert store.record == {
        "paper_id": "paper_1",
        "producer_run_id": "run_1",
        "schema_version": "v1",
        "blocks": [block],
    }


def test_scientific_output_store_persists_structured_paper_without_source_pdf() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.record: dict[str, object] | None = None

        def upsert_structured_paper(self, record: dict[str, object]) -> None:
            self.record = record

    store = FakeStore()

    persist_structured_paper(
        store,
        paper_id="paper_1",
        payload={"source_pdf": "/tmp/paper_1.pdf", "metadata": {}, "sections": [], "blocks": []},
        producer_run_id="run_1",
    )

    assert store.record == {
        "paper_id": "paper_1",
        "producer_run_id": "run_1",
        "schema_version": "v1",
        "payload": {"paper_id": "paper_1", "metadata": {}, "sections": [], "blocks": []},
    }


def test_scientific_output_store_persists_evidence_blocks_payload() -> None:
    class FakeStore:
        def __init__(self) -> None:
            self.record: dict[str, object] | None = None

        def upsert_evidence_blocks(self, record: dict[str, object]) -> None:
            self.record = record

    store = FakeStore()
    block = {
        "block_id": "block_1",
        "paper_id": "paper_1",
        "content_hash": "hash_1",
        "order": 1,
        "section_path": ["Results"],
        "section_type": "results",
        "content_kind": "paragraph",
        "text": "Result text.",
    }

    persist_evidence_blocks(store, paper_id="paper_1", blocks=[block], producer_run_id="run_1")

    assert store.record == {
        "paper_id": "paper_1",
        "producer_run_id": "run_1",
        "schema_version": "v1",
        "blocks": [block],
    }


def test_stable_experiment_map_id_is_deterministic() -> None:
    payload = {"experiment_scopes": [{"source_block_ids": ["b1", "b2"]}], "unmapped_block_ids": []}

    assert stable_experiment_map_id("paper_1", payload) == stable_experiment_map_id("paper_1", dict(payload))


def test_processing_state_scans_data_outputs(tmp_path: Path) -> None:
    paper_id = "paper_1"
    pdf = tmp_path / "artifacts" / "pdfs" / f"{paper_id}.pdf"
    markdown = tmp_path / "artifacts" / "markdown" / f"{paper_id}.md"
    for path in (pdf, markdown):
        path.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4\n")
    markdown.write_text("# Paper\n", encoding="utf-8")

    records = build_processing_state_records(
        data_dir=tmp_path,
        postgres_facts={
            paper_id: {
                "has_structured_paper": True,
                "has_structured_blocks": True,
                "has_evidence_blocks": False,
                "has_paper_classification": False,
                "has_experiment_map": False,
                "has_canonical_evidence": False,
            }
        },
    )

    assert len(records) == 1
    assert records[0]["paper_id"] == paper_id
    assert records[0]["has_pdf"] is True
    assert records[0]["has_markdown"] is True
    assert records[0]["has_structured_paper"] is True
    assert records[0]["has_structured_blocks"] is True
    assert records[0]["next_stage"] == "classification.classify"
