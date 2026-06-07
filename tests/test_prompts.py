from __future__ import annotations

from pathlib import Path

import pytest

from src.application.metadata_extraction.paper_selector import PaperCandidate
from src.prompts import (
    build_paper_selector_user_prompt,
    get_paper_selector_prompt,
)


ROOT_PROMPT_FILES_REMOVED = {
    "canonical_evidence.md",
    "experiment_scope_mapper.md",
    "md_to_json_first.md",
    "md_to_json_next.md",
    "paper_classifier.md",
    "paper_selector_dataset_gaps_system.md",
    "paper_selector_system.md",
}


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


def test_paper_selector_profiles_load_from_markdown() -> None:
    assert "scientific RAG focused on nutrition" in get_paper_selector_prompt("broad-nutrition")
    assert "dataset gaps in nutrition coverage" in get_paper_selector_prompt("dataset-gaps")

    with pytest.raises(ValueError):
        get_paper_selector_prompt("unknown")


def test_legacy_root_prompt_files_are_removed() -> None:
    prompt_root = Path(__file__).resolve().parents[1] / "src" / "prompts"

    for filename in ROOT_PROMPT_FILES_REMOVED:
        assert not (prompt_root / filename).exists()
