from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def append_processing_status(
    status_file: Path,
    *,
    paper_id: str,
    status: str,
    error: str | None = None,
    error_description: str | None = None,
) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "paper_id": paper_id,
        "status": status,
        "error": error,
        "error_description": error_description,
        "updated_at": utc_now_iso(),
    }
    index = load_processing_status_index(status_file)
    index[paper_id] = record
    write_processing_status_index(status_file, index)


def load_processing_status_index(status_file: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not status_file.exists():
        return index
    for line in status_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        paper_id = str(record.get("paper_id") or "")
        status = str(record.get("status") or "")
        if not paper_id or status not in {"done", "failed"}:
            continue
        index[paper_id] = {
            "paper_id": paper_id,
            "status": status,
            "error": record.get("error"),
            "error_description": record.get("error_description"),
            "updated_at": record.get("updated_at") or utc_now_iso(),
        }
    return index


def write_processing_status_index(status_file: Path, index: dict[str, dict[str, Any]]) -> None:
    status_file.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(index.values(), key=lambda item: str(item.get("paper_id") or ""))
    content = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    status_file.write_text(content + ("\n" if content else ""), encoding="utf-8")
