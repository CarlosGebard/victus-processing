from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from src.workspace import config as ctx
from src.application.pdf_processing.batching import MarkdownBatchingError, build_markdown_batches
from src.application.ports.llm import LLMClient
from src.application.ports.prompt_registry import PromptRegistry, PromptSpec
from src.infrastructure.prompts.compile import compile_template
from src.application.pdf_processing.llm_markdown import LLMMarkdownResponseError, extract_markdown_batch
from src.application.pdf_processing.markdown import pdf_to_markdown
from src.application.pdf_processing.merge import merge_batch_outputs
from src.application.pdf_processing.models import PdfProcessingConfig
from src.application.pdf_processing.processed_paper_contract import build_final_paper, enforce_processed_paper_contract
from src.application.pdf_processing.status import append_processing_status, load_processing_status_index, write_processing_status_index


def load_pdf_processing_config() -> PdfProcessingConfig:
    cfg = ctx.CONFIG.get("pdf_processing") or {}
    return PdfProcessingConfig(
        model=str(cfg.get("model", "litellm_proxy/gemini-flash-lite")),
        input_dir=ctx.resolve_project_path(cfg.get("input_dir"), ctx.DATA_RUNTIME_PDFS_ACTIVE_DIR),
        output_dir=ctx.resolve_project_path(cfg.get("output_dir"), ctx.DATA_RUNTIME_PDF_PROCESSING_DIR),
        workers=int(cfg.get("workers", 1)),
        prompt_first_batch=ctx.resolve_project_path(
            cfg.get("prompt_first_batch"),
            ctx.ROOT_DIR / "src/prompts/pdf_processing/markdown_first_batch.md",
        ),
        prompt_continuation_batch=ctx.resolve_project_path(
            cfg.get("prompt_continuation_batch"),
            ctx.ROOT_DIR / "src/prompts/pdf_processing/markdown_continuation_batch.md",
        ),
        markdown_batch_chars=int(cfg.get("markdown_batch_chars", 6000)),
        markdown_batch_soft_limit_chars=int(cfg.get("markdown_batch_soft_limit_chars", 9000)),
        markdown_batch_hard_limit_chars=int(cfg.get("markdown_batch_hard_limit_chars", 14000)),
        max_batches=int(cfg["max_batches"]) if cfg.get("max_batches") is not None else None,
        max_tokens=int(cfg["max_tokens"]) if cfg.get("max_tokens") is not None else None,
        request_timeout_seconds=float(cfg.get("request_timeout_seconds", 120)),
    )


def paper_output_dir(base_output_dir: Path, pdf_path: Path) -> Path:
    return base_output_dir / pdf_path.stem


def _read_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def _load_prompt(
    registry: PromptRegistry | None,
    *,
    name: str,
    label: str,
    local_path: Path,
) -> tuple[str, PromptSpec | None]:
    if registry is None:
        return _read_prompt(local_path), None
    spec = registry.get(name, label=label)
    return spec.template, spec


def _prompt_config_value(config: dict[str, Any], key: str, default: Any) -> Any:
    value = config.get(key)
    return default if value is None else value


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


