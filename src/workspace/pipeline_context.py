from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.workspace import runs


class PipelineRecordStore(Protocol):
    def upsert_paper_pipeline_state(self, record: dict[str, Any]) -> None:
        ...


@dataclass
class PipelineRunContext:
    run: dict[str, Any]
    process_name: str
    lake_dir: Path | None = None
    runtime_runs_dir: Path | None = None
    registry_dir: Path | None = None
    config_hash: str | None = None
    trace_ref: str | None = None
    record_store: PipelineRecordStore | None = None

    @classmethod
    def start(
        cls,
        *,
        pipeline_name: str,
        pipeline_version: str,
        execution_mode: str,
        process_name: str,
        input_scope: dict[str, Any] | None = None,
        created_by: str | None = None,
        config_hash: str | None = None,
        trace_ref: str | None = None,
        record_store: PipelineRecordStore | None = None,
        lake_dir: Path | None = None,
        runtime_runs_dir: Path | None = None,
        registry_dir: Path | None = None,
    ) -> PipelineRunContext:
        runs.validate_process_name(process_name)
        run = runs.create_pipeline_run(
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version,
            execution_mode=execution_mode,
            input_scope=input_scope,
            created_by=created_by,
            config_hash=config_hash,
            trace_ref=trace_ref,
            lake_dir=lake_dir,
            runtime_runs_dir=runtime_runs_dir,
        )
        context = cls(
            run=run,
            process_name=process_name,
            lake_dir=lake_dir,
            runtime_runs_dir=runtime_runs_dir,
            registry_dir=registry_dir,
            config_hash=config_hash,
            trace_ref=trace_ref,
            record_store=record_store,
        )
        return context

    @property
    def run_id(self) -> str:
        return str(self.run["run_id"])

    def stage_attempt(
        self,
        *,
        stage: str,
        paper_id: str | None = None,
        attempt_number: int = 1,
    ) -> StageAttempt:
        runs.validate_stage(stage)
        return StageAttempt(
            context=self,
            stage=stage,
            paper_id=paper_id,
            attempt_number=attempt_number,
            stage_attempt_id=runs.stable_stage_attempt_id(
                run_id=self.run_id,
                paper_id=paper_id,
                stage=stage,
                attempt_number=attempt_number,
            ),
        )

    def finish(self, *, status: str, summary: dict[str, Any] | None = None) -> dict[str, Any]:
        self.run = runs.finish_pipeline_run(self.run, status=status, summary=summary, lake_dir=self.lake_dir)
        return self.run

    def fail(self, *, stage: str | None, error: BaseException, paper_id: str | None = None) -> dict[str, Any]:
        runs.append_run_error(
            run_id=self.run_id,
            paper_id=paper_id,
            stage=stage,
            error_type=type(error).__name__,
            message=str(error),
            runtime_runs_dir=self.runtime_runs_dir,
        )
        return self.finish(status="failed", summary={"error_type": type(error).__name__, "message": str(error)})

    def _deliver_pipeline_state(self, record: dict[str, Any]) -> None:
        if self.record_store is None:
            return
        record_id = str(record["pipeline_state_id"])
        try:
            self.record_store.upsert_paper_pipeline_state(record)
        except Exception as exc:
            runs.append_postgres_outbox(
                record_type="paper_pipeline_state",
                record_id=record_id,
                idempotency_key=record_id,
                payload_ref=f"paper_pipeline_state#{record_id}",
                payload=record,
                last_error=str(exc),
                runtime_dir=_runtime_dir_from_runs_dir(self.runtime_runs_dir),
            )
            runs.emit_pipeline_event(
                run_id=self.run_id,
                process_name=self.process_name,
                stage="data_layout.report",
                event_type="warning",
                severity="warning",
                status="warning",
                message="PostgreSQL dual-write failed; record retained in local outbox",
                metadata={"record_type": "paper_pipeline_state", "record_id": record_id},
                lake_dir=self.lake_dir,
            )


