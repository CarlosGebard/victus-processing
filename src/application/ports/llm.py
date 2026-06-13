from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


LLMMessage = dict[str, Any]


@dataclass(frozen=True)
class LLMRequest:
    operation: str
    model: str
    messages: list[LLMMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_seconds: float | None = None
    response_format: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse:
        ...

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        ...
