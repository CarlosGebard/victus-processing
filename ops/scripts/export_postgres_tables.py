from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import psycopg
from psycopg.rows import dict_row

from src.workspace import config as ctx


DEFAULT_TABLES = (
    "paper_processing_state",
    "structured_blocks",
    "paper_classifications",
    "experiment_maps",
    "canonical_evidence",
)
ALLOWED_TABLES = DEFAULT_TABLES + (
    "structured_papers",
    "paper_pipeline_state",
)


def export_tables(
    *,
    conninfo: str,
    output_dir: Path,
    tables: tuple[str, ...] = DEFAULT_TABLES,
    formats: tuple[str, ...] = ("csv", "parquet"),
) -> dict[str, list[Path]]:
    if not conninfo.strip():
        raise ValueError("Postgres conninfo must be non-empty")
    for table in tables:
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Unsupported table: {table}")
    for output_format in formats:
        if output_format not in {"csv", "parquet"}:
            raise ValueError(f"Unsupported format: {output_format}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, list[Path]] = {table: [] for table in tables}
    with psycopg.connect(conninfo, row_factory=dict_row) as connection:
        for table in tables:
            rows = [_normalize_row(row) for row in _read_table(connection, table)]
            if "csv" in formats:
                path = output_dir / f"{table}.csv"
                _write_csv(path, rows)
                written[table].append(path)
            if "parquet" in formats:
                path = output_dir / f"{table}.parquet"
                _write_parquet(path, rows)
                written[table].append(path)
    return written


def _read_table(connection: psycopg.Connection[Any], table: str) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {table}")  # table name is allow-listed before this call.
        return list(cursor.fetchall())


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict | list):
            normalized[key] = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            continue
        normalized[key] = value
    return normalized


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export Victus PostgreSQL tables to CSV and Parquet.")
    parser.add_argument("--dsn", default=ctx.VICTUS_PIPELINE_POSTGRES_DSN)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ctx.DATA_REPORTS_EXPORTS_DIR / "postgres",
        help="Directory where table exports will be written.",
    )
    parser.add_argument(
        "--table",
        action="append",
        choices=ALLOWED_TABLES,
        default=None,
        help="Table to export. Can be repeated. Defaults to scientific output tables.",
    )
    parser.add_argument(
        "--format",
        action="append",
        choices=("csv", "parquet"),
        default=None,
        help="Output format. Can be repeated. Defaults to csv and parquet.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.dsn:
        raise SystemExit("VICTUS_PIPELINE_POSTGRES_DSN or --dsn is required")
    tables = tuple(args.table or DEFAULT_TABLES)
    formats = tuple(args.format or ("csv", "parquet"))
    try:
        written = export_tables(
            conninfo=str(args.dsn),
            output_dir=args.output_dir.expanduser().resolve(),
            tables=tables,
            formats=formats,
        )
    except Exception as exc:
        if type(exc).__name__ == "UndefinedTable":
            raise SystemExit(
                "ERROR: faltan tablas PostgreSQL. Aplica las migraciones en orden:\n"
                "  psql \"$DATABASE_URL\" -f ops/sql/005_simplified_postgres_schema.sql"
            ) from exc
        raise
    print("PostgreSQL table export")
    for table, paths in written.items():
        print(f"- {table}:")
        for path in paths:
            print(f"  - {ctx.display_path(path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
