from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
from typing import Any

import requests

from src.application.metadata_to_pdf.common import (
    append_jsonl,
    is_pdf_bytes,
    iter_jsonl,
    normalize_doi,
    utc_now_iso,
)


DEFAULT_INPUT_FILE = Path("data/lake/papers_missing_pdfs.jsonl")
DEFAULT_OUTPUT_DIR = Path("data/artifacts/intake/unpaywall-pdfs")
DEFAULT_ARTIFACT_DIR = Path("data/artifacts/pdfs")
DEFAULT_LINKS_FILE = Path("data/lake/paper_pdf_links.jsonl")
DEFAULT_OA_STATUS_FILE = Path("data/lake/unpaywall_pdf_status.jsonl")
UNPAYWALL_API = "https://api.unpaywall.org/v2/{doi}"


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


def _get_json(url: str, *, timeout: float) -> dict[str, Any]:
    response = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("JSON response is not an object")
    return payload


def _download_pdf(url: str, *, timeout: float) -> bytes:
    response = requests.get(url, timeout=timeout, headers={"Accept": "application/pdf,*/*"})
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
    unpaywall_is_oa: bool,
    unpaywall_oa_status: str | None,
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
        "source": "unpaywall",
        "unpaywall_is_oa": unpaywall_is_oa,
        "unpaywall_oa_status": unpaywall_oa_status,
    }


def fetch_unpaywall_pdfs(
    *,
    input_file: Path = DEFAULT_INPUT_FILE,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    links_file: Path = DEFAULT_LINKS_FILE,
    oa_status_file: Path = DEFAULT_OA_STATUS_FILE,
    email: str,
    limit: int | None = None,
    timeout: float = 30.0,
    promote: bool = True,
    overwrite: bool = False,
    retry_checked: bool = False,
    retry_missing_pdf_url: bool = False,
) -> dict[str, int]:
    counts = {"checked": 0, "oa": 0, "not_oa": 0, "downloaded": 0, "failed": 0, "skipped": 0}
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
            "source": "unpaywall",
            "is_oa": None,
            "oa_status": None,
            "pdf_url": None,
            "downloaded": False,
            "artifact_pdf_path": None,
            "error": None,
        }

        if not doi or not paper_id or not metadata_id:
            counts["skipped"] += 1
            base_status["error"] = "missing doi, paper_id, or metadata_id"
            append_jsonl(oa_status_file, base_status)
            continue

        try:
            unpaywall_url = UNPAYWALL_API.format(doi=doi)
            payload = _get_json(f"{unpaywall_url}?email={email}", timeout=timeout)
            is_oa = bool(payload.get("is_oa"))
            oa_status = str(payload.get("oa_status") or "") or None
            pdf_url = _best_unpaywall_pdf_url(payload)
            base_status.update({"is_oa": is_oa, "oa_status": oa_status, "pdf_url": pdf_url})

            if is_oa:
                counts["oa"] += 1
            else:
                counts["not_oa"] += 1

            if not is_oa or not pdf_url:
                append_jsonl(oa_status_file, base_status)
                continue

            pdf_bytes = _download_pdf(pdf_url, timeout=timeout)
            staging_path, artifact_path = _write_pdf(
                pdf_bytes=pdf_bytes,
                paper_id=paper_id,
                staging_dir=output_dir,
                artifact_dir=artifact_dir,
                promote=promote,
                overwrite=overwrite,
            )

            base_status.update(
                {
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
                        source_url=pdf_url,
                        unpaywall_is_oa=is_oa,
                        unpaywall_oa_status=oa_status,
                        now=now,
                    ),
                )
            counts["downloaded"] += 1
            append_jsonl(oa_status_file, base_status)
        except Exception as exc:
            counts["failed"] += 1
            base_status["error"] = str(exc)
            append_jsonl(oa_status_file, base_status)

    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check missing PDF candidates in Unpaywall and download available OA PDFs."
    )
    parser.add_argument("--input-file", type=Path, default=DEFAULT_INPUT_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--links-file", type=Path, default=DEFAULT_LINKS_FILE)
    parser.add_argument("--oa-status-file", type=Path, default=DEFAULT_OA_STATUS_FILE)
    parser.add_argument("--email", default=os.environ.get("UNPAYWALL_EMAIL"))
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
    if not args.email:
        raise SystemExit("--email or UNPAYWALL_EMAIL is required by the Unpaywall API")

    counts = fetch_unpaywall_pdfs(
        input_file=args.input_file,
        output_dir=args.output_dir,
        artifact_dir=args.artifact_dir,
        links_file=args.links_file,
        oa_status_file=args.oa_status_file,
        email=args.email,
        limit=args.limit,
        timeout=args.timeout,
        promote=not args.staging_only,
        overwrite=args.overwrite,
        retry_checked=args.retry_checked,
        retry_missing_pdf_url=args.retry_missing_pdf_url,
    )
    print("Unpaywall PDF fetch summary")
    for key in ("checked", "oa", "not_oa", "downloaded", "failed", "skipped"):
        print(f"- {key}: {counts[key]}")
    print(f"OA status output: {args.oa_status_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
