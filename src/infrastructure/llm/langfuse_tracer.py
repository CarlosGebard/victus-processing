from __future__ import annotations

from typing import Any

from src.application.ports.llm import LLMRequest, LLMResponse


class LangfuseTracer:
    def __init__(self) -> None:
        try:
            from langfuse import Langfuse
        except ImportError:
            self._client = None
        else:
            try:
                self._client = Langfuse()
            except Exception:
                self._client = None

    def trace_success(self, request: LLMRequest, response: LLMResponse) -> None:
        self._event("llm.request", request, {"usage": response.usage, "status": "ok"})

    def trace_error(self, request: LLMRequest, exc: Exception) -> None:
        self._event("llm.request", request, {"status": "error", "error": f"{type(exc).__name__}: {exc}"})

    def _event(self, name: str, request: LLMRequest, metadata: dict[str, Any]) -> None:
        if self._client is None:
            return
        payload = {
            "operation": request.operation,
            "model": request.model,
            **request.metadata,
            **metadata,
        }
        create_event = getattr(self._client, "create_event", None)
        if callable(create_event):
            try:
                create_event(name=name, metadata=payload)
            except Exception:
                return
