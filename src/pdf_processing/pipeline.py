from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from src.workspace import config as ctx
from src.pdf_processing.batching import MarkdownBatchingError, build_markdown_batches
from src.pdf_processing.gemini import GeminiClient, load_gemini_api_keys
from src.pdf_processing.markdown import pdf_to_markdown
from src.pdf_processing.merge import merge_batch_outputs
from src.pdf_processing.models import PdfProcessingConfig
from src.pdf_processing.quota import GeminiKeyScheduler, SQLiteQuotaRepository
from src.pdf_processing.status import append_processing_status, load_processing_status_index, write_processing_status_index


def load_pdf_processing_config() -> PdfProcessingConfig:
    cfg = ctx.CONFIG.get("pdf_processing") or {}
    return PdfProcessingConfig(
        model=str(cfg.get("model", "gemini-3.1-flash-lite")),
        input_dir=ctx.resolve_project_path(cfg.get("input_dir"), ctx.DATA_RUNTIME_PDFS_ACTIVE_DIR),
        output_dir=ctx.resolve_project_path(cfg.get("output_dir"), ctx.DATA_RUNTIME_PDF_PROCESSING_DIR),
        workers=int(cfg.get("workers", 1)),
        prompt_first_batch=ctx.resolve_project_path(
            cfg.get("prompt_first_batch"),
            ctx.ROOT_DIR / "src/prompts/md_to_json_first.md",
        ),
        prompt_continuation_batch=ctx.resolve_project_path(
            cfg.get("prompt_continuation_batch"),
            ctx.ROOT_DIR / "src/prompts/md_to_json_next.md",
        ),
        markdown_batch_chars=int(cfg.get("markdown_batch_chars", 10000)),
        markdown_batch_hard_limit_chars=int(cfg.get("markdown_batch_hard_limit_chars", 25000)),
        max_batches=int(cfg["max_batches"]) if cfg.get("max_batches") is not None else None,
        requests_per_minute=int(cfg.get("requests_per_minute", 15)),
        requests_per_day=int(cfg.get("requests_per_day", 500)),
        cooldown_429_seconds=int(cfg.get("cooldown_429_seconds", 60)),
        cooldown_5xx_seconds=int(cfg.get("cooldown_5xx_seconds", 30)),
        cooldown_network_seconds=int(cfg.get("cooldown_network_seconds", 30)),
        request_timeout_seconds=float(cfg.get("request_timeout_seconds", 120)),
    )


def paper_output_dir(base_output_dir: Path, pdf_path: Path) -> Path:
    return base_output_dir / pdf_path.stem


