from __future__ import annotations

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
        ("metadata", "--help"),
        ("metadata", "explore", "--help"),
        ("metadata", "from-doi", "--help"),
        ("metadata", "seed-dois", "--help"),
        ("bib", "generate", "--help"),
        ("pdfs", "normalize", "--help"),
        ("pdf-processing", "--help"),
        ("pdf-processing", "run", "--help"),
        ("pdf-processing", "markdown", "--help"),
        ("claims", "extract", "--help"),
        ("bridge", "--help"),
        ("data-layout", "create", "--help"),
    ],
)
def test_cli_help_commands_are_available(args: tuple[str, ...]) -> None:
    result = run_cli(*args)

    assert result.returncode == 0
    assert "usage:" in result.stdout


def test_main_help_exposes_domain_contract_groups() -> None:
    result = run_cli("--help")

    assert result.returncode == 0
    for group in ("metadata", "bib", "pdfs", "pdf-processing", "claims", "bridge", "data-layout"):
        assert group in result.stdout


def test_main_prints_help_when_no_command(capsys) -> None:
    parser = cli.build_parser()
    parser.print_help()
    captured = capsys.readouterr()
    assert "metadata" in captured.out
    assert "claims" in captured.out


def test_main_routes_metadata_explore(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(sys, "argv", ["cli.py", "metadata", "explore", "--mode", "dataset-gaps"])
    monkeypatch.setattr(cli, "run_metadata_exploration_flow", lambda mode: called.append(mode))

    cli.main()

    assert called == ["dataset-gaps"]


def test_main_routes_metadata_seed_dois(monkeypatch, tmp_path: Path) -> None:
    called: list[dict[str, object]] = []
    terms_file = tmp_path / "terms.txt"
    metadata_dir = tmp_path / "metadata"
    terms_file.write_text("diet\n", encoding="utf-8")
    metadata_dir.mkdir()
    output_file = tmp_path / "generated_seed_dois.jsonl"
    explored_file = tmp_path / "explored_seed_dois.jsonl"

    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "metadata", "seed-dois", "--mode", "broad-nutrition"],
    )
    monkeypatch.setattr(cli.ctx, "METADATA_DIR", metadata_dir)
    monkeypatch.setattr(cli.ctx, "EXPLORATION_COMPLETED_SEED_DOI_FILE", explored_file)
    monkeypatch.setattr(cli.seed_dois, "DEFAULT_TERMS_FILE", terms_file)
    monkeypatch.setattr(cli.seed_dois, "DEFAULT_OUTPUT_FILE", output_file)
    monkeypatch.setattr(cli.seed_dois, "load_keyword_dictionary", lambda terms_file: ["diet"])
    monkeypatch.setattr(cli.seed_dois, "load_explored_dois", lambda explored_dois_file: {"10.1000/seen"})
    monkeypatch.setattr(
        cli.seed_dois,
        "collect_candidate_rows",
        lambda metadata_dir, **kwargs: called.append({"metadata_dir": metadata_dir, **kwargs}) or [],
    )
    monkeypatch.setattr(cli.seed_dois, "write_doi_output", lambda rows, output_path, **kwargs: 0)

    cli.main()

    assert called == [
        {
            "metadata_dir": metadata_dir.resolve(),
            "explored_dois": {"10.1000/seen"},
            "keywords": ["diet"],
            "min_citations": cli.seed_dois.DEFAULT_MIN_CITATIONS,
        }
    ]


def test_main_routes_bib_generate(monkeypatch, tmp_path: Path) -> None:
    called: list[tuple[Path | None, Path | None]] = []
    output = tmp_path / "papers.bib"
    input_csv = tmp_path / "missing.csv"

    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "bib", "generate", "--output", str(output), "--input-csv", str(input_csv)],
    )
    monkeypatch.setattr(cli, "generate_bib_flow", lambda target, source_csv: called.append((target, source_csv)))

    cli.main()

    assert called == [(output.resolve(), input_csv.resolve())]


def test_main_routes_claims_extract(monkeypatch, tmp_path: Path) -> None:
    called: list[dict[str, object]] = []
    input_path = tmp_path / "input"
    output_path = tmp_path / "output"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "claims",
            "extract",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--skip-existing",
            "--auto-approve-under-7000-tokens",
        ],
    )
    monkeypatch.setattr(cli, "run_llm_to_claim_flow", lambda **kwargs: called.append(kwargs))

    cli.main()

    assert called == [
        {
            "input_path": input_path,
            "output_path": output_path,
            "model": None,
            "max_claims": None,
            "temperature": None,
            "pattern": "*/*.final.json",
            "auto_approve_max_tokens": cli.ctx.LLM_CLAIMS_AUTO_APPROVE_MAX_TOKENS,
            "skip_existing": True,
        }
    ]


def test_main_routes_pdf_processing_run(monkeypatch, tmp_path: Path) -> None:
    called: list[dict[str, object]] = []
    pdf_path = tmp_path / "paper.pdf"

    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "pdf-processing", "run", "--pdf", str(pdf_path), "--force-markdown"],
    )
    monkeypatch.setattr(cli, "run_pdf_processing", lambda pdf, **kwargs: called.append({"pdf": pdf, **kwargs}) or tmp_path / "paper.processed.json")

    cli.main()

    assert called == [{
        "pdf": pdf_path.resolve(),
        "output_dir": None,
        "prompt_first_batch": None,
        "prompt_continuation_batch": None,
        "force_markdown": True,
        "max_batches": None,
    }]


def test_main_routes_pdf_processing_markdown(monkeypatch, tmp_path: Path) -> None:
    called: list[dict[str, object]] = []
    input_dir = tmp_path / "active"
    output_dir = tmp_path / "processing"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "pdf-processing",
            "markdown",
            "--input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--limit",
            "2",
            "--skip-existing",
            "--force",
        ],
    )
    monkeypatch.setattr(
        cli,
        "pdf_dir_to_markdown",
        lambda input_dir, output_dir, **kwargs: called.append(
            {"input_dir": input_dir, "output_dir": output_dir, **kwargs}
        )
        or (tmp_path / "paper.md",),
    )

    cli.main()

    assert called == [
        {
            "input_dir": input_dir.resolve(),
            "output_dir": output_dir.resolve(),
            "limit": 2,
            "skip_existing": True,
            "force": True,
            "status_file": None,
        }
    ]
