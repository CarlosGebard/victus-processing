from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

import psycopg
from psycopg.types.json import Jsonb


class PipelineRecordStore(Protocol):
    def upsert_paper_pipeline_state(self, record: dict[str, Any]) -> None:
        ...

    def upsert_structured_paper(self, record: dict[str, Any]) -> None:
        ...

    def fetch_structured_paper(self, paper_id: str) -> dict[str, Any] | None:
        ...

    def fetch_structured_paper_ids(self, limit: int | None = None) -> list[str]:
        ...

    def has_canonical_evidence(self, paper_id: str) -> bool:
        ...

    def upsert_structured_blocks(self, record: dict[str, Any]) -> None:
        ...

    def upsert_paper_classification(self, record: dict[str, Any]) -> None:
        ...

    def upsert_experiment_map(self, record: dict[str, Any]) -> None:
        ...

    def upsert_canonical_evidence(self, record: dict[str, Any]) -> None:
        ...

    def replace_evidence_derivation_build(self, artifacts: dict[str, Any]) -> None:
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

    def upsert_paper_pipeline_state(self, record: dict[str, Any]) -> None:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO paper_pipeline_state (
                      pipeline_state_id,
                      paper_id,
                      stage,
                      status,
                      attempt_number,
                      run_id,
                      pipeline_name,
                      pipeline_version,
                      execution_mode,
                      input_scope,
                      artifact_path,
                      error_code,
                      error_message,
                      metadata,
                      started_at,
                      ended_at,
                      updated_at
                    )
                    VALUES (
                      %(pipeline_state_id)s,
                      %(paper_id)s,
                      %(stage)s,
                      %(status)s,
                      %(attempt_number)s,
                      %(run_id)s,
                      %(pipeline_name)s,
                      %(pipeline_version)s,
                      %(execution_mode)s,
                      %(input_scope)s,
                      %(artifact_path)s,
                      %(error_code)s,
                      %(error_message)s,
                      %(metadata)s,
                      %(started_at)s,
                      %(ended_at)s,
                      %(updated_at)s
                    )
                    ON CONFLICT (pipeline_state_id) DO UPDATE SET
                      status = EXCLUDED.status,
                      artifact_path = COALESCE(EXCLUDED.artifact_path, paper_pipeline_state.artifact_path),
                      error_code = EXCLUDED.error_code,
                      error_message = EXCLUDED.error_message,
                      metadata = paper_pipeline_state.metadata || EXCLUDED.metadata,
                      started_at = COALESCE(paper_pipeline_state.started_at, EXCLUDED.started_at),
                      ended_at = COALESCE(EXCLUDED.ended_at, paper_pipeline_state.ended_at),
                      updated_at = EXCLUDED.updated_at
                    """,
                    _paper_pipeline_state_params(record),
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

    def has_canonical_evidence(self, paper_id: str) -> bool:
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM canonical_evidence WHERE paper_id = %s)",
                    (paper_id,),
                )
                row = cursor.fetchone()
        return bool(row and row[0])

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
                          study_id,
                          evidence_type,
                          evidence_role_in_paper,
                          assertion_type,
                          organism,
                          effect_direction,
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
                          %(study_id)s,
                          %(evidence_type)s,
                          %(evidence_role_in_paper)s,
                          %(assertion_type)s,
                          %(organism)s,
                          %(effect_direction)s,
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
                          study_id = EXCLUDED.study_id,
                          evidence_type = EXCLUDED.evidence_type,
                          evidence_role_in_paper = EXCLUDED.evidence_role_in_paper,
                          assertion_type = EXCLUDED.assertion_type,
                          organism = EXCLUDED.organism,
                          effect_direction = EXCLUDED.effect_direction,
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

    def replace_evidence_derivation_build(self, artifacts: dict[str, Any]) -> None:
        build_id = _required_str(artifacts, "build_id")
        exposures = _record_list(artifacts, "exposure_registry")
        outcomes = _record_list(artifacts, "outcome_registry")
        projections = _record_list(artifacts, "evidence_projections")
        general = _record_list(artifacts, "general_evidence")
        support = _record_list(artifacts, "general_evidence_support")
        with psycopg.connect(self.conninfo) as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM general_evidence WHERE build_id = %s", (build_id,))
                cursor.execute("DELETE FROM evidence_projections WHERE build_id = %s", (build_id,))
                cursor.executemany(_EXPOSURE_UPSERT_SQL, [_exposure_params(item) for item in exposures])
                cursor.executemany(_OUTCOME_UPSERT_SQL, [_outcome_params(item) for item in outcomes])
                cursor.executemany(
                    _EVIDENCE_PROJECTION_INSERT_SQL,
                    [_evidence_projection_params(build_id, item) for item in projections],
                )
                cursor.executemany(
                    _GENERAL_EVIDENCE_INSERT_SQL,
                    [_general_evidence_params(build_id, item) for item in general],
                )
                cursor.executemany(
                    _GENERAL_EVIDENCE_SUPPORT_INSERT_SQL,
                    [_general_evidence_support_params(item) for item in support],
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
                      SELECT paper_id FROM paper_pipeline_state
                      UNION
                      SELECT paper_id FROM structured_papers
                      UNION
                      SELECT paper_id FROM structured_blocks
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
                        SELECT 1 FROM paper_classifications pc WHERE pc.paper_id = ids.paper_id
                      ) AS has_paper_classification,
                      EXISTS (
                        SELECT 1 FROM experiment_maps em WHERE em.paper_id = ids.paper_id
                      ) AS has_experiment_map,
                      EXISTS (
                        SELECT 1 FROM canonical_evidence ce WHERE ce.paper_id = ids.paper_id
                      ) AS has_canonical_evidence,
                      lc.paper_family,
                      lps.stage,
                      lps.status,
                      lps.error_code,
                      lps.error_message
                    FROM paper_ids ids
                    LEFT JOIN latest_classification lc ON lc.paper_id = ids.paper_id
                    LEFT JOIN LATERAL (
                      SELECT stage, status, error_code, error_message
                      FROM paper_pipeline_state pps
                      WHERE pps.paper_id = ids.paper_id
                      ORDER BY pps.updated_at DESC
                      LIMIT 1
                    ) lps ON TRUE
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
                "has_paper_classification": bool(row[3]),
                "has_experiment_map": bool(row[4]),
                "has_canonical_evidence": bool(row[5]),
                "paper_family": row[6],
                "latest_pipeline_stage": row[7],
                "latest_pipeline_status": row[8],
                "last_error_code": row[9],
                "last_error_message": row[10],
            }
        return facts


_EXPOSURE_UPSERT_SQL = """
INSERT INTO exposure_registry (
  exposure_id, canonical_name, display_name, exposure_type, aliases,
  parent_exposure_id, definition, status, created_by, confidence, payload, updated_at
) VALUES (
  %(exposure_id)s, %(canonical_name)s, %(display_name)s, %(exposure_type)s, %(aliases)s,
  %(parent_exposure_id)s, %(definition)s, %(status)s, %(created_by)s, %(confidence)s, %(payload)s, now()
)
ON CONFLICT (exposure_id) DO UPDATE SET
  canonical_name = EXCLUDED.canonical_name,
  display_name = EXCLUDED.display_name,
  exposure_type = EXCLUDED.exposure_type,
  aliases = EXCLUDED.aliases,
  parent_exposure_id = EXCLUDED.parent_exposure_id,
  definition = EXCLUDED.definition,
  status = EXCLUDED.status,
  created_by = EXCLUDED.created_by,
  confidence = EXCLUDED.confidence,
  payload = EXCLUDED.payload,
  updated_at = now()
