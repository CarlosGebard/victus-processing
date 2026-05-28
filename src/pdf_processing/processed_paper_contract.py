from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any


CANONICAL_SECTION_TYPES = {
    "front_matter",
    "abstract",
    "background",
    "introduction",
    "related_work",
    "methods",
    "dataset",
    "evaluation",
    "experiments",
    "results",
    "discussion",
    "limitations",
    "future_work",
    "conclusion",
    "clinical_guideline",
    "recommendations",
    "diagnostic_criteria",
    "treatment",
    "prevention",
    "statistical_analysis",
    "appendix",
    "supplementary",
    "references",
    "acknowledgements",
    "funding",
    "disclosure",
    "ethics",
    "unknown",
}

SECTION_TYPE_ALIASES = {
    "frontmatter": "front_matter",
    "metadata": "front_matter",
    "material_and_methods": "methods",
    "materials_and_methods": "methods",
    "method": "methods",
    "statistical_methods": "statistical_analysis",
    "statistical_analyses": "statistical_analysis",
    "data_availability": "dataset",
    "publisher_note": "disclosure",
    "author_contributions": "acknowledgements",
    "abbreviations": "supplementary",
}

MIN_BLOCK_FIELDS = {
    "block_id",
    "content_hash",
    "section_path",
    "section_type",
    "content_kind",
    "text",
    "retrieval_exclude",
}

FRONTMATTER_PATTERNS = (
    "open access",
    "affiliation",
    "affiliations",
    "correspondence",
    "copyright",
    "publisher note",
    "received:",
    "accepted:",
    "available online",
    "http://",
    "https://",
    "repository",
)

BAD_ENDINGS = ("and", "of", "with", ",", ";", "(")


def enforce_processed_paper_contract(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    paper_hash = _source_id(normalized)
    blocks = _repair_split_blocks(_dedupe_frontmatter_abstracts(_sorted_blocks(normalized.get("blocks"))))
    normalized["blocks"] = [_normalize_block(block, paper_hash, index) for index, block in enumerate(blocks)]
    validate_processed_paper_contract(normalized)
    return normalized


def validate_processed_paper_contract(payload: dict[str, Any]) -> None:
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("Processed paper schema invalid: blocks must be a list")
    for index, block in enumerate(blocks):
        missing = MIN_BLOCK_FIELDS.difference(block)
        if missing:
            raise ValueError(f"Processed paper block {index} missing fields: {sorted(missing)}")
        if not isinstance(block["section_path"], list):
            raise ValueError(f"Processed paper block {index} section_path must be a list")
        if not isinstance(block["retrieval_exclude"], bool):
            raise ValueError(f"Processed paper block {index} retrieval_exclude must be boolean")
        if not str(block["text"]).strip():
            raise ValueError(f"Processed paper block {index} text must be non-empty")
        if block["section_type"] not in CANONICAL_SECTION_TYPES:
            raise ValueError(f"Processed paper block {index} invalid section_type: {block['section_type']}")


def _normalize_block(block: dict[str, Any], paper_hash: str, index: int) -> dict[str, Any]:
    section_path = _normalize_section_path(block.get("section_path"), block.get("section_title"))
    section_title = _canonical_section_title(block.get("section_title") or (section_path[-1] if section_path else None))
    section_type = _canonical_section_type(block.get("section_type"), section_title)
    text = _clean_text(block.get("text"))
    return {
        **block,
        "block_id": f"{paper_hash}:b{index}",
        "content_hash": content_hash(text),
        "order": index,
        "section_path": section_path,
        "section_title": section_title,
        "section_slug": _slugify(section_title),
        "section_type": section_type,
        "content_kind": str(block.get("content_kind") or "paragraph").strip() or "paragraph",
        "text": text,
        "retrieval_exclude": bool(block.get("retrieval_exclude")) or _is_frontmatter_noise(block, section_title),
    }


def content_hash(text: Any) -> str:
    return hashlib.sha256(_normalize_text_for_hash(text).encode("utf-8")).hexdigest()


def _normalize_text_for_hash(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff").replace("ﬃ", "ffi").replace("ﬄ", "ffl")
    return " ".join(text.lower().split()).strip()


def _source_id(payload: dict[str, Any]) -> str:
    source_pdf = str(payload.get("source_pdf") or "paper")
    stem = source_pdf.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return _slugify(stem) or "paper"


def _sorted_blocks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return sorted([dict(block) for block in value if isinstance(block, dict)], key=lambda block: int(block.get("order", 0) or 0))


def _dedupe_frontmatter_abstracts(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for block in blocks:
        section_type = str(block.get("section_type") or "").strip().lower()
        content_kind = str(block.get("content_kind") or "").strip().lower()
        signature = (section_type, content_kind, _normalize_text_for_hash(block.get("text")))
        if section_type in {"abstract", "frontmatter", "front_matter", "metadata"} and signature in seen:
            continue
        seen.add(signature)
        output.append(block)
    return output


def _repair_split_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repaired: list[dict[str, Any]] = []
    index = 0
    while index < len(blocks):
        current = dict(blocks[index])
        while index + 1 < len(blocks) and _should_join(current, blocks[index + 1]):
            current["text"] = f"{_clean_text(current.get('text'))} {_clean_text(blocks[index + 1].get('text'))}".strip()
            index += 1
        repaired.append(current)
        index += 1
    return repaired


def _should_join(current: dict[str, Any], next_block: dict[str, Any]) -> bool:
    if _section_key(current) != _section_key(next_block):
        return False
    text = _clean_text(current.get("text"))
    lowered = text.lower().rstrip()
    return bool(text) and (lowered.endswith(BAD_ENDINGS) or not re.search(r"[.!?][\"')\]]?$", text))


def _normalize_section_path(value: Any, section_title: Any) -> list[str]:
    path = [_canonical_section_title(item) for item in value if str(item or "").strip()] if isinstance(value, list) else []
    if not path and str(section_title or "").strip():
        path = [_canonical_section_title(section_title)]
    return path


def _canonical_section_title(value: Any) -> str:
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", _clean_text(value)).strip()


def _canonical_section_type(value: Any, section_title: str) -> str:
    current = str(value or "unknown").strip().lower().replace("-", "_").replace(" ", "_") or "unknown"
    current = SECTION_TYPE_ALIASES.get(current, current)
    title = section_title.lower()
    if "ethic" in title:
        return "ethics"
    if "data availability" in title or "availability of data" in title or "repository" in title:
        return "dataset"
    if "author contribution" in title or "contributions" in title:
        return "acknowledgements"
    if "publisher note" in title:
        return "disclosure"
    if "abbreviation" in title:
        return "supplementary"
    if "statistical analysis" in title or title == "statistics":
        return "statistical_analysis"
    return current if current in CANONICAL_SECTION_TYPES else "unknown"


def _is_frontmatter_noise(block: dict[str, Any], section_title: str) -> bool:
    haystack = f"{section_title} {_clean_text(block.get('text'))}".lower()
    section_type = str(block.get("section_type") or "").strip().lower()
    return section_type in {"metadata", "frontmatter", "front_matter"} or any(pattern in haystack for pattern in FRONTMATTER_PATTERNS)


def _section_key(block: dict[str, Any]) -> tuple[str, str]:
    path = block.get("section_path")
    path_key = " > ".join(_canonical_section_title(item).lower() for item in path) if isinstance(path, list) else ""
    return (path_key, _canonical_section_title(block.get("section_title") or "").lower())


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _slugify(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
