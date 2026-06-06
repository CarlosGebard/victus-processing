from __future__ import annotations

from src.application.metadata.citation_exploration import (
    normalize_selection_mode,
    run_dataset_gaps_exploration,
    run_nutrition_rag_exploration,
)
from src.application.ports.llm import LLMClient
from src.application.ports.prompt_registry import PromptRegistry


def run_metadata_exploration_flow(
    mode: str = "broad-nutrition",
    *,
    llm_client: LLMClient,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
) -> None:
    normalized_mode = normalize_selection_mode(mode)
    if normalized_mode == "broad-nutrition":
        run_nutrition_rag_exploration(llm_client=llm_client, prompt_registry=prompt_registry, prompt_label=prompt_label)
        return
    if normalized_mode == "dataset-gaps":
        run_dataset_gaps_exploration(llm_client=llm_client, prompt_registry=prompt_registry, prompt_label=prompt_label)
        return
    raise ValueError(f"Modo metadata no soportado: {mode}")