"""

_OUTCOME_UPSERT_SQL = """
INSERT INTO outcome_registry (
  outcome_id, canonical_name, display_name, outcome_type, aliases,
  parent_outcome_id, definition, status, created_by, confidence, payload, updated_at
) VALUES (
  %(outcome_id)s, %(canonical_name)s, %(display_name)s, %(outcome_type)s, %(aliases)s,
  %(parent_outcome_id)s, %(definition)s, %(status)s, %(created_by)s, %(confidence)s, %(payload)s, now()
)
ON CONFLICT (outcome_id) DO UPDATE SET
  canonical_name = EXCLUDED.canonical_name,
  display_name = EXCLUDED.display_name,
  outcome_type = EXCLUDED.outcome_type,
  aliases = EXCLUDED.aliases,
  parent_outcome_id = EXCLUDED.parent_outcome_id,
  definition = EXCLUDED.definition,
  status = EXCLUDED.status,
  created_by = EXCLUDED.created_by,
  confidence = EXCLUDED.confidence,
  payload = EXCLUDED.payload,
  updated_at = now()
"""

_EVIDENCE_PROJECTION_INSERT_SQL = """
INSERT INTO evidence_projections (
  projection_id, build_id, canonical_evidence_id, paper_id, study_id,
  exposure_id, outcome_id, organism, population_scope, context_identity,
  effect_direction, study_design, evidence_rank, aggregation_weight, rag_use,
  causal_language_allowed, requires_caveat, rank_reason, projection_status,
  payload, created_at, updated_at
) VALUES (
  %(projection_id)s, %(build_id)s, %(canonical_evidence_id)s, %(paper_id)s, %(study_id)s,
  %(exposure_id)s, %(outcome_id)s, %(organism)s, %(population_scope)s, %(context_identity)s,
  %(effect_direction)s, %(study_design)s, %(evidence_rank)s, %(aggregation_weight)s, %(rag_use)s,
  %(causal_language_allowed)s, %(requires_caveat)s, %(rank_reason)s, %(projection_status)s,
  %(payload)s, %(created_at)s, now()
)
"""

_GENERAL_EVIDENCE_INSERT_SQL = """
INSERT INTO general_evidence (
  general_evidence_id, build_id, exposure_id, outcome_id, organism,
  population_scope, context_identity, question, dominant_direction,
  consensus_level, paper_count, study_count, evidence_count, recommendation_use,
  causal_language_allowed, requires_caveat, conclusion_claim, conclusion_status,
  status, payload, created_at, updated_at
) VALUES (
  %(general_evidence_id)s, %(build_id)s, %(exposure_id)s, %(outcome_id)s, %(organism)s,
  %(population_scope)s, %(context_identity)s, %(question)s, %(dominant_direction)s,
  %(consensus_level)s, %(paper_count)s, %(study_count)s, %(evidence_count)s, %(recommendation_use)s,
  %(causal_language_allowed)s, %(requires_caveat)s, %(conclusion_claim)s, %(conclusion_status)s,
  %(status)s, %(payload)s, %(created_at)s, now()
)
"""

_GENERAL_EVIDENCE_SUPPORT_INSERT_SQL = """
INSERT INTO general_evidence_support (general_evidence_id, projection_id, support_role)
VALUES (%(general_evidence_id)s, %(projection_id)s, %(support_role)s)
"""

_PAPER_PROCESSING_STATE_UPSERT_SQL = """
INSERT INTO paper_processing_state (
  paper_id,
  overall_status,
  current_stage,
  last_successful_stage,
  next_stage,
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
  has_paper_classification,
  has_experiment_map,
  has_canonical_evidence,
  paper_family,
  updated_at
)
VALUES (
  %(paper_id)s,
  %(overall_status)s,
  %(current_stage)s,
  %(last_successful_stage)s,
  %(next_stage)s,
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
  %(has_paper_classification)s,
  %(has_experiment_map)s,
  %(has_canonical_evidence)s,
  %(paper_family)s,
  now()
)
ON CONFLICT (paper_id) DO UPDATE SET
  overall_status = EXCLUDED.overall_status,
  current_stage = EXCLUDED.current_stage,
  last_successful_stage = EXCLUDED.last_successful_stage,
  next_stage = EXCLUDED.next_stage,
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
  has_paper_classification = EXCLUDED.has_paper_classification,
  has_experiment_map = EXCLUDED.has_experiment_map,
  has_canonical_evidence = EXCLUDED.has_canonical_evidence,
  paper_family = EXCLUDED.paper_family,
  updated_at = now()
