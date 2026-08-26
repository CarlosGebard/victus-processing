from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.workspace import config as ctx
from src.application.evidence_derivation.general_evidence import build_general_evidence_artifacts
from src.application.evidence_extraction.llm_evidence import classify_paper, extract_canonical_evidence, map_experiment_scopes
from src.application.ports.llm import LLMClient
from src.application.ports.prompt_registry import PromptRegistry, PromptSpec
from src.application.scientific_output_store import (
    ScientificOutputStore,
    persist_canonical_evidence,
    persist_experiment_map,
    persist_paper_classification,
    stable_experiment_map_id,
)
from src.infrastructure.prompts.compile import compile_template


EVIDENCE_SECTION_TYPES = {"methods", "results", "discussion", "conclusion"}
EvidenceProgressCallback = Callable[[str, dict[str, Any]], None]
CLASSIFIER_EXCLUDED_SECTION_TYPES = {
    "front_matter",
    "references",
    "acknowledgements",
    "funding",
    "disclosure",
    "ethics",
    "appendix",
    "supplementary",
}
PAPER_FAMILIES = {
    "primary_research",
    "evidence_synthesis",
    "methodological",
    "case_based",
    "opinion_or_theory",
    "unknown",
}
EVIDENCE_GENERATION_MODES = {
    "generates_original_data",
    "synthesizes_existing_evidence",
    "proposes_method",
    "reports_cases",
    "argues_or_interprets",
    "unclear",
}
EVIDENCE_TYPES = {
    "between_group_result",
    "within_group_change",
    "dose_response",
    "time_course",
    "feasibility_result",
    "specificity_or_selectivity_result",
    "other",
    "unclear",
}
LEGACY_EVIDENCE_TYPE_MAP = {
    "association": "other",
    "correlation": "other",
    "subgroup_result": "other",
    "mechanistic_result": "other",
    "null_result": "other",
    "adverse_effect": "other",
    "descriptive_result": "other",
}
ORGANISMS = {"human", "animal", "in_vitro", "mixed", "unclear", None}
DIRECTIONS = {
    "increase",
    "decrease",
    "no_effect",
    "mixed",
    "not_applicable",
    "unclear",
}
LEGACY_DIRECTION_MAP = {
    "no_change": "no_effect",
    "positive_association": "increase",
    "negative_association": "decrease",
}
STUDY_DESIGNS = {
    "rct",
    "prospective_cohort",
    "retrospective_cohort",
    "case_control",
    "cross_sectional",
    "meta_analysis",
    "systematic_review",
    "animal_experiment",
    "in_vitro",
    "mechanistic_experiment",
    "descriptive_microbiome",
    "method_validation",
    "unclear",
}
STUDY_ROLES = {
    "main_study",
    "secondary_analysis",
    "subgroup_analysis",
    "sensitivity_analysis",
    "mechanistic_substudy",
    "external_meta_analysis",
    "method_validation",
    "unclear",
}
EVIDENCE_ROLES = {
    "primary_result",
    "secondary_result",
    "subgroup_result",
    "sensitivity_result",
    "mechanistic_result",
    "descriptive_result",
    "adverse_event",
    "limitation",
    "method_detail",
    "background_context",
    "unclear",
}
ASSERTION_TYPES = {
    "causal_effect",
    "comparative_effect",
    "association",
    "no_association",
    "descriptive_comparison",
    "mechanistic_link",
    "methodological",
    "safety_signal",
    "unclear",
}
CANONICAL_STATUSES = {"accepted", "needs_review", "rejected"}
OBSERVATION_ROLES = {"primary_finding", "quantitative_support", "context_support", "limitation_or_caution"}
UNEXTRACTED_REASONS = {
    "background_only",
    "method_only",
    "unsupported_interpretation",
    "insufficient_context",
    "duplicate_finding_pattern",
    "not_scientific_finding",
    "unknown",
}


@dataclass(frozen=True)
class EvidenceProcessingConfig:
    model: str
    prompt_paper_classifier: Path
    prompt_results_scope_mapper: Path
    prompt_canonical_evidence_extractor: Path
    request_timeout_seconds: float


