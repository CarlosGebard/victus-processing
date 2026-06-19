from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_doi(doi: str | None) -> str | None:
    if doi is None:
        return None
    value = str(doi).strip()
    if not value:
        return None
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^doi:\s*", "", value, flags=re.IGNORECASE)
    normalized = value.strip().lower()
    return normalized or None


def paper_id_from_metadata_id(metadata_id: str) -> str:
    normalized = metadata_id.strip()
    if not normalized:
        raise ValueError("metadata_id cannot be empty")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            yield payload


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> int:
    rows = list(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(rows)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def source_metadata(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("source_metadata")
    return value if isinstance(value, dict) else {}


def doi_from_metadata_record(record: dict[str, Any]) -> str | None:
    metadata = source_metadata(record)
    return normalize_doi(metadata.get("doi") or record.get("doi"))


def pdf_url_from_metadata_record(record: dict[str, Any]) -> str | None:
    metadata = source_metadata(record)
    value = str(metadata.get("pdf_url") or "").strip()
    return value or None


def title_from_metadata_record(record: dict[str, Any]) -> str | None:
    metadata = source_metadata(record)
    value = str(metadata.get("title") or record.get("title") or "").strip()
    return value or None


def should_keep_metadata_record(record: dict[str, Any]) -> bool:
    screening = record.get("domain_screening")
    if not isinstance(screening, dict):
        return True
    return str(screening.get("decision") or "").strip().lower() == "keep"


def linked_metadata_ids_and_dois(links_file: Path) -> tuple[set[str], set[str]]:
    metadata_ids: set[str] = set()
    dois: set[str] = set()
    for record in iter_jsonl(links_file):
        metadata_id = str(record.get("metadata_id") or "").strip()
        if metadata_id:
            metadata_ids.add(metadata_id)
        doi = normalize_doi(record.get("doi"))
        if doi:
            dois.add(doi)
    return metadata_ids, dois


def is_pdf_bytes(payload: bytes) -> bool:
    return payload[:5] == b"%PDF-"
