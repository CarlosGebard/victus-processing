from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.infrastructure.postgres.pipeline_store import PostgresPipelineRecordStore
from src.workspace import config as ctx
from src.workspace.runs import append_jsonl, read_jsonl, utc_now_iso


def replay_outbox(*, outbox_file: Path, conninfo: str, dry_run: bool = False) -> dict[str, int]:
    store = PostgresPipelineRecordStore(conninfo)
    delivered = 0
    skipped = 0
    failed = 0
    results: list[dict[str, Any]] = []

    for record in read_jsonl(outbox_file):
        if record.get("status") == "delivered":
            skipped += 1
            results.append(record)
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict) or not payload:
            failed += 1
            results.append(_mark(record, "failed", "missing compact payload"))
            continue
        if dry_run:
            skipped += 1
            results.append(record)
            continue
        try:
            _deliver(store, str(record.get("record_type") or ""), payload)
        except Exception as exc:
            failed += 1
            results.append(_mark(record, "failed", str(exc)))
            continue
        delivered += 1
        results.append(_mark(record, "delivered", None))

    if not dry_run and results:
        replay_report = outbox_file.with_suffix(".replay.jsonl")
        for item in results:
            append_jsonl(replay_report, item)

    return {"delivered": delivered, "skipped": skipped, "failed": failed}


def _deliver(store: PostgresPipelineRecordStore, record_type: str, payload: dict[str, Any]) -> None:
    if record_type == "pipeline_run":
        store.upsert_pipeline_run(payload)
        return
    if record_type == "pipeline_event":
        store.insert_pipeline_event(payload)
        return
    if record_type == "paper_stage_state":
        store.upsert_paper_stage_state(payload)
        return
    if record_type == "artifact_registry":
        store.upsert_artifact_registry(payload)
        return
    if record_type == "structured_paper":
        store.upsert_structured_paper(payload)
        return
    if record_type == "structured_blocks":
        store.upsert_structured_blocks(payload)
        return
    if record_type == "evidence_blocks":
        store.upsert_evidence_blocks(payload)
        return
    if record_type == "paper_classification":
        store.upsert_paper_classification(payload)
        return
    if record_type == "experiment_map":
        store.upsert_experiment_map(payload)
        return
    if record_type == "canonical_evidence":
        store.upsert_canonical_evidence(payload)
        return
    if record_type == "paper_processing_state":
        store.upsert_paper_processing_state(payload)
        return
    raise ValueError(f"Unsupported outbox record_type: {record_type}")


def _mark(record: dict[str, Any], status: str, error: str | None) -> dict[str, Any]:
    updated = dict(record)
    updated["status"] = status
    updated["attempt_count"] = int(updated.get("attempt_count") or 0) + 1
    updated["last_attempt_at"] = utc_now_iso()
    updated["last_error"] = error
    updated["updated_at"] = utc_now_iso()
    return updated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay pending PostgreSQL outbox records.")
    parser.add_argument("--outbox", type=Path, default=ctx.DATA_RUNTIME_POSTGRES_OUTBOX_FILE)
    parser.add_argument("--dsn", default=ctx.VICTUS_PIPELINE_POSTGRES_DSN)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    outbox_file = args.outbox.expanduser().resolve()
    if not args.dsn:
        raise SystemExit("VICTUS_PIPELINE_POSTGRES_DSN or --dsn is required")
    if not outbox_file.exists():
        print("PostgreSQL outbox replay")
        print("- delivered: 0")
        print("- skipped:   0")
        print("- failed:    0")
        return 0
    result = replay_outbox(outbox_file=outbox_file, conninfo=args.dsn, dry_run=bool(args.dry_run))
    print("PostgreSQL outbox replay")
    print(f"- delivered: {result['delivered']}")
    print(f"- skipped:   {result['skipped']}")
    print(f"- failed:    {result['failed']}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
