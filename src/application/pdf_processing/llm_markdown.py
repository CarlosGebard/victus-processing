from __future__ import annotations

import json
import re
from typing import Any

from src.application.pdf_processing.models import MarkdownBatch, MarkdownBatchOutput
from src.application.ports.llm import LLMClient, LLMRequest
from src.application.ports.prompt_registry import PromptSpec


class LLMMarkdownResponseError(Exception):
    """Raised when an LLM returns unusable Markdown-batch JSON."""

    def __init__(self, message: str, *, response_text: str | None = None) -> None:
        super().__init__(message)
        self.response_text = response_text


def build_markdown_messages(prompt: str, batch: MarkdownBatch) -> list[dict[str, str]]:
    context = {
        "previous_section_path": list(batch.previous_section_path),
        "last_heading": batch.last_heading,
        "last_300_chars": batch.last_300_chars,
        "oversized_unit": batch.oversized_unit,
    }
    content = (
        prompt
        + "\n\n# BATCH STRUCTURAL CONTEXT\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
        + f"\n\n# MARKDOWN BATCH {batch.index}\n\n{batch.text}"
    )
    return [{"role": "user", "content": content}]


def parse_llm_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise LLMMarkdownResponseError("LLM response text is empty")
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        extracted = _extract_json_object(stripped)
        if extracted is None:
            raise LLMMarkdownResponseError("LLM response is not valid JSON", response_text=text) from exc
        try:
            parsed = json.loads(extracted)
        except json.JSONDecodeError as extracted_exc:
            raise LLMMarkdownResponseError("LLM response is not valid JSON", response_text=text) from extracted_exc
    if not isinstance(parsed, dict):
        raise LLMMarkdownResponseError("LLM JSON response must be an object", response_text=text)
    return parsed


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


async def extract_markdown_batch(
    client: LLMClient,
    *,
    model: str,
    prompt: str,
    batch: MarkdownBatch,
    paper_id: str,
    prompt_spec: PromptSpec | None = None,
    prompt_label: str = "production",
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    response = await client.acomplete(
        LLMRequest(
            operation="pdf_processing.markdown_batch",
            model=model,
            messages=build_markdown_messages(prompt, batch),
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            metadata={
                "paper_id": paper_id,
                "batch_index": batch.index,
                "start_char": batch.start_char,
                "end_char": batch.end_char,
                "prompt_name": prompt_spec.name if prompt_spec else "pdf_processing/local_path",
                "prompt_version": prompt_spec.version if prompt_spec else None,
                "prompt_label": prompt_label,
                "prompt_source": prompt_spec.source if prompt_spec else "local_path",
            },
        )
    )
    try:
        parsed = parse_llm_json(response.text)
        return MarkdownBatchOutput.model_validate(parsed).as_clean_dict()
    except LLMMarkdownResponseError:
        raise
    except Exception as exc:
        raise LLMMarkdownResponseError("LLM response does not match Markdown batch contract", response_text=response.text) from exc
