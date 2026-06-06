from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shutil import copy2


@dataclass(frozen=True)
class TestingArtifactCopy:
    paper_id: str
    source_pdf: Path
    source_markdown: Path
    output_dir: Path
    copied_pdf: bool
    copied_markdown: bool


@dataclass(frozen=True)
class TestingArtifactSkip:
    paper_id: str
    reason: str
    source_pdf: Path
    source_markdown: Path


@dataclass(frozen=True)
class TestingArtifactResult:
    copied: tuple[TestingArtifactCopy, ...]
    skipped: tuple[TestingArtifactSkip, ...]


def collect_testing_artifacts(
    *,
    pdf_dir: Path,
    markdown_dir: Path,
    output_dir: Path,
    paper_ids: tuple[str, ...] = (),
    limit: int | None = None,
    overwrite: bool = False,
) -> TestingArtifactResult:
    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1 when provided")

    resolved_pdf_dir = pdf_dir.expanduser().resolve()
    resolved_markdown_dir = markdown_dir.expanduser().resolve()
    resolved_output_dir = output_dir.expanduser().resolve()

    selected_paper_ids = paper_ids or _paper_ids_from_pdf_dir(resolved_pdf_dir)
    if limit is not None:
        selected_paper_ids = selected_paper_ids[:limit]

    copied: list[TestingArtifactCopy] = []
    skipped: list[TestingArtifactSkip] = []
    for paper_id in selected_paper_ids:
        source_pdf = resolved_pdf_dir / f"{paper_id}.pdf"
        source_markdown = resolved_markdown_dir / paper_id / "paper.md"
        if not source_pdf.exists():
            skipped.append(
                TestingArtifactSkip(
                    paper_id=paper_id,
                    reason="missing_pdf",
                    source_pdf=source_pdf,
                    source_markdown=source_markdown,
                )
            )
            continue
        if not source_markdown.exists():
            skipped.append(
                TestingArtifactSkip(
                    paper_id=paper_id,
                    reason="missing_markdown",
                    source_pdf=source_pdf,
                    source_markdown=source_markdown,
                )
            )
            continue

        paper_output_dir = resolved_output_dir / paper_id
        paper_output_dir.mkdir(parents=True, exist_ok=True)
        target_pdf = paper_output_dir / "source.pdf"
        target_markdown = paper_output_dir / "paper.md"

        copied_pdf = _copy_if_needed(source_pdf, target_pdf, overwrite=overwrite)
        copied_markdown = _copy_if_needed(source_markdown, target_markdown, overwrite=overwrite)
        copied.append(
            TestingArtifactCopy(
                paper_id=paper_id,
                source_pdf=source_pdf,
                source_markdown=source_markdown,
                output_dir=paper_output_dir,
                copied_pdf=copied_pdf,
                copied_markdown=copied_markdown,
            )
        )

    return TestingArtifactResult(copied=tuple(copied), skipped=tuple(skipped))


def iter_testing_pdf_paths(
    *,
    pdf_dir: Path,
    paper_ids: tuple[str, ...] = (),
    limit: int | None = None,
) -> tuple[Path, ...]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be >= 1 when provided")

    resolved_pdf_dir = pdf_dir.expanduser().resolve()
    selected_paper_ids = paper_ids or _paper_ids_from_pdf_dir(resolved_pdf_dir)
    if limit is not None:
        selected_paper_ids = selected_paper_ids[:limit]

    pdf_paths: list[Path] = []
    for paper_id in selected_paper_ids:
        pdf_path = resolved_pdf_dir / f"{paper_id}.pdf"
        if not pdf_path.exists():
            raise FileNotFoundError(f"No existe PDF para paper_id={paper_id}: {pdf_path}")
        if not pdf_path.is_file():
            raise ValueError(f"La ruta PDF no es un archivo: {pdf_path}")
        pdf_paths.append(pdf_path)
    return tuple(pdf_paths)


def copy_testing_source_pdf(pdf_path: Path, output_dir: Path, *, overwrite: bool = False) -> Path:
    resolved_pdf_path = pdf_path.expanduser().resolve()
    paper_output_dir = output_dir.expanduser().resolve() / resolved_pdf_path.stem
    paper_output_dir.mkdir(parents=True, exist_ok=True)
    target_pdf = paper_output_dir / "source.pdf"
    _copy_if_needed(resolved_pdf_path, target_pdf, overwrite=overwrite)
    return target_pdf


def copy_testing_markdown(markdown_dir: Path, output_dir: Path, paper_id: str, *, overwrite: bool = False) -> Path:
    source_markdown = markdown_dir.expanduser().resolve() / paper_id / "paper.md"
    if not source_markdown.exists():
        raise FileNotFoundError(f"No existe paper.md para paper_id={paper_id}: {source_markdown}")
    if not source_markdown.is_file():
        raise ValueError(f"La ruta Markdown no es un archivo: {source_markdown}")
    target_markdown = output_dir.expanduser().resolve() / paper_id / "paper.md"
    target_markdown.parent.mkdir(parents=True, exist_ok=True)
    _copy_if_needed(source_markdown, target_markdown, overwrite=overwrite)
    return target_markdown


def _paper_ids_from_pdf_dir(pdf_dir: Path) -> tuple[str, ...]:
    if not pdf_dir.exists():
        raise FileNotFoundError(f"No existe el directorio de PDFs: {pdf_dir}")
    if not pdf_dir.is_dir():
        raise ValueError(f"La ruta de PDFs no es un directorio: {pdf_dir}")
    return tuple(path.stem for path in sorted(pdf_dir.glob("*.pdf")) if path.is_file())


def _copy_if_needed(source: Path, target: Path, *, overwrite: bool) -> bool:
    if target.exists() and not overwrite:
        return False
    copy2(source, target)
    return True
