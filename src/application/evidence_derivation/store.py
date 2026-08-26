from __future__ import annotations

from typing import Any, Protocol


class EvidenceDerivationStore(Protocol):
    def replace_evidence_derivation_build(self, artifacts: dict[str, Any]) -> None:
        """Atomically replace all persisted rows for one evidence build."""