def load_evidence_processing_config() -> EvidenceProcessingConfig:
    cfg = ctx.CONFIG.get("evidence") or {}
    return EvidenceProcessingConfig(
        model=str(cfg.get("model", "litellm_proxy/gemini-flash-lite")),
        prompt_paper_classifier=ctx.resolve_project_path(
            cfg.get("prompt_paper_classifier"),
            ctx.ROOT_DIR / "src/prompts/evidence_extraction/paper_classifier.md",
        ),
        prompt_results_scope_mapper=ctx.resolve_project_path(
            cfg.get("prompt_results_scope_mapper"),
            ctx.ROOT_DIR / "src/prompts/evidence_extraction/results_scope_mapper.md",
        ),
        prompt_canonical_evidence_extractor=ctx.resolve_project_path(
            cfg.get("prompt_canonical_evidence_extractor"),
            ctx.ROOT_DIR / "src/prompts/evidence_extraction/canonical_evidence_extractor.md",
        ),
        request_timeout_seconds=float(cfg.get("request_timeout_seconds", 120)),
    )


def build_classifier_input(payload: dict[str, Any], *, paper_id: str | None = None) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    source_paper_id = paper_id or _paper_id_from_payload(payload)
    blocks: list[dict[str, Any]] = []
    for block in payload.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        section_type = str(block.get("section_type") or "unknown")
        if section_type in CLASSIFIER_EXCLUDED_SECTION_TYPES:
            continue
        cleaned = dict(block)
        cleaned["paper_id"] = str(cleaned.get("paper_id") or source_paper_id)
        cleaned.pop("section_registry", None)
        cleaned.pop("updated_section_registry", None)
        cleaned.pop("batch_end", None)
        cleaned.pop("batch_ends", None)
        cleaned.pop("batch_warnings", None)
        blocks.append(cleaned)
    return {"metadata": dict(metadata), "blocks": blocks}


def validate_classifier_input(payload: dict[str, Any]) -> None:
    if set(payload) != {"metadata", "blocks"}:
        raise ValueError("Paper classifier input must contain only metadata and blocks")
    if not isinstance(payload["metadata"], dict):
        raise ValueError("Paper classifier metadata must be an object")
    if not isinstance(payload["blocks"], list):
        raise ValueError("Paper classifier blocks must be a list")
    for index, block in enumerate(payload["blocks"]):
        if not isinstance(block, dict):
            raise ValueError(f"Paper classifier block {index} must be an object")
        for key in ("block_id", "paper_id", "section_path", "section_type", "content_kind", "text"):
            if key not in block:
                raise ValueError(f"Paper classifier block {index} missing {key}")
        if block["section_type"] in CLASSIFIER_EXCLUDED_SECTION_TYPES:
            raise ValueError(f"Paper classifier block {index} has excluded section_type: {block['section_type']}")
        if not str(block["text"]).strip():
            raise ValueError(f"Paper classifier block {index} text must be non-empty")


def validate_paper_classification(payload: dict[str, Any]) -> dict[str, Any]:
    required = {
        "paper_family",
        "paper_type",
        "evidence_generation_mode",
        "has_original_experiments",
        "has_systematic_search",
        "has_meta_analysis",
        "classification_confidence",
        "quality_flags",
        "risk_flags",
        "routing_evidence",
        "reasoning_summary",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"Paper classification missing fields: {sorted(missing)}")
    _validate_enum(payload.get("paper_family"), PAPER_FAMILIES, "paper_classification.paper_family")
    _validate_enum(
        payload.get("evidence_generation_mode"),
        EVIDENCE_GENERATION_MODES,
        "paper_classification.evidence_generation_mode",
    )
    if not isinstance(payload.get("paper_type"), str) or not payload["paper_type"].strip():
        raise ValueError("Paper classification paper_type must be a non-empty string")
    for key in ("has_original_experiments", "has_systematic_search", "has_meta_analysis"):
        if not isinstance(payload.get(key), bool):
            raise ValueError(f"Paper classification {key} must be a boolean")
    confidence = payload.get("classification_confidence")
    if not isinstance(confidence, int | float) or not 0 <= float(confidence) <= 1:
        raise ValueError("Paper classification confidence must be a number between 0 and 1")
    for key in ("quality_flags", "risk_flags", "routing_evidence"):
        if not isinstance(payload.get(key), list):
            raise ValueError(f"Paper classification {key} must be a list")
    if not isinstance(payload.get("reasoning_summary"), str):
        raise ValueError("Paper classification reasoning_summary must be a string")
    return {key: payload[key] for key in required}