"""


def _paper_pipeline_state_params(record: dict[str, Any]) -> dict[str, Any]:
    attempt_number = int(record.get("attempt_number") or 0)
    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1")
    return {
        "pipeline_state_id": _required_str(record, "pipeline_state_id"),
        "paper_id": _required_str(record, "paper_id"),
        "stage": _required_str(record, "stage"),
        "status": _required_str(record, "status"),
        "attempt_number": attempt_number,
        "run_id": _required(record, "run_id"),
        "pipeline_name": _required(record, "pipeline_name"),
        "pipeline_version": _required(record, "pipeline_version"),
        "execution_mode": _required(record, "execution_mode"),
        "input_scope": Jsonb(_json_object(record.get("input_scope"), "input_scope")),
        "artifact_path": record.get("artifact_path"),
        "error_code": record.get("error_code"),
        "error_message": record.get("error_message"),
        "metadata": Jsonb(_json_object(record.get("metadata"), "metadata")),
        "started_at": record.get("started_at"),
        "ended_at": record.get("ended_at"),
        "updated_at": _required(record, "updated_at"),
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
        "study_id": _required_str(payload, "study_id"),
        "evidence_type": _required_str(payload, "evidence_type"),
        "evidence_role_in_paper": _required_str(payload, "evidence_role_in_paper"),
        "assertion_type": _required_str(payload, "assertion_type"),
        "organism": payload.get("organism"),
        "effect_direction": _required_str(payload, "effect_direction", fallback=payload.get("direction")),
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
        "has_paper_classification": bool(record.get("has_paper_classification")),
        "has_experiment_map": bool(record.get("has_experiment_map")),
        "has_canonical_evidence": bool(record.get("has_canonical_evidence")),
        "paper_family": record.get("paper_family"),
    }


def _exposure_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "exposure_id": _required_str(record, "exposure_id"),
        "canonical_name": _required_str(record, "canonical_name"),
        "display_name": _required_str(record, "display_name"),
        "exposure_type": _required_str(record, "exposure_type"),
        "aliases": Jsonb(_json_array(record.get("aliases"), "aliases")),
        "parent_exposure_id": record.get("parent_exposure_id"),
        "definition": record.get("definition"),
        "status": _required_str(record, "status"),
        "created_by": _required_str(record, "created_by"),
        "confidence": _required_str(record, "confidence"),
        "payload": Jsonb(record),
    }


def _outcome_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome_id": _required_str(record, "outcome_id"),
        "canonical_name": _required_str(record, "canonical_name"),
        "display_name": _required_str(record, "display_name"),
        "outcome_type": _required_str(record, "outcome_type"),
        "aliases": Jsonb(_json_array(record.get("aliases"), "aliases")),
        "parent_outcome_id": record.get("parent_outcome_id"),
        "definition": record.get("definition"),
        "status": _required_str(record, "status"),
        "created_by": _required_str(record, "created_by"),
        "confidence": _required_str(record, "confidence"),
        "payload": Jsonb(record),
    }


def _evidence_projection_params(build_id: str, record: dict[str, Any]) -> dict[str, Any]:
    if _required_str(record, "build_id") != build_id:
        raise ValueError("EvidenceProjection build_id does not match artifact build_id")
    return {
        "projection_id": _required_str(record, "projection_id"),
        "build_id": build_id,
        "canonical_evidence_id": _required_str(record, "canonical_evidence_id"),
        "paper_id": _required_str(record, "paper_id"),
        "study_id": _required_str(record, "study_id"),
        "exposure_id": record.get("exposure_id"),
        "outcome_id": record.get("outcome_id"),
        "organism": record.get("organism"),
        "population_scope": record.get("population_scope"),
        "context_identity": Jsonb(_json_object(record.get("context_identity"), "context_identity")),
        "effect_direction": _required_str(record, "effect_direction"),
        "study_design": _required_str(record, "study_design"),
        "evidence_rank": _required_str(record, "evidence_rank"),
        "aggregation_weight": float(record.get("aggregation_weight") or 0.0),
        "rag_use": _required_str(record, "rag_use"),
        "causal_language_allowed": bool(record.get("causal_language_allowed")),
        "requires_caveat": bool(record.get("requires_caveat")),
        "rank_reason": _required_str(record, "rank_reason"),
        "projection_status": _required_str(record, "projection_status"),
        "payload": Jsonb(record),
        "created_at": _required_str(record, "created_at"),
    }


def _general_evidence_params(build_id: str, record: dict[str, Any]) -> dict[str, Any]:
    if _required_str(record, "build_id") != build_id:
        raise ValueError("GeneralEvidence build_id does not match artifact build_id")
    return {
        "general_evidence_id": _required_str(record, "general_evidence_id"),
        "build_id": build_id,
        "exposure_id": record.get("exposure_id"),
        "outcome_id": record.get("outcome_id"),
        "organism": record.get("organism"),
        "population_scope": record.get("population_scope"),
        "context_identity": Jsonb(_json_object(record.get("context_identity"), "context_identity")),
        "question": _required_str(record, "question"),
        "dominant_direction": _required_str(record, "dominant_direction"),
        "consensus_level": _required_str(record, "consensus_level"),
        "paper_count": int(record.get("paper_count") or 0),
        "study_count": int(record.get("study_count") or 0),
        "evidence_count": int(record.get("evidence_count") or 0),
        "recommendation_use": _required_str(record, "recommendation_use"),
        "causal_language_allowed": bool(record.get("causal_language_allowed")),
        "requires_caveat": bool(record.get("requires_caveat")),
        "conclusion_claim": _required_str(record, "conclusion_claim"),
        "conclusion_status": _required_str(record, "conclusion_status"),
        "status": _required_str(record, "status"),
        "payload": Jsonb(record),
        "created_at": _required_str(record, "created_at"),
    }


def _general_evidence_support_params(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "general_evidence_id": _required_str(record, "general_evidence_id"),
        "projection_id": _required_str(record, "projection_id"),
        "support_role": _required_str(record, "support_role"),
    }


def _record_list(record: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = record.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{key} must be a list of objects")
    return value


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
