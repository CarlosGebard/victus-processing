from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from src.workspace import config as ctx
from src.workspace.artifacts import normalize_doi

LINK_METHOD: Literal["manual_intake"] = "manual_intake"


@dataclass(frozen=True)
class PaperPdfLink:
    metadata_id: str
    paper_id: str
    doi: str | None
    source_pdf_path: str
    artifact_pdf_path: str
    linked_at: str
    link_method: Literal["manual_intake"] = LINK_METHOD

    def as_dict(self) -> dict[str, str | None]:
        return {
            "metadata_id": self.metadata_id,
            "paper_id": self.paper_id,
            "doi": self.doi,
            "source_pdf_path": self.source_pdf_path,
            "artifact_pdf_path": self.artifact_pdf_path,
            "linked_at": self.linked_at,
            "link_method": self.link_method,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def paper_id_from_metadata_id(metadata_id: str) -> str:
    normalized = metadata_id.strip()
    if not normalized:
        raise ValueError("metadata_id no puede estar vacio")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"No existe metadata_file: {path}")
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            records.append(payload)
    return records


def find_metadata_record(metadata_file: Path, metadata_id: str) -> dict[str, Any]:
    for record in _iter_jsonl(metadata_file):
        if str(record.get("metadata_id") or "") == metadata_id:
            return record
    raise ValueError(f"No existe metadata_id en {ctx.display_path(metadata_file)}: {metadata_id}")


def load_metadata_by_doi(metadata_file: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for record in _iter_jsonl(metadata_file):
        doi = doi_from_metadata_record(record)
        if doi and doi not in records:
            records[doi] = record
    return records


def doi_from_metadata_record(record: dict[str, Any]) -> str | None:
    source_metadata = record.get("source_metadata")
    if not isinstance(source_metadata, dict):
        return None
    doi = str(source_metadata.get("doi") or "").strip()
    return normalize_doi(doi) if doi else None


def _display_or_absolute(path: Path) -> str:
    return ctx.display_path(path)


def link_manual_pdf(
    *,
    metadata_id: str,
    source_pdf: Path,
    metadata_file: Path = ctx.DATA_LAKE_DIR / "paper_metadata.jsonl",
    artifact_dir: Path = ctx.DATA_ARTIFACTS_PDFS_DIR,
    links_file: Path = ctx.DATA_LAKE_PAPER_PDF_LINKS_FILE,
    move: bool = True,
    overwrite: bool = False,
    linked_at: str | None = None,
) -> PaperPdfLink:
    source_pdf = source_pdf.expanduser().resolve()
    metadata_file = metadata_file.expanduser().resolve()
    artifact_dir = artifact_dir.expanduser().resolve()
    links_file = links_file.expanduser().resolve()

    if source_pdf.suffix.lower() != ".pdf":
        raise ValueError(f"El archivo no es PDF: {source_pdf}")
    if not source_pdf.exists():
        raise FileNotFoundError(f"No existe PDF fuente: {source_pdf}")

    metadata_record = find_metadata_record(metadata_file, metadata_id)
    paper_id = paper_id_from_metadata_id(metadata_id)
    artifact_pdf = artifact_dir / f"{paper_id}.pdf"

    if artifact_pdf.exists() and not overwrite:
        raise FileExistsError(f"Ya existe artifact PDF: {artifact_pdf}")

    artifact_dir.mkdir(parents=True, exist_ok=True)
    links_file.parent.mkdir(parents=True, exist_ok=True)

    if move:
        shutil.move(str(source_pdf), artifact_pdf)
    else:
        shutil.copy2(source_pdf, artifact_pdf)

    link = PaperPdfLink(
        metadata_id=metadata_id,
        paper_id=paper_id,
        doi=doi_from_metadata_record(metadata_record),
        source_pdf_path=_display_or_absolute(source_pdf),
        artifact_pdf_path=_display_or_absolute(artifact_pdf),
        linked_at=linked_at or utc_now_iso(),
    )
    with links_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(link.as_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    return link


def backfill_links_from_existing_artifacts(
    *,
    metadata_file: Path = ctx.DATA_LAKE_DIR / "paper_metadata.jsonl",
    legacy_links_file: Path = ctx.DATA_LAKE_DIR / "links.jsonl",
    artifact_dir: Path = ctx.DATA_ARTIFACTS_PDFS_DIR,
    links_file: Path = ctx.DATA_LAKE_PAPER_PDF_LINKS_FILE,
    overwrite: bool = False,
    linked_at: str | None = None,
) -> tuple[int, int]:
    metadata_file = metadata_file.expanduser().resolve()
    legacy_links_file = legacy_links_file.expanduser().resolve()
    artifact_dir = artifact_dir.expanduser().resolve()
    links_file = links_file.expanduser().resolve()

    metadata_by_doi = load_metadata_by_doi(metadata_file)
    legacy_by_paper_id: dict[str, dict[str, Any]] = {}
    if legacy_links_file.exists():
        for record in _iter_jsonl(legacy_links_file):
            paper_id = str(record.get("paper_id") or "").strip()
            if paper_id:
                legacy_by_paper_id[paper_id] = record

    if links_file.exists() and not overwrite:
        raise FileExistsError(f"Ya existe links_file: {links_file}")

    output_records: list[dict[str, str | None]] = []
    skipped = 0
    timestamp = linked_at or utc_now_iso()
    for artifact_pdf in sorted(artifact_dir.glob("*.pdf")):
        paper_id = artifact_pdf.stem
        legacy = legacy_by_paper_id.get(paper_id)
        doi = normalize_doi(str((legacy or {}).get("doi") or "")) if legacy else None
        metadata_record = metadata_by_doi.get(doi or "") if doi else None
        metadata_id = str((metadata_record or {}).get("metadata_id") or "").strip()
        if not metadata_id:
            skipped += 1
            continue
        output_records.append(
            PaperPdfLink(
                metadata_id=metadata_id,
                paper_id=paper_id,
                doi=doi,
                source_pdf_path=ctx.display_path(artifact_pdf),
                artifact_pdf_path=ctx.display_path(artifact_pdf),
                linked_at=timestamp,
            ).as_dict()
        )

    links_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in output_records]
    links_file.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(output_records), skipped
