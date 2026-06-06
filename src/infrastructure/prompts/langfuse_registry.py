from __future__ import annotations

from typing import Any

from src.application.ports.prompt_registry import PromptSpec


class LangfusePromptRegistry:
    def __init__(self, client: Any) -> None:
        self.client = client

    def get(self, name: str, label: str = "production") -> PromptSpec:
        prompt = self.client.get_prompt(name, label=label, type="text")
        template = getattr(prompt, "prompt", None)
        if not isinstance(template, str):
            raise ValueError(f"Langfuse prompt must be text: {name}")
        return PromptSpec(
            name=str(getattr(prompt, "name", name)),
            version=getattr(prompt, "version", None),
            template=template,
            config=dict(getattr(prompt, "config", None) or {}),
            source="langfuse",
        )
