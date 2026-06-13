from __future__ import annotations

import json
from typing import Any

from src.application.pdf_processing.llm_markdown import parse_llm_json
from src.application.ports.llm import LLMClient, LLMRequest
from src.application.ports.prompt_registry import PromptSpec


def build_experiment_scope_messages(prompt: str, blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    content = prompt + "\n\n# INPUT\n\n" + json.dumps({"blocks": blocks}, ensure_ascii=False, indent=2)
    return [{"role": "user", "content": content}]


def build_paper_classifier_messages(
    prompt: str,
    *,
    metadata: dict[str, Any],
    blocks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    content = (
        prompt
        + "\n\n# INPUT\n\n"
        + json.dumps(
            {
                "metadata": metadata,
                "blocks": blocks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return [{"role": "user", "content": content}]


def build_canonical_evidence_messages(
    prompt: str,
    *,
    experiment_packet: dict[str, Any],
) -> list[dict[str, str]]:
    content = (
        prompt
        + "\n\n# INPUT\n\n"
        + json.dumps(
            {
                "experiment_packet": experiment_packet,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return [{"role": "user", "content": content}]


async def map_experiment_scopes(
    client: LLMClient,
    *,
    model: str,
    prompt: str,
    blocks: list[dict[str, Any]],
    paper_id: str,
    prompt_spec: PromptSpec | None = None,
    prompt_label: str = "production",
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    response = await client.acomplete(
        LLMRequest(
            operation="evidence_extraction.results_scope_mapper",
            model=model,
            messages=build_experiment_scope_messages(prompt, blocks),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            response_format={"type": "json_object"},
            metadata={
                "paper_id": paper_id,
                "prompt_name": prompt_spec.name if prompt_spec else "evidence_extraction/results_scope_mapper",
                "prompt_version": prompt_spec.version if prompt_spec else None,
                "prompt_label": prompt_label,
                "prompt_source": prompt_spec.source if prompt_spec else "local_path",
            },
        )
    )
    return parse_llm_json(response.text)


async def classify_paper(
    client: LLMClient,
    *,
    model: str,
    prompt: str,
    metadata: dict[str, Any],
    blocks: list[dict[str, Any]],
    paper_id: str,
    prompt_spec: PromptSpec | None = None,
    prompt_label: str = "production",
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    response = await client.acomplete(
        LLMRequest(
            operation="evidence_extraction.paper_classifier",
            model=model,
            messages=build_paper_classifier_messages(prompt, metadata=metadata, blocks=blocks),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            response_format={"type": "json_object"},
            metadata={
                "paper_id": paper_id,
                "prompt_name": prompt_spec.name if prompt_spec else "evidence_extraction/paper_classifier",
                "prompt_version": prompt_spec.version if prompt_spec else None,
                "prompt_label": prompt_label,
                "prompt_source": prompt_spec.source if prompt_spec else "local_path",
            },
        )
    )
    return parse_llm_json(response.text)


async def extract_canonical_evidence(
    client: LLMClient,
    *,
    model: str,
    prompt: str,
    experiment_packet: dict[str, Any],
    paper_id: str,
    prompt_spec: PromptSpec | None = None,
    prompt_label: str = "production",
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    response = await client.acomplete(
        LLMRequest(
            operation="evidence_extraction.canonical_evidence_extractor",
            model=model,
            messages=build_canonical_evidence_messages(
                prompt,
                experiment_packet=experiment_packet,
            ),
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=timeout_seconds,
            response_format={"type": "json_object"},
            metadata={
                "paper_id": paper_id,
                "scope_index": experiment_packet.get("scope_index"),
                "prompt_name": prompt_spec.name if prompt_spec else "evidence_extraction/canonical_evidence_extractor",
                "prompt_version": prompt_spec.version if prompt_spec else None,
                "prompt_label": prompt_label,
                "prompt_source": prompt_spec.source if prompt_spec else "local_path",
            },
        )
    )
    return parse_llm_json(response.text)