def _read_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _continuation_prompt(template: str, previous_result: dict[str, Any], section_registry: list[dict[str, Any]]) -> str:
    batch_end = previous_result.get("batch_end") or {}
    return (
        template
        + "\n\n# PREVIOUS BATCH END\n\n"
        + json.dumps(batch_end, ensure_ascii=False, indent=2)
        + "\n\n# SECTION REGISTRY\n\n"
        + json.dumps(section_registry, ensure_ascii=False, indent=2)
        + "\n\n# PREVIOUS TAIL CONTEXT\n\n"
        + str(batch_end.get("tail_context") or "")
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _final_output_paths(output_dir: Path, pdf_path: Path) -> tuple[Path, Path]:
    paper_dir = paper_output_dir(output_dir, pdf_path)
    return paper_dir / "paper.processed.json", paper_dir / "paper.json"


def _rename_legacy_output(final_output: Path, legacy_final_output: Path) -> Path:
    if legacy_final_output.exists() and not final_output.exists():
        legacy_final_output.rename(final_output)
    return final_output if final_output.exists() else legacy_final_output


def _append_failed_status(status_file: Path, *, paper_id: str, error: str, exc: Exception) -> None:
    append_processing_status(
        status_file,
        paper_id=paper_id,
        status="failed",
        error=error,
        error_description=_short_error_description(exc),
    )


def _short_error_description(exc: Exception, *, max_words: int = 200) -> str:
    words = f"{type(exc).__name__}: {exc}".split()
    return " ".join(words[:max_words])


async def _load_or_create_markdown(
    pdf_path: Path,
    markdown_output: Path,
    *,
    force_markdown: bool,
) -> str:
    if force_markdown or not markdown_output.exists():
        return await asyncio.to_thread(pdf_to_markdown, pdf_path, markdown_output)
    return await asyncio.to_thread(markdown_output.read_text, encoding="utf-8")


async def run_pdf_processing_async(
    pdf_path: Path,
    *,
    config: PdfProcessingConfig | None = None,
    output_dir: Path | None = None,
    prompt_first_batch: Path | None = None,
    prompt_continuation_batch: Path | None = None,
    force_markdown: bool = False,
    max_batches: int | None = None,
) -> Path:
    resolved_config = config or load_pdf_processing_config()
    if output_dir is not None:
        resolved_config = PdfProcessingConfig(**{**resolved_config.__dict__, "output_dir": output_dir})
    if prompt_first_batch is not None:
        resolved_config = PdfProcessingConfig(
            **{**resolved_config.__dict__, "prompt_first_batch": prompt_first_batch.expanduser().resolve()}
        )
    if prompt_continuation_batch is not None:
        resolved_config = PdfProcessingConfig(
            **{**resolved_config.__dict__, "prompt_continuation_batch": prompt_continuation_batch.expanduser().resolve()}
        )
    if max_batches is not None:
        resolved_config = PdfProcessingConfig(**{**resolved_config.__dict__, "max_batches": max_batches})

    pdf_path = pdf_path.expanduser().resolve()
    paper_dir = paper_output_dir(resolved_config.output_dir, pdf_path)
    paper_id = pdf_path.stem
    markdown_output = paper_dir / "paper.md"
    raw_batches_dir = paper_dir / "raw_batches"
    final_output, legacy_final_output = _final_output_paths(resolved_config.output_dir, pdf_path)
    status_file = resolved_config.output_dir / "processing_status.jsonl"
    if final_output.exists() or legacy_final_output.exists():
        resolved_output = _rename_legacy_output(final_output, legacy_final_output)
        append_processing_status(
            status_file,
            paper_id=paper_id,
            status="done",
        )
        print(f"[SKIP DONE] {paper_id}")
        return resolved_output

    status_error_written = False
    try:
        print(f"[PROCESSING] {paper_id}")
        try:
            markdown = await _load_or_create_markdown(
                pdf_path,
                markdown_output,
                force_markdown=force_markdown,
            )
        except Exception as exc:
            _append_failed_status(status_file, paper_id=paper_id, error="docling_failed", exc=exc)
            status_error_written = True
            print(f"[FAILED] {paper_id}: docling_failed: {type(exc).__name__}: {exc}")
            raise
        print(f"[PDF TO MARKDOWN] {paper_id}: chars={len(markdown)} output={ctx.display_path(markdown_output)}")
        try:
            batches = build_markdown_batches(
                markdown,
                min_chars=resolved_config.markdown_batch_chars,
                hard_limit_chars=resolved_config.markdown_batch_hard_limit_chars,
            )
        except MarkdownBatchingError as exc:
            _append_failed_status(status_file, paper_id=paper_id, error="batching_failed", exc=exc)
            status_error_written = True
            print(f"[FAILED] {paper_id}: batching_failed: {type(exc).__name__}: {exc}")
            raise
        if resolved_config.max_batches is not None:
            if resolved_config.max_batches < 1:
                raise ValueError("max_batches must be >= 1 when provided")
            batches = batches[: resolved_config.max_batches]
        if not batches:
            raise RuntimeError(f"No markdown batches generated for {pdf_path}")

        api_keys = load_gemini_api_keys()
        quota_repo = SQLiteQuotaRepository(ctx.DATA_RUNTIME_QUOTAS_DIR / "gemini.sqlite3")
        scheduler = GeminiKeyScheduler(
            quota_repo,
            requests_per_minute=resolved_config.requests_per_minute,
            requests_per_day=resolved_config.requests_per_day,
        )
        client = GeminiClient(config=resolved_config, scheduler=scheduler, api_keys=api_keys)

        first_prompt = _read_prompt(resolved_config.prompt_first_batch)
        continuation_template = _read_prompt(resolved_config.prompt_continuation_batch)
        results: list[dict[str, Any]] = []
        section_registry: list[dict[str, Any]] = []

        for batch in batches:
            prompt = first_prompt if batch.index == 1 else _continuation_prompt(continuation_template, results[-1], section_registry)
            print(
                f"[MARKDOWN BATCH] {paper_id}: batch={batch.index}/{len(batches)} "
                f"chars={len(batch.text)} range={batch.start_char}:{batch.end_char}"
            )
            try:
                result = await client.extract_markdown_batch(prompt, batch)
            except Exception as exc:
                _append_failed_status(status_file, paper_id=paper_id, error="llm_failed", exc=exc)
                status_error_written = True
                print(f"[FAILED] {paper_id}: llm_failed: {type(exc).__name__}: {exc}")
                raise
            result_with_debug = {
                "batch_index": batch.index,
                "start_char": batch.start_char,
                "end_char": batch.end_char,
                "result": result,
            }
            _write_json(raw_batches_dir / f"batch_{batch.index:04d}.json", result_with_debug)
            results.append(result)
            section_registry = _merge_section_registry(
                section_registry,
                result.get("section_registry") if batch.index == 1 else result.get("updated_section_registry"),
            )

        merged = merge_batch_outputs(
            source_pdf=pdf_path,
            batches=results,
            config=resolved_config,
        )
        _write_json(final_output, merged)
        append_processing_status(
            status_file,
            paper_id=paper_id,
            status="done",
        )
        print(f"[DONE] {paper_id}")
        return final_output
    except Exception as exc:
        if not status_error_written:
            _append_failed_status(status_file, paper_id=paper_id, error="processing_failed", exc=exc)
        print(f"[FAILED] {paper_id}: {type(exc).__name__}: {exc}")
        raise


def run_pdf_processing(pdf_path: Path, **kwargs: Any) -> Path:
    return asyncio.run(run_pdf_processing_async(pdf_path, **kwargs))


def _merge_section_registry(
    current: list[dict[str, Any]],
    incoming: Any,
) -> list[dict[str, Any]]:
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
        normalized = {
            "title": str(item.get("title") or "").strip(),
            "type": str(item.get("type") or "unknown").strip(),
            "parent": item.get("parent"),
        }
        if not normalized["title"]:
            continue
        key = (
            normalized["title"].lower(),
            normalized["type"].lower(),
            str(normalized["parent"] or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


async def run_pdf_processing_dir_async(
    input_dir: Path,
    *,
    limit: int | None = None,
    workers: int | None = None,
    config: PdfProcessingConfig | None = None,
    **kwargs: Any,
) -> list[Path]:
    resolved_config = config or load_pdf_processing_config()
    if workers is not None:
        resolved_config = PdfProcessingConfig(**{**resolved_config.__dict__, "workers": workers})
    if resolved_config.workers < 1:
        raise ValueError("workers must be >= 1")

    input_dir = input_dir.expanduser().resolve()
    pdfs = sorted(input_dir.glob("*.pdf"))
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be >= 1 when provided")

    status_file = resolved_config.output_dir / "processing_status.jsonl"
    status_index = load_processing_status_index(status_file)
    pending_pdfs: list[Path] = []
    for pdf_path in pdfs:
        paper_id = pdf_path.stem
        final_output, legacy_final_output = _final_output_paths(resolved_config.output_dir, pdf_path)
        if final_output.exists() or legacy_final_output.exists():
            resolved_output = _rename_legacy_output(final_output, legacy_final_output)
            append_processing_status(
                status_file,
                paper_id=paper_id,
                status="done",
            )
            status_index[paper_id] = {
                "paper_id": paper_id,
                "status": "done",
                "error": None,
            }
            print(f"[SKIP DONE] {paper_id}")
            continue
        if (status_index.get(paper_id) or {}).get("status") == "done":
            print(f"[SKIP DONE] {paper_id}")
            continue
        pending_pdfs.append(pdf_path)
        if limit is not None and len(pending_pdfs) >= limit:
            break
    write_processing_status_index(status_file, status_index)

    outputs: list[Path] = []
    queue: asyncio.Queue[Path] = asyncio.Queue()
    for pdf_path in pending_pdfs:
        queue.put_nowait(pdf_path)

    async def worker() -> None:
        while True:
            try:
                pdf_path = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                outputs.append(await run_pdf_processing_async(pdf_path, config=resolved_config, **kwargs))
            except Exception as exc:
                print(f"[FAIL] {pdf_path}: {type(exc).__name__}: {exc}")
            finally:
                queue.task_done()

    if pending_pdfs:
        await asyncio.gather(*(worker() for _ in range(min(resolved_config.workers, len(pending_pdfs)))))
    return outputs


def run_pdf_processing_dir(input_dir: Path, **kwargs: Any) -> list[Path]:
    return asyncio.run(run_pdf_processing_dir_async(input_dir, **kwargs))