def build_trimmed_paper(payload: dict[str, Any], *, paper_id: str | None = None) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    source_paper_id = paper_id or _paper_id_from_payload(payload)
    blocks: list[dict[str, Any]] = []
    for block in payload.get("blocks") or []:
        if not isinstance(block, dict) or block.get("section_type") not in EVIDENCE_SECTION_TYPES:
            continue
        cleaned = dict(block)
        cleaned["paper_id"] = str(cleaned.get("paper_id") or source_paper_id)
        cleaned.pop("section_registry", None)
        cleaned.pop("updated_section_registry", None)
        cleaned.pop("batch_end", None)
        cleaned.pop("batch_ends", None)
        cleaned.pop("batch_warnings", None)
        quality = cleaned.get("quality")
        if isinstance(quality, dict):
            cleaned["quality"] = {
                key: value for key, value in quality.items() if key not in {"is_truncated", "is_duplicate"}
            }
            if not cleaned["quality"]:
                cleaned.pop("quality", None)
        blocks.append(cleaned)
    return {"metadata": dict(metadata), "blocks": blocks}


def validate_trimmed_paper(payload: dict[str, Any]) -> None:
    if set(payload) != {"metadata", "blocks"}:
        raise ValueError("Trimmed evidence input must contain only metadata and blocks")
    if not isinstance(payload["metadata"], dict):
        raise ValueError("Trimmed evidence metadata must be an object")
    if not isinstance(payload["blocks"], list):
        raise ValueError("Trimmed evidence blocks must be a list")
    for index, block in enumerate(payload["blocks"]):
        if not isinstance(block, dict):
            raise ValueError(f"Trimmed block {index} must be an object")
        for key in ("block_id", "paper_id", "section_path", "section_type", "content_kind", "text"):
            if key not in block:
                raise ValueError(f"Trimmed block {index} missing {key}")
        if block["section_type"] not in EVIDENCE_SECTION_TYPES:
            raise ValueError(f"Trimmed block {index} has invalid section_type: {block['section_type']}")
        if not str(block["text"]).strip():
            raise ValueError(f"Trimmed block {index} text must be non-empty")


def validate_experiment_map(payload: dict[str, Any], *, block_ids: set[str]) -> dict[str, Any]:
    scopes = payload.get("experiment_scopes")
    unmapped = payload.get("unmapped_block_ids", [])
    if not isinstance(scopes, list):
        raise ValueError("Experiment map must contain experiment_scopes list")
    if not isinstance(unmapped, list):
        raise ValueError("Experiment map unmapped_block_ids must be a list")
    normalized_scopes: list[dict[str, Any]] = []
    referenced: set[str] = set()
    for index, scope in enumerate(scopes):
        if not isinstance(scope, dict):
            raise ValueError(f"Experiment scope {index} must be an object")
        source_block_ids = _normalize_block_id_list(scope.get("source_block_ids"), block_ids, f"Experiment scope {index}")
        referenced.update(source_block_ids)
        study_id = str(scope.get("study_id") or scope.get("experiment_scope_id") or f"study_{index + 1}")
        study_design = str(scope.get("study_design") or "unclear")
        study_role = str(scope.get("study_role_in_paper") or "unclear")
        _validate_enum(study_design, STUDY_DESIGNS, f"experiment_scopes[{index}].study_design")
        _validate_enum(study_role, STUDY_ROLES, f"experiment_scopes[{index}].study_role_in_paper")
        normalized_scopes.append(
            {
                "experiment_scope_id": str(scope.get("experiment_scope_id") or study_id),
                "study_id": study_id,
                "source_block_ids": source_block_ids,
                "study_design": study_design,
                "study_role_in_paper": study_role,
            }
        )
    normalized_unmapped = _normalize_block_id_list(unmapped, block_ids, "Experiment map unmapped_block_ids")
    referenced.update(normalized_unmapped)
    unknown = referenced.difference(block_ids)
    if unknown:
        raise ValueError(f"Experiment map references unknown block ids: {sorted(unknown)}")
    return {"experiment_scopes": normalized_scopes, "unmapped_block_ids": normalized_unmapped}


