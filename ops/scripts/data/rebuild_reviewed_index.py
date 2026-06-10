from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.workspace import config as ctx
from src.workspace.artifacts import normalize_doi


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _record_from_metadata(path: Path) -> dict[str, Any] | None:
    payload = _load_json(path)
    if payload is None:
        return None
    section = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else payload
    doi = normalize_doi(str(section.get("doi") or ""))
    if not doi:
        return None
    record = {
        "doi": doi,
        "status": "kept",
        "dataset": str(section.get("dataset") or "dataset_nutrition"),
        "created_at": str(section.get("created_at") or utc_now_iso()),
    }
    paper_id = str(section.get("paperId") or section.get("document_id") or "").strip()
    if paper_id:
        record["paperId"] = paper_id
    return record


def _dataset_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("dataset")
        or payload.get("mode")
        or (payload.get("selection") or {}).get("mode")
        or "dataset_nutrition"
    )
    return "dataset_nutrition"


def _record_from_discarded(payload: dict[str, Any]) -> dict[str, Any] | None:
    doi = normalize_doi(str(payload.get("doi") or ""))
    if not doi:
        return None
    record = {
        "doi": doi,
        "status": "discarded",
        "dataset": _dataset_from_payload(payload),
        "created_at": str(payload.get("created_at") or utc_now_iso()),
    }
    paper_id = str(payload.get("paperId") or "").strip()
    if paper_id:
        record["paperId"] = paper_id
    return record


def _iter_discarded_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            record = _record_from_discarded(payload)
            if record is not None:
                records.append(record)
    return records


def _iter_discarded_json_records(directory: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(directory.rglob("*.json")):
        if path.name == "reviewed.jsonl":
            continue
        payload = _load_json(path)
        if payload is None:
            continue
        record = _record_from_discarded(payload)
        if record is not None:
            records.append(record)
    return records


def rebuild_reviewed_index() -> Path:
    active_dir = ctx.METADATA_DIR
    discarded_dir = ctx.PATHS["discarded_dir"]
    discarded_jsonl = discarded_dir / "discarded.jsonl"
    index_path = active_dir.parent / "reviewed.jsonl"

    records: dict[str, dict[str, Any]] = {}
    for metadata_path in sorted(active_dir.rglob("*.metadata.json")):
        record = _record_from_metadata(metadata_path)
        if record is not None:
            records[record["doi"]] = record

    for record in _iter_discarded_json_records(discarded_dir):
        records[record["doi"]] = record

    for record in _iter_discarded_jsonl_records(discarded_jsonl):
        records[record["doi"]] = record

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as handle:
        for record in sorted(records.values(), key=lambda item: str(item.get("doi") or "")):
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return index_path


if __name__ == "__main__":
    path = rebuild_reviewed_index()
    print(path)
