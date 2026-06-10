from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.metadata_extraction.paper_selector import PaperCandidate


def _read_prompt(filename: str) -> str:
    return resources.files(__package__).joinpath(filename).read_text(encoding="utf-8")


PAPER_SELECTOR_SYSTEM_PROMPT = _read_prompt("metadata_extraction/paper_selector.md")


def get_paper_selector_prompt(selection_profile: str = "broad-nutrition") -> str:
    if selection_profile in {"broad-nutrition", "nutrition-rag"}:
        return PAPER_SELECTOR_SYSTEM_PROMPT
    raise ValueError(f"Unknown paper selector profile: {selection_profile}")


def build_paper_selector_user_prompt(candidates: list["PaperCandidate"]) -> str:
    candidate_blocks = []
    for candidate in candidates:
        preview = candidate.abstract_preview.strip() or "No abstract preview available."
        candidate_blocks.append(
            f"{candidate.id}\n"
            f"TITLE: {candidate.title}\n"
            f"ABSTRACT_PREVIEW: {preview}"
        )

    return (
        "Candidate papers:\n\n"
        + "\n\n".join(candidate_blocks)
        + "\n\nReturn JSON with this shape:\n"
        + '{"decisions":[{"id":"...","decision":"keep|drop|uncertain"}]}'
    )

__all__ = [
    "PAPER_SELECTOR_SYSTEM_PROMPT",
    "build_paper_selector_user_prompt",
    "get_paper_selector_prompt",
]
