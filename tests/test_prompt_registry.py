from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.application.ports.prompt_registry import PromptSpec
from src.infrastructure.prompts.compile import compile_template
from src.infrastructure.prompts.fallback_registry import FallbackPromptRegistry
from src.infrastructure.prompts.langfuse_registry import LangfusePromptRegistry
from src.infrastructure.prompts.local_registry import LocalPromptRegistry


def test_compile_template_replaces_double_and_single_braces() -> None:
    assert compile_template("Hi {{name}} {count}", {"name": "Ana", "count": 2}) == "Hi Ana 2"


def test_compile_template_reports_missing_variable() -> None:
    with pytest.raises(ValueError, match="missing"):
        compile_template("Hi {{missing}}", {})


def test_local_prompt_registry_reads_markdown(tmp_path: Path) -> None:
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "canonical_evidence.md").write_text("Hello {{name}}", encoding="utf-8")

    spec = LocalPromptRegistry(prompt_dir, default_config={"model": "m"}).get("canonical_evidence")

    assert spec.template == "Hello {{name}}"
    assert spec.config == {"model": "m"}
    assert spec.source == "local"


def test_fallback_prompt_registry_uses_local_when_primary_fails(tmp_path: Path) -> None:
    class BrokenRegistry:
        def get(self, name: str, label: str = "production") -> PromptSpec:
            raise RuntimeError("offline")

    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    (prompt_dir / "p.md").write_text("local", encoding="utf-8")

    spec = FallbackPromptRegistry(BrokenRegistry(), LocalPromptRegistry(prompt_dir)).get("p")

    assert spec.template == "local"
    assert spec.source == "local"


def test_langfuse_prompt_registry_maps_prompt_object() -> None:
    @dataclass
    class FakePrompt:
        name: str = "canonical_evidence"
        version: int = 3
        prompt: str = "Hello {{name}}"
        config: dict[str, object] | None = None

    class FakeClient:
        def get_prompt(self, name: str, **kwargs):
            assert name == "canonical_evidence"
            assert kwargs["label"] == "staging"
            assert kwargs["type"] == "text"
            return FakePrompt(config={"model": "m"})

    spec = LangfusePromptRegistry(FakeClient()).get("canonical_evidence", label="staging")

    assert spec.version == 3
    assert spec.template == "Hello {{name}}"
    assert spec.config == {"model": "m"}
    assert spec.source == "langfuse"
