from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class PromptSpec:
    name: str
    version: str | int | None
    template: str
    config: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"


class PromptRegistry(Protocol):
    def get(self, name: str, label: str = "production") -> PromptSpec:
        ...
