from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.application.ports.llm import LLMRequest, LLMResponse
from src.application.pdf_processing.evidence import (
    build_classifier_input,
    build_experiment_packets,
    build_trimmed_paper,
    run_pdf_evidence,
    validate_canonical_evidence,
    validate_classifier_input,
    validate_experiment_map,
    validate_trimmed_paper,
)


class FakeEvidenceLLM:
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if request.operation == "pdf_processing.paper_classifier":
            return LLMResponse(
                text=json.dumps(
                    {
                        "paper_family": "primary_research",
                        "paper_type": "controlled_trial",
                        "evidence_generation_mode": "generates_original_data",
                        "has_original_experiments": True,
                        "has_systematic_search": False,
                        "has_meta_analysis": False,
                        "classification_confidence": 0.9,
                        "quality_flags": ["control_group_reported"],
                        "risk_flags": [],
                        "routing_evidence": ["Adults received intervention or control."],
                        "reasoning_summary": "The paper reports original intervention data.",
                    }
                )
            )
        if request.operation == "pdf_processing.experiment_scope_mapper":
            return LLMResponse(
                text=json.dumps(
                    {
                        "experiment_scopes": [
                            {
                                "scope_label": "Intervention results",
                                "scope_kind": "experimental",
                                "scope_basis": "method_result_link",
                                "source_block_ids": ["paper-1:b0", "paper-1:b1"],
                            },
                            {
                                "scope_label": "Discussion context",
                                "scope_kind": "descriptive",
                                "scope_basis": "single_block_scope",
                                "source_block_ids": ["paper-1:b3"],
                            }
                        ],
                        "unmapped_block_ids": [],
                    }
                )
            )
        if request.operation == "pdf_processing.canonical_evidence_extractor":
            return LLMResponse(
                text=json.dumps(
                    {
                        "canonical_evidence": [
                            {
                                "evidence_type": "between_group_result",
                                "evidence_text": "The intervention increased the measured outcome versus control.",
                                "population": "Adults",
                                "subgroup": None,
                                "organism": "human",
                                "intervention_or_exposure": "Intervention",
                                "comparator": "Control",
                                "outcomes": ["Measured outcome"],
                                "direction": "increase",
                                "timepoint": None,
                                "duration": None,
                                "dose": None,
                                "measurement_method": None,
                                "observations": [
                                    {
                                        "source_block_id": "paper-1:b1",
                                        "source_quote": "The intervention increased the measured outcome versus control.",
                                        "observation_role": "primary_finding",
                                    }
                                ],
                                "quantitative_data": {
                                    "summary": None,
                                    "values": [],
                                },
                                "source_block_ids": ["paper-1:b0", "paper-1:b1"],
                            }
                        ]
                        if request.metadata.get("scope_index") == 0
                        else [],
                        "unextracted_packet_items": []
                        if request.metadata.get("scope_index") == 0
                        else [{"source_block_ids": ["paper-1:b3"], "reason": "insufficient_context"}],
                    }
                )
            )
        raise AssertionError(f"Unexpected operation: {request.operation}")


class FakeNonPrimaryLLM:
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if request.operation == "pdf_processing.paper_classifier":
            return LLMResponse(
                text=json.dumps(
                    {
                        "paper_family": "evidence_synthesis",
                        "paper_type": "systematic_review",
                        "evidence_generation_mode": "synthesizes_existing_evidence",
                        "has_original_experiments": False,
                        "has_systematic_search": True,
                        "has_meta_analysis": False,
                        "classification_confidence": 0.88,
                        "quality_flags": ["systematic_search_reported"],
                        "risk_flags": [],
                        "routing_evidence": ["The authors searched databases."],
                        "reasoning_summary": "The paper synthesizes prior studies.",
                    }
                )
            )
        raise AssertionError(f"Unexpected operation: {request.operation}")


