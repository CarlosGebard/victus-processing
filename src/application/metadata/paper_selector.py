from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.application.ports.llm import LLMClient, LLMRequest
from src.application.ports.prompt_registry import PromptRegistry, PromptSpec
from src.infrastructure.prompts.compile import compile_template
from src.prompts import (
    build_paper_selector_user_prompt,
    get_paper_selector_system_prompt,
)

DEFAULT_DOTENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def load_dotenv(dotenv_path: str | Path = DEFAULT_DOTENV_PATH) -> dict[str, str]:
    path = Path(dotenv_path).resolve()
    values: dict[str, str] = {}

    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value

    return values


def get_env_value(name: str, default: str = "", dotenv_path: str | Path = DEFAULT_DOTENV_PATH) -> str:
    if name in os.environ:
        env_value = os.environ[name].strip()
        if env_value:
            return env_value

    dotenv_values = load_dotenv(dotenv_path)
    dotenv_value = dotenv_values.get(name, "").strip()
    return dotenv_value or default


OUTPUT_SCHEMA: dict[str, Any] = {
    "name": "paper_selection_decisions",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "decision": {
                            "type": "string",
                            "enum": ["keep", "drop", "uncertain"],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "decision", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["decisions"],
        "additionalProperties": False,
    },
}


@dataclass
class PaperCandidate:
    id: str
    title: str
    abstract_preview: str


def build_user_prompt(candidates: list[PaperCandidate]) -> str:
    return build_paper_selector_user_prompt(candidates)


def build_responses_payload(
    model: str,
    candidates: list[PaperCandidate],
    *,
    selection_profile: str = "broad-nutrition",
) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": get_paper_selector_system_prompt(selection_profile),
            },
            {"role": "user", "content": build_user_prompt(candidates)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": OUTPUT_SCHEMA["name"],
                "strict": OUTPUT_SCHEMA["strict"],
                "schema": OUTPUT_SCHEMA["schema"],
            }
        },
    }


def extract_output_text(response_json: dict[str, Any]) -> str:
    output = response_json.get("output", [])
    if not isinstance(output, list):
        raise ValueError("La respuesta del modelo no contiene una lista válida en 'output'.")

    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise ValueError("No se encontró texto JSON en la respuesta del modelo.")


def normalize_decisions_text(
    raw_text: str,
    candidates: list[PaperCandidate],
) -> list[dict[str, str]]:
    parsed = json.loads(raw_text)
    return _normalize_decision_payload(parsed, candidates)


def normalize_decisions(
    response_json: dict[str, Any],
    candidates: list[PaperCandidate],
) -> list[dict[str, str]]:
    raw_text = extract_output_text(response_json)
    parsed = json.loads(raw_text)
    return _normalize_decision_payload(parsed, candidates)


def _normalize_decision_payload(
    parsed: dict[str, Any],
    candidates: list[PaperCandidate],
) -> list[dict[str, str]]:
    decisions = parsed.get("decisions", [])
    if not isinstance(decisions, list):
        raise ValueError("La respuesta JSON del modelo no contiene una lista válida en 'decisions'.")

    valid_ids = {candidate.id for candidate in candidates}
    normalized: list[dict[str, str]] = []

    for item in decisions:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "")).strip()
        decision = str(item.get("decision", "")).strip()
        reason = str(item.get("reason", "")).strip()

        if item_id not in valid_ids:
            continue
        if decision not in {"keep", "drop", "uncertain"}:
            continue

        normalized.append(
            {
                "id": item_id,
                "decision": decision,
                "reason": reason,
            }
        )

    missing_ids = valid_ids - {item["id"] for item in normalized}
    for missing_id in sorted(missing_ids):
        normalized.append(
            {
                "id": missing_id,
                "decision": "uncertain",
                "reason": "missing_from_model_output",
            }
        )

    return sorted(normalized, key=lambda item: item["id"])


def classify_papers_with_llm(
    candidates: list[PaperCandidate],
    model: str,
    *,
    selection_profile: str = "broad-nutrition",
    client: LLMClient,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
    dotenv_path: str | Path = DEFAULT_DOTENV_PATH,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    prompt_name = "paper-selector-dataset-gaps" if selection_profile == "dataset-gaps" else "paper-selector"
    prompt_spec: PromptSpec | None = None
    system_prompt = get_paper_selector_system_prompt(selection_profile)
    if prompt_registry is not None:
        prompt_spec = prompt_registry.get(prompt_name, label=prompt_label)
        system_prompt = compile_template(prompt_spec.template, {})
    prompt_config = prompt_spec.config if prompt_spec else {}
    effective_model = str(prompt_config.get("model") or model)
    effective_temperature = prompt_config.get("temperature")
    response = client.complete(
        LLMRequest(
            operation="metadata.paper_selection",
            model=effective_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": build_user_prompt(candidates)},
            ],
            temperature=effective_temperature,
            max_tokens=prompt_config.get("max_tokens"),
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": OUTPUT_SCHEMA["name"],
                    "strict": OUTPUT_SCHEMA["strict"],
                    "schema": OUTPUT_SCHEMA["schema"],
                },
            },
            metadata={
                "selection_profile": selection_profile,
                "candidate_count": len(candidates),
                "prompt_name": prompt_spec.name if prompt_spec else f"legacy.{prompt_name}",
                "prompt_version": prompt_spec.version if prompt_spec else None,
                "prompt_label": prompt_label,
                "prompt_source": prompt_spec.source if prompt_spec else "legacy",
            },
        )
    )
    decisions = normalize_decisions_text(response.text, candidates)
    return decisions, response.raw