def build_experiment_packets(trimmed: dict[str, Any], experiment_map: dict[str, Any]) -> list[dict[str, Any]]:
    blocks = trimmed.get("blocks") or []
    block_by_id = {str(block.get("block_id")): block for block in blocks if isinstance(block, dict)}
    packets: list[dict[str, Any]] = []
    for index, scope in enumerate(experiment_map.get("experiment_scopes") or []):
        if not isinstance(scope, dict):
            raise ValueError(f"Experiment scope {index} must be an object")
        source_block_ids = [str(block_id) for block_id in scope.get("source_block_ids") or []]
        packet_blocks = []
        for block_id in source_block_ids:
            block = block_by_id.get(block_id)
            if block is None:
                raise ValueError(f"Experiment packet {index} references unknown block id: {block_id}")
            packet_blocks.append(block)
        if not packet_blocks:
            raise ValueError(f"Experiment packet {index} must contain at least one block")
        packets.append(
            {
                "scope_index": index,
                "paper_id": experiment_map.get("paper_id"),
                "experiment_map_id": experiment_map.get("experiment_map_id"),
                "experiment_scope_id": scope.get("experiment_scope_id"),
                "study_id": scope.get("study_id") or scope.get("experiment_scope_id") or f"study_{index + 1}",
                "study_design": scope.get("study_design") or "unclear",
                "study_role_in_paper": scope.get("study_role_in_paper") or "unclear",
                "source_block_ids": source_block_ids,
                "blocks": packet_blocks,
            }
        )
    return packets


