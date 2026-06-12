from __future__ import annotations

import json
import random
import threading
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import requests
from requests import HTTPError

from src.workspace.config import (
    EXPLORATION_COMPLETED_SEED_DOI_FILE,
    EXPLORATION_SEED_DOI_FILE,
    DATA_LAKE_DIR,
    get_config,
    get_env_or_config,
    get_pipeline_paths,
)
from src.workspace.artifacts import build_base_name, normalize_doi
from src.application.ports.llm import LLMClient
from src.application.ports.prompt_registry import PromptRegistry
from src.application.metadata_extraction.paper_selector import PaperCandidate, classify_papers_with_llm


config = get_config()
paths = get_pipeline_paths(config)

SEMANTIC_URL = config["api"]["semantic_scholar_url"]
SEMANTIC_API_KEY = get_env_or_config(
    "SEMANTIC_SCHOLAR_API_KEY",
    "api",
    "semantic_scholar_api_key",
    config=config,
)

seed = config["seed_paper"]
seed_doi_file = EXPLORATION_SEED_DOI_FILE
completed_seed_doi_file = EXPLORATION_COMPLETED_SEED_DOI_FILE

limit = config["exploration"]["limit"]
min_citations = config["exploration"]["min_citations"]
buffer_size = config["exploration"]["buffer_size"]
max_words = config["exploration"]["max_abstract_words"]
min_year = config["exploration"].get("min_year", 2000)
metadata_selection_cfg = config.get("metadata_selection") or {}
selection_model = get_env_or_config(
    "LITELLM_METADATA_SELECTION_MODEL",
    "metadata_selection",
    "model",
    default="gpt-5-mini",
    config=config,
)
selection_preview_words = max(1, int(metadata_selection_cfg.get("abstract_preview_words", 20)))
selection_batch_size = max(1, int(metadata_selection_cfg.get("batch_size", 20)))

paper_metadata_lake_file = DATA_LAKE_DIR / "paper_metadata.jsonl"

session = requests.Session()
if SEMANTIC_API_KEY:
    session.headers.update({"x-api-key": SEMANTIC_API_KEY})

_rate_lock = threading.Lock()
_last_request_ts = 0.0
REQUEST_INTERVAL_SECONDS = 1.0
PAPER_FIELDS = "paperId,title,year,authors,citationCount,externalIds,openAccessPdf,abstract"
CITATION_FIELDS = f"citingPaper.{PAPER_FIELDS}"


def normalize_selection_mode(selection_mode: str) -> str:
    normalized = str(selection_mode or "").strip()
    if normalized in {"broad-nutrition", "nutrition-rag", "nutrition"}:
        return "broad-nutrition"
    raise ValueError(f"Selection mode no soportado: {selection_mode}")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _collect_lake_paper_metadata_ids(lake_file: Path | None = None) -> set[str]:
    return _collect_lake_paper_metadata_ids_cached(str((lake_file or paper_metadata_lake_file).resolve()))


@lru_cache(maxsize=1)
def _collect_lake_paper_metadata_ids_cached(lake_file_path: str) -> set[str]:
    processed: set[str] = set()
    lake_file = Path(lake_file_path)
    if not lake_file.exists():
        return processed

    for raw_line in lake_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        source_metadata = payload.get("source_metadata")
        if not isinstance(source_metadata, dict):
            continue
        paper_id = str(source_metadata.get("source_paper_id") or "").strip()
        if paper_id:
            processed.add(paper_id)
        doi = normalize_doi(str(source_metadata.get("doi") or ""))
        if doi:
            processed.add(build_base_name(doi))
    return processed


def collect_processed_papers() -> set[str]:
    return _collect_lake_paper_metadata_ids()


def _semantic_rate_limit() -> None:
    global _last_request_ts
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_ts
        if elapsed < REQUEST_INTERVAL_SECONDS:
            time.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
        _last_request_ts = time.monotonic()


def request_with_backoff(url: str, params: dict[str, Any] | None = None) -> requests.Response:
    retries = config["rate_limit"]["retries"]
    base_delay = config["rate_limit"]["base_delay"]
    max_delay = config["rate_limit"]["max_delay"]

    for attempt in range(retries):
        _semantic_rate_limit()
        response = session.get(url, params=params, timeout=60)

        if response.status_code == 200:
            return response

        if response.status_code in (429, 500, 502, 503, 504):
            delay = min(max_delay, base_delay * (2**attempt))
            delay += random.uniform(0, 1)
            time.sleep(delay)
            continue

        response.raise_for_status()

    raise RuntimeError("Max retries exceeded")


