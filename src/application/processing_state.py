from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Protocol

from src.workspace import config as ctx
from src.workspace import runs


class ProcessingStateStore(Protocol):
    def upsert_paper_processing_state(self, record: dict[str, Any]) -> None:
        ...

    def upsert_paper_processing_states(self, records: list[dict[str, Any]]) -> None:
        ...

    def fetch_processing_facts(self) -> dict[str, dict[str, Any]]:
        ...


CSV_FIELDS = (
    "paper_id",
    "overall_status",
    "current_stage",
    "last_successful_stage",
    "next_stage",
    "pipeline_version",
    "config_hash",
    "is_processable",
    "is_complete",
    "is_ready_for_export",
    "is_exported",
    "blocked_reason",
    "last_error_code",
    "last_error_message",
    "has_pdf",
    "has_markdown",
    "has_structured_paper",
    "has_structured_blocks",
    "has_evidence_blocks",
    "has_paper_classification",
    "has_experiment_map",
    "has_canonical_evidence",
    "paper_family",
    "pdf_path",
    "markdown_path",
)


def refresh_processing_state(
    *,
    data_dir: Path = ctx.DATA_DIR,
    store: ProcessingStateStore | None = None,
    csv_output: Path | None = None,
    pipeline_version: str = "v1",
    config_hash: str | None = None,
) -> list[dict[str, Any]]:
    records = build_processing_state_records(
        data_dir=data_dir,
        postgres_facts=store.fetch_processing_facts() if store is not None else {},
        pipeline_version=pipeline_version,
        config_hash=config_hash,
    )
    if csv_output is not None:
        write_processing_state_csv(csv_output, records)
    if store is not None:
        payloads = [_store_record(record) for record in records]
        try:
            store.upsert_paper_processing_states(payloads)
        except Exception as exc:
            for payload in payloads:
                runs.append_postgres_outbox(
                    record_type="paper_processing_state",
                    record_id=str(payload["paper_id"]),
                    idempotency_key=f"paper_processing_state:{payload['paper_id']}",
                    payload_ref=f"paper_processing_state#{payload['paper_id']}",
                    payload=payload,
                    last_error=str(exc),
                )
    return records


def build_processing_state_records(
    *,
    data_dir: Path = ctx.DATA_DIR,
    postgres_facts: dict[str, dict[str, Any]] | None = None,
    pipeline_version: str = "v1",
    config_hash: str | None = None,
) -> list[dict[str, Any]]:
    root = data_dir.expanduser().resolve()
    pdf_dir = root / "artifacts/pdfs"
    markdown_dir = root / "artifacts/markdown"
    facts_by_paper = postgres_facts or {}

    paper_ids = set[str]()
    paper_ids.update(path.stem for path in pdf_dir.glob("*.pdf"))
    paper_ids.update(path.stem for path in markdown_dir.glob("*.md"))
    paper_ids.update(facts_by_paper)

    records = []
    for paper_id in sorted(paper_ids):
        paths = _paths_for_paper(
            paper_id,
            pdf_dir=pdf_dir,
            markdown_dir=markdown_dir,
        )
        physical_facts = {f"has_{name}": path.exists() for name, path in paths.items()}
        postgres_fact = facts_by_paper.get(paper_id, {})
        facts = {
            **physical_facts,
            "has_structured_paper": bool(postgres_fact.get("has_structured_paper")),
            "has_structured_blocks": bool(postgres_fact.get("has_structured_blocks")),
            "has_evidence_blocks": bool(postgres_fact.get("has_evidence_blocks")),
            "has_paper_classification": bool(postgres_fact.get("has_paper_classification")),
            "has_experiment_map": bool(postgres_fact.get("has_experiment_map")),
            "has_canonical_evidence": bool(postgres_fact.get("has_canonical_evidence")),
            "paper_family": postgres_fact.get("paper_family"),
        }
        status = _derive_status(facts)
        record = {
            "paper_id": paper_id,
            **status,
            "pipeline_version": pipeline_version,
            "config_hash": config_hash,
            "is_exported": False,
            **facts,
            **{f"{name}_path": ctx.display_path(path) if path.exists() else "" for name, path in paths.items()},
        }
        records.append(record)
    return records


def write_processing_state_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def _paths_for_paper(
    paper_id: str,
    *,
    pdf_dir: Path,
    markdown_dir: Path,
) -> dict[str, Path]:
    return {
        "pdf": pdf_dir / f"{paper_id}.pdf",
        "markdown": markdown_dir / f"{paper_id}.md",
    }


def _derive_status(facts: dict[str, Any]) -> dict[str, Any]:
    if not facts["has_pdf"] and not facts["has_markdown"]:
        return _status(
            overall_status="blocked",
            current_stage="input.discovery",
            next_stage=None,
            last_successful_stage=None,
            is_processable=False,
            blocked_reason="missing_pdf_and_markdown",
        )
    if not facts["has_markdown"]:
        return _status("pending", "pdf.markdown", "pdf.markdown", "pdf.available")
    if not facts["has_structured_paper"]:
        return _status("pending", "pdf.process", "pdf.process", "pdf.markdown")
    if not facts["has_paper_classification"]:
        return _status("pending", "classification.classify", "classification.classify", "pdf.process")
    if facts.get("paper_family") != "primary_research":
        return _status(
            overall_status="succeeded",
            current_stage="classification.classify",
            next_stage=None,
            last_successful_stage="classification.classify",
            is_complete=True,
            is_ready_for_export=True,
        )
    if not facts["has_evidence_blocks"]:
        return _status("pending", "evidence.trim", "evidence.trim", "classification.classify")
    if not facts["has_experiment_map"]:
        return _status("pending", "evidence.map", "evidence.map", "classification.classify")
    if not facts["has_canonical_evidence"]:
        return _status("pending", "evidence.extract", "evidence.extract", "evidence.map")
    return _status(
        overall_status="succeeded",
        current_stage="export.ready",
        next_stage=None,
        last_successful_stage="evidence.extract",
        is_complete=True,
        is_ready_for_export=True,
    )


def _status(
    overall_status: str,
    current_stage: str,
    next_stage: str | None,
    last_successful_stage: str | None,
    *,
    is_processable: bool = True,
    is_complete: bool = False,
    is_ready_for_export: bool = False,
    blocked_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "overall_status": overall_status,
        "current_stage": current_stage,
        "last_successful_stage": last_successful_stage,
        "next_stage": next_stage,
        "is_processable": is_processable,
        "is_complete": is_complete,
        "is_ready_for_export": is_ready_for_export,
        "blocked_reason": blocked_reason,
        "last_error_code": blocked_reason,
        "last_error_message": blocked_reason,
    }


def _store_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record.get(key) for key in (
        "paper_id",
        "overall_status",
        "current_stage",
        "last_successful_stage",
        "next_stage",
        "active_pipeline_run_id",
        "pipeline_version",
        "config_hash",
        "is_processable",
        "is_complete",
        "is_ready_for_export",
        "is_exported",
        "blocked_reason",
        "last_error_code",
        "last_error_message",
        "has_pdf",
        "has_markdown",
        "has_structured_paper",
        "has_structured_blocks",
        "has_evidence_blocks",
        "has_paper_classification",
        "has_experiment_map",
        "has_canonical_evidence",
        "paper_family",
    )}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
