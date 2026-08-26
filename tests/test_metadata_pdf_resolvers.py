from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.application.metadata_to_pdf import fetch_unpaywall_pdfs as resolver


def _candidate_file(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "metadata_id": "meta:paper-1",
                "paper_id": "paper_1",
                "doi": "10.1000/example",
                "metadata_pdf_url": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_resolver_falls_back_from_unpaywall_to_europe_pmc(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "papers_missing_pdfs.jsonl"
    status_file = tmp_path / "unpaywall_pdf_status.jsonl"
    _candidate_file(input_file)

    def fake_get_json(url: str, *, timeout: float, headers=None) -> dict[str, Any]:
        if "unpaywall" in url:
            return {"is_oa": False, "oa_status": "closed", "oa_locations": []}
        return {
            "resultList": {
                "result": [
                    {
                        "doi": "10.1000/example",
                        "source": "MED",
                        "id": "123",
                        "pmcid": "PMC123",
                        "hasPDF": "Y",
                        "isOpenAccess": "Y",
                    }
                ]
            }
        }

    monkeypatch.setattr(resolver, "_get_json", fake_get_json)
    monkeypatch.setattr(resolver, "_download_pdf", lambda url, *, timeout: b"%PDF-1.4\n")

    counts = resolver.fetch_unpaywall_pdfs(
        input_file=input_file,
        output_dir=tmp_path / "staging",
        artifact_dir=tmp_path / "artifacts",
        links_file=tmp_path / "paper_pdf_links.jsonl",
        oa_status_file=status_file,
        email="operator@example.com",
    )

    status = json.loads(status_file.read_text(encoding="utf-8"))
    assert counts["downloaded"] == 1
    assert status["source"] == "europe_pmc"
    assert status["resolution_status"] == "downloaded"
    assert [attempt["source"] for attempt in status["attempts"]] == ["unpaywall", "europe_pmc"]


def test_resolver_keeps_europe_pmc_url_when_pdf_is_unavailable(tmp_path: Path, monkeypatch) -> None:
    input_file = tmp_path / "papers_missing_pdfs.jsonl"
    status_file = tmp_path / "unpaywall_pdf_status.jsonl"
    _candidate_file(input_file)

    monkeypatch.setattr(
        resolver,
        "_get_json",
        lambda url, *, timeout: {
            "resultList": {
                "result": [
                    {"doi": "10.1000/example", "source": "MED", "id": "123", "hasPDF": "N"}
                ]
            }
        },
    )

    counts = resolver.fetch_unpaywall_pdfs(
        input_file=input_file,
        output_dir=tmp_path / "staging",
        artifact_dir=tmp_path / "artifacts",
        links_file=tmp_path / "paper_pdf_links.jsonl",
        oa_status_file=status_file,
        email=None,
    )

    status = json.loads(status_file.read_text(encoding="utf-8"))
    assert counts["url_only"] == 1
    assert status["resolution_status"] == "url_only"
    assert status["landing_url"] == "https://europepmc.org/article/MED/123"
    assert status["pdf_url"] is None


def test_core_resolution_requires_exact_doi_and_preserves_auth(monkeypatch) -> None:
    observed: dict[str, Any] = {}

    def fake_get_json(url: str, *, timeout: float, headers=None) -> dict[str, Any]:
        observed.update({"url": url, "headers": headers})
        return {
            "results": [
                {
                    "id": 42,
                    "doi": "10.1000/example",
                    "downloadUrl": "https://api.core.ac.uk/v3/works/42/download",
                    "sourceFulltextUrls": ["https://repository.example/paper"],
                }
            ]
        }

    monkeypatch.setattr(resolver, "_get_json", fake_get_json)

    result = resolver._core_result("10.1000/example", api_key="secret", timeout=10)

    assert result.pdf_url == "https://api.core.ac.uk/v3/works/42/download"
    assert result.landing_url == "https://repository.example/paper"
    assert observed["headers"] == {"Authorization": "Bearer secret"}
