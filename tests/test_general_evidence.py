from __future__ import annotations

import json

from src.application.evidence_derivation.general_evidence import (
    build_general_evidence_artifacts,
    build_rag_export,
    validate_conclusion_text,
)
from src.application.evidence_derivation.stage import build_evidence_derivation_for_paper


def _canonical(
    evidence_id: str,
    *,
    paper_id: str = "paper_1",
    study_id: str = "study_1",
    raw_exposure: str = "Egg intake",
    raw_outcomes: list[str] | None = None,
    effect_direction: str = "increase",
    organism: str = "human",
    evidence_role: str = "primary_result",
    assertion_type: str = "comparative_effect",
) -> dict[str, object]:
    return {
        "canonical_evidence_id": evidence_id,
        "paper_id": paper_id,
        "study_id": study_id,
        "evidence_type": "between_group_result",
        "evidence_role_in_paper": evidence_role,
        "assertion_type": assertion_type,
        "evidence_text": "Egg intake increased LDL cholesterol compared with control.",
        "population": "adults",
        "subgroup": None,
        "organism": organism,
        "raw_exposure": raw_exposure,
        "comparator": "control",
        "raw_outcomes": raw_outcomes or ["LDL cholesterol"],
        "effect_direction": effect_direction,
        "timepoint": None,
        "duration": None,
        "dose": None,
        "measurement_method": None,
        "observations": [{"source_block_id": "b1", "source_quote": "Egg intake increased LDL.", "observation_role": "primary_finding"}],
        "quantitative_data": {"summary": "p<0.05", "values": []},
        "canonical_evidence_status": "accepted",
    }


def _experiment_map() -> dict[str, object]:
    return {
        "paper_id": "paper_1",
        "experiment_scopes": [
            {
                "experiment_scope_id": "study_1",
                "study_id": "study_1",
                "source_block_ids": ["b1"],
                "study_design": "rct",
                "study_role_in_paper": "main_study",
            }
        ],
        "unmapped_block_ids": [],
    }


def test_registry_deduplicates_obvious_exposure_variants() -> None:
    artifacts = build_general_evidence_artifacts(
        canonical_evidence=[
            _canonical("ev_1", raw_exposure="Egg intake"),
            _canonical("ev_2", raw_exposure="egg consumption"),
            _canonical("ev_3", raw_exposure="Whole egg intake"),
        ],
        experiment_map=_experiment_map(),
    )

    exposures = artifacts["exposure_registry"]

    assert [record["exposure_id"] for record in exposures] == ["exposure.egg"]


def test_projection_fans_out_one_evidence_per_outcome() -> None:
    artifacts = build_general_evidence_artifacts(
        canonical_evidence=[_canonical("ev_1", raw_outcomes=["LDL cholesterol", "BMI"])],
        experiment_map=_experiment_map(),
    )

    projections = artifacts["evidence_projections"]

    assert len(projections) == 2
    assert {projection["outcome_id"] for projection in projections} == {"outcome.bmi", "outcome.ldl_cholesterol"}


def test_rank_caps_animal_evidence_to_mechanistic_c() -> None:
    experiment_map = _experiment_map()
    experiment_map["experiment_scopes"][0]["study_design"] = "animal_experiment"  # type: ignore[index]
    artifacts = build_general_evidence_artifacts(
        canonical_evidence=[_canonical("ev_1", organism="animal")],
        experiment_map=experiment_map,
    )

    projection = artifacts["evidence_projections"][0]

    assert projection["evidence_rank"] == "C"
    assert projection["rag_use"] == "mechanistic_only"


def test_general_evidence_counts_support_units_not_raw_records() -> None:
    artifacts = build_general_evidence_artifacts(
        canonical_evidence=[
            _canonical("ev_1", paper_id="paper_1", study_id="study_1"),
            _canonical("ev_2", paper_id="paper_1", study_id="study_1"),
        ],
        experiment_map=_experiment_map(),
    )

    general = artifacts["general_evidence"][0]

    assert general["paper_count"] == 1
    assert general["study_count"] == 1
    assert general["evidence_count"] == 2
    assert general["study_direction_distribution"]["increase"] == 1


def test_rag_export_filters_general_and_support_documents() -> None:
    general = [
        {"general_evidence_id": "ge_1", "status": "active", "consensus_level": "moderate", "recommendation_use": "usable_with_caveat"},
        {"general_evidence_id": "ge_2", "status": "active", "consensus_level": "insufficient", "recommendation_use": "usable_with_caveat"},
    ]
    projections = [
        {"projection_id": "p_1", "evidence_rank": "A", "projection_status": "accepted", "rag_use": "primary"},
        {"projection_id": "p_2", "evidence_rank": "D", "projection_status": "accepted", "rag_use": "audit_only"},
    ]

    export = build_rag_export(general_evidence=general, evidence_projections=projections)

    assert [(doc["document_type"], doc["id"]) for doc in export["documents"]] == [
        ("general_evidence", "ge_1"),
        ("evidence_support", "p_1"),
    ]


def test_conclusion_validator_rejects_causal_overstatement() -> None:
    errors = validate_conclusion_text(
        {
            "causal_language_allowed": False,
            "recommendation_use": "usable_with_caveat",
            "consensus_level": "weak",
            "dominant_direction": "decrease",
            "conclusion_claim": "Egg intake reduces LDL cholesterol.",
            "plain_language_conclusion": "",
            "evidence_balance_summary": "",
            "recommendation_interpretation": None,
        }
    )

    assert "causal wording is not allowed" in errors


def test_evidence_derivation_stage_writes_outputs(tmp_path) -> None:
    paper_dir = tmp_path / "paper_1"
    paper_dir.mkdir()
    (paper_dir / "canonical_evidence.json").write_text(
        json.dumps({"canonical_evidence": [_canonical("ev_1")]}),
        encoding="utf-8",
    )
    (paper_dir / "experiment_map.json").write_text(json.dumps(_experiment_map()), encoding="utf-8")

    output = build_evidence_derivation_for_paper(paper_dir)

    assert output == paper_dir.resolve() / "general_evidence_artifacts.json"
    assert output.exists()
    assert (paper_dir / "rag_export.json").exists()