def validate_canonical_evidence(payload: dict[str, Any], *, block_ids: set[str]) -> dict[str, Any]:
    evidence_items = payload.get("canonical_evidence")
    unextracted_items = payload.get("unextracted_packet_items", [])
    if not isinstance(evidence_items, list):
        raise ValueError("Canonical evidence output must contain canonical_evidence list")
    if not isinstance(unextracted_items, list):
        raise ValueError("Canonical evidence unextracted_packet_items must be a list")
    normalized_evidence = []
    for index, item in enumerate(evidence_items):
        if not isinstance(item, dict):
            raise ValueError(f"Canonical evidence item {index} must be an object")
        item = _normalize_canonical_evidence_item(item)
        _validate_enum(item.get("evidence_type"), EVIDENCE_TYPES, f"canonical_evidence[{index}].evidence_type")
        _validate_enum(item.get("evidence_role_in_paper"), EVIDENCE_ROLES, f"canonical_evidence[{index}].evidence_role_in_paper")
        _validate_enum(item.get("assertion_type"), ASSERTION_TYPES, f"canonical_evidence[{index}].assertion_type")
        _validate_enum(item.get("organism"), ORGANISMS, f"canonical_evidence[{index}].organism")
        _validate_enum(item.get("effect_direction"), DIRECTIONS, f"canonical_evidence[{index}].effect_direction")
        _validate_enum(
            item.get("canonical_evidence_status"),
            CANONICAL_STATUSES,
            f"canonical_evidence[{index}].canonical_evidence_status",
        )
        if not isinstance(item.get("raw_outcomes"), list):
            raise ValueError(f"Canonical evidence item {index} raw_outcomes must be a list")
        if not str(item.get("evidence_text") or "").strip():
            raise ValueError(f"Canonical evidence item {index} evidence_text must be non-empty")
        source_block_ids = _normalize_block_id_list(
            item.get("source_block_ids"),
            block_ids,
            f"canonical_evidence[{index}].source_block_ids",
        )
        if not source_block_ids:
            raise ValueError(f"Canonical evidence item {index} requires source_block_ids")
        observations = item.get("observations")
        if not isinstance(observations, list) or not observations:
            raise ValueError(f"Canonical evidence item {index} requires observations")
        normalized_observations = []
        for observation_index, observation in enumerate(observations):
            if not isinstance(observation, dict):
                raise ValueError(f"canonical_evidence[{index}].observations[{observation_index}] must be an object")
            source_block_id = str(observation.get("source_block_id") or "")
            if source_block_id not in block_ids:
                raise ValueError(
                    f"canonical_evidence[{index}].observations[{observation_index}].source_block_id "
                    f"references unknown block id: {source_block_id}"
                )
            source_quote = str(observation.get("source_quote") or "").strip()
            if not source_quote:
                raise ValueError(
                    f"canonical_evidence[{index}].observations[{observation_index}].source_quote must be non-empty"
                )
            observation_role = observation.get("observation_role")
            _validate_enum(
                observation_role,
                OBSERVATION_ROLES,
                f"canonical_evidence[{index}].observations[{observation_index}].observation_role",
            )
            normalized_observations.append(
                {
                    "source_block_id": source_block_id,
                    "source_quote": source_quote,
                    "observation_role": observation_role,
                }
            )
        quantitative_data = item.get("quantitative_data")
        if isinstance(quantitative_data, dict):
            for value_index, value in enumerate(quantitative_data.get("values") or []):
                if not isinstance(value, dict):
                    raise ValueError(f"canonical_evidence[{index}].quantitative_data.values[{value_index}] must be an object")
                source_block_id = str(value.get("source_block_id") or "")
                if source_block_id not in block_ids:
                    raise ValueError(
                        f"canonical_evidence[{index}].quantitative_data.values[{value_index}].source_block_id "
                        f"references unknown block id: {source_block_id}"
                    )
        normalized = dict(item)
        normalized["observations"] = normalized_observations
        normalized["source_block_ids"] = source_block_ids
        normalized_evidence.append(normalized)
    normalized_unextracted = []
    for index, item in enumerate(unextracted_items):
        if not isinstance(item, dict):
            raise ValueError(f"Unextracted item {index} must be an object")
        reason = item.get("reason")
        _validate_enum(reason, UNEXTRACTED_REASONS, f"unextracted_packet_items[{index}].reason")
        normalized_unextracted.append(
            {
                "source_block_ids": _normalize_block_id_list(
                    item.get("source_block_ids", []),
                    block_ids,
                    f"unextracted_packet_items[{index}].source_block_ids",
                ),
                "reason": reason,
            }
        )
    return {"canonical_evidence": normalized_evidence, "unextracted_packet_items": normalized_unextracted}


def _normalize_canonical_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    evidence_type = normalized.get("evidence_type")
    normalized["evidence_type"] = LEGACY_EVIDENCE_TYPE_MAP.get(str(evidence_type), evidence_type)
    direction = normalized.get("effect_direction", normalized.get("direction"))
    normalized["effect_direction"] = LEGACY_DIRECTION_MAP.get(str(direction), direction)
    normalized.pop("direction", None)
    normalized["raw_exposure"] = normalized.get("raw_exposure", normalized.get("intervention_or_exposure"))
    normalized.pop("intervention_or_exposure", None)
    normalized["raw_outcomes"] = normalized.get("raw_outcomes", normalized.get("outcomes") or [])
    normalized.pop("outcomes", None)
    normalized.setdefault("study_id", str(normalized.get("experiment_scope_id") or "unclear"))
    normalized.setdefault("evidence_role_in_paper", _default_evidence_role(normalized))
    normalized.setdefault("assertion_type", _default_assertion_type(normalized))
    normalized.setdefault("canonical_evidence_status", "accepted")
    if not isinstance(normalized.get("quantitative_data"), dict):
        normalized["quantitative_data"] = {"summary": None, "values": []}
    return normalized


