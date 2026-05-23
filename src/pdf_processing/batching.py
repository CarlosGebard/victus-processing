from __future__ import annotations

from src.pdf_processing.models import MarkdownBatch


class MarkdownBatchingError(ValueError):
    """Raised when Markdown cannot be split within the configured tolerance."""


def build_markdown_batches(
    markdown: str,
    *,
    min_chars: int,
    hard_limit_chars: int = 18000,
) -> tuple[MarkdownBatch, ...]:
    if min_chars < 1:
        raise ValueError("min_chars must be >= 1")
    if hard_limit_chars < min_chars:
        raise ValueError("hard_limit_chars must be >= min_chars")

    text = markdown.strip()
    if not text:
        return ()

    batches: list[MarkdownBatch] = []
    start = 0

    while start < len(text):
        remaining = len(text) - start
        if remaining <= hard_limit_chars:
            batches.append(_make_batch(text, start, len(text), len(batches) + 1))
            break

        end = _find_heading_cut(text, start, min_chars=min_chars, hard_limit_chars=hard_limit_chars)
        if end is None:
            end = _find_block_cut(text, start, min_chars=min_chars, hard_limit_chars=hard_limit_chars)
        if end is None:
            raise MarkdownBatchingError(
                f"Markdown batch exceeded hard limit without safe cut: start={start}, "
                f"min_chars={min_chars}, hard_limit_chars={hard_limit_chars}"
            )
        batches.append(_make_batch(text, start, end, len(batches) + 1))
        start = _skip_separators(text, end)

    return tuple(batch for batch in batches if batch.text)


def _find_heading_cut(text: str, start: int, *, min_chars: int, hard_limit_chars: int) -> int | None:
    window_start = start + min_chars
    window_end = min(start + hard_limit_chars, len(text))
    search_from = window_start
    while search_from < window_end:
        heading_at = text.find("\n## ", search_from, window_end)
        if heading_at == -1:
            return None
        if heading_at > start:
            return heading_at
        search_from = heading_at + 1
    return None


def _find_block_cut(text: str, start: int, *, min_chars: int, hard_limit_chars: int) -> int | None:
    window_start = start + min_chars
    window_end = min(start + hard_limit_chars, len(text))
    block_at = text.rfind("\n\n", window_start, window_end)
    if block_at > start:
        return block_at
    line_at = text.rfind("\n", window_start, window_end)
    if line_at > start:
        return line_at
    return None


def _skip_separators(text: str, pos: int) -> int:
    while pos < len(text) and text[pos] == "\n":
        pos += 1
    return pos


def _make_batch(text: str, start: int, end: int, index: int) -> MarkdownBatch:
    batch_text = text[start:end].strip()
    return MarkdownBatch(
        index=index,
        text=batch_text,
        start_char=start,
        end_char=start + len(batch_text),
    )
