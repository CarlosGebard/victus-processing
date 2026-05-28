from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


@dataclass(frozen=True)
class PdfProcessingConfig:
    model: str
    input_dir: Path
    output_dir: Path
    prompt_first_batch: Path
    prompt_continuation_batch: Path
    workers: int = 1
    markdown_batch_chars: int = 6000
    markdown_batch_soft_limit_chars: int = 9000
    markdown_batch_hard_limit_chars: int = 14000
    max_batches: int | None = None
    requests_per_minute: int = 15
    requests_per_day: int = 500
    cooldown_429_seconds: int = 60
    cooldown_5xx_seconds: int = 30
    cooldown_network_seconds: int = 30
    request_timeout_seconds: float = 120.0


@dataclass(frozen=True)
class MarkdownBatch:
    index: int
    text: str
    start_char: int
    end_char: int
    previous_section_path: tuple[str, ...] = ()
    last_heading: str | None = None
    last_300_chars: str | None = None
    oversized_unit: bool = False


class JsonMetadata(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None


class CurrentSection(BaseModel):
    main: str | None = None
    subsection: str | None = None
    title: str | None = None
    type: str = "unknown"


class BlockQuality(BaseModel):
    confidence: Literal["high", "medium", "low"] = "medium"
    is_truncated: bool = False
    is_duplicate: bool = False


class SectionRegistryEntry(BaseModel):
    title: str = ""
    type: str = "unknown"
    original_title: str | None = None
    canonical_title: str | None = None
    section_type: str | None = None
    parent: str | None = None

    @model_validator(mode="after")
    def normalize_registry_fields(self) -> SectionRegistryEntry:
        if not self.title:
            self.title = self.canonical_title or self.original_title or ""
        if self.section_type and self.type == "unknown":
            self.type = self.section_type
        if self.original_title is None:
            self.original_title = self.title
        if self.canonical_title is None:
            self.canonical_title = self.title
        if self.section_type is None:
            self.section_type = self.type
        return self


class JsonBlock(BaseModel):
    local_id: str | None = None
    order: int = 0
    section_path: list[str] = Field(default_factory=list)
    section_type: str = "unknown"
    content_kind: str = "paragraph"
    text: str


class BatchEnd(BaseModel):
    last_section_path: list[str] = Field(default_factory=list)
    last_section_title: str | None = None
    last_section_type: str | None = None
    ends_mid_block: bool = False
    cut_off_type: Literal["sentence", "paragraph", "table", "reference", "none"] = "none"
    tail_context: str | None = None


class BatchWarnings(BaseModel):
    possible_cut_table: bool = False
    possible_cut_list: bool = False
    possible_cut_reference: bool = False
    reason: str | None = None


class MarkdownBatchOutput(BaseModel):
    metadata: JsonMetadata | None = None
    current_section: CurrentSection = Field(default_factory=CurrentSection)
    section_registry: list[SectionRegistryEntry] = Field(default_factory=list)
    updated_section_registry: list[SectionRegistryEntry] = Field(default_factory=list)
    batch_index: int = 0
    blocks: list[JsonBlock] = Field(default_factory=list)
    batch_end: BatchEnd = Field(default_factory=BatchEnd)
    batch_warnings: BatchWarnings = Field(default_factory=BatchWarnings)

    def as_clean_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


@dataclass(frozen=True)
class KeyState:
    key_id: str
    daily_used: int = 0
    minute_used: int = 0
    cooldown_until: float | None = None
    last_error: str | None = None
    updated_at: str | None = None
