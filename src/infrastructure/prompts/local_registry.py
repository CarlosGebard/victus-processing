from __future__ import annotations

from pathlib import Path
from typing import Any

from src.application.ports.prompt_registry import PromptSpec


class LocalPromptRegistry:
    def __init__(self, prompt_dir: Path, *, default_config: dict[str, Any] | None = None) -> None:
        self.prompt_dir = prompt_dir.expanduser().resolve()
        self.default_config = default_config or {}

    def get(self, name: str, label: str = "production") -> PromptSpec:
        path = self.prompt_dir / f"{name}.md"
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Local prompt not found: {path}")
        return PromptSpec(
            name=name,
            version=None,
            template=path.read_text(encoding="utf-8"),
            config=dict(self.default_config),
            source="local",
        )
