from __future__ import annotations

import argparse
import json
import os
import queue
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import requests

from src.claims.extraction import (
    build_claims_preview,
    build_prompt,
    estimate_text_tokens,
    normalize_missing_section,
    parse_input_sections,
    validate_claims,
)


DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_API_VERSION = "v1beta"
DEFAULT_INPUT_DIR = Path("data/papers")
DEFAULT_OUTPUT_DIR = Path("data/runtime/claims")
DEFAULT_PATTERN = "*/docling/final.json"
REQUEST_DELAY_SECONDS = 1.5
KEY_FAILURE_DELAY_SECONDS = 30.0
KEY_ENV_NAMES = ("GEMINI_KEY_1", "GEMINI_KEY_2", "GEMINI_KEY_3")


@dataclass(frozen=True)
class ClaimJob:
    paper_id: str
    final_json_path: Path
    output_path: Path


class GeminiRequestError(RuntimeError):
    pass


class GeminiRateLimitError(GeminiRequestError):
    def __init__(self, message: str, retry_delay: float | None = None) -> None:
        super().__init__(message)
        self.retry_delay = retry_delay


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract claims from data/papers/*/docling/final.json using Gemini."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-version", default=DEFAULT_API_VERSION)
    parser.add_argument("--max-claims", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--request-delay", type=float, default=REQUEST_DELAY_SECONDS)
    parser.add_argument("--key-failure-delay", type=float, default=KEY_FAILURE_DELAY_SECONDS)
    return parser.parse_args()


def load_api_keys(env: dict[str, str] | None = None) -> list[str]:
    source = env if env is not None else os.environ
    keys = [str(source.get(name, "")).strip() for name in KEY_ENV_NAMES]
    if all(keys):
        return keys

    missing = [name for name, value in zip(KEY_ENV_NAMES, keys, strict=True) if not value]
    raise ValueError(
        f"Missing Gemini API keys: {', '.join(missing)}. "
        "Set them in the environment or in the repo .env file."
    )


def discover_jobs(
    input_dir: Path,
    output_dir: Path,
    pattern: str = DEFAULT_PATTERN,
    limit: int | None = None,
    overwrite: bool = False,
) -> list[ClaimJob]:
    input_root = input_dir.expanduser().resolve()
    output_root = output_dir.expanduser().resolve()
    files = sorted(path for path in input_root.glob(pattern) if path.is_file())
    jobs: list[ClaimJob] = []
    for final_json_path in files:
        try:
            paper_id = final_json_path.relative_to(input_root).parts[0]
        except ValueError:
            paper_id = final_json_path.parents[1].name
        paper_claims = input_root / paper_id / "claims" / "claims.json"
        runtime_claims = output_root / f"{paper_id}.claims.json"
        if not overwrite and (paper_claims.exists() or runtime_claims.exists()):
            continue
        jobs.append(
            ClaimJob(
                paper_id=paper_id,
                final_json_path=final_json_path,
                output_path=runtime_claims,
            )
        )
        if limit is not None and len(jobs) >= limit:
            break
    return jobs


def build_prompt_for_final_json(final_json_path: Path, max_claims: int | None) -> tuple[str, dict[str, Any]]:
    sections = parse_input_sections(final_json_path)
    preview = build_claims_preview(final_json_path, max_claims=max_claims)
    trace_text = normalize_missing_section(sections.get("trace"))
    sections_text = normalize_missing_section(sections.get("sections_text"))
    available_sections = ", ".join(
        str(title) for title in sections.get("available_sections", []) if str(title).strip()
    ) or "none"
    prompt = build_prompt(
        trace_text=trace_text,
        sections_text=sections_text,
        max_claims=int(preview["claims_limit"]["final_claims"]),
        available_sections=available_sections,
    )
    return prompt, preview


def gemini_endpoint(model: str, api_version: str) -> str:
    return f"https://generativelanguage.googleapis.com/{api_version}/models/{model}:generateContent"


def extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise GeminiRequestError("Gemini response has no candidates.")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise GeminiRequestError("Gemini response has no content parts.")
    texts = [part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")]
    if not texts:
        raise GeminiRequestError("Gemini response has no text.")
    return "\n".join(str(text) for text in texts)


def parse_claims_text(text: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return validate_claims(json.loads(stripped))


def call_gemini(
    prompt: str,
    api_key: str,
    model: str,
    api_version: str,
    post: Callable[..., Any] = requests.post,
) -> str:
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    response = post(
        gemini_endpoint(model, api_version),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        json=body,
        timeout=120,
    )
    if response.status_code >= 400:
        message = f"Gemini HTTP {response.status_code}: {response.text[:500]}"
        if response.status_code == 429:
            raise GeminiRateLimitError(message, retry_delay=parse_retry_delay(response.text))
        raise GeminiRequestError(message)
    return extract_gemini_text(response.json())


def parse_retry_delay(text: str) -> float | None:
    match = re.search(r"Please retry in ([0-9.]+)s", text)
    if match:
        return float(match.group(1))
    match = re.search(r"Please retry in ([0-9.]+)ms", text)
    if match:
        return float(match.group(1)) / 1000
    return None


def call_with_key_rotation(
    prompt: str,
    keys: list[str],
    start_index: int,
    model: str,
    api_version: str,
    request_delay: float = REQUEST_DELAY_SECONDS,
    key_failure_delay: float = KEY_FAILURE_DELAY_SECONDS,
    post: Callable[..., Any] = requests.post,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, int, int]:
    attempts = 0
    key_index = start_index
    max_attempts = max(1, len(keys) * 3)
    last_error: Exception | None = None
    while attempts < max_attempts:
        current_index = key_index % len(keys)
        attempts += 1
        try:
            text = call_gemini(
                prompt=prompt,
                api_key=keys[current_index],
                model=model,
                api_version=api_version,
                post=post,
            )
            sleep(request_delay)
            return text, current_index, attempts
        except Exception as exc:
            last_error = exc
            sleep(key_failure_delay)
            key_index += 1
    raise GeminiRequestError(f"All Gemini keys failed after {attempts} attempts: {last_error}")


def call_with_single_key(
    prompt: str,
    api_key: str,
    key_index: int,
    model: str,
    api_version: str,
    request_delay: float = REQUEST_DELAY_SECONDS,
    post: Callable[..., Any] = requests.post,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[str, int, int]:
    text = call_gemini(
        prompt=prompt,
        api_key=api_key,
        model=model,
        api_version=api_version,
        post=post,
    )
    sleep(request_delay)
    return text, key_index, 1


def write_claims_output(
    job: ClaimJob,
    claims: list[dict[str, Any]],
    model: str,
    key_index: int,
    attempts: int,
    prompt: str,
    preview: dict[str, Any],
) -> None:
    payload = {
        "metadata": {
            "paper_id": job.paper_id,
            "model": model,
            "created_at": datetime.now(UTC).isoformat(),
            "source_final_json": str(job.final_json_path),
            "prompt_tokens_estimated": estimate_text_tokens(prompt),
            "claims_limit": preview["claims_limit"]["final_claims"],
            "key_index_used": key_index + 1,
            "attempts": attempts,
        },
        "claims": claims,
    }
    job.output_path.parent.mkdir(parents=True, exist_ok=True)
    job.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def progress_iter(items: list[ClaimJob]) -> Any:
    try:
        from tqdm import tqdm

        return tqdm(items, desc="Gemini claims")
    except Exception:
        return items


def run_parallel(args: argparse.Namespace, jobs: list[ClaimJob], keys: list[str]) -> tuple[int, int]:
    try:
        from tqdm import tqdm

        progress = tqdm(total=len(jobs), desc="Gemini claims")
    except Exception:
        progress = None

    work_queue: queue.Queue[ClaimJob | None] = queue.Queue()
    for job in jobs:
        work_queue.put(job)

    lock = threading.Lock()
    counts = {"processed": 0, "failed": 0}
    worker_count = max(1, args.workers)

    def worker(worker_id: int, api_key: str) -> None:
        while True:
            job = work_queue.get()
            if job is None:
                work_queue.task_done()
                return
            try:
                print(f"[W{worker_id + 1}] {job.paper_id}", flush=True)
                prompt, preview = build_prompt_for_final_json(job.final_json_path, args.max_claims)
                raw_text, key_index, attempts = call_with_key_rotation(
                    prompt=prompt,
                    keys=keys,
                    start_index=worker_id,
                    model=args.model,
                    api_version=args.api_version,
                    request_delay=args.request_delay,
                    key_failure_delay=args.key_failure_delay,
                )
                claims = parse_claims_text(raw_text)
                write_claims_output(
                    job=job,
                    claims=claims,
                    model=args.model,
                    key_index=key_index,
                    attempts=attempts,
                    prompt=prompt,
                    preview=preview,
                )
                with lock:
                    counts["processed"] += 1
                    if progress is not None:
                        progress.update(1)
            except Exception as exc:
                if isinstance(exc, GeminiRateLimitError) or "HTTP 429" in str(exc):
                    delay = getattr(exc, "retry_delay", None) or args.key_failure_delay
                    delay = max(delay, args.key_failure_delay)
                    print(f"[429 W{worker_id + 1}] {job.paper_id}: sleep {delay:.1f}s", file=sys.stderr, flush=True)
                    time.sleep(delay)
                    work_queue.put(job)
                else:
                    print(f"[SKIP W{worker_id + 1}] {job.paper_id}: {exc}", file=sys.stderr, flush=True)
                    with lock:
                        counts["failed"] += 1
                        if progress is not None:
                            progress.update(1)
            finally:
                work_queue.task_done()

    threads = [
        threading.Thread(target=worker, args=(index, keys[index % len(keys)]), daemon=True)
        for index in range(worker_count)
    ]
    for thread in threads:
        thread.start()
    for _ in threads:
        work_queue.put(None)
    work_queue.join()
    for thread in threads:
        thread.join()
    if progress is not None:
        progress.close()
    return counts["processed"], counts["failed"]


def run(args: argparse.Namespace) -> int:
    jobs = discover_jobs(
        input_dir=args.input,
        output_dir=args.output_dir,
        pattern=args.pattern,
        limit=args.limit,
        overwrite=args.overwrite,
    )
    print(f"Jobs: {len(jobs)}")
    if args.dry_run:
        for job in jobs:
            print(f"{job.paper_id}: {job.final_json_path} -> {job.output_path}")
        return 0

    keys = load_api_keys()
    if args.workers > 1:
        processed, failed = run_parallel(args, jobs, keys)
        print(f"Processed: {processed}")
        print(f"Failed: {failed}")
        return 1 if failed else 0

    key_cursor = 0
    processed = 0
    failed = 0
    for job in progress_iter(jobs):
        try:
            print(f"[RUN] {job.paper_id} -> {job.output_path}", flush=True)
            prompt, preview = build_prompt_for_final_json(job.final_json_path, args.max_claims)
            raw_text, key_index, attempts = call_with_key_rotation(
                prompt=prompt,
                keys=keys,
                start_index=key_cursor,
                model=args.model,
                api_version=args.api_version,
                request_delay=args.request_delay,
                key_failure_delay=args.key_failure_delay,
            )
            key_cursor = key_index + 1
            claims = parse_claims_text(raw_text)
            write_claims_output(
                job=job,
                claims=claims,
                model=args.model,
                key_index=key_index,
                attempts=attempts,
                prompt=prompt,
                preview=preview,
            )
            processed += 1
        except Exception as exc:
            failed += 1
            print(f"[SKIP] {job.paper_id}: {exc}", file=sys.stderr)
    print(f"Processed: {processed}")
    print(f"Failed: {failed}")
    return 1 if failed else 0


def main() -> None:
    try:
        raise SystemExit(run(parse_args()))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
