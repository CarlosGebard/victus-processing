from __future__ import annotations

import json
import re
from typing import Any

from src.application.pdf_processing.models import MarkdownBatch, MarkdownBatchOutput
from src.application.ports.llm import LLMClient, LLMRequest


class LLMMarkdownResponseError(Exception):
    """Raised when an LLM returns unusable Markdown-batch JSON."""


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
        raise LLMMarkdownResponseError("LLM response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMMarkdownResponseError("LLM JSON response must be an object")
    return parsed


async def extract_markdown_batch(
    client: LLMClient,
    *,
    model: str,
    prompt: str,
    batch: MarkdownBatch,
    paper_id: str,
) -> dict[str, Any]:
    response = await client.acomplete(
        LLMRequest(
            operation="pdf_processing.markdown_batch",
            model=model,
            messages=build_markdown_messages(prompt, batch),
            response_format={"type": "json_object"},
            metadata={
                "paper_id": paper_id,
                "batch_index": batch.index,
                "start_char": batch.start_char,
                "end_char": batch.end_char,
            },
        )
    )
    parsed = parse_llm_json(response.text)
    return MarkdownBatchOutput.model_validate(parsed).as_clean_dict()
