from __future__ import annotations

import hashlib
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

    def upsert_structured_paper(self, record: dict[str, Any]) -> None:
        ...

    def fetch_structured_paper(self, paper_id: str) -> dict[str, Any] | None:
        ...

    def fetch_structured_paper_ids(self, limit: int | None = None) -> list[str]:
        ...

    def upsert_structured_blocks(self, record: dict[str, Any]) -> None:
        ...

    def upsert_evidence_blocks(self, record: dict[str, Any]) -> None:
        ...

    def fetch_evidence_blocks(self, paper_id: str) -> list[dict[str, Any]]:
        ...

    def upsert_paper_classification(self, record: dict[str, Any]) -> None:
        ...

    def upsert_experiment_map(self, record: dict[str, Any]) -> None:
        ...

    def upsert_canonical_evidence(self, record: dict[str, Any]) -> None:
        ...

    def upsert_paper_processing_state(self, record: dict[str, Any]) -> None:
        ...

    def upsert_paper_processing_states(self, records: list[dict[str, Any]]) -> None:
        ...

    def fetch_processing_facts(self) -> dict[str, dict[str, Any]]:
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

    def upsert_structured_paper(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO structured_papers (
                      paper_id,
                      payload,
                      producer_run_id,
                      schema_version,
                      updated_at
                    )
                    VALUES (
                      %(paper_id)s,
                      %(payload)s,
                      %(producer_run_id)s,
                      %(schema_version)s,
                      now()
                    )
                    ON CONFLICT (paper_id) DO UPDATE SET
                      payload = EXCLUDED.payload,
                      producer_run_id = EXCLUDED.producer_run_id,
                      schema_version = EXCLUDED.schema_version,
                      updated_at = now()
                    """,
                    _structured_paper_params(record),
                )

    def fetch_structured_paper(self, paper_id: str) -> dict[str, Any] | None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT payload FROM structured_papers WHERE paper_id = %s",
                    (paper_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        payload = row[0]
        return payload if isinstance(payload, dict) else None

    def fetch_structured_paper_ids(self, limit: int | None = None) -> list[str]:
        query = "SELECT paper_id FROM structured_papers ORDER BY paper_id"
        params: tuple[Any, ...] = ()
        if limit is not None:
            query += " LIMIT %s"
            params = (limit,)
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        return [str(row[0]) for row in rows]

    def upsert_structured_blocks(self, record: dict[str, Any]) -> None:
        blocks = record.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError("structured_blocks record requires blocks list")
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                for block in blocks:
                    if not isinstance(block, dict):
                        raise ValueError("structured_blocks items must be objects")
                    cursor.execute(
                        """
                        INSERT INTO structured_blocks (
                          block_id,
                          paper_id,
                          content_hash,
                          block_order,
                          section_path,
                          section_type,
                          content_kind,
                          text,
                          payload,
                          producer_run_id,
                          schema_version,
                          updated_at
                        )
                        VALUES (
                          %(block_id)s,
                          %(paper_id)s,
                          %(content_hash)s,
                          %(block_order)s,
                          %(section_path)s,
                          %(section_type)s,
                          %(content_kind)s,
                          %(text)s,
                          %(payload)s,
                          %(producer_run_id)s,
                          %(schema_version)s,
                          now()
                        )
                        ON CONFLICT (block_id) DO UPDATE SET
                          paper_id = EXCLUDED.paper_id,
                          content_hash = EXCLUDED.content_hash,
                          block_order = EXCLUDED.block_order,
                          section_path = EXCLUDED.section_path,
                          section_type = EXCLUDED.section_type,
                          content_kind = EXCLUDED.content_kind,
                          text = EXCLUDED.text,
                          payload = EXCLUDED.payload,
                          producer_run_id = EXCLUDED.producer_run_id,
                          schema_version = EXCLUDED.schema_version,
                          updated_at = now()
                        """,
                        _structured_block_params(record, block),
                    )

    def upsert_evidence_blocks(self, record: dict[str, Any]) -> None:
        blocks = record.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError("evidence_blocks record requires blocks list")
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                for block in blocks:
                    if not isinstance(block, dict):
                        raise ValueError("evidence_blocks items must be objects")
                    cursor.execute(
                        """
                        INSERT INTO evidence_blocks (
                          block_id,
                          paper_id,
                          content_hash,
                          block_order,
                          section_path,
                          section_type,
                          content_kind,
                          text,
                          payload,
                          producer_run_id,
                          schema_version,
                          updated_at
                        )
                        VALUES (
                          %(block_id)s,
                          %(paper_id)s,
                          %(content_hash)s,
                          %(block_order)s,
                          %(section_path)s,
                          %(section_type)s,
                          %(content_kind)s,
                          %(text)s,
                          %(payload)s,
                          %(producer_run_id)s,
                          %(schema_version)s,
                          now()
                        )
                        ON CONFLICT (block_id) DO UPDATE SET
                          paper_id = EXCLUDED.paper_id,
                          content_hash = EXCLUDED.content_hash,
                          block_order = EXCLUDED.block_order,
                          section_path = EXCLUDED.section_path,
                          section_type = EXCLUDED.section_type,
                          content_kind = EXCLUDED.content_kind,
                          text = EXCLUDED.text,
                          payload = EXCLUDED.payload,
                          producer_run_id = EXCLUDED.producer_run_id,
                          schema_version = EXCLUDED.schema_version,
                          updated_at = now()
                        """,
                        _structured_block_params(record, block),
                    )

    def fetch_evidence_blocks(self, paper_id: str) -> list[dict[str, Any]]:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT payload
                    FROM evidence_blocks
                    WHERE paper_id = %s
                    ORDER BY block_order
                    """,
                    (paper_id,),
                )
                rows = cursor.fetchall()
        return [row[0] for row in rows if isinstance(row[0], dict)]

    def upsert_paper_classification(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO paper_classifications (
                      paper_id,
                      producer_run_id,
                      paper_family,
                      paper_type,
                      evidence_generation_mode,
                      has_original_experiments,
                      has_systematic_search,
                      has_meta_analysis,
                      classification_confidence,
                      payload,
                      schema_version,
                      updated_at
                    )
                    VALUES (
                      %(paper_id)s,
                      %(producer_run_id)s,
                      %(paper_family)s,
                      %(paper_type)s,
                      %(evidence_generation_mode)s,
                      %(has_original_experiments)s,
                      %(has_systematic_search)s,
                      %(has_meta_analysis)s,
                      %(classification_confidence)s,
                      %(payload)s,
                      %(schema_version)s,
                      now()
                    )
                    ON CONFLICT (paper_id, producer_run_id) DO UPDATE SET
                      paper_family = EXCLUDED.paper_family,
                      paper_type = EXCLUDED.paper_type,
                      evidence_generation_mode = EXCLUDED.evidence_generation_mode,
                      has_original_experiments = EXCLUDED.has_original_experiments,
                      has_systematic_search = EXCLUDED.has_systematic_search,
                      has_meta_analysis = EXCLUDED.has_meta_analysis,
                      classification_confidence = EXCLUDED.classification_confidence,
                      payload = EXCLUDED.payload,
                      schema_version = EXCLUDED.schema_version,
                      updated_at = now()
                    """,
                    _paper_classification_params(record),
                )

    def upsert_experiment_map(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO experiment_maps (
                      experiment_map_id,
                      paper_id,
                      producer_run_id,
                      experiment_scopes,
                      unmapped_block_ids,
                      payload,
                      schema_version,
                      updated_at
                    )
                    VALUES (
                      %(experiment_map_id)s,
                      %(paper_id)s,
                      %(producer_run_id)s,
                      %(experiment_scopes)s,
                      %(unmapped_block_ids)s,
                      %(payload)s,
                      %(schema_version)s,
                      now()
                    )
                    ON CONFLICT (experiment_map_id) DO UPDATE SET
                      paper_id = EXCLUDED.paper_id,
                      producer_run_id = EXCLUDED.producer_run_id,
                      experiment_scopes = EXCLUDED.experiment_scopes,
                      unmapped_block_ids = EXCLUDED.unmapped_block_ids,
                      payload = EXCLUDED.payload,
                      schema_version = EXCLUDED.schema_version,
                      updated_at = now()
                    """,
                    _experiment_map_params(record),
                )

    def upsert_canonical_evidence(self, record: dict[str, Any]) -> None:
        evidence_items = record.get("canonical_evidence")
        if not isinstance(evidence_items, list):
            raise ValueError("canonical_evidence record requires canonical_evidence list")
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                for index, item in enumerate(evidence_items):
                    if not isinstance(item, dict):
                        raise ValueError("canonical_evidence items must be objects")
                    cursor.execute(
                        """
                        INSERT INTO canonical_evidence (
                          canonical_evidence_id,
                          paper_id,
                          producer_run_id,
                          experiment_map_id,
                          experiment_scope_id,
                          evidence_type,
                          organism,
                          direction,
                          evidence_text,
                          source_block_ids,
                          observations,
                          quantitative_data,
                          payload,
                          schema_version,
                          updated_at
                        )
                        VALUES (
                          %(canonical_evidence_id)s,
                          %(paper_id)s,
                          %(producer_run_id)s,
                          %(experiment_map_id)s,
                          %(experiment_scope_id)s,
                          %(evidence_type)s,
                          %(organism)s,
                          %(direction)s,
                          %(evidence_text)s,
                          %(source_block_ids)s,
                          %(observations)s,
                          %(quantitative_data)s,
                          %(payload)s,
                          %(schema_version)s,
                          now()
                        )
                        ON CONFLICT (canonical_evidence_id) DO UPDATE SET
                          paper_id = EXCLUDED.paper_id,
                          producer_run_id = EXCLUDED.producer_run_id,
                          experiment_map_id = EXCLUDED.experiment_map_id,
                          experiment_scope_id = EXCLUDED.experiment_scope_id,
                          evidence_type = EXCLUDED.evidence_type,
                          organism = EXCLUDED.organism,
                          direction = EXCLUDED.direction,
                          evidence_text = EXCLUDED.evidence_text,
                          source_block_ids = EXCLUDED.source_block_ids,
                          observations = EXCLUDED.observations,
                          quantitative_data = EXCLUDED.quantitative_data,
                          payload = EXCLUDED.payload,
                          schema_version = EXCLUDED.schema_version,
                          updated_at = now()
                        """,
                        _canonical_evidence_params(record, item, index),
                    )

    def upsert_paper_processing_state(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(_PAPER_PROCESSING_STATE_UPSERT_SQL, _paper_processing_state_params(record))

    def upsert_paper_processing_states(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    _PAPER_PROCESSING_STATE_UPSERT_SQL,
                    [_paper_processing_state_params(record) for record in records],
                )

    def fetch_processing_facts(self) -> dict[str, dict[str, Any]]:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH paper_ids AS (
                      SELECT paper_id FROM structured_papers
                      UNION
                      SELECT paper_id FROM structured_blocks
                      UNION
                      SELECT paper_id FROM evidence_blocks
                      UNION
                      SELECT paper_id FROM paper_classifications
                      UNION
                      SELECT paper_id FROM experiment_maps
                      UNION
                      SELECT paper_id FROM canonical_evidence
                    ),
                    latest_classification AS (
                      SELECT DISTINCT ON (paper_id)
                        paper_id,
                        paper_family
                      FROM paper_classifications
                      ORDER BY paper_id, updated_at DESC
                    )
                    SELECT
                      ids.paper_id,
                      EXISTS (
                        SELECT 1 FROM structured_papers sp WHERE sp.paper_id = ids.paper_id
                      ) AS has_structured_paper,
                      EXISTS (
                        SELECT 1 FROM structured_blocks sb WHERE sb.paper_id = ids.paper_id
                      ) AS has_structured_blocks,
                      EXISTS (
                        SELECT 1 FROM evidence_blocks eb WHERE eb.paper_id = ids.paper_id
                      ) AS has_evidence_blocks,
                      EXISTS (
                        SELECT 1 FROM paper_classifications pc WHERE pc.paper_id = ids.paper_id
                      ) AS has_paper_classification,
                      EXISTS (
                        SELECT 1 FROM experiment_maps em WHERE em.paper_id = ids.paper_id
                      ) AS has_experiment_map,
                      EXISTS (
                        SELECT 1 FROM canonical_evidence ce WHERE ce.paper_id = ids.paper_id
                      ) AS has_canonical_evidence,
                      lc.paper_family
                    FROM paper_ids ids
                    LEFT JOIN latest_classification lc ON lc.paper_id = ids.paper_id
                    ORDER BY ids.paper_id
                    """
                )
                rows = cursor.fetchall()
        facts: dict[str, dict[str, Any]] = {}
        for row in rows:
            paper_id = str(row[0])
            facts[paper_id] = {
                "has_structured_paper": bool(row[1]),
                "has_structured_blocks": bool(row[2]),
                "has_evidence_blocks": bool(row[3]),
                "has_paper_classification": bool(row[4]),
                "has_experiment_map": bool(row[5]),
                "has_canonical_evidence": bool(row[6]),
                "paper_family": row[7],
            }
        return facts


_PAPER_PROCESSING_STATE_UPSERT_SQL = """
INSERT INTO paper_processing_state (
  paper_id,
  overall_status,
  current_stage,
  last_successful_stage,
  next_stage,
  active_pipeline_run_id,
  pipeline_version,
  config_hash,
  is_processable,
  is_complete,
  is_ready_for_export,
  is_exported,
  blocked_reason,
  last_error_code,
  last_error_message,
  has_pdf,
  has_markdown,
  has_structured_paper,
  has_structured_blocks,
  has_evidence_blocks,
  has_paper_classification,
  has_experiment_map,
  has_canonical_evidence,
  paper_family,
  locked_by,
  locked_until,
  updated_at
)
VALUES (
  %(paper_id)s,
  %(overall_status)s,
  %(current_stage)s,
  %(last_successful_stage)s,
  %(next_stage)s,
  %(active_pipeline_run_id)s,
  %(pipeline_version)s,
  %(config_hash)s,
  %(is_processable)s,
  %(is_complete)s,
  %(is_ready_for_export)s,
  %(is_exported)s,
  %(blocked_reason)s,
  %(last_error_code)s,
  %(last_error_message)s,
  %(has_pdf)s,
  %(has_markdown)s,
  %(has_structured_paper)s,
  %(has_structured_blocks)s,
  %(has_evidence_blocks)s,
  %(has_paper_classification)s,
  %(has_experiment_map)s,
  %(has_canonical_evidence)s,
  %(paper_family)s,
  %(locked_by)s,
  %(locked_until)s,
  now()
)
ON CONFLICT (paper_id) DO UPDATE SET
  overall_status = EXCLUDED.overall_status,
  current_stage = EXCLUDED.current_stage,
  last_successful_stage = EXCLUDED.last_successful_stage,
  next_stage = EXCLUDED.next_stage,
  active_pipeline_run_id = EXCLUDED.active_pipeline_run_id,
  pipeline_version = EXCLUDED.pipeline_version,
  config_hash = EXCLUDED.config_hash,
  is_processable = EXCLUDED.is_processable,
  is_complete = EXCLUDED.is_complete,
  is_ready_for_export = EXCLUDED.is_ready_for_export,
  is_exported = EXCLUDED.is_exported,
  blocked_reason = EXCLUDED.blocked_reason,
  last_error_code = EXCLUDED.last_error_code,
  last_error_message = EXCLUDED.last_error_message,
  has_pdf = EXCLUDED.has_pdf,
  has_markdown = EXCLUDED.has_markdown,
  has_structured_paper = EXCLUDED.has_structured_paper,
  has_structured_blocks = EXCLUDED.has_structured_blocks,
  has_evidence_blocks = EXCLUDED.has_evidence_blocks,
  has_paper_classification = EXCLUDED.has_paper_classification,
  has_experiment_map = EXCLUDED.has_experiment_map,
  has_canonical_evidence = EXCLUDED.has_canonical_evidence,
  paper_family = EXCLUDED.paper_family,
  locked_by = EXCLUDED.locked_by,
  locked_until = EXCLUDED.locked_until,
  updated_at = now()
"""


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


def _structured_block_params(record: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    return {
        "block_id": _required_str(block, "block_id"),
        "paper_id": _required_str(block, "paper_id", fallback=record.get("paper_id")),
        "content_hash": block.get("content_hash"),
        "block_order": int(_required_value(block, "order")),
        "section_path": Jsonb(_json_array(block.get("section_path"), "section_path")),
        "section_type": _required_str(block, "section_type"),
        "content_kind": _required_str(block, "content_kind"),
        "text": _required_str(block, "text"),
        "payload": Jsonb(_json_object(block, "payload")),
        "producer_run_id": record.get("producer_run_id"),
        "schema_version": record.get("schema_version") or "v1",
    }


def _structured_paper_params(record: dict[str, Any]) -> dict[str, Any]:
    paper_id = _required_str(record, "paper_id")
    payload = _json_object(record.get("payload"), "payload")
    payload = {**payload, "paper_id": paper_id}
    payload.pop("source_pdf", None)
    return {
        "paper_id": paper_id,
        "payload": Jsonb(payload),
        "producer_run_id": record.get("producer_run_id"),
        "schema_version": record.get("schema_version") or "v1",
    }


def _paper_classification_params(record: dict[str, Any]) -> dict[str, Any]:
    payload = _json_object(record.get("classification"), "classification")
    return {
        "paper_id": _required_str(record, "paper_id"),
        "producer_run_id": str(record.get("producer_run_id") or "unknown"),
        "paper_family": _required_str(payload, "paper_family"),
        "paper_type": _required_str(payload, "paper_type"),
        "evidence_generation_mode": _required_str(payload, "evidence_generation_mode"),
        "has_original_experiments": bool(_required_value(payload, "has_original_experiments")),
        "has_systematic_search": bool(_required_value(payload, "has_systematic_search")),
        "has_meta_analysis": bool(_required_value(payload, "has_meta_analysis")),
        "classification_confidence": float(_required_value(payload, "classification_confidence")),
        "payload": Jsonb(payload),
        "schema_version": record.get("schema_version") or "v1",
    }


def _experiment_map_params(record: dict[str, Any]) -> dict[str, Any]:
    payload = _json_object(record.get("experiment_map"), "experiment_map")
    paper_id = _required_str(record, "paper_id")
    experiment_map_id = str(payload.get("experiment_map_id") or record.get("experiment_map_id") or "")
    if not experiment_map_id:
        experiment_map_id = stable_experiment_map_id(paper_id, payload)
    payload = {**payload, "experiment_map_id": experiment_map_id, "paper_id": paper_id}
    return {
        "experiment_map_id": experiment_map_id,
        "paper_id": paper_id,
        "producer_run_id": record.get("producer_run_id"),
        "experiment_scopes": Jsonb(_json_array(payload.get("experiment_scopes"), "experiment_scopes")),
        "unmapped_block_ids": Jsonb(_json_array(payload.get("unmapped_block_ids"), "unmapped_block_ids")),
        "payload": Jsonb(payload),
        "schema_version": record.get("schema_version") or "v1",
    }


def _canonical_evidence_params(record: dict[str, Any], item: dict[str, Any], index: int) -> dict[str, Any]:
    paper_id = _required_str(record, "paper_id")
    payload = dict(item)
    evidence_id = str(payload.get("canonical_evidence_id") or "")
    if not evidence_id:
        evidence_id = _stable_id("canonical_evidence", paper_id, index, payload)
        payload["canonical_evidence_id"] = evidence_id
        payload.setdefault("paper_id", paper_id)
    return {
        "canonical_evidence_id": evidence_id,
        "paper_id": str(payload.get("paper_id") or paper_id),
        "producer_run_id": record.get("producer_run_id"),
        "experiment_map_id": payload.get("experiment_map_id") or record.get("experiment_map_id"),
        "experiment_scope_id": payload.get("experiment_scope_id"),
        "evidence_type": _required_str(payload, "evidence_type"),
        "organism": payload.get("organism"),
        "direction": _required_str(payload, "direction"),
        "evidence_text": _required_str(payload, "evidence_text"),
        "source_block_ids": Jsonb(_json_array(payload.get("source_block_ids"), "source_block_ids")),
        "observations": Jsonb(_json_array(payload.get("observations"), "observations")),
        "quantitative_data": Jsonb(payload["quantitative_data"]) if isinstance(payload.get("quantitative_data"), dict) else None,
        "payload": Jsonb(payload),
        "schema_version": record.get("schema_version") or "v1",
    }


def _paper_processing_state_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "paper_id": _required_str(record, "paper_id"),
        "overall_status": _required_str(record, "overall_status"),
        "current_stage": _required_str(record, "current_stage"),
        "last_successful_stage": record.get("last_successful_stage"),
        "next_stage": record.get("next_stage"),
        "active_pipeline_run_id": record.get("active_pipeline_run_id"),
        "pipeline_version": _required_str(record, "pipeline_version"),
        "config_hash": record.get("config_hash"),
        "is_processable": bool(record.get("is_processable")),
        "is_complete": bool(record.get("is_complete")),
        "is_ready_for_export": bool(record.get("is_ready_for_export")),
        "is_exported": bool(record.get("is_exported")),
        "blocked_reason": record.get("blocked_reason"),
        "last_error_code": record.get("last_error_code"),
        "last_error_message": record.get("last_error_message"),
        "has_pdf": bool(record.get("has_pdf")),
        "has_markdown": bool(record.get("has_markdown")),
        "has_structured_paper": bool(record.get("has_structured_paper")),
        "has_structured_blocks": bool(record.get("has_structured_blocks")),
        "has_evidence_blocks": bool(record.get("has_evidence_blocks")),
        "has_paper_classification": bool(record.get("has_paper_classification")),
        "has_experiment_map": bool(record.get("has_experiment_map")),
        "has_canonical_evidence": bool(record.get("has_canonical_evidence")),
        "paper_family": record.get("paper_family"),
        "locked_by": record.get("locked_by"),
        "locked_until": record.get("locked_until"),
    }


def _required(record: dict[str, Any], key: str) -> str:
    return _required_str(record, key)


def _required_str(record: dict[str, Any], key: str, *, fallback: Any = None) -> str:
    value = record.get(key)
    if value is None:
        value = fallback
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string field: {key}")
    return value


def _required_value(record: dict[str, Any], key: str) -> Any:
    if key not in record:
        raise ValueError(f"Missing required field: {key}")
    return record[key]


def _json_object(value: Any, key: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    # Force JSON-serializability at the boundary.
    json.dumps(value)
    return value


def _json_array(value: Any, key: str) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a JSON array")
    json.dumps(value)
    return value


def _stable_id(prefix: str, *parts: Any) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()}"


def stable_experiment_map_id(paper_id: str, experiment_map: dict[str, Any]) -> str:
    payload = {
        "experiment_scopes": experiment_map.get("experiment_scopes") or [],
        "unmapped_block_ids": experiment_map.get("unmapped_block_ids") or [],
    }
    encoded = json.dumps(
        ("experiment_map", paper_id, payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"experiment_map_{hashlib.sha256(encoded).hexdigest()}"
