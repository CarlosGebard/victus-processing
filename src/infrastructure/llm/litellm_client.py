from __future__ import annotations

import asyncio
import os
from typing import Any

from src.application.ports.llm import LLMRequest, LLMResponse
from src.infrastructure.llm.langfuse_tracer import LangfuseTracer


class LiteLLMClient:
    def __init__(self, *, tracer: LangfuseTracer | None = None) -> None:
        self.tracer = tracer

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError("litellm is required for LLM requests. Run `uv sync`.") from exc

        try:
            raw = litellm.completion(**self._kwargs(request))
            response = self._to_response(raw)
            if self.tracer:
                self.tracer.trace_success(request, response)
            return response
        except Exception as exc:
            if self.tracer:
                self.tracer.trace_error(request, exc)
            raise

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError("litellm is required for LLM requests. Run `uv sync`.") from exc

        try:
            raw = await litellm.acompletion(**self._kwargs(request))
            response = self._to_response(raw)
            if self.tracer:
                self.tracer.trace_success(request, response)
            return response
        except AttributeError:
            return await asyncio.to_thread(self.complete, request)
        except Exception as exc:
            if self.tracer:
                self.tracer.trace_error(request, exc)
            raise

    def _kwargs(self, request: LLMRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "metadata": {"operation": request.operation, **request.metadata},
        }
        proxy_base = os.getenv("LITELLM_PROXY_API_BASE")
        proxy_key = os.getenv("LITELLM_PROXY_API_KEY") or os.getenv("LITELLM_KEY")
        if proxy_base:
            kwargs["api_base"] = proxy_base.rstrip("/")
        if proxy_key:
            kwargs["api_key"] = proxy_key
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.timeout_seconds is not None:
            kwargs["timeout"] = request.timeout_seconds
        if request.response_format is not None:
            kwargs["response_format"] = request.response_format
        return kwargs

    def _to_response(self, raw: Any) -> LLMResponse:
        data = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
        choices = data.get("choices") or []
        text = ""
        if choices:
            message = choices[0].get("message") or {}
            text = str(message.get("content") or "")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return LLMResponse(text=text, raw=data, usage=usage)
