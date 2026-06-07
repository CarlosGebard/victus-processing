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
        ("metadata-extraction", "--help"),
        ("metadata-extraction", "explore", "--help"),
        ("metadata-extraction", "from-doi", "--help"),
        ("metadata-extraction", "seed-dois", "--help"),
        ("metadata-to-pdf", "generate-bib", "--help"),
        ("metadata-to-pdf", "normalize-pdfs", "--help"),
        ("pdf-processing", "--help"),
        ("pdf-processing", "run", "--help"),
        ("pdf-processing", "markdown", "--help"),
        ("evidence-extraction", "run", "--help"),
        ("testing-pipeline", "run", "--help"),
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
    for group in (
        "metadata-extraction",
        "metadata-to-pdf",
        "pdf-processing",
        "evidence-extraction",
        "testing-pipeline",
        "bridge",
        "data-layout",
    ):
        assert group in result.stdout


def test_main_prints_help_when_no_command(capsys) -> None:
    parser = cli.build_parser()
    parser.print_help()
    captured = capsys.readouterr()
    assert "metadata-extraction" in captured.out
    assert "pdf-processing" in captured.out


def test_main_routes_metadata_explore(monkeypatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(sys, "argv", ["cli.py", "metadata-extraction", "explore", "--mode", "dataset-gaps"])
    monkeypatch.setattr(cli, "run_metadata_exploration_flow", lambda mode, **kwargs: called.append(mode))

    cli.main()

    assert called == ["dataset-gaps"]


def test_main_routes_metadata_seed_dois(monkeypatch, tmp_path: Path) -> None:
    called: list[dict[str, object]] = []
    terms_file = tmp_path / "terms.txt"
    metadata_dir = tmp_path / "metadata-extraction"
    terms_file.write_text("diet\n", encoding="utf-8")
    metadata_dir.mkdir()
    output_file = tmp_path / "generated_seed_dois.jsonl"
    explored_file = tmp_path / "explored_seed_dois.jsonl"

    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "metadata-extraction", "seed-dois", "--mode", "broad-nutrition"],
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
        ["cli.py", "metadata-to-pdf", "generate-bib", "--output", str(output), "--input-csv", str(input_csv)],
    )
    monkeypatch.setattr(cli, "generate_bib_flow", lambda target, source_csv: called.append((target, source_csv)))

    cli.main()

    assert called == [(output.resolve(), input_csv.resolve())]


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
        "llm_client": called[0]["llm_client"],
        "prompt_registry": called[0]["prompt_registry"],
        "prompt_label": cli.ctx.PROMPT_LABEL,
    }]


def test_main_routes_pdf_processing_run_markdown(monkeypatch, tmp_path: Path) -> None:
    called: list[dict[str, object]] = []
    markdown_path = tmp_path / "paper-1" / "paper.md"
    markdown_path.parent.mkdir()
    markdown_path.write_text("# Paper", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["cli.py", "pdf-processing", "run", "--markdown", str(markdown_path), "--max-batches", "1"],
    )
    monkeypatch.setattr(
        cli,
        "run_markdown_processing",
        lambda markdown, **kwargs: called.append({"markdown": markdown, **kwargs}) or tmp_path / "paper.final.json",
    )

    cli.main()

    assert called == [{
        "markdown": markdown_path.resolve(),
        "output_dir": None,
        "prompt_first_batch": None,
        "prompt_continuation_batch": None,
        "force_markdown": False,
        "max_batches": 1,
        "llm_client": called[0]["llm_client"],
        "prompt_registry": called[0]["prompt_registry"],
        "prompt_label": cli.ctx.PROMPT_LABEL,
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
            "--max-pages",
            "75",
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
            "max_pages": 75,
            "status_file": None,
        }
    ]


def test_main_routes_pdf_processing_evidence(monkeypatch, tmp_path: Path) -> None:
    called: list[dict[str, object]] = []
    input_path = tmp_path / "paper.processed.json"
    input_path.write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "evidence"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "evidence-extraction", "run",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
            "--model",
            "test-model",
            "--skip-existing",
        ],
    )
    monkeypatch.setattr(
        cli,
        "run_pdf_evidence",
        lambda input_path, **kwargs: called.append({"input_path": input_path, **kwargs})
        or output_dir / "paper-1" / "canonical_evidence.json",
    )

    cli.main()

    assert called == [
        {
            "input_path": input_path.resolve(),
            "output_dir": output_dir.resolve(),
            "model": "test-model",
            "skip_existing": True,
            "llm_client": called[0]["llm_client"],
            "prompt_registry": called[0]["prompt_registry"],
            "prompt_label": cli.ctx.PROMPT_LABEL,
        }
    ]


