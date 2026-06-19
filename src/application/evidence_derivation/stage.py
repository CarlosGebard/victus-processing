from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.workspace import config as ctx
from src.application.evidence_derivation.general_evidence import (
    apply_llm_conclusions,
    build_general_evidence_artifacts,
    build_rag_export,
)
from src.application.ports.llm import LLMClient
from src.application.ports.prompt_registry import PromptRegistry, PromptSpec


DEFAULT_GENERAL_EVIDENCE_PROMPT = ctx.ROOT_DIR / "src/prompts/evidence_derivation/general_evidence.md"


def build_evidence_derivation_for_paper(
    paper_dir: Path,
    *,
    build_id: str | None = None,
    llm_client: LLMClient | None = None,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
    model: str | None = None,
    language: str = "en",
) -> Path:
    resolved_paper_dir = paper_dir.expanduser().resolve()
    canonical_path = resolved_paper_dir / "canonical_evidence.json"
    experiment_map_path = resolved_paper_dir / "experiment_map.json"
    if not canonical_path.exists():
        raise FileNotFoundError(f"Missing canonical evidence artifact: {canonical_path}")
    if not experiment_map_path.exists():
        raise FileNotFoundError(f"Missing experiment map artifact: {experiment_map_path}")

    canonical = _read_json(canonical_path)
    experiment_map = _read_json(experiment_map_path)
    evidence_items = canonical.get("canonical_evidence")
    if not isinstance(evidence_items, list):
        raise ValueError(f"canonical_evidence must be a list: {canonical_path}")

    artifacts = build_general_evidence_artifacts(
        canonical_evidence=evidence_items,
        experiment_map=experiment_map,
        build_id=build_id,
    )
    if llm_client is not None:
        prompt, prompt_spec = _load_prompt(
            prompt_registry,
            name="evidence_derivation/general_evidence",
            label=prompt_label,
            local_path=DEFAULT_GENERAL_EVIDENCE_PROMPT,
        )
        artifacts["general_evidence"] = apply_llm_conclusions(
            general_evidence=artifacts["general_evidence"],
            evidence_projections=artifacts["evidence_projections"],
            exposure_registry=artifacts["exposure_registry"],
            outcome_registry=artifacts["outcome_registry"],
            llm_client=llm_client,
            model=model or "litellm_proxy/gemini-flash-lite",
            prompt=prompt,
            prompt_spec=prompt_spec,
            prompt_label=prompt_label,
            language=language,
        )
        artifacts["rag_export"] = build_rag_export(
            general_evidence=artifacts["general_evidence"],
            evidence_projections=artifacts["evidence_projections"],
        )

    output_path = resolved_paper_dir / "general_evidence_artifacts.json"
    rag_path = resolved_paper_dir / "rag_export.json"
    _write_json(output_path, artifacts)
    _write_json(rag_path, artifacts["rag_export"])
    return output_path


def build_evidence_derivation_dir(
    input_dir: Path,
    *,
    pattern: str = "*/canonical_evidence.json",
    limit: int | None = None,
    **kwargs: Any,
) -> list[Path]:
    resolved_input_dir = input_dir.expanduser().resolve()
    paths = sorted(resolved_input_dir.glob(pattern))
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be >= 1 when provided")
        paths = paths[:limit]
    outputs = []
    for canonical_path in paths:
        outputs.append(build_evidence_derivation_for_paper(canonical_path.parent, **kwargs))
    return outputs


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
