from __future__ import annotations

import argparse
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from src.application.metadata_to_pdf.common import (
    append_jsonl,
    is_pdf_bytes,
    iter_jsonl,
    normalize_doi,
    utc_now_iso,
)


DEFAULT_INPUT_FILE = Path("data/lake/papers_missing_pdfs.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/artifacts/intake/metadata-pdfs")
DEFAULT_ARTIFACT_DIR = Path("data/artifacts/pdfs")
DEFAULT_LINKS_FILE = Path("data/lake/paper_pdf_links.jsonl")
DEFAULT_OA_STATUS_FILE = Path("data/lake/unpaywall_pdf_status.jsonl")
UNPAYWALL_API = "https://api.unpaywall.org/v2/{doi}"
EUROPE_PMC_SEARCH_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPE_PMC_ARTICLE_URL = "https://europepmc.org/article/{source}/{external_id}"
EUROPE_PMC_PDF_URL = "https://europepmc.org/articles/{pmcid}?pdf=render"
CORE_SEARCH_API = "https://api.core.ac.uk/v3/search/works"


@dataclass(frozen=True)
class ProviderResult:
    source: str
    status: str
    pdf_url: str | None = None
    landing_url: str | None = None
    external_id: str | None = None
    is_oa: bool | None = None
    oa_status: str | None = None
    error: str | None = None


