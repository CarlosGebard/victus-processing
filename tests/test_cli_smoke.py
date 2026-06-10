from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import src.cli as cli


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
        ("metadata-to-pdf", "normalize-pdfs", "--help"),
        ("pdf-processing", "run", "--help"),
        ("evidence-extraction", "run", "--help"),
        ("data-layout", "create", "--help"),
    ],
)
def test_cli_core_help_commands_are_available(args: tuple[str, ...]) -> None:
    result = run_cli(*args)

    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_metadata_seed_dois_reads_nested_active_metadata(tmp_path: Path) -> None:
    metadata_dir = tmp_path / "active"
    dated_dir = metadata_dir / "2026-05-18"
    dated_dir.mkdir(parents=True)
    (dated_dir / "doi-10.1000-example.metadata.json").write_text(
        json.dumps(
            {
                "doi": "10.1000/example",
                "title": "Precision nutrition responses",
                "citationCount": 250,
                "abstract": "",
            }
        ),
        encoding="utf-8",
    )

    rows = cli.seed_dois.collect_candidate_rows(
        metadata_dir,
        explored_dois=set(),
        keywords=["nutrition"],
        min_citations=100,
    )

    assert [row["doi"] for row in rows] == ["10.1000/example"]
