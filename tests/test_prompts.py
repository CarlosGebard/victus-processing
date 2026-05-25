from __future__ import annotations

import pytest

from src.metadata.paper_selector import PaperCandidate
from src.prompts import (
    CLAIMS_PROMPT_TEMPLATE,
    build_claims_prompt,
    build_paper_selector_user_prompt,
    get_paper_selector_system_prompt,
)


def test_claims_prompt_template_loads_from_markdown() -> None:
    assert "MAX_CLAIMS = {max_claims}" in CLAIMS_PROMPT_TEMPLATE
    assert "[TRACE]" in CLAIMS_PROMPT_TEMPLATE
    assert "[SECTIONS]" in CLAIMS_PROMPT_TEMPLATE


def test_build_claims_prompt_renders_variables() -> None:
    prompt = build_claims_prompt(
        trace_text="trace body",
        sections_text="section body",
        max_claims=3,
        available_sections="Intro, Results",
    )

    assert "MAX_CLAIMS = 3" in prompt
    assert "AVAILABLE_SECTIONS = Intro, Results" in prompt
    assert "trace body" in prompt
    assert "section body" in prompt


def test_paper_selector_user_prompt_renders_candidate_blocks() -> None:
    prompt = build_paper_selector_user_prompt(
        [
            PaperCandidate(id="p1", title="Diet and health", abstract_preview=""),
            PaperCandidate(id="p2", title="Protein intake", abstract_preview="Preview"),
        ]
    )

    assert "p1\nTITLE: Diet and health\nABSTRACT_PREVIEW: No abstract preview available." in prompt
    assert "p2\nTITLE: Protein intake\nABSTRACT_PREVIEW: Preview" in prompt
    assert '"decisions"' in prompt


def test_paper_selector_system_profiles_load_from_markdown() -> None:
    assert "scientific RAG focused on nutrition" in get_paper_selector_system_prompt("broad-nutrition")
    assert "dataset gaps in nutrition coverage" in get_paper_selector_system_prompt("dataset-gaps")

    with pytest.raises(ValueError):
        get_paper_selector_system_prompt("unknown")