@dataclass
class StageAttempt:
    context: PipelineRunContext
    stage: str
    paper_id: str | None
    attempt_number: int
    stage_attempt_id: str

    def event(
        self,
        *,
        event_type: str,
        severity: str,
        status: str,
        message: str,
        action: str,
        artifact_id: str | None = None,
        artifact_path: str | None = None,
        contract_version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = runs.emit_pipeline_event(
            run_id=self.context.run_id,
            process_name=self.context.process_name,
            stage=self.stage,
            stage_attempt_id=self.stage_attempt_id,
            attempt_number=self.attempt_number,
            idempotency_key=runs.stable_idempotency_key(
                run_id=self.context.run_id,
                stage=self.stage,
                action=action,
                subject=self.paper_id or artifact_id,
            ),
            event_type=event_type,
            severity=severity,
            status=status,
            message=message,
            paper_id=self.paper_id,
            artifact_id=artifact_id,
            artifact_path=artifact_path,
            contract_version=contract_version,
            trace_ref=self.context.trace_ref,
            metadata=metadata,
            lake_dir=self.context.lake_dir,
        )
        if self.paper_id and event["event_type"] in {"stage_started", "stage_succeeded", "stage_failed", "skipped"}:
            self.context._deliver_pipeline_state(self._state_from_event(event))
        return event

    def set_state(
        self,
        *,
        status: str,
        last_event_id: str | None = None,
        primary_artifact_id: str | None = None,
        error_summary: str | None = None,
    ) -> dict[str, Any] | None:
        if not self.paper_id:
            return None
        state = runs.upsert_paper_stage_state(
            paper_id=self.paper_id,
            stage=self.stage,
            stage_attempt_id=self.stage_attempt_id,
            attempt_number=self.attempt_number,
            run_id=self.context.run_id,
            status=status,
            last_event_id=last_event_id,
            idempotency_key=runs.stable_idempotency_key(
                run_id=self.context.run_id,
                stage=self.stage,
                action=f"state.{status}",
                subject=self.paper_id,
            ),
            config_hash=self.context.config_hash,
            trace_ref=self.context.trace_ref,
            primary_artifact_id=primary_artifact_id,
            error_summary=error_summary,
            lake_dir=self.context.lake_dir,
        )
        self.context._deliver_pipeline_state(self._state_from_stage_state(state))
        return state

    def register_artifact(
        self,
        *,
        artifact_type: str,
        artifact_version: str,
        storage_uri: str,
        storage_backend: str,
        content_format: str,
        size_bytes: int = 0,
        checksum: str | None = None,
        contract_version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        manifest = runs.register_artifact_manifest(
            artifact_type=artifact_type,
            artifact_version=artifact_version,
            paper_id=self.paper_id,
            run_id=self.context.run_id,
            stage=self.stage,
            stage_attempt_id=self.stage_attempt_id,
            storage_uri=storage_uri,
            storage_backend=storage_backend,
            content_format=content_format,
            checksum=checksum,
            size_bytes=size_bytes,
            contract_version=contract_version,
            config_hash=self.context.config_hash,
            trace_ref=self.context.trace_ref,
            metadata=metadata,
            registry_dir=self.context.registry_dir,
        )
        runs.register_artifact_registry(
            artifact_id=manifest["artifact_id"],
            paper_id=self.paper_id,
            artifact_kind=artifact_type,
            stage=self.stage,
            artifact_path=storage_uri,
            content_hash=checksum,
            schema_version=artifact_version,
            contract_version=contract_version,
            producer_run_id=self.context.run_id,
            validation_status="unknown",
            registry_dir=self.context.registry_dir,
        )
        return manifest

    def _base_pipeline_state(self) -> dict[str, Any]:
        return {
            "pipeline_state_id": self.stage_attempt_id,
            "paper_id": self.paper_id,
            "stage": self.stage,
            "attempt_number": self.attempt_number,
            "run_id": self.context.run_id,
            "pipeline_name": self.context.run["pipeline_name"],
            "pipeline_version": self.context.run["pipeline_version"],
            "execution_mode": self.context.run["execution_mode"],
            "input_scope": self.context.run.get("input_scope") or {},
        }

    def _state_from_event(self, event: dict[str, Any]) -> dict[str, Any]:
        status = "running" if event["status"] == "started" else event["status"]
        timestamp = event["timestamp"]
        terminal = status in {"succeeded", "failed", "skipped"}
        return {
            **self._base_pipeline_state(),
            "status": status,
            "artifact_path": event.get("artifact_path"),
            "error_code": event.get("event_type") if status == "failed" else None,
            "error_message": event.get("message") if status == "failed" else None,
            "metadata": {
                **(event.get("metadata") or {}),
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "severity": event["severity"],
                "message": event["message"],
            },
            "started_at": timestamp if status == "running" else None,
            "ended_at": timestamp if terminal else None,
            "updated_at": timestamp,
        }

    def _state_from_stage_state(self, state: dict[str, Any]) -> dict[str, Any]:
        status = str(state["status"])
        timestamp = state["updated_at"]
        return {
            **self._base_pipeline_state(),
            "status": status,
            "artifact_path": state.get("artifact_path"),
            "error_code": "stage_failed" if status == "failed" else None,
            "error_message": state.get("error_summary"),
            "metadata": {
                "last_event_id": state.get("last_event_id"),
                "primary_artifact_id": state.get("primary_artifact_id"),
            },
            "started_at": timestamp if status == "running" else None,
            "ended_at": timestamp if status in {"succeeded", "failed", "skipped", "blocked"} else None,
            "updated_at": timestamp,
        }


def _runtime_dir_from_runs_dir(runtime_runs_dir: Path | None) -> Path | None:
    if runtime_runs_dir is None:
        return None
    return runtime_runs_dir.parent
