from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import requests

from src.workspace import config as ctx
from src.workspace.artifacts import normalize_doi


INPUT_FILE = ctx.DATA_LAKE_DIR / "paper_metadata.jsonl"
OUTPUT_FILE = ctx.DATA_LAKE_DIR / "paper_metadata.s2_refreshed.jsonl"
MODEL_NAME = "gpt-4o"
SCHEMA_VERSION = "v1"
SOURCE_NAME = "semantic_scholar"
PAPER_FIELDS = "paperId,title,year,authors,citationCount,externalIds,openAccessPdf,abstract"


class PaperClient(Protocol):
    def fetch_by_doi(self, doi: str) -> dict[str, Any] | None:
        ...


@dataclass(frozen=True)
class RefreshSummary:
    read: int
    written: int
    refreshed: int
    missing_doi: int
    not_found: int
    failed: int


class SemanticScholarClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        retries: int = 5,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        request_interval: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.request_interval = request_interval
        self.last_request_ts = 0.0
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({"x-api-key": api_key})

    def fetch_by_doi(self, doi: str) -> dict[str, Any] | None:
        normalized = normalize_doi(doi)
        if not normalized:
            return None
        url = f"{self.base_url}/paper/DOI:{normalized}"
        for attempt in range(self.retries):
            self._rate_limit()
            response = self.session.get(url, params={"fields": PAPER_FIELDS}, timeout=60)
            if response.status_code == 200:
                payload = response.json()
                return payload if isinstance(payload, dict) and payload.get("paperId") else None
            if response.status_code == 404:
                return None
            if response.status_code in (429, 500, 502, 503, 504):
                delay = min(self.max_delay, self.base_delay * (2**attempt))
                time.sleep(delay + random.uniform(0, 1))
                continue
            response.raise_for_status()
        raise RuntimeError(f"Max retries exceeded for DOI: {normalized}")

    def _rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_request_ts
        if elapsed < self.request_interval:
            time.sleep(self.request_interval - elapsed)
        self.last_request_ts = time.monotonic()


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _as_str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = _as_str_or_none(item.get("name"))
        else:
            name = _as_str_or_none(item)
        if name:
            authors.append(name)
    return authors


def _doi_from_record(record: dict[str, Any]) -> str | None:
    source_metadata = record.get("source_metadata")
    if isinstance(source_metadata, dict):
        doi = normalize_doi(str(source_metadata.get("doi") or ""))
        if doi:
            return doi
    return normalize_doi(str(record.get("doi") or "")) or None


def _source_metadata_from_paper(paper: dict[str, Any], fallback_doi: str) -> dict[str, Any]:
    external_ids = paper.get("externalIds") if isinstance(paper.get("externalIds"), dict) else {}
    open_access_pdf = paper.get("openAccessPdf") if isinstance(paper.get("openAccessPdf"), dict) else {}
    doi = normalize_doi(str(external_ids.get("DOI") or fallback_doi)) or None
    return {
        "source": SOURCE_NAME,
        "source_paper_id": _as_str_or_none(paper.get("paperId")),
        "doi": doi,
        "arxiv": _as_str_or_none(external_ids.get("ArXiv")),
        "title": _as_str_or_none(paper.get("title")) or "",
        "year": paper.get("year") if isinstance(paper.get("year"), int) else None,
        "citation_count": paper.get("citationCount") if isinstance(paper.get("citationCount"), int) else None,
        "pdf_url": _as_str_or_none(open_access_pdf.get("url")),
        "authors": _authors(paper.get("authors")),
    }


def _ordered_source_metadata(source_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": _as_str_or_none(source_metadata.get("source")),
        "source_paper_id": _as_str_or_none(source_metadata.get("source_paper_id")),
        "doi": normalize_doi(str(source_metadata.get("doi") or "")) or None,
        "arxiv": _as_str_or_none(source_metadata.get("arxiv")),
        "title": _as_str_or_none(source_metadata.get("title")) or "",
        "year": source_metadata.get("year") if isinstance(source_metadata.get("year"), int) else None,
        "citation_count": (
            source_metadata.get("citation_count") if isinstance(source_metadata.get("citation_count"), int) else None
        ),
        "pdf_url": _as_str_or_none(source_metadata.get("pdf_url")),
        "authors": _authors(source_metadata.get("authors")),
    }


def refresh_record_from_paper(record: dict[str, Any], paper: dict[str, Any], *, doi: str, now: str) -> dict[str, Any]:
    paper_id = _as_str_or_none(paper.get("paperId"))
    if not paper_id:
        raise ValueError(f"Semantic Scholar response missing paperId for DOI: {doi}")

    return {
        "metadata_id": f"meta:s2:{paper_id}",
        "source_metadata": _source_metadata_from_paper(paper, doi),
        "schema_version": SCHEMA_VERSION,
        "discovery": record.get("discovery") if isinstance(record.get("discovery"), dict) else {},
        "domain_screening": {
            "decision": str((record.get("domain_screening") or {}).get("decision") or "uncertain"),
            "model": MODEL_NAME,
        },
        "created_at": _as_str_or_none(record.get("created_at")) or now,
        "updated_at": now,
    }