def _processed_payload() -> dict[str, Any]:
    return {
        "source_pdf": "/tmp/paper-1.pdf",
        "metadata": {"title": "Paper 1", "authors": []},
        "sections": [{"title": "Methods"}],
        "section_registry": [{"canonical_title": "Methods"}],
        "batch_ends": [{"tail_context": "x"}],
        "processing": {"model": "m"},
        "blocks": [
            {
                "block_id": "paper-1:b0",
                "paper_id": "paper-1",
                "content_hash": "h0",
                "order": 0,
                "section_path": ["Methods"],
                "section_type": "methods",
                "content_kind": "paragraph",
                "text": "Adults received intervention or control.",
            },
            {
                "block_id": "paper-1:b1",
                "paper_id": "paper-1",
                "content_hash": "h1",
                "order": 1,
                "section_path": ["Results"],
                "section_type": "results",
                "content_kind": "paragraph",
                "text": "The intervention increased the measured outcome versus control.",
                "quality": {"confidence": "high", "is_truncated": False, "is_duplicate": False},
            },
            {
                "block_id": "paper-1:b2",
                "paper_id": "paper-1",
                "content_hash": "h2",
                "order": 2,
                "section_path": ["Abstract"],
                "section_type": "abstract",
                "content_kind": "paragraph",
                "text": "Abstract text.",
            },
            {
                "block_id": "paper-1:b3",
                "paper_id": "paper-1",
                "content_hash": "h3",
                "order": 3,
                "section_path": ["Discussion"],
                "section_type": "discussion",
                "content_kind": "paragraph",
                "text": "Discussion context was insufficient by itself.",
            },
            {
                "block_id": "paper-1:b4",
                "paper_id": "paper-1",
                "content_hash": "h4",
                "order": 4,
                "section_path": ["References"],
                "section_type": "references",
                "content_kind": "paragraph",
                "text": "Reference text.",
            },
        ],
    }


def test_build_classifier_input_removes_administrative_sections() -> None:
    classifier_input = build_classifier_input(_processed_payload(), paper_id="paper-1")

    validate_classifier_input(classifier_input)

    block_ids = [block["block_id"] for block in classifier_input["blocks"]]
    assert "paper-1:b4" not in block_ids
    assert block_ids == ["paper-1:b0", "paper-1:b1", "paper-1:b2", "paper-1:b3"]


def test_build_trimmed_paper_outputs_only_metadata_and_blocks() -> None:
    trimmed = build_trimmed_paper(_processed_payload(), paper_id="paper-1")

    validate_trimmed_paper(trimmed)

    assert set(trimmed) == {"metadata", "blocks"}
    assert [block["block_id"] for block in trimmed["blocks"]] == ["paper-1:b0", "paper-1:b1", "paper-1:b3"]
    assert "is_truncated" not in trimmed["blocks"][1]["quality"]


def test_build_experiment_packets_uses_scope_source_block_ids() -> None:
    trimmed = build_trimmed_paper(_processed_payload(), paper_id="paper-1")
    experiment_map = {
        "experiment_scopes": [
            {
                "scope_label": "Intervention results",
                "scope_kind": "experimental",
                "scope_basis": "method_result_link",
                "source_block_ids": ["paper-1:b1", "paper-1:b0"],
            }
        ],
        "unmapped_block_ids": [],
    }

    packets = build_experiment_packets(trimmed, experiment_map)

    assert set(packets[0]) == {"scope_index", "source_block_ids", "blocks"}
    assert packets == [
        {
            "scope_index": 0,
            "source_block_ids": ["paper-1:b1", "paper-1:b0"],
            "blocks": [trimmed["blocks"][1], trimmed["blocks"][0]],
        }
    ]


def test_validate_experiment_map_normalizes_missing_scope_kind_and_basis_to_unclear() -> None:
    experiment_map = {
        "experiment_scopes": [
            {
                "scope_label": "Ambiguous scope",
                "scope_kind": None,
                "scope_basis": None,
                "source_block_ids": ["paper-1:b0"],
            }
        ],
        "unmapped_block_ids": [],
    }

    normalized = validate_experiment_map(experiment_map, block_ids={"paper-1:b0"})

    assert normalized["experiment_scopes"][0]["scope_kind"] == "unclear"
    assert normalized["experiment_scopes"][0]["scope_basis"] == "unclear"


