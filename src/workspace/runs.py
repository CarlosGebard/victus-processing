from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.workspace import config as ctx


PIPELINE_RUN_EXECUTION_MODES = {"single_paper", "batch", "stage_only", "testing", "backfill", "replay"}
PIPELINE_RUN_STATUSES = {"pending", "running", "succeeded", "failed", "partially_succeeded", "cancelled"}
PIPELINE_EVENT_TYPES = {
    "stage_started",
    "stage_succeeded",
    "stage_failed",
    "artifact_created",
    "artifact_validated",
    "artifact_invalid",
    "routing_decision",
    "skipped",
    "warning",
    "retry_scheduled",
    "retry_exhausted",
}
PIPELINE_EVENT_SEVERITIES = {"debug", "info", "warning", "error", "critical"}
PIPELINE_EVENT_STATUSES = {"started", "succeeded", "failed", "skipped", "warning"}
PAPER_STAGE_STATE_STATUSES = {"pending", "running", "succeeded", "failed", "skipped", "blocked"}
ARTIFACT_REGISTRY_STATUSES = {"current", "superseded", "discarded", "invalid"}
ARTIFACT_VALIDATION_STATUSES = {"valid", "invalid", "pending", "unknown"}
POSTGRES_OUTBOX_STATUSES = {"pending", "delivered", "failed"}
SCHEMA_VERSION = "v1"
PIPELINE_EVENT_SCHEMA_VERSION = "pipeline-event:v1"
NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._][a-z0-9]+)*$")
ALLOWED_PROCESS_NAMES = {
    "victus.processing.data_layout_migration",
    "victus.processing.seed_ingestion",
    "victus.processing.candidate_discovery",
    "victus.processing.candidate_review",
    "victus.processing.pdf_acquisition",
    "victus.processing.pdf_normalization",
    "victus.processing.pdf_processing",
    "victus.processing.paper_classification",
    "victus.processing.evidence_extraction",
    "victus.processing.artifact_registration",
}
ALLOWED_STAGES = {
    "data_layout.plan",
    "data_layout.copy",
    "data_layout.conflict_detection",
    "data_layout.unresolved_detection",
    "data_layout.report",
    "seed.load",
    "seed.validate",
    "candidate.discover",
    "candidate.review",
    "pdf.acquire",
    "pdf.normalize",
    "pdf.process",
    "classification.classify",
    "evidence.extract",
    "artifact.register",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


def new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


def create_pipeline_run(
    *,
    pipeline_name: str,
    pipeline_version: str,
    execution_mode: str,
    input_scope: dict[str, Any] | None = None,
    created_by: str | None = None,
    config_hash: str | None = None,
    schema_version: str = SCHEMA_VERSION,
    trace_ref: str | None = None,
    status: str = "running",
    run_id: str | None = None,
    lake_dir: Path | None = None,
    runtime_runs_dir: Path | None = None,
) -> dict[str, Any]:
    if execution_mode not in PIPELINE_RUN_EXECUTION_MODES:
        raise ValueError(f"Invalid PipelineRun execution_mode: {execution_mode}")
    if status not in PIPELINE_RUN_STATUSES:
        raise ValueError(f"Invalid PipelineRun status: {status}")
    if not pipeline_name.strip():
        raise ValueError("PipelineRun pipeline_name must be non-empty")
    if not pipeline_version.strip():
        raise ValueError("PipelineRun pipeline_version must be non-empty")

    now = utc_now_iso()
    record = {
        "run_id": run_id or new_run_id(),
        "pipeline_name": pipeline_name,
        "pipeline_version": pipeline_version,
        "execution_mode": execution_mode,
        "status": status,
        "input_scope": input_scope or {},
        "started_at": now,
        "ended_at": None,
        "created_by": created_by,
        "summary": {},
        "config_hash": config_hash,
        "schema_version": schema_version,
        "trace_ref": trace_ref,
        "created_at": now,
        "updated_at": now,
    }
    append_jsonl(_pipeline_runs_file(lake_dir), record)
    write_run_manifest(record, runtime_runs_dir=runtime_runs_dir)
    return record


def finish_pipeline_run(
    run: dict[str, Any],
    *,
    status: str,
    summary: dict[str, Any] | None = None,
    lake_dir: Path | None = None,
) -> dict[str, Any]:
    if status not in PIPELINE_RUN_STATUSES:
        raise ValueError(f"Invalid PipelineRun status: {status}")
    now = utc_now_iso()
    updated = dict(run)
    updated["status"] = status
    updated["ended_at"] = now
    updated["summary"] = summary or {}
    updated["updated_at"] = now
    append_jsonl(_pipeline_runs_file(lake_dir), updated)
    return updated


def emit_pipeline_event(
    *,
    run_id: str,
    process_name: str,
    stage: str,
    event_type: str,
    severity: str,
    status: str,
    message: str,
    stage_attempt_id: str | None = None,
    attempt_number: int | None = None,
    idempotency_key: str | None = None,
    paper_id: str | None = None,
    artifact_id: str | None = None,
    artifact_path: str | None = None,
    contract_version: str | None = None,
    schema_version: str = PIPELINE_EVENT_SCHEMA_VERSION,
    trace_ref: str | None = None,
    metadata: dict[str, Any] | None = None,
    lake_dir: Path | None = None,
) -> dict[str, Any]:
    if not run_id.strip():
        raise ValueError("PipelineEvent run_id must be non-empty")
    if event_type not in PIPELINE_EVENT_TYPES:
        raise ValueError(f"Invalid PipelineEvent event_type: {event_type}")
    if severity not in PIPELINE_EVENT_SEVERITIES:
        raise ValueError(f"Invalid PipelineEvent severity: {severity}")
    if status not in PIPELINE_EVENT_STATUSES:
        raise ValueError(f"Invalid PipelineEvent status: {status}")
    validate_process_name(process_name)
    validate_stage(stage)
    if not message.strip():
        raise ValueError("PipelineEvent message must be non-empty")
    if attempt_number is not None and attempt_number < 1:
        raise ValueError("PipelineEvent attempt_number must be positive")

    record = {
        "event_id": new_event_id(),
        "run_id": run_id,
        "stage_attempt_id": stage_attempt_id,
        "attempt_number": attempt_number,
        "idempotency_key": idempotency_key,
        "timestamp": utc_now_iso(),
        "process_name": process_name,
        "stage": stage,
        "event_type": event_type,
        "severity": severity,
        "status": status,
        "paper_id": paper_id,
        "artifact_id": artifact_id,
        "artifact_path": artifact_path,
        "contract_version": contract_version,
        "schema_version": schema_version,
        "trace_ref": trace_ref,
        "message": message,
        "metadata": _json_object(metadata or {}, "metadata"),
    }
    append_jsonl(_pipeline_events_file(lake_dir), record)
    return record


def write_run_manifest(run: dict[str, Any], *, runtime_runs_dir: Path | None = None) -> Path:
    run_id = str(run.get("run_id") or "").strip()
    if not run_id:
        raise ValueError("Run manifest requires run_id")
    path = _runtime_runs_dir(runtime_runs_dir) / run_id / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def append_run_error(
    *,
    run_id: str,
    error_type: str,
    message: str,
    paper_id: str | None = None,
    stage: str | None = None,
    runtime_runs_dir: Path | None = None,
) -> dict[str, Any]:
    if not run_id.strip():
        raise ValueError("Run error requires run_id")
    record = {
        "run_id": run_id,
        "timestamp": utc_now_iso(),
        "paper_id": paper_id,
        "stage": stage,
        "error_type": error_type,
        "message": message,
    }
    append_jsonl(_runtime_runs_dir(runtime_runs_dir) / run_id / "errors.jsonl", record)
    return record


def register_artifact_manifest(
    *,
    artifact_type: str,
    artifact_version: str,
    run_id: str,
    storage_uri: str,
    storage_backend: str,
    content_format: str,
    stage: str | None = None,
    stage_attempt_id: str | None = None,
    status: str = "current",
    contract_version: str | None = None,
    schema_version: str = SCHEMA_VERSION,
    config_hash: str | None = None,
    trace_ref: str | None = None,
    paper_id: str | None = None,
    checksum: str | None = None,
    size_bytes: int = 0,
    metadata: dict[str, Any] | None = None,
    artifact_id: str | None = None,
    registry_dir: Path | None = None,
) -> dict[str, Any]:
    if size_bytes < 0:
        raise ValueError("ArtifactManifest size_bytes must be non-negative")
    if status not in ARTIFACT_REGISTRY_STATUSES:
        raise ValueError(f"Invalid ArtifactRegistry status: {status}")
    if stage is not None:
        validate_stage(stage)
    for field_name, value in {
        "artifact_type": artifact_type,
        "artifact_version": artifact_version,
        "run_id": run_id,
        "storage_uri": storage_uri,
        "storage_backend": storage_backend,
        "content_format": content_format,
    }.items():
        if not value.strip():
            raise ValueError(f"ArtifactManifest {field_name} must be non-empty")
    record = {
        "artifact_id": artifact_id or stable_artifact_id(run_id=run_id, artifact_type=artifact_type, storage_uri=storage_uri),
        "artifact_type": artifact_type,
        "artifact_version": artifact_version,
        "paper_id": paper_id,
        "run_id": run_id,
        "stage": stage,
        "stage_attempt_id": stage_attempt_id,
        "storage_uri": storage_uri,
        "storage_backend": storage_backend,
        "content_format": content_format,
        "checksum": checksum,
        "size_bytes": size_bytes,
        "status": status,
        "contract_version": contract_version,
        "schema_version": schema_version,
        "config_hash": config_hash,
        "trace_ref": trace_ref,
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "metadata": metadata or {},
    }
    append_jsonl(_artifact_manifest_file(registry_dir), record)
    return record


def register_artifact_registry(
    *,
    artifact_id: str,
    artifact_kind: str,
    stage: str,
    artifact_path: str,
    producer_run_id: str,
    paper_id: str | None = None,
    content_hash: str | None = None,
    schema_version: str | None = None,
    contract_version: str | None = None,
    validation_status: str = "unknown",
    registry_dir: Path | None = None,
) -> dict[str, Any]:
    for field_name, value in {
        "artifact_id": artifact_id,
        "artifact_kind": artifact_kind,
        "stage": stage,
        "artifact_path": artifact_path,
        "producer_run_id": producer_run_id,
    }.items():
        if not value.strip():
            raise ValueError(f"ArtifactRegistry {field_name} must be non-empty")
    validate_stage(stage)
    if validation_status not in ARTIFACT_VALIDATION_STATUSES:
        raise ValueError(f"Invalid ArtifactRegistry validation_status: {validation_status}")
    record = {
        "artifact_id": artifact_id,
        "paper_id": paper_id,
        "artifact_kind": artifact_kind,
        "stage": stage,
        "artifact_path": artifact_path,
        "content_hash": content_hash,
        "schema_version": schema_version,
        "contract_version": contract_version,
        "producer_run_id": producer_run_id,
        "validation_status": validation_status,
        "created_at": utc_now_iso(),
    }
    append_jsonl(_artifact_registry_file(registry_dir), record)
    return record


def upsert_paper_stage_state(
    *,
    paper_id: str,
    stage: str,
    stage_attempt_id: str,
    attempt_number: int,
    run_id: str,
    status: str,
    last_event_id: str | None = None,
    started_at: str | None = None,
    ended_at: str | None = None,
    retry_count: int = 0,
    idempotency_key: str | None = None,
    contract_version: str | None = None,
    schema_version: str = SCHEMA_VERSION,
    config_hash: str | None = None,
    trace_ref: str | None = None,
    primary_artifact_id: str | None = None,
    artifact_path: str | None = None,
    error_code: str | None = None,
    error_summary: str | None = None,
    lake_dir: Path | None = None,
) -> dict[str, Any]:
    if not paper_id.strip():
        raise ValueError("PaperStageState paper_id must be non-empty")
    validate_stage(stage)
    if not stage_attempt_id.strip():
        raise ValueError("PaperStageState stage_attempt_id must be non-empty")
    if attempt_number < 1:
        raise ValueError("PaperStageState attempt_number must be positive")
    if not run_id.strip():
        raise ValueError("PaperStageState run_id must be non-empty")
    if status not in PAPER_STAGE_STATE_STATUSES:
        raise ValueError(f"Invalid PaperStageState status: {status}")
    if retry_count < 0:
        raise ValueError("PaperStageState retry_count must be non-negative")

    now = utc_now_iso()
    record = {
        "paper_id": paper_id,
        "stage": stage,
        "stage_attempt_id": stage_attempt_id,
        "attempt_number": attempt_number,
        "run_id": run_id,
        "status": status,
        "last_event_id": last_event_id,
        "last_transition_at": now,
        "started_at": started_at,
        "ended_at": ended_at,
        "retry_count": retry_count,
        "attempt_count": attempt_number,
        "idempotency_key": idempotency_key,
        "contract_version": contract_version,
        "schema_version": schema_version,
        "config_hash": config_hash,
        "trace_ref": trace_ref,
        "primary_artifact_id": primary_artifact_id,
        "artifact_id": primary_artifact_id,
        "artifact_path": artifact_path,
        "error_code": error_code,
        "error_message": error_summary,
        "error_summary": error_summary,
        "updated_at": now,
    }
    append_jsonl(_paper_stage_state_file(lake_dir), record)
    return record


def append_postgres_outbox(
    *,
    record_type: str,
    record_id: str,
    idempotency_key: str,
    payload_ref: str,
    payload: dict[str, Any] | None = None,
    target: str = "postgres",
    status: str = "pending",
    attempt_count: int = 0,
    last_error: str | None = None,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    for field_name, value in {
        "record_type": record_type,
        "record_id": record_id,
        "idempotency_key": idempotency_key,
        "payload_ref": payload_ref,
        "target": target,
    }.items():
        if not value.strip():
            raise ValueError(f"Outbox {field_name} must be non-empty")
    if status not in POSTGRES_OUTBOX_STATUSES:
        raise ValueError(f"Invalid outbox status: {status}")
    if attempt_count < 0:
        raise ValueError("Outbox attempt_count must be non-negative")
    now = utc_now_iso()
    record = {
        "outbox_id": stable_outbox_id(target=target, record_type=record_type, idempotency_key=idempotency_key),
        "record_type": record_type,
        "record_id": record_id,
        "idempotency_key": idempotency_key,
        "target": target,
        "status": status,
        "attempt_count": attempt_count,
        "last_attempt_at": None,
        "last_error": last_error,
        "payload_ref": payload_ref,
        "payload": _json_object(payload or {}, "payload"),
        "created_at": now,
        "updated_at": now,
    }
    append_jsonl(_postgres_outbox_file(runtime_dir), record)
    return record


def stable_artifact_id(*, run_id: str, artifact_type: str, storage_uri: str) -> str:
    digest = hashlib.sha256(f"{run_id}\0{artifact_type}\0{storage_uri}".encode("utf-8")).hexdigest()[:24]
    return f"artifact_{digest}"


def content_hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def config_hash(effective_config: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(effective_config).encode("utf-8")).hexdigest()


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(_sanitize_config(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sanitize_config(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in ("secret", "token", "key", "password", "dsn")):
                continue
            sanitized[str(key)] = _sanitize_config(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_config(item) for item in value]
    if isinstance(value, Path):
        return value.name
    return value


def stable_stage_attempt_id(*, run_id: str, paper_id: str | None, stage: str, attempt_number: int) -> str:
    digest = hashlib.sha256(f"{run_id}\0{paper_id or ''}\0{stage}\0{attempt_number}".encode("utf-8")).hexdigest()[:24]
    return f"attempt_{digest}"


def stable_idempotency_key(*, run_id: str, stage: str, action: str, subject: str | None = None) -> str:
    digest = hashlib.sha256(f"{run_id}\0{stage}\0{action}\0{subject or ''}".encode("utf-8")).hexdigest()
    return f"idm_{digest}"


def stable_outbox_id(*, target: str, record_type: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f"{target}\0{record_type}\0{idempotency_key}".encode("utf-8")).hexdigest()[:24]
    return f"outbox_{digest}"


def validate_process_name(process_name: str) -> None:
    if process_name not in ALLOWED_PROCESS_NAMES or not NAME_PATTERN.match(process_name):
        raise ValueError(f"Invalid process_name: {process_name}")


def validate_stage(stage: str) -> None:
    if stage not in ALLOWED_STAGES or not NAME_PATTERN.match(stage):
        raise ValueError(f"Invalid stage: {stage}")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _json_object(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    json.dumps(value)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL record must be an object: {path}")
        records.append(payload)
    return records


def _pipeline_runs_file(lake_dir: Path | None) -> Path:
    return (lake_dir or ctx.DATA_LAKE_DIR) / "pipeline_runs.jsonl"


def _pipeline_events_file(lake_dir: Path | None) -> Path:
    return (lake_dir or ctx.DATA_LAKE_DIR) / "pipeline_events.jsonl"


def _paper_stage_state_file(lake_dir: Path | None) -> Path:
    return (lake_dir or ctx.DATA_LAKE_DIR) / "paper_stage_state.jsonl"


def _artifact_manifest_file(registry_dir: Path | None) -> Path:
    return (registry_dir or ctx.DATA_REGISTRY_DIR) / "artifact_manifest.jsonl"


def _artifact_registry_file(registry_dir: Path | None) -> Path:
    return (registry_dir or ctx.DATA_REGISTRY_DIR) / "artifact_registry.jsonl"


def _runtime_runs_dir(runtime_runs_dir: Path | None) -> Path:
    return runtime_runs_dir or ctx.DATA_RUNTIME_RUNS_DIR


def _postgres_outbox_file(runtime_dir: Path | None) -> Path:
    return (runtime_dir or ctx.DATA_RUNTIME_DIR) / "outbox" / "postgres_pipeline_records.jsonl"
