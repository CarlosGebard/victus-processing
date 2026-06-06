from __future__ import annotations

from src.workspace import config as ctx
from src.application.ports.prompt_registry import PromptRegistry
from src.infrastructure.prompts.fallback_registry import FallbackPromptRegistry
from src.infrastructure.prompts.langfuse_registry import LangfusePromptRegistry
from src.infrastructure.prompts.local_registry import LocalPromptRegistry


def build_prompt_registry() -> PromptRegistry:
    local = LocalPromptRegistry(
        ctx.PROMPTS_LOCAL_DIR,
        default_config={
            "model": ctx.DEFAULT_LLM_MODEL,
            "temperature": 0,
            "max_tokens": ctx.DEFAULT_LLM_MAX_TOKENS,
            "response_format": "json",
        },
    )
    return FallbackPromptRegistry(_build_langfuse_registry(), local)


def _build_langfuse_registry() -> PromptRegistry | None:
    if not (ctx.LANGFUSE_PUBLIC_KEY and ctx.LANGFUSE_SECRET_KEY):
        return None
    try:
        from langfuse import Langfuse

        return LangfusePromptRegistry(Langfuse())
    except Exception:
        return None