def test_validate_canonical_evidence_rejects_source_ids_outside_packet() -> None:
    payload = {
        "canonical_evidence": [
            {
                "evidence_type": "between_group_result",
                "evidence_text": "Text.",
                "population": None,
                "subgroup": None,
                "organism": "human",
                "intervention_or_exposure": None,
                "comparator": None,
                "outcomes": [],
                "direction": "unclear",
                "timepoint": None,
                "duration": None,
                "dose": None,
                "measurement_method": None,
                "observations": [
                    {
                        "source_block_id": "paper-1:b0",
                        "source_quote": "Text.",
                        "observation_role": "primary_finding",
                    }
                ],
                "quantitative_data": {"summary": None, "values": []},
                "source_block_ids": ["paper-1:b0", "paper-1:b9"],
            }
        ],
        "unextracted_packet_items": [],
    }

    try:
        validate_canonical_evidence(payload, block_ids={"paper-1:b0"})
    except ValueError as exc:
        assert "paper-1:b9" in str(exc)
    else:
        raise AssertionError("Expected source ids outside packet to fail validation")


def test_run_pdf_evidence_writes_prompt_contract_outputs(tmp_path: Path) -> None:
    input_dir = tmp_path / "processing" / "paper-1"
    input_dir.mkdir(parents=True)
    input_path = input_dir / "paper.processed.json"
    input_path.write_text(json.dumps(_processed_payload()), encoding="utf-8")
    llm = FakeEvidenceLLM()

    output_path = run_pdf_evidence(input_path, output_dir=tmp_path / "evidence", llm_client=llm)

    paper_dir = tmp_path / "evidence" / "paper-1"
    assert output_path == paper_dir / "canonical_evidence.json"
    assert json.loads((paper_dir / "trimmed.json").read_text(encoding="utf-8")) == {
        "metadata": {"title": "Paper 1", "authors": []},
        "blocks": [
            {
                "block_id": "paper-1:b0",
                "paper_id": "paper-1",
                "content_hash": "h0",
                "order": 0,
                "section_path": ["Methods"],
                "section_type": "methods",
                "content_kind": "paragraph",
                "text": "Adults received intervention or control.",
            },
            {
                "block_id": "paper-1:b1",
                "paper_id": "paper-1",
                "content_hash": "h1",
                "order": 1,
                "section_path": ["Results"],
                "section_type": "results",
                "content_kind": "paragraph",
                "text": "The intervention increased the measured outcome versus control.",
                "quality": {"confidence": "high"},
            },
            {
                "block_id": "paper-1:b3",
                "paper_id": "paper-1",
                "content_hash": "h3",
                "order": 3,
                "section_path": ["Discussion"],
                "section_type": "discussion",
                "content_kind": "paragraph",
                "text": "Discussion context was insufficient by itself.",
            },
        ],
    }
    experiment_map = json.loads((paper_dir / "experiment_map.json").read_text(encoding="utf-8"))
    experiment_packets = json.loads((paper_dir / "experiment_packets.json").read_text(encoding="utf-8"))
    canonical = json.loads(output_path.read_text(encoding="utf-8"))
    assert set(experiment_map) == {"experiment_scopes", "unmapped_block_ids"}
    assert [packet["source_block_ids"] for packet in experiment_packets["experiment_packets"]] == [
        ["paper-1:b0", "paper-1:b1"],
        ["paper-1:b3"],
    ]
    assert set(canonical) == {"canonical_evidence", "unextracted_packet_items"}
    assert [request.operation for request in llm.requests] == [
        "pdf_processing.paper_classifier",
        "pdf_processing.experiment_scope_mapper",
        "pdf_processing.canonical_evidence_extractor",
        "pdf_processing.canonical_evidence_extractor",
    ]


def test_run_pdf_evidence_skips_non_primary_research_after_classification(tmp_path: Path) -> None:
    input_dir = tmp_path / "processing" / "paper-1"
    input_dir.mkdir(parents=True)
    input_path = input_dir / "paper.processed.json"
    input_path.write_text(json.dumps(_processed_payload()), encoding="utf-8")
    llm = FakeNonPrimaryLLM()

    output_path = run_pdf_evidence(input_path, output_dir=tmp_path / "evidence", llm_client=llm)

    paper_dir = tmp_path / "evidence" / "paper-1"
    assert output_path == paper_dir / "evidence_skipped.json"
    skipped = json.loads(output_path.read_text(encoding="utf-8"))
    assert skipped["reason"] == "non_primary_research"
    assert skipped["paper_family"] == "evidence_synthesis"
    assert (paper_dir / "paper.classifier_input.json").exists()
    assert (paper_dir / "paper.classification.json").exists()
    assert not (paper_dir / "trimmed.json").exists()
    assert [request.operation for request in llm.requests] == ["pdf_processing.paper_classifier"]