def fetch_paper_by_doi(doi: str) -> dict[str, Any]:
    normalized_doi = normalize_doi(doi)
    url = f"{SEMANTIC_URL}/paper/DOI:{normalized_doi}"
    response = request_with_backoff(url, params={"fields": PAPER_FIELDS})
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("paperId"):
        raise RuntimeError(f"Seed DOI inválido o no encontrado: {normalized_doi}")
    return payload


def _as_int_or_none(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = _as_str_or_none(item.get("name"))
        else:
            name = _as_str_or_none(item)
        if name:
            authors.append(name)
    return authors


def _metadata_id_for_record(record: dict[str, Any]) -> str | None:
    paper_id = _as_str_or_none(record.get("paperId"))
    if paper_id:
        return f"meta:s2:{paper_id}"
    doi = normalize_doi(str(record.get("doi") or ""))
    if doi:
        return f"meta:crossref:{doi}"
    return None


def normalize_candidate_record(record: dict[str, Any], *, decision: str) -> dict[str, Any] | None:
    metadata_id = _metadata_id_for_record(record)
    title = _as_str_or_none(record.get("title"))
    if not metadata_id or not title:
        return None

    timestamp = utc_now_iso()
    doi = normalize_doi(str(record.get("doi") or "")) or None
    return {
        "metadata_id": metadata_id,
        "source_metadata": {
            "source": "semantic_scholar",
            "source_paper_id": _as_str_or_none(record.get("paperId")),
            "doi": doi,
            "arxiv": _as_str_or_none(record.get("arxiv")),
            "title": title,
            "year": _as_int_or_none(record.get("year")),
            "citation_count": _as_int_or_none(record.get("citationCount")),
            "pdf_url": _as_str_or_none(record.get("pdf_url")),
            "authors": _authors(record.get("authors")),
        },
        "schema_version": "v1",
        "discovery": {
            "seed_papers": [normalize_doi(str(item)) for item in record.get("seed_papers", []) if normalize_doi(str(item))],
            "is_seed_paper": bool(record.get("is_seed_paper")),
        },
        "domain_screening": {
            "decision": decision,
            "model": None,
        },
        "created_at": _as_str_or_none(record.get("created_at")) or timestamp,
        "updated_at": timestamp,
    }


def _upsert_lake_metadata_record(
    candidate: dict[str, Any],
    *,
    decision: str,
    output_file: Path | None = None,
    overwrite: bool = True,
) -> tuple[Path, str, dict[str, Any]]:
    output_file = output_file or paper_metadata_lake_file
    metadata = normalize_candidate_record(candidate, decision=decision)
    if metadata is None:
        raise ValueError("No se pudo construir metadata lake record.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    if output_file.exists():
        for line in output_file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))

    source_metadata = metadata["source_metadata"]
    metadata_id = metadata["metadata_id"]
    doi_key = source_metadata.get("doi")
    existing_index = next(
        (
            index
            for index, row in enumerate(rows)
            if row.get("metadata_id") == metadata_id
            or (
                doi_key
                and isinstance(row.get("source_metadata"), dict)
                and row["source_metadata"].get("doi") == doi_key
            )
        ),
        None,
    )
    if existing_index is not None and not overwrite:
        return output_file, "skipped_existing", rows[existing_index]

    if existing_index is None:
        rows.append(metadata)
    else:
        existing = rows[existing_index]
        metadata["created_at"] = existing.get("created_at") or metadata["created_at"]
        rows[existing_index] = metadata

    output_file.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    _collect_lake_paper_metadata_ids_cached.cache_clear()
    return output_file, "written", metadata


def write_metadata_for_doi(
    doi: str,
    *,
    output_dir: Path = paper_metadata_lake_file,
    overwrite: bool = False,
) -> tuple[Path, str]:
    normalized_doi = normalize_doi(doi)
    paper = fetch_paper_by_doi(normalized_doi)
    candidate = paper_to_metadata_record(
        paper,
        parent=None,
        seed_doi=normalized_doi,
        is_seed_paper=True,
        abstract_word_limit=10**9,
    )
    output_path, status, _metadata = _upsert_lake_metadata_record(
        candidate,
        decision="keep",
        output_file=output_dir,
        overwrite=overwrite,
    )
    return output_path, status


