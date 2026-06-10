from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.workspace import runs


class PipelineRecordStore(Protocol):
    def upsert_pipeline_run(self, record: dict[str, Any]) -> None:
        ...

    def insert_pipeline_event(self, record: dict[str, Any]) -> None:
        ...

    def upsert_paper_stage_state(self, record: dict[str, Any]) -> None:
        ...

    def upsert_artifact_registry(self, record: dict[str, Any]) -> None:
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
        context._deliver("pipeline_run", run["run_id"], run, "pipeline_runs")
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
        self._deliver("pipeline_run", self.run_id, self.run, "pipeline_runs")
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

    def _deliver(self, record_type: str, record_id: str, record: dict[str, Any], local_file: str) -> None:
        if self.record_store is None:
            return
        try:
            if record_type == "pipeline_run":
                self.record_store.upsert_pipeline_run(record)
            elif record_type == "pipeline_event":
                self.record_store.insert_pipeline_event(record)
            elif record_type == "paper_stage_state":
                self.record_store.upsert_paper_stage_state(record)
            elif record_type == "artifact_registry":
                self.record_store.upsert_artifact_registry(record)
            else:
                raise ValueError(f"Unsupported record type: {record_type}")
        except Exception as exc:
            runs.append_postgres_outbox(
                record_type=record_type,
                record_id=record_id,
                idempotency_key=str(record.get("idempotency_key") or record_id),
                payload_ref=f"data/{local_file}#{record_id}",
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
                metadata={"record_type": record_type, "record_id": record_id},
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
        self.context._deliver("pipeline_event", event["event_id"], event, "lake/pipeline_events.jsonl")
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
        self.context._deliver("paper_stage_state", f"{self.paper_id}:{self.stage}", state, "lake/paper_stage_state.jsonl")
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
        registry = runs.register_artifact_registry(
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
        self.context._deliver("artifact_registry", registry["artifact_id"], registry, "registry/artifact_registry.jsonl")
        return manifest


def _runtime_dir_from_runs_dir(runtime_runs_dir: Path | None) -> Path | None:
    if runtime_runs_dir is None:
        return None
    return runtime_runs_dir.parent
