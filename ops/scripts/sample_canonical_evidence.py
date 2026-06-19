from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.workspace import config as ctx


def sample_canonical_evidence(
    *,
    conninfo: str,
    sample_dir: Path,
    pdf_dir: Path = ctx.DATA_ARTIFACTS_PDFS_DIR,
    limit: int = 5,
    seed: str | None = None,
) -> dict[str, Path]:
    if not conninfo.strip():
        raise ValueError("Postgres conninfo must be non-empty")
    if limit < 1:
        raise ValueError("limit must be >= 1")

    with psycopg.connect(conninfo, row_factory=dict_row) as connection:
        paper_ids = _sample_paper_ids(connection, limit=limit, seed=seed)
        rows = _fetch_canonical_evidence(connection, paper_ids)

    return write_sample_bundle(
        sample_dir=sample_dir,
        pdf_dir=pdf_dir,
        paper_ids=paper_ids,
        evidence_rows=rows,
        seed=seed,
    )


def write_sample_bundle(
    *,
    sample_dir: Path,
    pdf_dir: Path,
    paper_ids: list[str],
    evidence_rows: list[dict[str, Any]],
    seed: str | None = None,
) -> dict[str, Path]:
    resolved_sample_dir = sample_dir.expanduser().resolve()
    resolved_pdf_dir = pdf_dir.expanduser().resolve()
    bundle_pdf_dir = resolved_sample_dir / "pdfs"
    resolved_sample_dir.mkdir(parents=True, exist_ok=True)
    bundle_pdf_dir.mkdir(parents=True, exist_ok=True)

    normalized_rows = [_normalize_row(row) for row in evidence_rows]
    grouped = _group_by_paper_id(evidence_rows)
    manifest_rows = []
    for paper_id in paper_ids:
        source_pdf = resolved_pdf_dir / f"{paper_id}.pdf"
        target_pdf = bundle_pdf_dir / f"{paper_id}.pdf"
        copied = False
        if source_pdf.exists():
            shutil.copy2(source_pdf, target_pdf)
            copied = True
        manifest_rows.append(
            {
                "paper_id": paper_id,
                "evidence_rows": len(grouped.get(paper_id, [])),
                "source_pdf_path": str(source_pdf),
                "sample_pdf_path": str(target_pdf) if copied else "",
                "pdf_copied": copied,
                "missing_pdf": not copied,
            }
        )

    csv_path = resolved_sample_dir / "canonical_evidence.csv"
    json_path = resolved_sample_dir / "canonical_evidence.json"
    manifest_path = resolved_sample_dir / "manifest.csv"
    metadata_path = resolved_sample_dir / "sample_metadata.json"
    _write_csv(csv_path, normalized_rows)
    _write_json(json_path, {"papers": [{"paper_id": paper_id, "canonical_evidence": grouped.get(paper_id, [])} for paper_id in paper_ids]})
    _write_csv(manifest_path, manifest_rows)
    _write_json(
        metadata_path,
        {
            "created_at": datetime.now(UTC).isoformat(),
            "seed": seed,
            "requested_papers": len(paper_ids),
            "evidence_rows": len(evidence_rows),
            "sample_dir": str(resolved_sample_dir),
            "pdf_dir": str(resolved_pdf_dir),
        },
    )
    return {
        "sample_dir": resolved_sample_dir,
        "canonical_evidence_csv": csv_path,
        "canonical_evidence_json": json_path,
        "manifest_csv": manifest_path,
        "metadata_json": metadata_path,
        "pdf_dir": bundle_pdf_dir,
    }


def _sample_paper_ids(connection: psycopg.Connection[Any], *, limit: int, seed: str | None) -> list[str]:
    order_seed = seed or datetime.now(UTC).isoformat()
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT paper_id
            FROM (
              SELECT DISTINCT paper_id
              FROM canonical_evidence
            ) sampled
            ORDER BY md5(paper_id || %s)
            LIMIT %s
            """,
            (order_seed, limit),
        )
        return [str(row["paper_id"]) for row in cursor.fetchall()]


def _fetch_canonical_evidence(connection: psycopg.Connection[Any], paper_ids: list[str]) -> list[dict[str, Any]]:
    if not paper_ids:
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT *
            FROM canonical_evidence
            WHERE paper_id = ANY(%s)
            ORDER BY paper_id, canonical_evidence_id
            """,
            (paper_ids,),
        )
        return list(cursor.fetchall())


def _group_by_paper_id(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        paper_id = str(row.get("paper_id") or "")
        grouped.setdefault(paper_id, []).append(_json_ready(row))
    return grouped


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict | list):
            normalized[key] = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        else:
            normalized[key] = value
    return normalized


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_ready(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _default_sample_dir() -> Path:
    sample_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return ctx.DATA_REPORTS_EXPORTS_DIR / "canonical-evidence-samples" / sample_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sample canonical evidence rows and matching PDFs for judge review.")
    parser.add_argument("--dsn", default=ctx.VICTUS_PIPELINE_POSTGRES_DSN)
    parser.add_argument("--limit", type=int, default=5, help="Number of random papers to sample.")
    parser.add_argument("--seed", default=None, help="Optional seed for reproducible paper sampling.")
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=ctx.DATA_ARTIFACTS_PDFS_DIR,
        help=f"Directory containing source PDFs (default: {ctx.display_path(ctx.DATA_ARTIFACTS_PDFS_DIR)}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Sample folder. Defaults to data/reports/exports/canonical-evidence-samples/<timestamp>.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.dsn:
        raise SystemExit("VICTUS_PIPELINE_POSTGRES_DSN or --dsn is required")
    sample_dir = args.output_dir if args.output_dir is not None else _default_sample_dir()
    written = sample_canonical_evidence(
        conninfo=str(args.dsn),
        sample_dir=sample_dir,
        pdf_dir=args.pdf_dir,
        limit=args.limit,
        seed=args.seed,
    )
    print("Canonical evidence judge sample")
    for label, path in written.items():
        print(f"- {label}: {ctx.display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
