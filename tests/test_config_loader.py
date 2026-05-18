from __future__ import annotations

from pathlib import Path

import pytest

import src.config as config_loader
from src import artifacts


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("metadata_dir", "data/runtime/01_candidates/active"),
        ("discarded_dir", "data/runtime/01_candidates/discarded"),
        ("raw_pdf_dir", "data/runtime/pdf_retrieval/raw"),
        ("unmatched_pdf_dir", "data/runtime/pdf_retrieval/unmatched"),
        ("docling_input_dir", "data/runtime/pdfs/normalized"),
        ("docling_heuristics_dir", "data/runtime/docling"),
        ("claims_output_dir", "data/runtime/claims"),
    ],
)
def test_pipeline_path_contract_defaults(key: str, expected: str) -> None:
    paths = config_loader.get_pipeline_paths({})

    assert paths[key] == config_loader.ROOT_DIR / expected


def test_testing_path_contract_defaults_to_archive_workspace() -> None:
    paths = config_loader.get_testing_paths({})

    assert paths == {
        "testing_root_dir": config_loader.ROOT_DIR / "data/archive/experiments/testing_1",
        "testing_docling_dir": config_loader.ROOT_DIR / "data/archive/experiments/testing_1/docling",
        "testing_claims_dir": config_loader.ROOT_DIR / "data/archive/experiments/testing_1/claims",
    }


def test_env_values_override_config(monkeypatch) -> None:
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "env-key")

    value = config_loader.get_env_or_config(
        "SEMANTIC_SCHOLAR_API_KEY",
        "api",
        "semantic_scholar_api_key",
        config={"api": {"semantic_scholar_api_key": "config-key"}},
    )

    assert value == "env-key"


def test_load_env_file_reads_required_local_keys(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'SEMANTIC_SCHOLAR_API_KEY="demo-key"\nOPENAI_API_KEY=test-openai\n',
        encoding="utf-8",
    )

    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config_loader.load_env_file(env_file)

    assert config_loader.os.environ["SEMANTIC_SCHOLAR_API_KEY"] == "demo-key"
    assert config_loader.os.environ["OPENAI_API_KEY"] == "test-openai"


def test_resolve_available_raw_pdf_dir_prefers_legacy_workspace_when_canonical_is_empty(tmp_path, monkeypatch) -> None:
    canonical = tmp_path / "pdf_retrieval" / "downloaded_pdfs"
    legacy = tmp_path / "pdf_retireval" / "downloaded_pdfs"
    canonical.mkdir(parents=True)
    legacy.mkdir(parents=True)
    (legacy / "example.pdf").write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(config_loader, "RAW_PDF_DIR", canonical)
    monkeypatch.setattr(config_loader, "LEGACY_PDF_RETIREVAL_DIR", tmp_path / "pdf_retireval")

    resolved = config_loader.resolve_available_raw_pdf_dir()

    assert resolved == legacy


def test_artifact_stage_status_detects_completed_pipeline(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_loader, "METADATA_DIR", tmp_path / "metadata")
    monkeypatch.setattr(config_loader, "DOCLING_INPUT_DIR", tmp_path / "input_pdfs")
    monkeypatch.setattr(config_loader, "DOCLING_HEURISTICS_DIR", tmp_path / "docling_heuristics")
    monkeypatch.setattr(config_loader, "CLAIMS_OUTPUT_DIR", tmp_path / "claims")

    paths = artifacts.artifact_paths_for_base_name("doi-10.1000-demo")
    for name, path in paths.items():
        if name == "docling_heuristics_dir":
            path.mkdir(parents=True, exist_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")

    status = artifacts.artifact_stage_status(paths)

    assert status["docling"] is True
    assert status["heuristics"] is True
    assert status["claims"] is True
    assert status["completed"] is True