def _default_evidence_role(item: dict[str, Any]) -> str:
    evidence_type = item.get("evidence_type")
    if evidence_type == "specificity_or_selectivity_result":
        return "mechanistic_result"
    if evidence_type == "feasibility_result":
        return "secondary_result"
    return "primary_result"


def _default_assertion_type(item: dict[str, Any]) -> str:
    evidence_type = item.get("evidence_type")
    direction = item.get("effect_direction")
    if direction == "no_effect":
        return "no_association"
    if evidence_type == "specificity_or_selectivity_result":
        return "mechanistic_link"
    if evidence_type == "between_group_result":
        return "comparative_effect"
    return "unclear"


async def run_pdf_evidence_async(
    paper_id: str,
    *,
    model: str | None = None,
    skip_existing: bool = False,
    llm_client: LLMClient | None = None,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
    output_store: ScientificOutputStore | None = None,
    producer_run_id: str | None = None,
    progress: EvidenceProgressCallback | None = None,
) -> str:
    if output_store is None:
        raise RuntimeError("PostgreSQL scientific output store is required")
    resolved_config = load_evidence_processing_config()
    source_payload = _structured_paper_from_store(output_store, paper_id)
    if not source_payload:
        raise FileNotFoundError(f"Structured paper not found in PostgreSQL: {paper_id}")
    if skip_existing and output_store.has_canonical_evidence(paper_id):
        _emit_progress(progress, "skip", paper_id=paper_id, reason="existing")
        return paper_id

    if llm_client is None:
        raise RuntimeError("LLM client is required.")
    effective_model = model or resolved_config.model

    classifier_input = build_classifier_input(source_payload, paper_id=paper_id)
    validate_classifier_input(classifier_input)

    classifier_prompt, classifier_spec = _load_prompt(
        prompt_registry,
        name="evidence_extraction/paper_classifier",
        label=prompt_label,
        local_path=resolved_config.prompt_paper_classifier,
    )
    classifier_config = classifier_spec.config if classifier_spec else {}
    classification_raw = await classify_paper(
        llm_client,
        model=str(classifier_config.get("model") or effective_model),
        prompt=compile_template(classifier_prompt, {}),
        metadata=classifier_input["metadata"],
        blocks=classifier_input["blocks"],
        paper_id=paper_id,
        prompt_spec=classifier_spec,
        prompt_label=prompt_label,
        temperature=classifier_config.get("temperature"),
        max_tokens=classifier_config.get("max_tokens"),
        timeout_seconds=float(classifier_config.get("request_timeout_seconds") or resolved_config.request_timeout_seconds),
    )
    classification = validate_paper_classification(classification_raw)
    persist_paper_classification(
        output_store,
        paper_id=paper_id,
        classification=classification,
        producer_run_id=producer_run_id,
    )
    _emit_progress(
        progress,
        "classified",
        paper_id=paper_id,
        paper_family=classification["paper_family"],
    )
    if classification["paper_family"] != "primary_research":
        _emit_progress(
            progress,
            "done",
            paper_id=paper_id,
            evidence_rows=0,
            reason="non_primary_research",
        )
        return paper_id

    trimmed = build_trimmed_paper(source_payload, paper_id=paper_id)
    validate_trimmed_paper(trimmed)
    evidence_blocks = trimmed["blocks"]
    block_ids = {str(block["block_id"]) for block in evidence_blocks}

    experiment_prompt, experiment_spec = _load_prompt(
        prompt_registry,
        name="evidence_extraction/results_scope_mapper",
        label=prompt_label,
        local_path=resolved_config.prompt_results_scope_mapper,
    )
    experiment_config = experiment_spec.config if experiment_spec else {}
    experiment_map_raw = await map_experiment_scopes(
        llm_client,
        model=str(experiment_config.get("model") or effective_model),
        prompt=compile_template(experiment_prompt, {}),
        blocks=evidence_blocks,
        paper_id=paper_id,
        prompt_spec=experiment_spec,
        prompt_label=prompt_label,
        temperature=experiment_config.get("temperature"),
        max_tokens=experiment_config.get("max_tokens"),
        timeout_seconds=float(experiment_config.get("request_timeout_seconds") or resolved_config.request_timeout_seconds),
    )
    experiment_map = validate_experiment_map(experiment_map_raw, block_ids=block_ids)
    experiment_map = {
        **experiment_map,
        "paper_id": paper_id,
        "experiment_map_id": stable_experiment_map_id(paper_id, experiment_map),
    }
    persist_experiment_map(
        output_store,
        paper_id=paper_id,
        experiment_map=experiment_map,
        producer_run_id=producer_run_id,
    )
    _emit_progress(
        progress,
        "mapped",
        paper_id=paper_id,
        experiments=len(experiment_map["experiment_scopes"]),
    )
    experiment_packets = build_experiment_packets({"metadata": trimmed["metadata"], "blocks": evidence_blocks}, experiment_map)

    canonical_prompt, canonical_spec = _load_prompt(
        prompt_registry,
        name="evidence_extraction/canonical_evidence_extractor",
        label=prompt_label,
        local_path=resolved_config.prompt_canonical_evidence_extractor,
    )
    canonical_config = canonical_spec.config if canonical_spec else {}
    canonical = {"canonical_evidence": [], "unextracted_packet_items": []}
    for packet in experiment_packets:
        packet_block_ids = {str(block_id) for block_id in packet["source_block_ids"]}
        canonical_raw = await extract_canonical_evidence(
            llm_client,
            model=str(canonical_config.get("model") or effective_model),
            prompt=compile_template(canonical_prompt, {}),
            experiment_packet=packet,
            paper_id=paper_id,
            prompt_spec=canonical_spec,
            prompt_label=prompt_label,
            temperature=canonical_config.get("temperature"),
            max_tokens=canonical_config.get("max_tokens"),
            timeout_seconds=float(canonical_config.get("request_timeout_seconds") or resolved_config.request_timeout_seconds),
        )
        packet_canonical = validate_canonical_evidence(canonical_raw, block_ids=packet_block_ids)
        canonical["canonical_evidence"].extend(
            _attach_canonical_identity_and_context(
                packet_canonical["canonical_evidence"],
                paper_id=paper_id,
                packet=packet,
                experiment_map_id=str(experiment_map.get("experiment_map_id") or ""),
            )
        )
        canonical["unextracted_packet_items"].extend(packet_canonical["unextracted_packet_items"])
    canonical = validate_canonical_evidence(canonical, block_ids=block_ids)
    persist_canonical_evidence(
        output_store,
        paper_id=paper_id,
        canonical=canonical,
        experiment_map_id=experiment_map.get("experiment_map_id"),
        producer_run_id=producer_run_id,
    )
    derived_artifacts = build_general_evidence_artifacts(
        canonical_evidence=canonical["canonical_evidence"],
        experiment_map=experiment_map,
        build_id=producer_run_id,
    )
    output_store.replace_evidence_derivation_build(derived_artifacts)
    _emit_progress(
        progress,
        "done",
        paper_id=paper_id,
        evidence_rows=len(canonical["canonical_evidence"]),
    )
    return paper_id


