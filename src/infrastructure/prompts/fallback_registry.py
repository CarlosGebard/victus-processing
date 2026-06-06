from __future__ import annotations

from src.application.ports.prompt_registry import PromptRegistry, PromptSpec


class FallbackPromptRegistry:
    def __init__(self, primary: PromptRegistry | None, fallback: PromptRegistry) -> None:
        self.primary = primary
        self.fallback = fallback

    def get(self, name: str, label: str = "production") -> PromptSpec:
        primary_error: Exception | None = None
        if self.primary is not None:
            try:
                return self.primary.get(name, label=label)
            except Exception as exc:
                primary_error = exc
        try:
            return self.fallback.get(name, label=label)
        except Exception as fallback_error:
            if primary_error is None:
                raise RuntimeError(f"Prompt '{name}' unavailable: {fallback_error}") from fallback_error
            raise RuntimeError(
                f"Prompt '{name}' unavailable in primary and fallback: "
                f"{type(primary_error).__name__}: {primary_error}; "
                f"{type(fallback_error).__name__}: {fallback_error}"
            ) from fallback_error