def _load_doi_list(doi_file: Path) -> list[str]:
    seeds: list[str] = []
    seen: set[str] = set()

    if doi_file.exists():
        for raw_line in doi_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = None
            doi_value = payload.get("doi") if isinstance(payload, dict) else line
            normalized = normalize_doi(str(doi_value or ""))
            if normalized and normalized not in seen:
                seeds.append(normalized)
                seen.add(normalized)

    return seeds


def load_seed_dois(
    doi_file: Path = seed_doi_file,
    fallback_seed: str | None = seed,
) -> list[str]:
    seeds = _load_doi_list(doi_file)

    if seeds:
        return seeds

    if doi_file.exists():
        return []

    if fallback_seed:
        normalized_seed = normalize_doi(fallback_seed)
        if normalized_seed:
            return [normalized_seed]

    raise ValueError(
        f"No se encontraron seed DOIs en {doi_file} y no hay fallback configurado."
    )


def load_completed_seed_dois(doi_file: Path = completed_seed_doi_file) -> set[str]:
    return set(_load_doi_list(doi_file))


def _remove_seed_doi_from_queue(doi: str, doi_file: Path) -> None:
    if not doi_file.exists():
        return

    normalized = normalize_doi(doi)
    kept_lines: list[str] = []

    for raw_line in doi_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        doi_value = line
        if line and not line.startswith("#"):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                doi_value = str(payload.get("doi") or "")
        if line and not line.startswith("#") and normalize_doi(doi_value) == normalized:
            continue
        kept_lines.append(raw_line)

    content = "\n".join(kept_lines)
    if kept_lines:
        content += "\n"
    doi_file.write_text(content, encoding="utf-8")


def sync_seed_doi_queue(
    *,
    source_doi_file: Path = seed_doi_file,
    completed_doi_file: Path = completed_seed_doi_file,
) -> None:
    completed_dois = load_completed_seed_dois(completed_doi_file)
    if not completed_dois or not source_doi_file.exists():
        return

    for doi in completed_dois:
        _remove_seed_doi_from_queue(doi, source_doi_file)


def append_completed_seed_doi(
    doi: str,
    doi_file: Path = completed_seed_doi_file,
    *,
    source_doi_file: Path | None = seed_doi_file,
) -> None:
    normalized = normalize_doi(doi)
    existing = load_completed_seed_dois(doi_file)
    if normalized in existing:
        if source_doi_file is not None:
            _remove_seed_doi_from_queue(normalized, source_doi_file)
        return
    doi_file.parent.mkdir(parents=True, exist_ok=True)
    with doi_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"doi": normalized}, ensure_ascii=False, sort_keys=True) + "\n")
    if source_doi_file is not None:
        _remove_seed_doi_from_queue(normalized, source_doi_file)


def truncate_abstract(text: str | None) -> str | None:
    if not text:
        return None
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "..."


def build_selection_preview(text: str | None, max_words: int = selection_preview_words) -> str:
    if not text:
        return ""
    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "..."


def paper_to_metadata_record(
    paper: dict[str, Any],
    *,
    parent: str | None,
    seed_doi: str | None = None,
    is_seed_paper: bool = False,
    abstract_word_limit: int = max_words,
) -> dict[str, Any]:
    abstract_text = str(paper.get("abstract") or "").strip()
    if abstract_text:
        words = abstract_text.split()
        if len(words) > abstract_word_limit:
            abstract_text = " ".join(words[:abstract_word_limit]) + "..."
    else:
        abstract_text = None

    external_ids = paper.get("externalIds") or {}
    open_access_pdf = paper.get("openAccessPdf") or {}
    normalized_seed_doi = normalize_doi(seed_doi) if seed_doi else None

    return {
        "paperId": paper["paperId"],
        "created_at": utc_now_iso(),
        "title": paper.get("title"),
        "year": paper.get("year"),
        "citationCount": paper.get("citationCount"),
        "doi": external_ids.get("DOI"),
        "arxiv": external_ids.get("ArXiv"),
        "pdf_url": open_access_pdf.get("url"),
        "abstract": abstract_text,
        "parent_papers": [parent] if parent else [],
        "seed_papers": [normalized_seed_doi] if normalized_seed_doi else [],
        "is_seed_paper": is_seed_paper,
        "authors": [a["name"] for a in paper.get("authors", []) if isinstance(a, dict) and a.get("name")],
    }


def _paper_file_stem(paper: dict[str, Any]) -> str:
    doi = str((paper.get("externalIds") or {}).get("DOI") or "").strip()
    paper_id = str(paper.get("paperId") or "").strip()
    if doi:
        return build_base_name(doi)
    if paper_id:
        return paper_id
    raise ValueError("Paper sin DOI ni paperId.")