def _write_llm_failure(path: Path, *, batch_index: int, batch_start: int, batch_end: int, exc: Exception) -> None:
    payload: dict[str, Any] = {
        "batch_index": batch_index,
        "start_char": batch_start,
        "end_char": batch_end,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    if isinstance(exc, LLMMarkdownResponseError) and exc.response_text is not None:
        payload["response_text"] = exc.response_text
    _write_json(path, payload)


def _write_markdown_batch_debug(output_dir: Path, batches: tuple[Any, ...]) -> None:
    for batch in batches:
        batch_md = output_dir / f"batch_{batch.index:04d}.md"
        batch_md.parent.mkdir(parents=True, exist_ok=True)
        batch_md.write_text(batch.text, encoding="utf-8")
        _write_json(
            output_dir / f"batch_{batch.index:04d}.json",
            {
                "batch_index": batch.index,
                "start_char": batch.start_char,
                "end_char": batch.end_char,
                "chars": len(batch.text),
                "previous_section_path": list(batch.previous_section_path),
                "last_heading": batch.last_heading,
                "last_300_chars": batch.last_300_chars,
                "oversized_unit": batch.oversized_unit,
            },
        )


def write_markdown_batch_debug_for_markdown(
    markdown_path: Path,
    output_dir: Path,
    *,
    config: PdfProcessingConfig | None = None,
    max_batches: int | None = None,
) -> tuple[Path, ...]:
    resolved_config = config or load_pdf_processing_config()
    markdown = markdown_path.expanduser().resolve().read_text(encoding="utf-8")
    batches = build_markdown_batches(
        markdown,
        min_chars=resolved_config.markdown_batch_chars,
        soft_limit_chars=resolved_config.markdown_batch_soft_limit_chars,
        hard_limit_chars=resolved_config.markdown_batch_hard_limit_chars,
    )
    effective_max_batches = max_batches if max_batches is not None else resolved_config.max_batches
    if effective_max_batches is not None:
        if effective_max_batches < 1:
            raise ValueError("max_batches must be >= 1 when provided")
        batches = batches[:effective_max_batches]
    if not batches:
        raise RuntimeError(f"No markdown batches generated for {markdown_path}")
    resolved_output_dir = output_dir.expanduser().resolve()
    _write_markdown_batch_debug(resolved_output_dir, batches)
    return tuple(resolved_output_dir / f"batch_{batch.index:04d}.md" for batch in batches)


def _final_output_paths(output_dir: Path, pdf_path: Path) -> tuple[Path, Path, Path]:
    paper_dir = paper_output_dir(output_dir, pdf_path)
    return paper_dir / "paper.processed.json", paper_dir / "paper.final.json", paper_dir / "paper.json"


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
    llm_client: LLMClient | None = None,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
    markdown_batches_dir: Path | None = None,
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
    processed_output, final_output, legacy_final_output = _final_output_paths(resolved_config.output_dir, pdf_path)
    status_file = resolved_config.output_dir / "processing_status.jsonl"
    if final_output.exists():
        append_processing_status(
            status_file,
            paper_id=paper_id,
            status="done",
        )
        print(f"[SKIP DONE] {paper_id}")
        return final_output
    if processed_output.exists() or legacy_final_output.exists():
        resolved_output = _rename_legacy_output(processed_output, legacy_final_output)
        processed = json.loads(resolved_output.read_text(encoding="utf-8"))
        _write_json(final_output, build_final_paper(processed))
        append_processing_status(
            status_file,
            paper_id=paper_id,
            status="done",
        )
        print(f"[FINALIZED] {paper_id}")
        return final_output

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
                soft_limit_chars=resolved_config.markdown_batch_soft_limit_chars,
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
        if markdown_batches_dir is not None:
            _write_markdown_batch_debug(markdown_batches_dir.expanduser().resolve(), batches)

        if llm_client is None:
            raise RuntimeError("LLM client is required.")
        client = llm_client

        first_template, first_spec = _load_prompt(
            prompt_registry,
            name="pdf_processing/markdown_first_batch",
            label=prompt_label,
            local_path=resolved_config.prompt_first_batch,
        )
        continuation_template, continuation_spec = _load_prompt(
            prompt_registry,
            name="pdf_processing/markdown_continuation_batch",
            label=prompt_label,
            local_path=resolved_config.prompt_continuation_batch,
        )
        results: list[dict[str, Any]] = []
        section_registry: list[dict[str, Any]] = []

        for batch in batches:
            if batch.index == 1:
                prompt = compile_template(first_template, {})
                prompt_spec = first_spec
            else:
                prompt = _continuation_prompt(
                    compile_template(continuation_template, {}),
                    results[-1],
                    section_registry,
                )
                prompt_spec = continuation_spec
            prompt_config = prompt_spec.config if prompt_spec else {}
            effective_model = str(_prompt_config_value(prompt_config, "model", resolved_config.model))
            effective_max_tokens = (
                prompt_config.get("max_tokens")
                if prompt_spec is not None and prompt_spec.source != "local"
                else resolved_config.max_tokens
            )
            print(
                f"[MARKDOWN BATCH] {paper_id}: batch={batch.index}/{len(batches)} "
                f"chars={len(batch.text)} range={batch.start_char}:{batch.end_char}"
            )
            try:
                result = await extract_markdown_batch(
                    client,
                    model=effective_model,
                    prompt=prompt,
                    batch=batch,
                    paper_id=paper_id,
                    prompt_spec=prompt_spec,
                    prompt_label=prompt_label,
                    temperature=prompt_config.get("temperature"),
                    max_tokens=effective_max_tokens,
                )
            except Exception as exc:
                _write_llm_failure(
                    raw_batches_dir / f"batch_{batch.index:04d}.failed.json",
                    batch_index=batch.index,
                    batch_start=batch.start_char,
                    batch_end=batch.end_char,
                    exc=exc,
                )
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
        merged = enforce_processed_paper_contract(merged)
        _write_json(processed_output, merged)
        _write_json(final_output, build_final_paper(merged))
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


async def run_markdown_processing_async(
    markdown_path: Path,
    *,
    config: PdfProcessingConfig | None = None,
    output_dir: Path | None = None,
    prompt_first_batch: Path | None = None,
    prompt_continuation_batch: Path | None = None,
    force_markdown: bool = False,
    max_batches: int | None = None,
    llm_client: LLMClient | None = None,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
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

    markdown_path = markdown_path.expanduser().resolve()
    if markdown_path.name != "paper.md":
        raise ValueError("Markdown input must be named paper.md")
    paper_id = markdown_path.parent.name
    if not paper_id:
        raise ValueError("Markdown input must live under a paper id directory")

    paper_dir = resolved_config.output_dir / paper_id
    raw_batches_dir = paper_dir / "raw_batches"
    source_pdf = resolved_config.input_dir / f"{paper_id}.pdf"
    processed_output = paper_dir / "paper.processed.json"
    final_output = paper_dir / "paper.final.json"
    legacy_final_output = paper_dir / "paper.json"
    status_file = resolved_config.output_dir / "processing_status.jsonl"
    if final_output.exists():
        append_processing_status(status_file, paper_id=paper_id, status="done")
        print(f"[SKIP DONE] {paper_id}")
        return final_output
    if processed_output.exists() or legacy_final_output.exists():
        resolved_output = _rename_legacy_output(processed_output, legacy_final_output)
        processed = json.loads(resolved_output.read_text(encoding="utf-8"))
        _write_json(final_output, build_final_paper(processed))
        append_processing_status(status_file, paper_id=paper_id, status="done")
        print(f"[FINALIZED] {paper_id}")
        return final_output

    status_error_written = False
    try:
        print(f"[PROCESSING MARKDOWN] {paper_id}")
        markdown = await asyncio.to_thread(markdown_path.read_text, encoding="utf-8")
        print(f"[MARKDOWN INPUT] {paper_id}: chars={len(markdown)} input={ctx.display_path(markdown_path)}")
        try:
            batches = build_markdown_batches(
                markdown,
                min_chars=resolved_config.markdown_batch_chars,
                soft_limit_chars=resolved_config.markdown_batch_soft_limit_chars,
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
            raise RuntimeError(f"No markdown batches generated for {markdown_path}")

        if llm_client is None:
            raise RuntimeError("LLM client is required.")
        client = llm_client
        first_template, first_spec = _load_prompt(
            prompt_registry,
            name="pdf_processing/markdown_first_batch",
            label=prompt_label,
            local_path=resolved_config.prompt_first_batch,
        )
        continuation_template, continuation_spec = _load_prompt(
            prompt_registry,
            name="pdf_processing/markdown_continuation_batch",
            label=prompt_label,
            local_path=resolved_config.prompt_continuation_batch,
        )
        results: list[dict[str, Any]] = []
        section_registry: list[dict[str, Any]] = []
        for batch in batches:
            if batch.index == 1:
                prompt = compile_template(first_template, {})
                prompt_spec = first_spec
            else:
                prompt = _continuation_prompt(
                    compile_template(continuation_template, {}),
                    results[-1],
                    section_registry,
                )
                prompt_spec = continuation_spec
            prompt_config = prompt_spec.config if prompt_spec else {}
            effective_model = str(_prompt_config_value(prompt_config, "model", resolved_config.model))
            effective_max_tokens = (
                prompt_config.get("max_tokens")
                if prompt_spec is not None and prompt_spec.source != "local"
                else resolved_config.max_tokens
            )
            print(
                f"[MARKDOWN BATCH] {paper_id}: batch={batch.index}/{len(batches)} "
                f"chars={len(batch.text)} range={batch.start_char}:{batch.end_char}"
            )
            try:
                result = await extract_markdown_batch(
                    client,
                    model=effective_model,
                    prompt=prompt,
                    batch=batch,
                    paper_id=paper_id,
                    prompt_spec=prompt_spec,
                    prompt_label=prompt_label,
                    temperature=prompt_config.get("temperature"),
                    max_tokens=effective_max_tokens,
                )
            except Exception as exc:
                _write_llm_failure(
                    raw_batches_dir / f"batch_{batch.index:04d}.failed.json",
                    batch_index=batch.index,
                    batch_start=batch.start_char,
                    batch_end=batch.end_char,
                    exc=exc,
                )
                _append_failed_status(status_file, paper_id=paper_id, error="llm_failed", exc=exc)
                status_error_written = True
                print(f"[FAILED] {paper_id}: llm_failed: {type(exc).__name__}: {exc}")
                raise
            _write_json(
                raw_batches_dir / f"batch_{batch.index:04d}.json",
                {"batch_index": batch.index, "start_char": batch.start_char, "end_char": batch.end_char, "result": result},
            )
            results.append(result)
            section_registry = _merge_section_registry(
                section_registry,
                result.get("section_registry") if batch.index == 1 else result.get("updated_section_registry"),
            )

        merged = merge_batch_outputs(source_pdf=source_pdf, batches=results, config=resolved_config)
        merged = enforce_processed_paper_contract(merged)
        _write_json(processed_output, merged)
        _write_json(final_output, build_final_paper(merged))
        append_processing_status(status_file, paper_id=paper_id, status="done")
        print(f"[DONE] {paper_id}")
        return final_output
    except Exception as exc:
        if not status_error_written:
            _append_failed_status(status_file, paper_id=paper_id, error="processing_failed", exc=exc)
        print(f"[FAILED] {paper_id}: {type(exc).__name__}: {exc}")
        raise


def run_markdown_processing(markdown_path: Path, **kwargs: Any) -> Path:
    return asyncio.run(run_markdown_processing_async(markdown_path, **kwargs))


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
        title = str(item.get("title") or item.get("canonical_title") or item.get("original_title") or "").strip()
        section_type = str(item.get("type") or item.get("section_type") or "unknown").strip()
        normalized = {
            "title": title,
            "type": section_type,
            "original_title": item.get("original_title") or title,
            "canonical_title": item.get("canonical_title") or title,
            "section_type": section_type,
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
        _processed_output, final_output, _legacy_final_output = _final_output_paths(resolved_config.output_dir, pdf_path)
        if final_output.exists():
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
        if (status_index.get(paper_id) or {}).get("status") == "done" and final_output.exists():
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
