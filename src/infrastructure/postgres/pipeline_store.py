from __future__ import annotations

import json
from typing import Any, Protocol

import psycopg
from psycopg.types.json import Jsonb


class PipelineRecordStore(Protocol):
    def upsert_pipeline_run(self, record: dict[str, Any]) -> None:
        ...

    def insert_pipeline_event(self, record: dict[str, Any]) -> None:
        ...

    def upsert_paper_stage_state(self, record: dict[str, Any]) -> None:
        ...

    def upsert_artifact_registry(self, record: dict[str, Any]) -> None:
        ...


class PostgresPipelineRecordStore:
    def __init__(self, conninfo: str) -> None:
        if not conninfo.strip():
            raise ValueError("Postgres conninfo must be non-empty")
        self.conninfo = conninfo

    def upsert_pipeline_run(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pipeline_runs (
                      run_id,
                      pipeline_name,
                      pipeline_version,
                      execution_mode,
                      status,
                      input_scope,
                      started_at,
                      ended_at,
                      created_by,
                      summary,
                      config_hash,
                      schema_version,
                      trace_ref,
                      created_at,
                      updated_at
                    )
                    VALUES (
                      %(run_id)s,
                      %(pipeline_name)s,
                      %(pipeline_version)s,
                      %(execution_mode)s,
                      %(status)s,
                      %(input_scope)s,
                      %(started_at)s,
                      %(ended_at)s,
                      %(created_by)s,
                      %(summary)s,
                      %(config_hash)s,
                      %(schema_version)s,
                      %(trace_ref)s,
                      %(created_at)s,
                      %(updated_at)s
                    )
                    ON CONFLICT (run_id) DO UPDATE SET
                      pipeline_name = EXCLUDED.pipeline_name,
                      pipeline_version = EXCLUDED.pipeline_version,
                      execution_mode = EXCLUDED.execution_mode,
                      status = EXCLUDED.status,
                      input_scope = EXCLUDED.input_scope,
                      started_at = EXCLUDED.started_at,
                      ended_at = EXCLUDED.ended_at,
                      created_by = EXCLUDED.created_by,
                      summary = EXCLUDED.summary,
                      config_hash = EXCLUDED.config_hash,
                      schema_version = EXCLUDED.schema_version,
                      trace_ref = EXCLUDED.trace_ref,
                      updated_at = EXCLUDED.updated_at
                    """,
                    _pipeline_run_params(record),
                )

    def insert_pipeline_event(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pipeline_events (
                      event_id,
                      run_id,
                      stage_attempt_id,
                      attempt_number,
                      idempotency_key,
                      timestamp,
                      process_name,
                      stage,
                      event_type,
                      severity,
                      status,
                      paper_id,
                      artifact_id,
                      artifact_path,
                      contract_version,
                      schema_version,
                      trace_ref,
                      message,
                      metadata
                    )
                    VALUES (
                      %(event_id)s,
                      %(run_id)s,
                      %(stage_attempt_id)s,
                      %(attempt_number)s,
                      %(idempotency_key)s,
                      %(timestamp)s,
                      %(process_name)s,
                      %(stage)s,
                      %(event_type)s,
                      %(severity)s,
                      %(status)s,
                      %(paper_id)s,
                      %(artifact_id)s,
                      %(artifact_path)s,
                      %(contract_version)s,
                      %(schema_version)s,
                      %(trace_ref)s,
                      %(message)s,
                      %(metadata)s
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    _pipeline_event_params(record),
                )

    def upsert_paper_stage_state(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO paper_stage_states (
                      paper_id,
                      stage,
                      status,
                      run_id,
                      artifact_id,
                      artifact_path,
                      error_code,
                      error_message,
                      attempt_count,
                      updated_at
                    )
                    VALUES (
                      %(paper_id)s,
                      %(stage)s,
                      %(status)s,
                      %(run_id)s,
                      %(artifact_id)s,
                      %(artifact_path)s,
                      %(error_code)s,
                      %(error_message)s,
                      %(attempt_count)s,
                      %(updated_at)s
                    )
                    ON CONFLICT (paper_id, stage) DO UPDATE SET
                      status = EXCLUDED.status,
                      run_id = EXCLUDED.run_id,
                      artifact_id = EXCLUDED.artifact_id,
                      artifact_path = EXCLUDED.artifact_path,
                      error_code = EXCLUDED.error_code,
                      error_message = EXCLUDED.error_message,
                      attempt_count = EXCLUDED.attempt_count,
                      updated_at = EXCLUDED.updated_at
                    """,
                    _paper_stage_state_params(record),
                )

    def upsert_artifact_registry(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO artifact_registry (
                      artifact_id,
                      paper_id,
                      artifact_kind,
                      stage,
                      artifact_path,
                      content_hash,
                      schema_version,
                      contract_version,
                      producer_run_id,
                      validation_status,
                      created_at
                    )
                    VALUES (
                      %(artifact_id)s,
                      %(paper_id)s,
                      %(artifact_kind)s,
                      %(stage)s,
                      %(artifact_path)s,
                      %(content_hash)s,
                      %(schema_version)s,
                      %(contract_version)s,
                      %(producer_run_id)s,
                      %(validation_status)s,
                      %(created_at)s
                    )
                    ON CONFLICT (artifact_id) DO UPDATE SET
                      paper_id = EXCLUDED.paper_id,
                      artifact_kind = EXCLUDED.artifact_kind,
                      stage = EXCLUDED.stage,
                      artifact_path = EXCLUDED.artifact_path,
                      content_hash = EXCLUDED.content_hash,
                      schema_version = EXCLUDED.schema_version,
                      contract_version = EXCLUDED.contract_version,
                      producer_run_id = EXCLUDED.producer_run_id,
                      validation_status = EXCLUDED.validation_status
                    """,
                    _artifact_registry_params(record),
                )


def _pipeline_run_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": _required(record, "run_id"),
        "pipeline_name": _required(record, "pipeline_name"),
        "pipeline_version": _required(record, "pipeline_version"),
        "execution_mode": _required(record, "execution_mode"),
        "status": _required(record, "status"),
        "input_scope": Jsonb(_json_object(record.get("input_scope"), "input_scope")),
        "started_at": _required(record, "started_at"),
        "ended_at": record.get("ended_at"),
        "created_by": record.get("created_by"),
        "summary": Jsonb(_json_object(record.get("summary"), "summary")),
        "config_hash": record.get("config_hash"),
        "schema_version": record.get("schema_version") or "v1",
        "trace_ref": record.get("trace_ref"),
        "created_at": _required(record, "created_at"),
        "updated_at": _required(record, "updated_at"),
    }


def _pipeline_event_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": _required(record, "event_id"),
        "run_id": _required(record, "run_id"),
        "stage_attempt_id": record.get("stage_attempt_id"),
        "attempt_number": record.get("attempt_number"),
        "idempotency_key": record.get("idempotency_key"),
        "timestamp": _required(record, "timestamp"),
        "process_name": _required(record, "process_name"),
        "stage": _required(record, "stage"),
        "event_type": _required(record, "event_type"),
        "severity": _required(record, "severity"),
        "status": _required(record, "status"),
        "paper_id": record.get("paper_id"),
        "artifact_id": record.get("artifact_id"),
        "artifact_path": record.get("artifact_path"),
        "contract_version": record.get("contract_version"),
        "schema_version": record.get("schema_version") or "v1",
        "trace_ref": record.get("trace_ref"),
        "message": _required(record, "message"),
        "metadata": Jsonb(_json_object(record.get("metadata"), "metadata")),
    }


def _paper_stage_state_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_id": _required(record, "paper_id"),
        "stage": _required(record, "stage"),
        "status": _required(record, "status"),
        "run_id": record.get("run_id"),
        "artifact_id": record.get("artifact_id") or record.get("primary_artifact_id"),
        "artifact_path": record.get("artifact_path"),
        "error_code": record.get("error_code"),
        "error_message": record.get("error_message") or record.get("error_summary"),
        "attempt_count": int(record.get("attempt_count") or record.get("attempt_number") or 0),
        "updated_at": _required(record, "updated_at"),
    }


def _artifact_registry_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": _required(record, "artifact_id"),
        "paper_id": record.get("paper_id"),
        "artifact_kind": _required(record, "artifact_kind"),
        "stage": _required(record, "stage"),
        "artifact_path": _required(record, "artifact_path"),
        "content_hash": record.get("content_hash"),
        "schema_version": record.get("schema_version"),
        "contract_version": record.get("contract_version"),
        "producer_run_id": _required(record, "producer_run_id"),
        "validation_status": _required(record, "validation_status"),
        "created_at": _required(record, "created_at"),
    }


def _required(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string field: {key}")
    return value


def _json_object(value: Any, key: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    # Force JSON-serializability at the boundary.
    json.dumps(value)
    return value