def _record_identifiers(record: dict[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    paper_id = str(record.get("paperId") or "").strip()
    doi = str(record.get("doi") or "").strip()
    if paper_id:
        identifiers.add(paper_id)
    if doi:
        identifiers.add(build_base_name(doi))
    return identifiers


def _ensure_parent_saved(
    parent: str | None,
    *,
    parent_paper: dict[str, Any] | None = None,
    seed_doi: str | None = None,
    selection_mode: str = "broad-nutrition",
    processed_papers: set[str] | None = None,
) -> None:
    if not parent or parent_paper is None:
        return
    if processed_papers is not None and parent in processed_papers:
        return
    save_paper(
        parent_paper,
        parent=None,
        seed_doi=seed_doi,
        is_seed_paper=False,
        selection_mode=selection_mode,
        processed_papers=processed_papers,
    )


def save_paper(
    paper: dict[str, Any],
    *,
    parent: str | None,
    parent_paper: dict[str, Any] | None = None,
    seed_doi: str | None = None,
    is_seed_paper: bool = False,
    selection_mode: str = "broad-nutrition",
    processed_papers: set[str] | None = None,
) -> None:
    _ensure_parent_saved(
        parent,
        parent_paper=parent_paper,
        seed_doi=seed_doi,
        selection_mode=selection_mode,
        processed_papers=processed_papers,
    )
    incoming = paper_to_metadata_record(
        paper,
        parent=parent,
        seed_doi=seed_doi,
        is_seed_paper=is_seed_paper,
    )
    _path, _status, metadata = _upsert_lake_metadata_record(incoming, decision="keep")

    if processed_papers is not None:
        processed_papers.update(_record_identifiers(incoming))
        processed_papers.add(str(metadata["metadata_id"]))


def save_discarded(
    paper: dict[str, Any],
    *,
    parent: str | None = None,
    parent_paper: dict[str, Any] | None = None,
    seed_doi: str | None = None,
    selection: dict[str, str] | None = None,
    processed_papers: set[str] | None = None,
) -> None:
    _ensure_parent_saved(
        parent,
        parent_paper=parent_paper,
        seed_doi=seed_doi,
        selection_mode=str((selection or {}).get("mode") or "broad-nutrition"),
        processed_papers=processed_papers,
    )
    candidate = paper_to_metadata_record(paper, parent=parent, seed_doi=seed_doi)
    decision = str((selection or {}).get("decision") or "drop")
    if decision not in {"keep", "drop", "uncertain"}:
        decision = "drop"
    _path, _status, metadata = _upsert_lake_metadata_record(candidate, decision=decision)

    if processed_papers is not None:
        processed_papers.update(_record_identifiers(candidate))
        processed_papers.add(str(metadata["metadata_id"]))


def _paper_storage_state(paper: dict[str, Any]) -> str | None:
    file_stem = _paper_file_stem(paper)
    if file_stem in _collect_lake_paper_metadata_ids():
        return "kept"
    return None


def iter_seed_citations(seed_paper: dict[str, Any]) -> Iterator[dict[str, Any]]:
    offset = 0
    url = f"{SEMANTIC_URL}/paper/{seed_paper['paperId']}/citations"

    while True:
        params = {
            "fields": CITATION_FIELDS,
            "limit": 100,
            "offset": offset,
        }
        response = request_with_backoff(url, params=params)
        data = response.json().get("data", [])
        if not data:
            break

        for entry in data:
            paper = entry.get("citingPaper", {})
            paper_id = paper.get("paperId")
            if not paper_id:
                continue
            citation_count = paper.get("citationCount") or 0
            year = paper.get("year") or 0
            if citation_count < min_citations:
                continue
            if year < min_year:
                continue
            yield paper
        offset += 100


def _build_paper_candidate(index: int, paper: dict[str, Any]) -> PaperCandidate:
    return PaperCandidate(
        id=f"cand_{index:03d}",
        title=str(paper.get("title") or "").strip() or "Untitled paper",
        abstract_preview=build_selection_preview(paper.get("abstract"), max_words=selection_preview_words),
    )


def _process_selection_batch(
    batch: list[dict[str, Any]],
    accepted: int,
    *,
    processed_papers: set[str],
    llm_client: LLMClient,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
    selection_mode: str = "broad-nutrition",
) -> tuple[int, int, int, int]:
    if not batch:
        return accepted, 0, 0, 0

    normalized_mode = normalize_selection_mode(selection_mode)
    candidates = [_build_paper_candidate(index + 1, item["paper"]) for index, item in enumerate(batch)]
    decisions, _raw_response = classify_papers_with_llm(
        candidates=candidates,
        model=selection_model,
        selection_profile=normalized_mode,
        client=llm_client,
        prompt_registry=prompt_registry,
        prompt_label=prompt_label,
    )
    decisions_by_id = {item["id"]: item for item in decisions}
    processed_count = 0
    kept_count = 0
    dropped_count = 0

    for candidate, item in zip(candidates, batch):
        paper = item["paper"]
        seed_doi = item["seed_doi"]
        parent = item["parent"]
        parent_paper = item.get("parent_paper")
        decision = decisions_by_id.get(
            candidate.id,
            {"decision": "uncertain", "reason": "missing_decision"},
        )
        processed_count += 1
        preview = candidate.abstract_preview or "No abstract preview available."
        title = candidate.title
        reason = decision["reason"]

        if decision["decision"] == "drop":
            print(f"[DROP] {title}")
            print(f"  preview: {preview}")
            print(f"  reason: {reason}")
            save_discarded(
                paper,
                parent=parent,
                parent_paper=parent_paper,
                seed_doi=seed_doi,
                selection={
                    "mode": selection_mode,
                    "profile": normalized_mode,
                    "decision": decision["decision"],
                    "reason": reason,
                    "preview": preview,
                },
                processed_papers=processed_papers,
            )
            dropped_count += 1
            continue

        print(f"[KEEP] {title}")
        print(f"  preview: {preview}")
        print(f"  reason: {reason}")
        save_paper(
            paper,
            parent=parent,
            parent_paper=parent_paper,
            seed_doi=seed_doi,
            selection_mode=selection_mode,
            processed_papers=processed_papers,
        )
        accepted += 1
        kept_count += 1

    return accepted, processed_count, kept_count, dropped_count


def explore_with_llm_selection(
    *,
    seed_dois: list[str] | None = None,
    selection_mode: str,
    summary_label: str,
    llm_client: LLMClient,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
) -> None:
    normalized_mode = normalize_selection_mode(selection_mode)
    if seed_dois is None:
        sync_seed_doi_queue()
    resolved_seed_dois = seed_dois or load_seed_dois()
    completed_seed_dois = load_completed_seed_dois()
    pending_seed_dois = [seed_doi for seed_doi in resolved_seed_dois if seed_doi not in completed_seed_dois]
    processed_papers = collect_processed_papers()
    accepted = 0
    reviewed = 0
    dropped = 0
    existing = 0
    skipped_seed_errors = 0
    skipped_completed = len(resolved_seed_dois) - len(pending_seed_dois)
    batch: list[dict[str, Any]] = []
    exhausted = True

    for seed_doi in pending_seed_dois:
        try:
            seed_paper = fetch_paper_by_doi(seed_doi)
        except HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                print(f"[SEED SKIP] {seed_doi} -> not found in Semantic Scholar")
                append_completed_seed_doi(seed_doi)
                skipped_seed_errors += 1
                continue
            raise
        save_paper(
            seed_paper,
            parent=None,
            seed_doi=seed_doi,
            is_seed_paper=True,
            processed_papers=processed_papers,
        )
        print(f"[SEED] {seed_doi} -> {seed_paper.get('title') or 'Unknown title'}")

        for paper in iter_seed_citations(seed_paper):
            state = _paper_storage_state(paper)
            if state == "kept":
                save_paper(
                    paper,
                    parent=seed_paper["paperId"],
                    seed_doi=seed_doi,
                    processed_papers=processed_papers,
                )
                existing += 1
                continue
            if state == "discarded":
                existing += 1
                continue

            batch.append(
                {
                    "paper": paper,
                    "seed_doi": seed_doi,
                    "parent": seed_paper["paperId"],
                    "parent_paper": seed_paper,
                }
            )
            if len(batch) < selection_batch_size:
                continue

            accepted, processed_count, _kept_count, dropped_count = _process_selection_batch(
                batch,
                accepted,
                processed_papers=processed_papers,
                llm_client=llm_client,
                prompt_registry=prompt_registry,
                prompt_label=prompt_label,
                selection_mode=normalized_mode,
            )
            reviewed += processed_count
            dropped += dropped_count
            batch = []

        if batch:
            accepted, processed_count, _kept_count, dropped_count = _process_selection_batch(
                batch,
                accepted,
                processed_papers=processed_papers,
                llm_client=llm_client,
                prompt_registry=prompt_registry,
                prompt_label=prompt_label,
                selection_mode=normalized_mode,
            )
            reviewed += processed_count
            dropped += dropped_count
            batch = []

        append_completed_seed_doi(seed_doi)

    if batch:
        accepted, processed_count, _kept_count, dropped_count = _process_selection_batch(
            batch,
            accepted,
            processed_papers=processed_papers,
            llm_client=llm_client,
            prompt_registry=prompt_registry,
            prompt_label=prompt_label,
            selection_mode=normalized_mode,
        )
        reviewed += processed_count
        dropped += dropped_count

    print(f"\nResumen metadata {summary_label}")
    print(f"- Modelo LLM:             {selection_model}")
    print(f"- Seed DOI file:          {seed_doi_file}")
    print(f"- Seed DOIs loaded:       {len(resolved_seed_dois)}")
    print(f"- Seed DOI done file:     {completed_seed_doi_file}")
    print(f"- Seed DOIs pending:      {len(pending_seed_dois)}")
    print(f"- Seed DOIs completed:    {skipped_completed}")
    print(f"- Seed DOIs skipped:      {skipped_seed_errors}")
    print(f"- Preview abstract words: {selection_preview_words}")
    print(f"- Batch size:             {selection_batch_size}")
    print(f"- Reviewed:               {reviewed}")
    print(f"- Existing merged:        {existing}")
    print(f"- Kept:                   {accepted}")
    print(f"- Dropped:                {dropped}")
    print(f"- Source exhausted:       {'yes' if exhausted else 'no'}")


def explore_with_nutrition_rag(
    seed_dois: list[str] | None = None,
    *,
    llm_client: LLMClient,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
) -> None:
    explore_with_llm_selection(
        seed_dois=seed_dois,
        selection_mode="broad-nutrition",
        summary_label="broad-nutrition",
        llm_client=llm_client,
        prompt_registry=prompt_registry,
        prompt_label=prompt_label,
    )


def run_nutrition_rag_exploration(
    *,
    llm_client: LLMClient,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
) -> None:
    _run_llm_selection_exploration(
        "broad-nutrition",
        llm_client=llm_client,
        prompt_registry=prompt_registry,
        prompt_label=prompt_label,
    )


def _run_llm_selection_exploration(
    selection_mode: str,
    *,
    llm_client: LLMClient,
    prompt_registry: PromptRegistry | None = None,
    prompt_label: str = "production",
) -> None:
    normalized_mode = normalize_selection_mode(selection_mode)
    try:
        sync_seed_doi_queue()
        resolved_seed_dois = load_seed_dois()
        completed_seed_dois = load_completed_seed_dois()
        pending_seed_dois = [seed_doi for seed_doi in resolved_seed_dois if seed_doi not in completed_seed_dois]
        if not pending_seed_dois:
            print(f"\nSelection mode: {normalized_mode}")
            print("Seed DOI file:", seed_doi_file)
            print("Seed DOI done file:", completed_seed_doi_file)
            print("Seed DOIs loaded:", len(resolved_seed_dois))
            print("Seed DOIs pending:", 0)
            print("No pending seed DOIs to process.")
            return
    except Exception as exc:
        raise SystemExit(f"Seed DOI inválido o no encontrado. Error: {exc}")

    print("\nSelection mode:", normalized_mode)
    print("Seed DOI file:", seed_doi_file)
    print("Seed DOI done file:", completed_seed_doi_file)
    print("Seed DOIs loaded:", len(resolved_seed_dois))
    print("Seed DOIs pending:", len(pending_seed_dois))
    print("First pending seed:", pending_seed_dois[0])
    print("Minimum citations:", min_citations)
    print("Minimum year:", min_year)
    print("Preview abstract words:", selection_preview_words)
    print("Selection batch size:", selection_batch_size)
    print("Semantic Scholar rate limit:", "1 request/second")
    print()

    if normalized_mode == "broad-nutrition":
        explore_with_nutrition_rag(
            pending_seed_dois,
            llm_client=llm_client,
            prompt_registry=prompt_registry,
            prompt_label=prompt_label,
        )
        return
    raise ValueError(f"Selection mode no soportado: {selection_mode}")


if __name__ == "__main__":
    raise SystemExit("Use the victus-processing CLI so the LLM client can be injected.")
