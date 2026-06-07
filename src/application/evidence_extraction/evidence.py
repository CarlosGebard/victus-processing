from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.workspace import config as ctx
from src.application.evidence_extraction.llm_evidence import classify_paper, extract_canonical_evidence, map_experiment_scopes
from src.application.ports.llm import LLMClient
from src.application.ports.prompt_registry import PromptRegistry, PromptSpec
from src.infrastructure.prompts.compile import compile_template


EVIDENCE_SECTION_TYPES = {"methods", "results", "discussion", "conclusion"}
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
    "association",
    "correlation",
    "dose_response",
    "time_course",
    "subgroup_result",
    "mechanistic_result",
    "null_result",
    "adverse_effect",
    "feasibility_result",
    "descriptive_result",
    "specificity_or_selectivity_result",
    "other",
    "unclear",
}
ORGANISMS = {"human", "animal", "in_vitro", "mixed", "unclear", None}
DIRECTIONS = {
    "increase",
    "decrease",
    "no_change",
    "mixed",
    "positive_association",
    "negative_association",
    "not_applicable",
    "unclear",
}
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
    output_dir: Path
    model: str
    prompt_paper_classifier: Path
    prompt_results_scope_mapper: Path
    prompt_canonical_evidence_extractor: Path


def load_evidence_processing_config() -> EvidenceProcessingConfig:
    cfg = ctx.CONFIG.get("evidence") or {}
    return EvidenceProcessingConfig(
        output_dir=ctx.resolve_project_path(cfg.get("output_dir"), ctx.EVIDENCE_OUTPUT_DIR),
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
        normalized_scopes.append({"source_block_ids": source_block_ids})
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
        _validate_enum(item.get("evidence_type"), EVIDENCE_TYPES, f"canonical_evidence[{index}].evidence_type")
        _validate_enum(item.get("organism"), ORGANISMS, f"canonical_evidence[{index}].organism")
        _validate_enum(item.get("direction"), DIRECTIONS, f"canonical_evidence[{index}].direction")
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


async def run_pdf_evidence_async(
    input_path: Path,
    *,
    output_dir: Path | None = None,
    model: str | None = None,
    skip_existing: bool = False,
    llm_client: LLMClient | None = None,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
) -> Path:
    resolved_config = load_evidence_processing_config()
    output_root = output_dir.expanduser().resolve() if output_dir is not None else resolved_config.output_dir
    source_path = input_path.expanduser().resolve()
    source_payload = _read_json(source_path)
    paper_id = _paper_id_from_path_or_payload(source_path, source_payload)
    paper_output_dir = output_root / paper_id
    classifier_input_output = paper_output_dir / "paper.classifier_input.json"
    classification_output = paper_output_dir / "paper.classification.json"
    evidence_skipped_output = paper_output_dir / "evidence_skipped.json"
    trimmed_output = paper_output_dir / "trimmed.json"
    experiment_map_output = paper_output_dir / "experiment_map.json"
    experiment_packets_output = paper_output_dir / "experiment_packets.json"
    canonical_output = paper_output_dir / "canonical_evidence.json"
    if skip_existing and canonical_output.exists():
        return canonical_output

    if llm_client is None:
        raise RuntimeError("LLM client is required.")
    effective_model = model or resolved_config.model

    classifier_input = build_classifier_input(source_payload, paper_id=paper_id)
    validate_classifier_input(classifier_input)
    _write_json(classifier_input_output, classifier_input)

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
    )
    classification = validate_paper_classification(classification_raw)
    _write_json(classification_output, classification)
    if classification["paper_family"] != "primary_research":
        skipped = {
            "paper_id": paper_id,
            "reason": "non_primary_research",
            "paper_family": classification["paper_family"],
            "paper_type": classification["paper_type"],
            "evidence_generation_mode": classification["evidence_generation_mode"],
        }
        _write_json(evidence_skipped_output, skipped)
        return evidence_skipped_output

    trimmed = build_trimmed_paper(source_payload, paper_id=paper_id)
    validate_trimmed_paper(trimmed)
    _write_json(trimmed_output, trimmed)
    block_ids = {str(block["block_id"]) for block in trimmed["blocks"]}

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
        blocks=trimmed["blocks"],
        paper_id=paper_id,
        prompt_spec=experiment_spec,
        prompt_label=prompt_label,
        temperature=experiment_config.get("temperature"),
        max_tokens=experiment_config.get("max_tokens"),
    )
    experiment_map = validate_experiment_map(experiment_map_raw, block_ids=block_ids)
    _write_json(experiment_map_output, experiment_map)
    experiment_packets = build_experiment_packets(trimmed, experiment_map)
    _write_json(experiment_packets_output, {"experiment_packets": experiment_packets})

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
        )
        packet_canonical = validate_canonical_evidence(canonical_raw, block_ids=packet_block_ids)
        canonical["canonical_evidence"].extend(packet_canonical["canonical_evidence"])
        canonical["unextracted_packet_items"].extend(packet_canonical["unextracted_packet_items"])
    validate_canonical_evidence(canonical, block_ids=block_ids)
    _write_json(canonical_output, canonical)
    return canonical_output


def run_pdf_evidence(input_path: Path, **kwargs: Any) -> Path:
    return asyncio.run(run_pdf_evidence_async(input_path, **kwargs))


async def run_pdf_evidence_dir_async(
    input_dir: Path,
    *,
    output_dir: Path | None = None,
    pattern: str = "*/paper.processed.json",
    limit: int | None = None,
    **kwargs: Any,
) -> list[Path]:
    source_dir = input_dir.expanduser().resolve()
    outputs = []
    paths = sorted(source_dir.glob(pattern))
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be >= 1 when provided")
        paths = paths[:limit]
    for path in paths:
        outputs.append(await run_pdf_evidence_async(path, output_dir=output_dir, **kwargs))
    return outputs


def run_pdf_evidence_dir(input_dir: Path, **kwargs: Any) -> list[Path]:
    return asyncio.run(run_pdf_evidence_dir_async(input_dir, **kwargs))


def _normalize_block_id_list(value: Any, known_block_ids: set[str], label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    normalized = [str(item) for item in value]
    unknown = set(normalized).difference(known_block_ids)
    if unknown:
        raise ValueError(f"{label} references unknown block ids: {sorted(unknown)}")
    return normalized


def _validate_enum(value: Any, allowed: set[Any], label: str) -> None:
    if value not in allowed:
        raise ValueError(f"{label} invalid value: {value}")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _paper_id_from_path_or_payload(path: Path, payload: dict[str, Any]) -> str:
    paper_id = _paper_id_from_payload(payload)
    if paper_id != "paper":
        return paper_id
    if path.name in {"paper.processed.json", "paper.final.json", "paper.json"} and path.parent.name:
        return path.parent.name
    return path.stem


def _paper_id_from_payload(payload: dict[str, Any]) -> str:
    source_pdf = str(payload.get("source_pdf") or "").strip()
    if source_pdf:
        return Path(source_pdf).stem
    for block in payload.get("blocks") or []:
        if isinstance(block, dict) and str(block.get("paper_id") or "").strip():
            return str(block["paper_id"])
    return "paper"