def _completed_candidate_keys(status_file: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for record in iter_jsonl(status_file):
        metadata_id = str(record.get("metadata_id") or "").strip()
        paper_id = str(record.get("paper_id") or "").strip()
        if metadata_id or paper_id:
            keys.add((metadata_id, paper_id))
    return keys


def _candidate_keys_with_pdf_url(status_file: Path) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for record in iter_jsonl(status_file):
        metadata_id = str(record.get("metadata_id") or "").strip()
        paper_id = str(record.get("paper_id") or "").strip()
        pdf_url = str(record.get("pdf_url") or "").strip()
        if (metadata_id or paper_id) and pdf_url:
            keys.add((metadata_id, paper_id))
    return keys


def _get_json(url: str, *, timeout: float, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request_headers = {"Accept": "application/json", **(headers or {})}
    response = requests.get(url, timeout=timeout, headers=request_headers)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("JSON response is not an object")
    return payload


def _download_pdf(url: str, *, timeout: float, headers: dict[str, str] | None = None) -> bytes:
    request_headers = {"Accept": "application/pdf,*/*", **(headers or {})}
    response = requests.get(url, timeout=timeout, headers=request_headers)
    response.raise_for_status()
    payload = response.content
    if not is_pdf_bytes(payload):
        content_type = response.headers.get("content-type", "")
        raise ValueError(f"downloaded payload is not a PDF; content-type={content_type}")
    return payload


def _best_unpaywall_pdf_url(payload: dict[str, Any]) -> str | None:
    best = payload.get("best_oa_location")
    if isinstance(best, dict):
        url = str(best.get("url_for_pdf") or "").strip()
        if url:
            return url

    locations = payload.get("oa_locations")
    if isinstance(locations, list):
        for location in locations:
            if not isinstance(location, dict):
                continue
            url = str(location.get("url_for_pdf") or "").strip()
            if url:
                return url
    return None


def _unpaywall_result(doi: str, *, email: str, timeout: float) -> ProviderResult:
    url = f"{UNPAYWALL_API.format(doi=doi)}?email={email}"
    payload = _get_json(url, timeout=timeout)
    is_oa = bool(payload.get("is_oa"))
    best = payload.get("best_oa_location")
    landing_url = str(best.get("url") or "").strip() if isinstance(best, dict) else ""
    return ProviderResult(
        source="unpaywall",
        status="pdf_found" if _best_unpaywall_pdf_url(payload) else ("url_found" if landing_url else "not_found"),
        pdf_url=_best_unpaywall_pdf_url(payload),
        landing_url=landing_url or f"https://doi.org/{doi}",
        is_oa=is_oa,
        oa_status=str(payload.get("oa_status") or "") or None,
    )


def _europe_pmc_result(doi: str, *, timeout: float) -> ProviderResult:
    query = f'DOI:"{doi}"'
    url = f"{EUROPE_PMC_SEARCH_API}?{urlencode({'query': query, 'format': 'json', 'pageSize': 5})}"
    payload = _get_json(url, timeout=timeout)
    result_list = payload.get("resultList")
    results = result_list.get("result") if isinstance(result_list, dict) else []
    if not isinstance(results, list):
        results = []
    match = next(
        (
            item
            for item in results
            if isinstance(item, dict) and normalize_doi(item.get("doi")) == doi
        ),
        None,
    )
    if match is None:
        return ProviderResult(source="europe_pmc", status="not_found")
    pmcid = str(match.get("pmcid") or "").strip() or None
    source = str(match.get("source") or "MED").strip()
    external_id = str(match.get("id") or pmcid or "").strip() or None
    has_pdf = str(match.get("hasPDF") or "").upper() == "Y"
    pdf_url = EUROPE_PMC_PDF_URL.format(pmcid=pmcid) if pmcid and has_pdf else None
    landing_url = (
        EUROPE_PMC_ARTICLE_URL.format(source=source, external_id=external_id)
        if external_id
        else f"https://doi.org/{doi}"
    )
    return ProviderResult(
        source="europe_pmc",
        status="pdf_found" if pdf_url else "url_found",
        pdf_url=pdf_url,
        landing_url=landing_url,
        external_id=pmcid or external_id,
        is_oa=str(match.get("isOpenAccess") or "").upper() == "Y",
    )


def _core_result(doi: str, *, api_key: str, timeout: float) -> ProviderResult:
    query = f'doi:"{doi}"'
    url = f"{CORE_SEARCH_API}?{urlencode({'q': query, 'limit': 10})}"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = _get_json(url, timeout=timeout, headers=headers)
    results = payload.get("results")
    if not isinstance(results, list):
        results = []
    match = next((item for item in results if isinstance(item, dict) and _core_has_doi(item, doi)), None)
    if match is None:
        return ProviderResult(source="core", status="not_found")
    core_id = str(match.get("id") or "").strip() or None
    pdf_url = str(match.get("downloadUrl") or "").strip() or None
    source_urls = match.get("sourceFulltextUrls")
    landing_url = (
        next((str(value).strip() for value in source_urls if str(value).strip()), None)
        if isinstance(source_urls, list)
        else None
    )
    if not landing_url and core_id:
        landing_url = f"https://core.ac.uk/works/{core_id}"
    return ProviderResult(
        source="core",
        status="pdf_found" if pdf_url else ("url_found" if landing_url else "not_found"),
        pdf_url=pdf_url,
        landing_url=landing_url,
        external_id=core_id,
        is_oa=True,
    )


def _core_has_doi(record: dict[str, Any], doi: str) -> bool:
    if normalize_doi(record.get("doi")) == doi:
        return True
    identifiers = record.get("identifiers")
    return isinstance(identifiers, list) and doi in {normalize_doi(str(value)) for value in identifiers}


def _write_pdf(
    *,
    pdf_bytes: bytes,
    paper_id: str,
    staging_dir: Path,
    artifact_dir: Path,
    promote: bool,
    overwrite: bool,
) -> tuple[Path, Path | None]:
    staging_dir.mkdir(parents=True, exist_ok=True)
    staging_path = staging_dir / f"{paper_id}.pdf"
    if staging_path.exists() and not overwrite:
        raise FileExistsError(f"staging PDF already exists: {staging_path}")
    staging_path.write_bytes(pdf_bytes)

    artifact_path: Path | None = None
    if promote:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{paper_id}.pdf"
        if artifact_path.exists() and not overwrite:
            raise FileExistsError(f"artifact PDF already exists: {artifact_path}")
        shutil.copy2(staging_path, artifact_path)
    return staging_path, artifact_path


def _link_record(
    *,
    candidate: dict[str, Any],
    artifact_path: Path,
    source_url: str,
    provider: ProviderResult,
    now: str,
) -> dict[str, Any]:
    return {
        "metadata_id": candidate["metadata_id"],
        "paper_id": candidate["paper_id"],
        "doi": normalize_doi(candidate.get("doi")),
        "source_pdf_path": source_url,
        "artifact_pdf_path": str(artifact_path),
        "linked_at": now,
        "link_method": "open_access_fetch",
        "source": provider.source,
        "source_external_id": provider.external_id,
        "is_oa": provider.is_oa,
        "oa_status": provider.oa_status,
    }


def resolve_missing_pdfs(
    *,
    input_file: Path = DEFAULT_INPUT_FILE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    links_file: Path = DEFAULT_LINKS_FILE,
    oa_status_file: Path = DEFAULT_OA_STATUS_FILE,
    email: str | None,
    core_api_key: str | None = None,
    limit: int | None = None,
    timeout: float = 30.0,
    promote: bool = True,
    overwrite: bool = False,
    retry_checked: bool = False,
    retry_missing_pdf_url: bool = False,
) -> dict[str, int]:
    counts = {
        "checked": 0,
        "oa": 0,
        "not_oa": 0,
        "downloaded": 0,
        "url_only": 0,
        "not_found": 0,
        "failed": 0,
        "skipped": 0,
    }
    if retry_checked:
        completed_keys: set[tuple[str, str]] = set()
    elif retry_missing_pdf_url:
        completed_keys = _candidate_keys_with_pdf_url(oa_status_file)
    else:
        completed_keys = _completed_candidate_keys(oa_status_file)

    for candidate in iter_jsonl(input_file):
        if limit is not None and counts["checked"] >= limit:
            break

        paper_id = str(candidate.get("paper_id") or "").strip()
        metadata_id = str(candidate.get("metadata_id") or "").strip()
        if (metadata_id, paper_id) in completed_keys:
            counts["skipped"] += 1
            continue

        counts["checked"] += 1
        now = utc_now_iso()
        doi = normalize_doi(candidate.get("doi"))
        base_status: dict[str, Any] = {
            "metadata_id": metadata_id,
            "paper_id": paper_id,
            "doi": doi,
            "checked_at": now,
            "source": None,
            "resolution_status": "pending",
            "is_oa": None,
            "oa_status": None,
            "pdf_url": None,
            "landing_url": None,
            "downloaded": False,
            "artifact_pdf_path": None,
            "error": None,
            "attempts": [],
        }

        if not doi or not paper_id or not metadata_id:
            counts["skipped"] += 1
            base_status["error"] = "missing doi, paper_id, or metadata_id"
            append_jsonl(oa_status_file, base_status)
            continue

        fallback: ProviderResult | None = None
        selected: ProviderResult | None = None
        download_error: str | None = None
        metadata_url = str(candidate.get("metadata_pdf_url") or "").strip()
        resolvers: list[tuple[str, Any]] = []
        if metadata_url:
            resolvers.append(
                ("metadata", lambda: ProviderResult("metadata", "pdf_found", metadata_url, metadata_url))
            )
        if email:
            resolvers.append(("unpaywall", lambda: _unpaywall_result(doi, email=email, timeout=timeout)))
        resolvers.append(("europe_pmc", lambda: _europe_pmc_result(doi, timeout=timeout)))
        if core_api_key:
            resolvers.append(("core", lambda: _core_result(doi, api_key=core_api_key, timeout=timeout)))

        for source, resolve in resolvers:
            try:
                result = resolve()
            except Exception as exc:
                result = ProviderResult(source=source, status="error", error=str(exc))
            base_status["attempts"].append(asdict(result))
            if result.landing_url or result.pdf_url:
                if fallback is None or (fallback.status == "not_found" and result.status != "not_found"):
                    fallback = result
            if not result.pdf_url:
                continue
            try:
                download_headers = (
                    {"Authorization": f"Bearer {core_api_key}"}
                    if result.source == "core" and core_api_key
                    else None
                )
                if download_headers:
                    pdf_bytes = _download_pdf(result.pdf_url, timeout=timeout, headers=download_headers)
                else:
                    pdf_bytes = _download_pdf(result.pdf_url, timeout=timeout)
                staging_path, artifact_path = _write_pdf(
                    pdf_bytes=pdf_bytes,
                    paper_id=paper_id,
                    staging_dir=output_dir,
                    artifact_dir=artifact_dir,
                    promote=promote,
                    overwrite=overwrite,
                )
                selected = result
                base_status.update(
                    {
                        "resolution_status": "downloaded",
                        "downloaded": True,
                        "staging_pdf_path": str(staging_path),
                        "artifact_pdf_path": str(artifact_path) if artifact_path else None,
                    }
                )
                if artifact_path is not None:
                    append_jsonl(
                        links_file,
                        _link_record(
                            candidate=candidate,
                            artifact_path=artifact_path,
                            source_url=result.pdf_url,
                            provider=result,
                            now=now,
                        ),
                    )
                counts["downloaded"] += 1
                break
            except Exception as exc:
                download_error = str(exc)
                base_status["attempts"][-1]["download_error"] = download_error

        selected = selected or fallback
        if selected is not None:
            base_status.update(
                {
                    "source": selected.source,
                    "is_oa": selected.is_oa,
                    "oa_status": selected.oa_status,
                    "pdf_url": selected.pdf_url,
                    "landing_url": selected.landing_url,
                }
            )
        if not base_status["downloaded"]:
            if selected is not None:
                base_status["resolution_status"] = "url_only"
                counts["url_only"] += 1
            elif any(attempt["status"] == "error" for attempt in base_status["attempts"]):
                base_status["resolution_status"] = "failed"
                counts["failed"] += 1
            else:
                base_status["resolution_status"] = "not_found"
                counts["not_found"] += 1
            base_status["error"] = download_error
        if selected and selected.is_oa is True:
            counts["oa"] += 1
        elif selected and selected.is_oa is False:
            counts["not_oa"] += 1
        append_jsonl(oa_status_file, base_status)

    return counts


# Backward-compatible public name for existing automation.
fetch_unpaywall_pdfs = resolve_missing_pdfs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Resolve missing PDFs through metadata, Unpaywall, Europe PMC, and CORE."
    )
    parser.add_argument("--input-file", type=Path, default=DEFAULT_INPUT_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--links-file", type=Path, default=DEFAULT_LINKS_FILE)
    parser.add_argument("--oa-status-file", type=Path, default=DEFAULT_OA_STATUS_FILE)
    parser.add_argument("--email", default=os.environ.get("UNPAYWALL_EMAIL"))
    parser.add_argument("--core-api-key", default=os.environ.get("CORE_API_KEY"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--staging-only", action="store_true", help="Do not copy PDFs to data/artifacts/pdfs.")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--retry-checked",
        action="store_true",
        help="Do not skip candidates already present in the OA status JSONL.",
    )
    parser.add_argument(
        "--retry-missing-pdf-url",
        action="store_true",
        help="Recheck candidates unless the OA status JSONL already has a pdf_url for them.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be >= 1")
    if args.retry_checked and args.retry_missing_pdf_url:
        raise SystemExit("--retry-checked and --retry-missing-pdf-url cannot be used together")
    if not args.email and not args.core_api_key:
        print("[WARN] UNPAYWALL_EMAIL and CORE_API_KEY are unset; using metadata URLs and Europe PMC only.")

    counts = resolve_missing_pdfs(
        input_file=args.input_file,
        output_dir=args.output_dir,
        artifact_dir=args.artifact_dir,
        links_file=args.links_file,
        oa_status_file=args.oa_status_file,
        email=args.email,
        core_api_key=args.core_api_key,
        limit=args.limit,
        timeout=args.timeout,
        promote=not args.staging_only,
        overwrite=args.overwrite,
        retry_checked=args.retry_checked,
        retry_missing_pdf_url=args.retry_missing_pdf_url,
    )
    print("Metadata-to-PDF resolution summary")
    for key in ("checked", "oa", "not_oa", "downloaded", "url_only", "not_found", "failed", "skipped"):
        print(f"- {key}: {counts[key]}")
    print(f"OA status output: {args.oa_status_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
