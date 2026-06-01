from __future__ import annotations

import sys
from types import SimpleNamespace

from src.application.ports.llm import LLMRequest
from src.infrastructure.llm.litellm_client import LiteLLMClient


def test_litellm_client_uses_proxy_env(monkeypatch) -> None:
    calls = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [{"message": {"content": "litellm ok"}}],
            "usage": {"total_tokens": 3},
        }

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(completion=fake_completion))
    monkeypatch.setenv("LITELLM_PROXY_API_BASE", "http://litellm.victus.io/")
    monkeypatch.setenv("LITELLM_PROXY_API_KEY", "test-key")

    response = LiteLLMClient().complete(
        LLMRequest(
            operation="test",
            model="gemini-flash-lite",
            messages=[{"role": "user", "content": "ping"}],
            temperature=0,
        )
    )

    assert response.text == "litellm ok"
    assert response.usage == {"total_tokens": 3}
    assert calls == [
        {
            "model": "gemini-flash-lite",
            "messages": [{"role": "user", "content": "ping"}],
            "metadata": {"operation": "test"},
            "api_base": "http://litellm.victus.io/v1",
            "api_key": "test-key",
            "temperature": 0,
        }
    ]
