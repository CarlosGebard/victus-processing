from __future__ import annotations

from src.metadata.citation_exploration import (
    normalize_selection_mode,
    run_dataset_gaps_exploration,
    run_nutrition_rag_exploration,
)


def run_metadata_exploration_flow(mode: str = "broad-nutrition") -> None:
    normalized_mode = normalize_selection_mode(mode)
    if normalized_mode == "broad-nutrition":
        run_nutrition_rag_exploration()
        return
    if normalized_mode == "dataset-gaps":
        run_dataset_gaps_exploration()
        return
    raise ValueError(f"Modo metadata no soportado: {mode}")
