from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.application.pdf_processing.models import MarkdownBatch


class MarkdownBatchingError(ValueError):
    """Raised when Markdown cannot be split within the configured tolerance."""


@dataclass(frozen=True)
class MarkdownUnit:
    kind: str
    text: str
    start_char: int
    end_char: int
    section_path: tuple[str, ...]
    heading: str | None = None
    oversized: bool = False


def build_markdown_batches(
    markdown: str,
    *,
    min_chars: int,
    soft_limit_chars: int | None = None,
    hard_limit_chars: int = 14000,
) -> tuple[MarkdownBatch, ...]:
    target_chars = min_chars
    if target_chars < 1:
        raise ValueError("min_chars must be >= 1")
    if soft_limit_chars is None:
        soft_limit_chars = min(target_chars + (target_chars // 2), hard_limit_chars)
    if soft_limit_chars < target_chars:
        raise ValueError("soft_limit_chars must be >= min_chars")
    if hard_limit_chars < soft_limit_chars:
        raise ValueError("hard_limit_chars must be >= soft_limit_chars")

    text = markdown.strip()
    if not text:
        return ()

    units = _split_structural_units(text, hard_limit_chars=hard_limit_chars)
    if not units:
        return ()

    batches: list[MarkdownBatch] = []
    current: list[MarkdownUnit] = []
    current_chars = 0
    previous_batch_tail: str | None = None
    previous_section_path: tuple[str, ...] = ()
    heading_open_threshold = max(1, target_chars // 2)

    for unit in units:
        unit_len = len(unit.text)
        if current and current_chars + unit_len > hard_limit_chars:
            previous_batch_tail, previous_section_path, current_chars = _close_current_batch(
                batches,
                current,
                previous_batch_tail,
                previous_section_path,
                avoid_trailing_heading=True,
            )

        should_close_for_heading = unit.kind == "heading" and current_chars >= heading_open_threshold
        should_close_for_soft_limit = current_chars >= target_chars and current_chars + unit_len > soft_limit_chars
        if current and (should_close_for_heading or should_close_for_soft_limit):
            previous_batch_tail, previous_section_path, current_chars = _close_current_batch(
                batches,
                current,
                previous_batch_tail,
                previous_section_path,
                avoid_trailing_heading=True,
            )

        current.append(unit)
        current_chars += unit_len

        if current_chars >= hard_limit_chars:
            previous_batch_tail, previous_section_path, current_chars = _close_current_batch(
                batches,
                current,
                previous_batch_tail,
                previous_section_path,
                avoid_trailing_heading=True,
            )

    if current:
        batches.append(_make_batch(current, len(batches) + 1, previous_batch_tail, previous_section_path))

    return tuple(batch for batch in batches if batch.text)


def _close_current_batch(
    batches: list[MarkdownBatch],
    current: list[MarkdownUnit],
    previous_tail: str | None,
    previous_section_path: tuple[str, ...],
    *,
    avoid_trailing_heading: bool,
) -> tuple[str | None, tuple[str, ...], int]:
    carry: MarkdownUnit | None = None
    if avoid_trailing_heading and len(current) > 1 and current[-1].kind == "heading":
        carry = current.pop()
    if current:
        batch = _make_batch(current, len(batches) + 1, previous_tail, previous_section_path)
        batches.append(batch)
        previous_tail = _tail_context(batch.text)
        previous_section_path = current[-1].section_path
    current.clear()
    if carry is not None:
        current.append(carry)
    return previous_tail, previous_section_path, sum(len(unit.text) for unit in current)


def _split_structural_units(text: str, *, hard_limit_chars: int) -> tuple[MarkdownUnit, ...]:
    raw_units = _parse_raw_units(text)
    units: list[MarkdownUnit] = []
    section_path: list[str] = []
    in_references = False

    for kind, raw_text, start, end in raw_units:
        heading = _heading_text(raw_text) if kind == "heading" else None
        if heading is not None:
            level = _heading_level(raw_text)
            section_path = section_path[: max(level - 1, 0)]
            section_path.append(heading)
            in_references = heading.strip().lower() in {"references", "bibliography", "reference"}

        classified_kind = "reference" if in_references and kind not in {"heading", "code"} else kind
        unit = MarkdownUnit(
            kind=classified_kind,
            text=raw_text.strip(),
            start_char=start,
            end_char=end,
            section_path=tuple(section_path),
            heading=heading,
        )
        units.extend(_split_oversized_unit(unit, hard_limit_chars=hard_limit_chars))

    return tuple(unit for unit in units if unit.text)


def _parse_raw_units(text: str) -> list[tuple[str, str, int, int]]:
    lines = text.splitlines(keepends=True)
    units: list[tuple[str, str, int, int]] = []
    pos = 0
    index = 0

    while index < len(lines):
        line = lines[index]
        start = pos
        stripped = line.strip()

        if not stripped:
            pos += len(line)
            index += 1
            continue

        if stripped.startswith("```"):
            index, pos = _consume_until_fence(lines, index, pos)
            units.append(("code", text[start:pos], start, pos))
            continue

        if _is_heading(stripped):
            pos += len(line)
            index += 1
            units.append(("heading", text[start:pos], start, pos))
            continue

        if _is_table_line(stripped):
            index, pos = _consume_while(lines, index, pos, _is_table_or_blank)
            units.append(("table", text[start:pos], start, pos))
            continue

        if _is_list_line(stripped):
            index, pos = _consume_while(lines, index, pos, _is_list_continuation)
            units.append(("list", text[start:pos], start, pos))
            continue

        if _is_caption(stripped):
            index, pos = _consume_paragraph(lines, index, pos)
            units.append(("caption", text[start:pos], start, pos))
            continue

        index, pos = _consume_paragraph(lines, index, pos)
        units.append(("paragraph", text[start:pos], start, pos))

    return units


def _consume_until_fence(lines: list[str], index: int, pos: int) -> tuple[int, int]:
    pos += len(lines[index])
    index += 1
    while index < len(lines):
        line = lines[index]
        pos += len(line)
        index += 1
        if line.strip().startswith("```"):
            break
    return index, pos


def _consume_while(lines: list[str], index: int, pos: int, predicate: Callable[[str], bool]) -> tuple[int, int]:
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped and not predicate(stripped):
            break
        pos += len(lines[index])
        index += 1
    return index, pos


def _consume_paragraph(lines: list[str], index: int, pos: int) -> tuple[int, int]:
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            pos += len(lines[index])
            index += 1
            break
        if index != 0 and (_is_heading(stripped) or _is_table_line(stripped) or _is_list_line(stripped)):
            break
        pos += len(lines[index])
        index += 1
    return index, pos


def _split_oversized_unit(unit: MarkdownUnit, *, hard_limit_chars: int) -> tuple[MarkdownUnit, ...]:
    if len(unit.text) <= hard_limit_chars:
        return (unit,)
    if unit.kind in {"table", "caption", "code"}:
        raise MarkdownBatchingError(f"Oversized {unit.kind} exceeds hard limit: chars={len(unit.text)}")

    chunks: list[MarkdownUnit] = []
    local_start = 0
    while local_start < len(unit.text):
        local_end = _find_internal_cut(unit.text, local_start, hard_limit_chars)
        if local_end is None:
            raise MarkdownBatchingError(
                f"Oversized {unit.kind} cannot be split safely: chars={len(unit.text)}, hard_limit_chars={hard_limit_chars}"
            )
        chunk_text = unit.text[local_start:local_end].strip()
        chunks.append(
            MarkdownUnit(
                kind=unit.kind,
                text=chunk_text,
                start_char=unit.start_char + local_start,
                end_char=unit.start_char + local_start + len(chunk_text),
                section_path=unit.section_path,
                heading=unit.heading,
                oversized=True,
            )
        )
        local_start = _skip_newlines(unit.text, local_end)
    return tuple(chunks)


def _find_internal_cut(text: str, start: int, hard_limit_chars: int) -> int | None:
    remaining = len(text) - start
    if remaining <= hard_limit_chars:
        return len(text)
    window_end = start + hard_limit_chars
    for separator in ("\n\n", "\n"):
        cut = text.rfind(separator, start + 1, window_end)
        if cut > start:
            return cut
    return None


def _make_batch(
    units: list[MarkdownUnit],
    index: int,
    previous_tail: str | None,
    previous_section_path: tuple[str, ...],
) -> MarkdownBatch:
    batch_text = "\n\n".join(unit.text for unit in units if unit.text).strip()
    last_heading = next((unit.heading for unit in reversed(units) if unit.heading), None)
    if last_heading is None:
        last_heading = units[-1].section_path[-1] if units[-1].section_path else None
    return MarkdownBatch(
        index=index,
        text=batch_text,
        start_char=units[0].start_char,
        end_char=units[-1].end_char,
        previous_section_path=previous_section_path,
        last_heading=last_heading,
        last_300_chars=previous_tail,
        oversized_unit=any(unit.oversized for unit in units),
    )


def _tail_context(text: str) -> str:
    return text[-300:]


def _skip_newlines(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] == "\n":
        pos += 1
    return pos


def _is_heading(stripped: str) -> bool:
    return stripped.startswith("#") and len(stripped) > 1 and stripped.lstrip("#").startswith(" ")


def _heading_level(line: str) -> int:
    return len(line) - len(line.lstrip("#"))


def _heading_text(line: str) -> str:
    return line.strip().lstrip("#").strip()


def _is_table_line(stripped: str) -> bool:
    return stripped.startswith("|") and stripped.endswith("|")


def _is_table_or_blank(stripped: str) -> bool:
    return not stripped or _is_table_line(stripped)


def _is_list_line(stripped: str) -> bool:
    return stripped.startswith(("- ", "* ", "+ ")) or _is_numbered_list_line(stripped)


def _is_numbered_list_line(stripped: str) -> bool:
    marker, sep, rest = stripped.partition(".")
    return bool(sep and rest.startswith(" ") and marker.isdigit())


def _is_list_continuation(stripped: str) -> bool:
    return not stripped or _is_list_line(stripped) or stripped.startswith(("  ", "\t"))


def _is_caption(stripped: str) -> bool:
    lowered = stripped.lower()
    return lowered.startswith(("figure ", "fig. ", "table ")) and ":" in stripped[:30]
