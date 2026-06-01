from __future__ import annotations

from importlib import resources
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.metadata.paper_selector import PaperCandidate


def _read_prompt(filename: str) -> str:
    return resources.files(__package__).joinpath(filename).read_text(encoding="utf-8")


CLAIMS_PROMPT_TEMPLATE = _read_prompt("claims.md")
PAPER_SELECTOR_SYSTEM_PROMPT = _read_prompt("paper_selector_system.md")
PAPER_SELECTOR_GAP_SYSTEM_PROMPT = _read_prompt("paper_selector_dataset_gaps_system.md")


def build_claims_prompt(
    trace_text: str,
    sections_text: str,
    max_claims: int,
    available_sections: str,
) -> str:
    return (
        CLAIMS_PROMPT_TEMPLATE.replace("{trace_text}", trace_text)
        .replace("{sections_text}", sections_text)
        .replace("{max_claims}", str(max_claims))
        .replace("{available_sections}", available_sections)
    )


def get_paper_selector_system_prompt(selection_profile: str = "broad-nutrition") -> str:
    if selection_profile in {"broad-nutrition", "nutrition-rag"}:
        return PAPER_SELECTOR_SYSTEM_PROMPT
    if selection_profile == "dataset-gaps":
        return PAPER_SELECTOR_GAP_SYSTEM_PROMPT
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
        + '{"decisions":[{"id":"...","decision":"keep|drop|uncertain","reason":"..."}]}'
    )

__all__ = [
    "CLAIMS_PROMPT_TEMPLATE",
    "PAPER_SELECTOR_GAP_SYSTEM_PROMPT",
    "PAPER_SELECTOR_SYSTEM_PROMPT",
    "build_claims_prompt",
    "build_paper_selector_user_prompt",
    "get_paper_selector_system_prompt",
]