def run_pdf_evidence(paper_id: str, **kwargs: Any) -> str:
    return asyncio.run(run_pdf_evidence_async(paper_id, **kwargs))


async def run_pdf_evidence_db_async(
    *,
    store: ScientificOutputStore,
    paper_id: str | None = None,
    limit: int | None = None,
    workers: int = 1,
    progress: EvidenceProgressCallback | None = None,
    **kwargs: Any,
) -> list[str]:
    if workers < 1:
        raise ValueError("workers must be >= 1")
    if paper_id:
        paper_ids = [paper_id]
    else:
        paper_ids = store.fetch_structured_paper_ids(limit=limit)
    outputs: list[str] = []
    total = len(paper_ids)
    queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
    for index, current_paper_id in enumerate(paper_ids, start=1):
        queue.put_nowait((index, current_paper_id))

    async def worker() -> None:
        while True:
            try:
                index, current_paper_id = queue.get_nowait()
            except asyncio.QueueEmpty:
                return

            def indexed_progress(event: str, details: dict[str, Any]) -> None:
                _emit_progress(progress, event, index=index, total=total, **details)

            indexed_progress("start", {"paper_id": current_paper_id})
            try:
                outputs.append(
                    await run_pdf_evidence_async(
                        current_paper_id,
                        output_store=store,
                        progress=indexed_progress,
                        **kwargs,
                    )
                )
            except Exception as exc:
                indexed_progress("error", {"paper_id": current_paper_id, "error": str(exc)})
                raise
            finally:
                queue.task_done()

    if not paper_ids:
        return outputs
    await asyncio.gather(*(worker() for _ in range(min(workers, len(paper_ids)))))
    return outputs

