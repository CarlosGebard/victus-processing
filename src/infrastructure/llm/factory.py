from __future__ import annotations

import os

from src.application.ports.llm import LLMClient
from src.infrastructure.llm.langfuse_tracer import LangfuseTracer
from src.infrastructure.llm.litellm_client import LiteLLMClient


def build_llm_client() -> LLMClient:
    tracer = LangfuseTracer() if _truthy(os.getenv("LANGFUSE_ENABLED", "0")) else None
    return LiteLLMClient(tracer=tracer)


def _truthy(value: str) -> bool:
    return value.strip().lower() not in {"0", "false", "no", "off"}
