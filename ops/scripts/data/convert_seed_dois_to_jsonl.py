from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.workspace import config as ctx
from src.workspace.artifacts import normalize_doi


SEED_FILES = (
    ctx.DATA_INPUT_SEEDS_DIR / "seed_dois.jsonl",
    ctx.DATA_INPUT_GENERATED_SEED_DOIS_DIR / "candidates_seed_dois.jsonl",
)
EXPLORED_SEED_FILE = ctx.DATA_INPUT_SEEDS_DIR / "explored_seed_dois.jsonl"


def _metadata_index() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in ctx.METADATA_DIR.rglob("*.metadata.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        section = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else payload
        doi = normalize_doi(str(section.get("doi") or ""))
        if doi:
            records[doi] = section
    return records


def _row_from_line(line: str, metadata: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        payload = None

    doi = normalize_doi(str(payload.get("doi") if isinstance(payload, dict) else line))
    if not doi:
        return None

    meta = metadata.get(doi, {})
    return {
        "doi": doi,
        "title": str((payload or {}).get("title") or meta.get("title") or ""),
        "citation_count": int((payload or {}).get("citation_count") or meta.get("citationCount") or 0),
    }


def convert_seed_file(path: Path, metadata: dict[str, dict[str, Any]]) -> int:
    if not path.exists():
        return 0
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        row = _row_from_line(line, metadata)
        if row is None or row["doi"] in seen:
            continue
        rows.append(row)
        seen.add(row["doi"])

    content = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    if rows:
        content += "\n"
    path.write_text(content, encoding="utf-8")
    return len(rows)


def convert_seed_dois_to_jsonl() -> dict[str, int]:
    metadata = _metadata_index()
    results = {str(path): convert_seed_file(path, metadata) for path in SEED_FILES}
    results[str(EXPLORED_SEED_FILE)] = convert_seed_file(EXPLORED_SEED_FILE, metadata)
    return results


if __name__ == "__main__":
    for path, count in convert_seed_dois_to_jsonl().items():
        print(f"{path}: {count}")
