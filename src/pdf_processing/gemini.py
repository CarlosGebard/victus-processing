from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from src.pdf_processing.models import MarkdownBatch, MarkdownBatchOutput, PdfProcessingConfig
from src.pdf_processing.quota import GeminiKeyScheduler, NoAvailableGeminiKeyError


GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiResponseError(Exception):
    """Raised when Gemini returns unusable output."""


def load_gemini_api_keys(env: dict[str, str] | None = None) -> dict[str, str]:
    source = env or os.environ
    keys: dict[str, str] = {}
    for name, value in sorted(source.items()):
        if not value:
            continue
        if name.startswith("GEMINI_KEY"):
            keys[name] = value
    return keys


def build_gemini_markdown_payload(prompt: str, batch: MarkdownBatch) -> dict[str, Any]:
    context = {
        "previous_section_path": list(batch.previous_section_path),
        "last_heading": batch.last_heading,
        "last_300_chars": batch.last_300_chars,
        "oversized_unit": batch.oversized_unit,
    }
    return {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"text": "\n\n# BATCH STRUCTURAL CONTEXT\n\n" + json.dumps(context, ensure_ascii=False, indent=2)},
                    {"text": f"\n\n# MARKDOWN BATCH {batch.index}\n\n{batch.text}"},
                ],
            }
        ],
        "generationConfig": {"response_mime_type": "application/json"},
    }


def parse_gemini_json(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        parts = payload["candidates"][0]["content"]["parts"]
        text = "\n".join(str(part.get("text", "")) for part in parts if part.get("text"))
    except (KeyError, IndexError, TypeError) as exc:
        finish_reason = _finish_reason(payload)
        prompt_feedback = payload.get("promptFeedback")
        raise GeminiResponseError(
            "Gemini response missing candidate text "
            f"(finish_reason={finish_reason!r}, prompt_feedback={prompt_feedback!r})"
        ) from exc

    text = text.strip()
    if not text:
        raise GeminiResponseError(f"Gemini candidate text is empty (finish_reason={_finish_reason(payload)!r})")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiResponseError("Gemini response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise GeminiResponseError("Gemini JSON response must be an object")
    return parsed


def _finish_reason(payload: dict[str, Any]) -> str | None:
    try:
        value = payload["candidates"][0].get("finishReason")
    except (KeyError, IndexError, TypeError):
        return None
    return str(value) if value is not None else None


def summarize_gemini_response(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = {}
    try:
        candidate = payload["candidates"][0]
    except (KeyError, IndexError, TypeError):
        pass
    return {
        "finish_reason": candidate.get("finishReason") if isinstance(candidate, dict) else None,
        "prompt_feedback": payload.get("promptFeedback"),
        "usage_metadata": payload.get("usageMetadata"),
        "has_content": bool(isinstance(candidate, dict) and candidate.get("content")),
        "candidate_keys": sorted(candidate.keys()) if isinstance(candidate, dict) else [],
    }


class GeminiClient:
    def __init__(
        self,
        *,
        config: PdfProcessingConfig,
        scheduler: GeminiKeyScheduler,
        api_keys: dict[str, str],
    ) -> None:
        self.config = config
        self.scheduler = scheduler
        self.api_keys = api_keys

    async def extract_markdown_batch(self, prompt: str, batch: MarkdownBatch) -> dict[str, Any]:
        response_payload = await self.generate_markdown_batch(prompt, batch)
        parsed = parse_gemini_json(response_payload)
        return MarkdownBatchOutput.model_validate(parsed).as_clean_dict()

    async def generate_markdown_batch(self, prompt: str, batch: MarkdownBatch) -> dict[str, Any]:
        return await self._generate_with_payload(lambda: build_gemini_markdown_payload(prompt, batch))

    async def _generate_with_payload(self, payload_factory: Any) -> dict[str, Any]:
        attempted: set[str] = set()
        last_error: Exception | None = None

        while len(attempted) < max(1, len(self.api_keys)):
            key_id, api_key = await self._acquire_unattempted_key(attempted)
            attempted.add(key_id)
            try:
                payload = payload_factory()
                response_payload = await self._post(api_key, payload)
                await self.scheduler.mark_success(key_id)
                return response_payload
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                last_error = exc
                body_preview = exc.response.text[:1000]
                if status == 429:
                    await self.scheduler.mark_cooldown(
                        key_id,
                        seconds=self.config.cooldown_429_seconds,
                        error=f"HTTP 429: {body_preview[:300]}",
                    )
                    continue
                if status >= 500:
                    await self.scheduler.mark_cooldown(
                        key_id,
                        seconds=self.config.cooldown_5xx_seconds,
                        error=f"HTTP {status}: {body_preview[:300]}",
                    )
                    continue
                raise GeminiResponseError(f"Gemini HTTP {status}: {body_preview}") from exc
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
                last_error = exc
                await self.scheduler.mark_cooldown(
                    key_id,
                    seconds=self.config.cooldown_network_seconds,
                    error=f"{type(exc).__name__}: {exc}",
                )
                continue

        if last_error:
            raise NoAvailableGeminiKeyError(f"All Gemini keys failed or are cooling down: {last_error}") from last_error
        raise NoAvailableGeminiKeyError("No Gemini API keys configured")

    async def _acquire_unattempted_key(self, attempted: set[str]) -> tuple[str, str]:
        available = {key_id: key for key_id, key in self.api_keys.items() if key_id not in attempted}
        return await self.scheduler.acquire_key(available)

    async def _post(self, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = GEMINI_ENDPOINT.format(model=self.config.model)
        timeout = httpx.Timeout(self.config.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, params={"key": api_key}, json=payload)
            response.raise_for_status()
            return response.json()