def test_main_routes_pdf_processing_testing_pipeline(monkeypatch, tmp_path: Path) -> None:
    called: list[tuple[str, dict[str, object]]] = []
    pdf_dir = tmp_path / "active"
    output_dir = tmp_path / "testing"
    pdf_dir.mkdir()
    pdf_path = pdf_dir / "paper-1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "testing-pipeline", "run",
            "--pdf-dir",
            str(pdf_dir),
            "--output-dir",
            str(output_dir),
            "--paper-id",
            "paper-1",
            "--max-batches",
            "1",
            "--skip-existing-evidence",
        ],
    )
    monkeypatch.setattr(
        cli,
        "run_pdf_processing",
        lambda pdf, **kwargs: called.append(("processing", {"pdf": pdf, **kwargs}))
        or output_dir
        / "paper-1"
        / "paper.final.json",
    )
    monkeypatch.setattr(
        cli,
        "run_pdf_evidence",
        lambda input_path, **kwargs: called.append(("evidence", {"input_path": input_path, **kwargs}))
        or output_dir
        / "paper-1"
        / "canonical_evidence.json",
    )
    monkeypatch.setattr(
        cli,
        "write_markdown_batch_debug_for_markdown",
        lambda markdown_path, output_dir, **kwargs: called.append(
            ("markdown_batches", {"markdown_path": markdown_path, "output_dir": output_dir, **kwargs})
        )
        or (output_dir / "batch_0001.md",),
    )

    cli.main()

    assert (output_dir / "paper-1" / "source.pdf").read_bytes() == b"%PDF-1.4\n"
    assert called == [
        (
            "processing",
            {
                "pdf": pdf_path.resolve(),
                "output_dir": output_dir.resolve(),
                "prompt_first_batch": None,
                "prompt_continuation_batch": None,
                "force_markdown": False,
                "max_batches": 1,
                "llm_client": called[0][1]["llm_client"],
                "prompt_registry": called[0][1]["prompt_registry"],
                "prompt_label": cli.ctx.PROMPT_LABEL,
                "markdown_batches_dir": output_dir.resolve() / "paper-1" / "markdown_batches",
            },
        ),
        (
            "markdown_batches",
            {
                "markdown_path": output_dir.resolve() / "paper-1" / "paper.md",
                "output_dir": output_dir.resolve() / "paper-1" / "markdown_batches",
                "max_batches": 1,
            },
        ),
        (
            "evidence",
            {
                "input_path": output_dir.resolve() / "paper-1" / "paper.final.json",
                "output_dir": output_dir.resolve(),
                "model": None,
                "skip_existing": True,
                "llm_client": called[2][1]["llm_client"],
                "prompt_registry": called[2][1]["prompt_registry"],
                "prompt_label": cli.ctx.PROMPT_LABEL,
            },
        ),
    ]


def test_main_routes_pdf_processing_testing_reuse_markdown(monkeypatch, tmp_path: Path) -> None:
    called: list[tuple[str, dict[str, object]]] = []
    pdf_dir = tmp_path / "active"
    markdown_dir = tmp_path / "processing"
    output_dir = tmp_path / "testing"
    pdf_dir.mkdir()
    source_markdown_dir = markdown_dir / "paper-1"
    source_markdown_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "paper-1.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    (source_markdown_dir / "paper.md").write_text("# Existing Markdown\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "testing-pipeline", "run",
            "--pdf-dir",
            str(pdf_dir),
            "--markdown-dir",
            str(markdown_dir),
            "--output-dir",
            str(output_dir),
            "--paper-id",
            "paper-1",
            "--reuse-markdown",
            "--overwrite-markdown",
        ],
    )
    monkeypatch.setattr(
        cli,
        "run_markdown_processing",
        lambda markdown, **kwargs: called.append(("processing", {"markdown": markdown, **kwargs}))
        or output_dir
        / "paper-1"
        / "paper.final.json",
    )
    monkeypatch.setattr(
        cli,
        "run_pdf_evidence",
        lambda input_path, **kwargs: called.append(("evidence", {"input_path": input_path, **kwargs}))
        or output_dir
        / "paper-1"
        / "canonical_evidence.json",
    )
    monkeypatch.setattr(
        cli,
        "write_markdown_batch_debug_for_markdown",
        lambda markdown_path, output_dir, **kwargs: called.append(
            ("markdown_batches", {"markdown_path": markdown_path, "output_dir": output_dir, **kwargs})
        )
        or (output_dir / "batch_0001.md",),
    )

    cli.main()

    testing_markdown = output_dir / "paper-1" / "paper.md"
    assert testing_markdown.read_text(encoding="utf-8") == "# Existing Markdown\n"
    assert called[0] == (
        "processing",
        {
            "markdown": testing_markdown.resolve(),
            "output_dir": output_dir.resolve(),
            "prompt_first_batch": None,
            "prompt_continuation_batch": None,
            "force_markdown": False,
            "max_batches": None,
            "llm_client": called[0][1]["llm_client"],
            "prompt_registry": called[0][1]["prompt_registry"],
            "prompt_label": cli.ctx.PROMPT_LABEL,
        },
    )
    assert called[1] == (
        "markdown_batches",
        {
            "markdown_path": testing_markdown.resolve(),
            "output_dir": output_dir.resolve() / "paper-1" / "markdown_batches",
            "max_batches": None,
        },
    )
    assert called[2][0] == "evidence"
