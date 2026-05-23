from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

from src.pdf_processing.models import PdfProcessingConfig


DEFAULT_METADATA = {
    "title": None,
    "authors": [],
    "abstract": None,
    "doi": None,
    "journal": None,
    "year": None,
}


def remove_recitation_separator(value: Any) -> Any:
    if isinstance(value, str):
        clean = value.replace("¶", "").replace("_X_", "")
        clean = re.sub(r"<!--\s*z\s*-->", "", clean)
        clean = re.sub(r"\*([A-Za-z0-9][^*\n]*?)\*", r"\1", clean)
        lines = clean.splitlines()
        return "\n".join(" ".join(line.split()) for line in lines)
    if isinstance(value, list):
        return [remove_recitation_separator(item) for item in value]
    if isinstance(value, dict):
        return {key: remove_recitation_separator(item) for key, item in value.items()}
    return value


def merge_batch_outputs(
    *,
    source_pdf: Path,
    batches: list[dict[str, Any]],
    config: PdfProcessingConfig,
) -> dict[str, Any]:
    metadata = dict(DEFAULT_METADATA)
    if batches and isinstance(batches[0].get("metadata"), dict):
        metadata.update({key: batches[0]["metadata"].get(key) for key in DEFAULT_METADATA})
    metadata = remove_recitation_separator(metadata)

    blocks: list[dict[str, Any]] = []
    seen_blocks: set[tuple[str, str, str, str]] = set()
    batch_ends: list[dict[str, Any]] = []
    batch_warnings: list[dict[str, Any]] = []
    section_registry: list[dict[str, Any]] = []
    for batch in batches:
        batch_end = batch.get("batch_end") or batch.get("batch_state")
        if isinstance(batch_end, dict):
            batch_ends.append(remove_recitation_separator(batch_end))
        warning = batch.get("batch_warnings")
        if isinstance(warning, dict):
            batch_warnings.append(remove_recitation_separator(warning))
        section_registry = _merge_section_registry(
            section_registry,
            batch.get("section_registry") or batch.get("updated_section_registry"),
        )

        raw_blocks = batch.get("blocks") or batch.get("elements") or []
        if not isinstance(raw_blocks, list):
            continue
        for block in raw_blocks:
            if not isinstance(block, dict):
                continue
            section_path = block.get("section_path")
            if not isinstance(section_path, list):
                section_path = [block.get("section_title") or block.get("section")] if block.get("section_title") or block.get("section") else []
            normalized = {
                "block_id": remove_recitation_separator(block.get("block_id") or block.get("local_id")),
                "order": len(blocks),
                "section_path": remove_recitation_separator(section_path),
                "section_title": remove_recitation_separator(
                    block.get("section_title") or block.get("section") or _last_section_title(section_path)
                ),
                "section_type": remove_recitation_separator(block.get("section_type") or block.get("type") or "unknown"),
                "content_kind": remove_recitation_separator(block.get("content_kind") or "paragraph"),
                "text": remove_recitation_separator(block.get("text") or block.get("content") or ""),
                "quality": _normalize_quality(block.get("quality")),
            }
            if not normalized["block_id"]:
                normalized["block_id"] = f"block_{len(blocks):05d}"
            signature = _block_signature(normalized)
            if signature in seen_blocks:
                continue
            seen_blocks.add(signature)
            blocks.append(normalized)

    sections = _sections_from_registry(section_registry) if section_registry else _sections_from_blocks(blocks)

    return {
        "source_pdf": str(source_pdf),
        "metadata": metadata,
        "sections": sections,
        "section_registry": section_registry,
        "blocks": blocks,
        "processing": {
            "model": config.model,
            "markdown_batch_chars": config.markdown_batch_chars,
            "total_batches": len(batches),
            "created_at": datetime.now(UTC).isoformat(),
        },
        "batch_ends": batch_ends,
        "batch_warnings": batch_warnings,
    }


def _last_section_title(section_path: Any) -> str | None:
    if not isinstance(section_path, list) or not section_path:
        return None
    value = section_path[-1]
    return str(value) if value is not None else None


def _block_signature(block: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(block.get("section_title") or ""),
        str(block.get("section_type") or ""),
        str(block.get("content_kind") or ""),
        " ".join(str(block.get("text") or "").lower().split()),
    )


def _normalize_quality(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "confidence": "medium",
            "is_truncated": False,
            "is_duplicate": False,
        }
    confidence = value.get("confidence")
    return {
        "confidence": confidence if confidence in {"high", "medium", "low"} else "medium",
        "is_truncated": bool(value.get("is_truncated", False)),
        "is_duplicate": bool(value.get("is_duplicate", False)),
    }


def _merge_section_registry(current: list[dict[str, Any]], incoming: Any) -> list[dict[str, Any]]:
    merged = list(current)
    seen = {
        (
            str(item.get("title") or "").strip().lower(),
            str(item.get("type") or "unknown").strip().lower(),
            str(item.get("parent") or "").strip().lower(),
        )
        for item in merged
        if isinstance(item, dict)
    }
    if not isinstance(incoming, list):
        return merged
    for item in incoming:
        if not isinstance(item, dict):
            continue
        normalized = remove_recitation_separator(
            {
                "title": str(item.get("title") or "").strip(),
                "type": str(item.get("type") or "unknown").strip(),
                "parent": item.get("parent"),
            }
        )
        if not normalized["title"]:
            continue
        key = (
            str(normalized["title"]).lower(),
            str(normalized["type"]).lower(),
            str(normalized.get("parent") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


def _sections_from_registry(registry: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "order": index,
            "title": item.get("title"),
            "type": item.get("type") or "unknown",
            "parent": item.get("parent"),
        }
        for index, item in enumerate(registry)
    ]


def _sections_from_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for block in blocks:
        key = (str(block.get("section_title") or ""), str(block.get("section_type") or "unknown"))
        if key in seen:
            continue
        seen.add(key)
        sections.append(
            {
                "order": len(sections),
                "title": block.get("section_title"),
                "type": block.get("section_type") or "unknown",
            }
        )
    return sections
