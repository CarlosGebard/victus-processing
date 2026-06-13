from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from src.workspace import runs


class ScientificOutputStore(Protocol):
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


def persist_structured_blocks(
    store: ScientificOutputStore | None,
    *,
    paper_id: str,
    blocks: list[dict[str, Any]],
    producer_run_id: str | None = None,
) -> None:
    _deliver(
        store,
        "structured_blocks",
        f"structured_blocks:{paper_id}:{producer_run_id or 'unknown'}",
        {"paper_id": paper_id, "producer_run_id": producer_run_id, "schema_version": "v1", "blocks": blocks},
    )


def persist_structured_paper(
    store: ScientificOutputStore | None,
    *,
    paper_id: str,
    payload: dict[str, Any],
    producer_run_id: str | None = None,
) -> None:
    structured_paper = {**payload, "paper_id": paper_id}
    structured_paper.pop("source_pdf", None)
    _deliver(
        store,
        "structured_paper",
        f"structured_paper:{paper_id}:{producer_run_id or 'unknown'}",
        {
            "paper_id": paper_id,
            "producer_run_id": producer_run_id,
            "schema_version": "v1",
            "payload": structured_paper,
        },
    )


def persist_evidence_blocks(
    store: ScientificOutputStore | None,
    *,
    paper_id: str,
    blocks: list[dict[str, Any]],
    producer_run_id: str | None = None,
) -> None:
    _deliver(
        store,
        "evidence_blocks",
        f"evidence_blocks:{paper_id}:{producer_run_id or 'unknown'}",
        {"paper_id": paper_id, "producer_run_id": producer_run_id, "schema_version": "v1", "blocks": blocks},
    )


def persist_paper_classification(
    store: ScientificOutputStore | None,
    *,
    paper_id: str,
    classification: dict[str, Any],
    producer_run_id: str | None = None,
) -> None:
    _deliver(
        store,
        "paper_classification",
        f"paper_classification:{paper_id}:{producer_run_id or 'unknown'}",
        {
            "paper_id": paper_id,
            "producer_run_id": producer_run_id,
            "schema_version": "v1",
            "classification": classification,
        },
    )


def persist_experiment_map(
    store: ScientificOutputStore | None,
    *,
    paper_id: str,
    experiment_map: dict[str, Any],
    producer_run_id: str | None = None,
) -> None:
    _deliver(
        store,
        "experiment_map",
        f"experiment_map:{paper_id}:{producer_run_id or 'unknown'}",
        {
            "paper_id": paper_id,
            "producer_run_id": producer_run_id,
            "schema_version": "v1",
            "experiment_map": experiment_map,
        },
    )


def persist_canonical_evidence(
    store: ScientificOutputStore | None,
    *,
    paper_id: str,
    canonical: dict[str, Any],
    experiment_map_id: str | None = None,
    producer_run_id: str | None = None,
) -> None:
    _deliver(
        store,
        "canonical_evidence",
        f"canonical_evidence:{paper_id}:{producer_run_id or 'unknown'}",
        {
            "paper_id": paper_id,
            "producer_run_id": producer_run_id,
            "experiment_map_id": experiment_map_id,
            "schema_version": "v1",
            "canonical_evidence": canonical.get("canonical_evidence") or [],
            "unextracted_packet_items": canonical.get("unextracted_packet_items") or [],
        },
    )


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


def _deliver(
    store: ScientificOutputStore | None,
    record_type: str,
    record_id: str,
    payload: dict[str, Any],
) -> None:
    if store is None:
        return
    try:
        if record_type == "structured_paper":
            store.upsert_structured_paper(payload)
        elif record_type == "structured_blocks":
            store.upsert_structured_blocks(payload)
        elif record_type == "evidence_blocks":
            store.upsert_evidence_blocks(payload)
        elif record_type == "paper_classification":
            store.upsert_paper_classification(payload)
        elif record_type == "experiment_map":
            store.upsert_experiment_map(payload)
        elif record_type == "canonical_evidence":
            store.upsert_canonical_evidence(payload)
        else:
            raise ValueError(f"Unsupported scientific output record type: {record_type}")
    except Exception as exc:
        runs.append_postgres_outbox(
            record_type=record_type,
            record_id=record_id,
            idempotency_key=record_id,
            payload_ref=f"scientific_outputs#{record_id}",
            payload=payload,
            last_error=str(exc),
        )