def run_pdf_evidence_db(*, store: ScientificOutputStore, **kwargs: Any) -> list[str]:
    return asyncio.run(run_pdf_evidence_db_async(store=store, **kwargs))


def _emit_progress(
    progress: EvidenceProgressCallback | None,
    event: str,
    **details: Any,
) -> None:
    if progress is not None:
        progress(event, details)


def _normalize_block_id_list(value: Any, known_block_ids: set[str], label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    normalized = [str(item) for item in value]
    unknown = set(normalized).difference(known_block_ids)
    if unknown:
        raise ValueError(f"{label} references unknown block ids: {sorted(unknown)}")
    return normalized


def _attach_canonical_identity_and_context(
    items: list[dict[str, Any]],
    *,
    paper_id: str,
    packet: dict[str, Any],
    experiment_map_id: str,
) -> list[dict[str, Any]]:
    output = []
    for index, item in enumerate(items):
        normalized = dict(item)
        normalized["paper_id"] = paper_id
        normalized["study_id"] = str(packet.get("study_id") or packet.get("experiment_scope_id") or "unclear")
        normalized["experiment_map_id"] = experiment_map_id
        normalized["experiment_scope_id"] = str(packet.get("experiment_scope_id") or normalized["study_id"])
        normalized.setdefault(
            "canonical_evidence_id",
            _stable_id("canonical_evidence", paper_id, normalized["study_id"], index, normalized),
        )
        output.append(normalized)
    return output


def _validate_enum(value: Any, allowed: set[Any], label: str) -> None:
    if value not in allowed:
        raise ValueError(f"{label} invalid value: {value}")


def _stable_id(prefix: str, *parts: Any) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()}"


def _load_prompt(
    registry: PromptRegistry | None,
    *,
    name: str,
    label: str,
    local_path: Path,
) -> tuple[str, PromptSpec | None]:
    if registry is not None:
        try:
            spec = registry.get(name, label=label)
            return spec.template, spec
        except Exception:
            pass
    if not local_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {local_path}")
    return local_path.read_text(encoding="utf-8"), None


def _paper_id_from_payload(payload: dict[str, Any]) -> str:
    paper_id = str(payload.get("paper_id") or "").strip()
    if paper_id:
        return paper_id
    source_pdf = str(payload.get("source_pdf") or "").strip()
    if source_pdf:
        return Path(source_pdf).stem
    for block in payload.get("blocks") or []:
        if isinstance(block, dict) and str(block.get("paper_id") or "").strip():
            return str(block["paper_id"])
    return "paper"


def _structured_paper_from_store(store: ScientificOutputStore | None, paper_id: str) -> dict[str, Any] | None:
    if store is None:
        return None
    payload = store.fetch_structured_paper(paper_id)
    if payload is None:
        return None
    return {**payload, "paper_id": str(payload.get("paper_id") or paper_id)}