def _record_with_model(record: dict[str, Any], *, now: str) -> dict[str, Any]:
    screening = record.get("domain_screening") if isinstance(record.get("domain_screening"), dict) else {}
    source_metadata = record.get("source_metadata") if isinstance(record.get("source_metadata"), dict) else {}
    return {
        "metadata_id": str(record.get("metadata_id") or ""),
        "source_metadata": _ordered_source_metadata(source_metadata),
        "schema_version": SCHEMA_VERSION,
        "discovery": record.get("discovery") if isinstance(record.get("discovery"), dict) else {},
        "domain_screening": {
            "decision": str(screening.get("decision") or "uncertain"),
            "model": MODEL_NAME,
        },
        "created_at": _as_str_or_none(record.get("created_at")) or now,
        "updated_at": now,
    }


def refresh_paper_metadata(
    *,
    input_file: Path,
    output_file: Path,
    client: PaperClient,
    limit: int | None = None,
    on_missing: str = "keep",
) -> RefreshSummary:
    rows = read_jsonl(input_file)
    if limit is not None:
        rows = rows[: max(0, limit)]

    now = utc_now_iso()
    written_rows: list[dict[str, Any]] = []
    refreshed = 0
    missing_doi = 0
    not_found = 0
    failed = 0

    for record in rows:
        doi = _doi_from_record(record)
        if not doi:
            missing_doi += 1
            if on_missing == "keep":
                written_rows.append(_record_with_model(record, now=now))
            continue
        try:
            paper = client.fetch_by_doi(doi)
        except Exception:
            failed += 1
            if on_missing == "keep":
                written_rows.append(_record_with_model(record, now=now))
            continue
        if paper is None:
            not_found += 1
            if on_missing == "keep":
                written_rows.append(_record_with_model(record, now=now))
            continue
        written_rows.append(refresh_record_from_paper(record, paper, doi=doi, now=now))
        refreshed += 1

    output_file.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in written_rows)
    if written_rows:
        content += "\n"
    if not written_rows and output_file.exists() and output_file.stat().st_size > 0:
        raise RuntimeError(f"Refusing to overwrite non-empty output with 0 records: {output_file}")
    temp_file = output_file.with_suffix(output_file.suffix + ".tmp")
    temp_file.write_text(content, encoding="utf-8")
    temp_file.replace(output_file)
    return RefreshSummary(
        read=len(rows),
        written=len(written_rows),
        refreshed=refreshed,
        missing_doi=missing_doi,
        not_found=not_found,
        failed=failed,
    )


def build_client() -> SemanticScholarClient:
    config = ctx.get_config()
    api_cfg = config.get("api") or {}
    rate_limit_cfg = config.get("rate_limit") or {}
    api_key = ctx.get_env_or_config(
        "SEMANTIC_SCHOLAR_API_KEY",
        "api",
        "semantic_scholar_api_key",
        config=config,
    )
    return SemanticScholarClient(
        base_url=str(api_cfg.get("semantic_scholar_url") or "https://api.semanticscholar.org/graph/v1"),
        api_key=api_key,
        retries=int(rate_limit_cfg.get("retries", 5)),
        base_delay=float(rate_limit_cfg.get("base_delay", 1.0)),
        max_delay=float(rate_limit_cfg.get("max_delay", 30.0)),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh data/lake paper metadata from DOI lookups in Semantic Scholar.",
    )
    parser.add_argument("--input", type=Path, default=INPUT_FILE, help=f"Input JSONL (default: {INPUT_FILE})")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE, help=f"Output JSONL (default: {OUTPUT_FILE})")
    parser.add_argument("--limit", type=int, default=None, help="Maximum records to read, useful for smoke tests.")
    parser.add_argument(
        "--on-missing",
        choices=["keep", "skip"],
        default="keep",
        help="Keep or skip records without a DOI, failed lookup, or missing Semantic Scholar result.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = refresh_paper_metadata(
        input_file=args.input.expanduser().resolve(),
        output_file=args.output.expanduser().resolve(),
        client=build_client(),
        limit=args.limit,
        on_missing=args.on_missing,
    )
    print("Paper metadata Semantic Scholar refresh")
    print(f"- input:       {ctx.display_path(args.input)}")
    print(f"- output:      {ctx.display_path(args.output)}")
    print(f"- read:        {summary.read}")
    print(f"- written:     {summary.written}")
    print(f"- refreshed:   {summary.refreshed}")
    print(f"- missing_doi: {summary.missing_doi}")
    print(f"- not_found:   {summary.not_found}")
    print(f"- failed:      {summary.failed}")


if __name__ == "__main__":
    main()
