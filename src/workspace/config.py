from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
DATA_CANDIDATES_DIR = DATA_DIR / "candidates"
DATA_CANDIDATES_ACTIVE_DIR = DATA_CANDIDATES_DIR / "active"
DATA_CANDIDATES_DISCARDED_DIR = DATA_CANDIDATES_DIR / "discarded"
DATA_PAPERS_DIR = DATA_DIR / "papers"
DATA_INPUTS_DIR = DATA_DIR / "inputs"
DATA_INPUT_GENERATED_SEED_DOIS_DIR = DATA_INPUTS_DIR / "generated_seed_dois"
DATA_INPUT_SEEDS_DIR = DATA_INPUTS_DIR / "seeds"
DATA_INPUT_RULES_DIR = DATA_INPUTS_DIR / "rules"
DATA_INPUT_IMPORTS_DIR = DATA_INPUTS_DIR / "imports"
DATA_REGISTRY_DIR = DATA_DIR / "registry"
DATA_RUNTIME_DIR = DATA_DIR / "runtime"
DATA_RUNTIME_CANDIDATES_DIR = DATA_RUNTIME_DIR / "01-candidates"
DATA_RUNTIME_CANDIDATES_ACTIVE_DIR = DATA_RUNTIME_CANDIDATES_DIR / "active"
DATA_RUNTIME_CANDIDATES_DISCARDED_DIR = DATA_RUNTIME_CANDIDATES_DIR / "discarded"
DATA_RUNTIME_PDF_RETRIEVAL_DIR = DATA_RUNTIME_DIR / "pdf_retrieval"
DATA_RUNTIME_PDFS_DIR = DATA_RUNTIME_DIR / "02-pdfs"
DATA_RUNTIME_PDFS_ACTIVE_DIR = DATA_RUNTIME_PDFS_DIR / "active"
DATA_RUNTIME_DOCLING_DIR = DATA_RUNTIME_DIR / "docling"
DATA_RUNTIME_PDF_PROCESSING_DIR = DATA_RUNTIME_DIR / "03-pdf_processing"
DATA_RUNTIME_EVIDENCE_DIR = DATA_RUNTIME_DIR / "04-evidence"
DATA_RUNTIME_TMP_DIR = DATA_RUNTIME_DIR / "tmp"
DATA_RUNTIME_LOGS_DIR = DATA_RUNTIME_DIR / "logs"
DATA_RUNTIME_QUEUES_DIR = DATA_RUNTIME_DIR / "queues"
DATA_REPORTS_DIR = DATA_DIR / "reports"
DATA_REPORTS_AUDITS_DIR = DATA_REPORTS_DIR / "audits"
DATA_REPORTS_EXPORTS_DIR = DATA_REPORTS_DIR / "exports"
DATA_ARCHIVE_DIR = DATA_DIR / "archive"
DATA_ARCHIVE_LEGACY_DIR = DATA_ARCHIVE_DIR / "legacy"
DATA_ARCHIVE_EXPERIMENTS_DIR = DATA_ARCHIVE_DIR / "experiments"
DATA_SOURCES_DIR = DATA_INPUTS_DIR
DATA_STAGES_DIR = DATA_RUNTIME_DIR
CSV_DIR = DATA_INPUT_IMPORTS_DIR
ANALYTICS_DIR = DATA_REPORTS_DIR
CORPUS_INFO_DIR = DATA_DIR / "corpus_info"
METADATA_RULES_DIR = CORPUS_INFO_DIR / "metadata_rules"
PDF_RETRIEVAL_DIR = CORPUS_INFO_DIR / "pdf_retrieval"
LEGACY_PDF_RETIREVAL_DIR = CORPUS_INFO_DIR / "pdf_retireval"
PRE_INGESTION_DIR = DATA_INPUTS_DIR
PRE_INGESTION_EDITABLE_DIR = DATA_INPUT_RULES_DIR
PRE_INGESTION_PAPERS_CSV = DATA_INPUT_RULES_DIR / "papers.csv"
PRE_INGESTION_CANDIDATE_TERMS_CSV = DATA_INPUT_RULES_DIR / "candidate_terms_top500.csv"
PRE_INGESTION_GENERATED_DRAFT_TOPICS_YAML = PRE_INGESTION_EDITABLE_DIR / "draft_topics.generated.yaml"
PRE_INGESTION_TOPICS_YAML = PRE_INGESTION_EDITABLE_DIR / "topics.yaml"
PRE_INGESTION_DRAFT_TOPICS_YAML = PRE_INGESTION_TOPICS_YAML
PRE_INGESTION_BOOTSTRAP_RULES_YAML = PRE_INGESTION_EDITABLE_DIR / "bootstrap_rules.yaml"
PRE_INGESTION_AUDIT_DIR = DATA_REPORTS_AUDITS_DIR / "pre_ingestion"
CONFIG_FILE = ROOT_DIR / "config.yaml"
CONFIG_DIR = ROOT_DIR / "config"
ENV_FILE = ROOT_DIR / ".env"


def resolve_project_path(path_value: str | None, fallback: Path) -> Path:
    if not path_value:
        return fallback
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def load_env_file(env_file: Path = ENV_FILE) -> None:
    if not env_file.exists() or not env_file.is_file():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


load_env_file()


@lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    config: dict[str, Any] = {}

    for config_file in iter_config_files():
        config = merge_config(config, load_yaml_mapping(config_file))

    if CONFIG_FILE.exists():
        config = merge_config(config, load_yaml_mapping(CONFIG_FILE))

    return config


def iter_config_files(config_dir: Path | None = None) -> tuple[Path, ...]:
    resolved_config_dir = config_dir or CONFIG_DIR
    if not resolved_config_dir.exists() or not resolved_config_dir.is_dir():
        return ()
    return tuple(sorted(resolved_config_dir.glob("*.yaml")))


def load_yaml_mapping(config_file: Path) -> dict[str, Any]:
    with config_file.open(encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {config_file}")
    return payload


def merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = merge_config(existing, value)
            continue
        merged[key] = value
    return merged


def get_pipeline_paths(config: dict[str, Any] | None = None) -> dict[str, Path]:
    cfg = config if config is not None else get_config()

    storage_cfg = cfg.get("storage") or {}
    docling_cfg = cfg.get("docling_ingestion") or {}

    metadata_dir = resolve_project_path(
        storage_cfg.get("papers_dir"),
        DATA_RUNTIME_CANDIDATES_ACTIVE_DIR,
    )
    discarded_dir = resolve_project_path(
        storage_cfg.get("discarded_dir"),
        DATA_RUNTIME_CANDIDATES_DISCARDED_DIR,
    )
    registry_dir = resolve_project_path(
        storage_cfg.get("registry_dir"),
        DATA_REGISTRY_DIR,
    )
    raw_pdf_dir = resolve_project_path(
        storage_cfg.get("raw_pdf_dir"),
        DATA_RUNTIME_PDF_RETRIEVAL_DIR / "raw",
    )
    unmatched_pdf_dir = resolve_project_path(
        storage_cfg.get("unmatched_pdf_dir"),
        DATA_RUNTIME_PDF_RETRIEVAL_DIR / "unmatched",
    )

    docling_input_dir = resolve_project_path(
        docling_cfg.get("input_dir"),
        DATA_RUNTIME_PDFS_DIR / "normalized",
    )
    docling_heuristics_dir = resolve_project_path(
        docling_cfg.get("output_dir"),
        DATA_RUNTIME_DOCLING_DIR,
    )
    evidence_output_dir = resolve_project_path(
        (cfg.get("evidence") or {}).get("output_dir"),
        DATA_RUNTIME_EVIDENCE_DIR,
    )

    return {
        "metadata_dir": metadata_dir,
        "discarded_dir": discarded_dir,
        "registry_dir": registry_dir,
        "raw_pdf_dir": raw_pdf_dir,
        "unmatched_pdf_dir": unmatched_pdf_dir,
        "docling_input_dir": docling_input_dir,
        "docling_heuristics_dir": docling_heuristics_dir,
        "evidence_output_dir": evidence_output_dir,
    }


def get_testing_paths(config: dict[str, Any] | None = None) -> dict[str, Path]:
    cfg = config if config is not None else get_config()
    testing_cfg = cfg.get("testing") or {}

    testing_root_dir = resolve_project_path(
        testing_cfg.get("root_dir"),
        DATA_ARCHIVE_EXPERIMENTS_DIR / "testing_1",
    )
    testing_docling_dir = resolve_project_path(
        testing_cfg.get("docling_output_dir"),
        testing_root_dir / "docling",
    )
    return {
        "testing_root_dir": testing_root_dir,
        "testing_docling_dir": testing_docling_dir,
    }


def get_exploration_seed_doi_file(config: dict[str, Any] | None = None) -> Path:
    cfg = config if config is not None else get_config()
    exploration_cfg = cfg.get("exploration") or {}
    return resolve_project_path(
        exploration_cfg.get("seed_doi_file"),
        DATA_INPUT_SEEDS_DIR / "seed_dois.jsonl",
    )


def get_exploration_completed_seed_doi_file(config: dict[str, Any] | None = None) -> Path:
    cfg = config if config is not None else get_config()
    exploration_cfg = cfg.get("exploration") or {}
    return resolve_project_path(
        exploration_cfg.get("completed_seed_doi_file"),
        DATA_INPUT_SEEDS_DIR / "explored_seed_dois.jsonl",
    )


def get_data_layout_dirs() -> tuple[Path, ...]:
    dirs = (
        DATA_DIR,
        DATA_SOURCES_DIR,
        DATA_STAGES_DIR,
        DATA_PAPERS_DIR,
        DATA_INPUTS_DIR,
        DATA_INPUT_GENERATED_SEED_DOIS_DIR,
        DATA_INPUT_SEEDS_DIR,
        DATA_INPUT_RULES_DIR,
        DATA_REGISTRY_DIR,
        DATA_RUNTIME_DIR,
        DATA_RUNTIME_CANDIDATES_DIR,
        DATA_RUNTIME_CANDIDATES_ACTIVE_DIR,
        DATA_RUNTIME_CANDIDATES_DISCARDED_DIR,
        DATA_RUNTIME_PDFS_DIR,
        DATA_RUNTIME_PDFS_ACTIVE_DIR,
        DATA_RUNTIME_PDF_PROCESSING_DIR,
        DATA_RUNTIME_EVIDENCE_DIR,
        TESTING_ROOT_DIR,
        DATA_REPORTS_DIR,
        DATA_REPORTS_AUDITS_DIR,
        PRE_INGESTION_EDITABLE_DIR,
        PRE_INGESTION_DIR,
        METADATA_DIR,
        DOCLING_INPUT_DIR,
        UNMATCHED_PDF_DIR,
        DOCLING_HEURISTICS_DIR,
        EVIDENCE_OUTPUT_DIR,
        REGISTRY_DIR,
        RAW_PDF_DIR,
    )
    return tuple(dict.fromkeys(dirs))


def get_env_or_config(
    env_name: str,
    *config_path: str,
    default: str | None = None,
    config: dict[str, Any] | None = None,
) -> str | None:
    env_value = os.getenv(env_name)
    if env_value:
        return env_value
    if not config_path:
        return default

    cfg = config if config is not None else get_config()
    current: Any = cfg
    for key in config_path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)

    if current in (None, ""):
        return default
    return str(current)


CONFIG = get_config()
PATHS = get_pipeline_paths(CONFIG)

METADATA_DIR = PATHS["metadata_dir"]
DOCLING_INPUT_DIR = PATHS["docling_input_dir"]
DOCLING_HEURISTICS_DIR = PATHS["docling_heuristics_dir"]
EVIDENCE_OUTPUT_DIR = PATHS["evidence_output_dir"]
REGISTRY_DIR = PATHS["registry_dir"]
RAW_PDF_DIR = PATHS["raw_pdf_dir"]
UNMATCHED_PDF_DIR = PATHS["unmatched_pdf_dir"]
EXPLORATION_SEED_DOI_FILE = get_exploration_seed_doi_file(CONFIG)
EXPLORATION_COMPLETED_SEED_DOI_FILE = get_exploration_completed_seed_doi_file(CONFIG)
TESTING_PATHS = get_testing_paths(CONFIG)
TESTING_ROOT_DIR = TESTING_PATHS["testing_root_dir"]
TESTING_DOCLING_DIR = TESTING_PATHS["testing_docling_dir"]
LANGFUSE_PUBLIC_KEY = get_env_or_config("LANGFUSE_PUBLIC_KEY", default="")
LANGFUSE_SECRET_KEY = get_env_or_config("LANGFUSE_SECRET_KEY", default="")
LANGFUSE_HOST = get_env_or_config("LANGFUSE_HOST", default="")
PROMPT_LABEL = get_env_or_config("PROMPT_LABEL", default="production") or "production"
PROMPTS_LOCAL_DIR = resolve_project_path(
    get_env_or_config("PROMPTS_LOCAL_DIR", default="src/prompts/local"),
    ROOT_DIR / "src/prompts/local",
)
DEFAULT_LLM_MODEL = (
    get_env_or_config("DEFAULT_LLM_MODEL", default="litellm_proxy/gemini-flash-lite")
    or "litellm_proxy/gemini-flash-lite"
)

REGISTRY_FILE = REGISTRY_DIR / "documents.jsonl"
BIB_OUTPUT_FILE = METADATA_DIR / "papers.bib"


def display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        return resolved.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return str(resolved)


def resolve_available_raw_pdf_dir(raw_pdf_dir: Path | None = None) -> Path:
    candidate = raw_pdf_dir or RAW_PDF_DIR
    legacy_candidate = LEGACY_PDF_RETIREVAL_DIR / "downloaded_pdfs"

    if candidate.exists() and any(candidate.glob("*.pdf")):
        return candidate
    if legacy_candidate.exists() and any(legacy_candidate.glob("*.pdf")):
        return legacy_candidate
    return candidate


@lru_cache(maxsize=1)
def resolve_raw_pdf_sync() -> Callable[[Path, Path, Path, Path | None], tuple[int, int]]:
    from src.application.metadata_to_pdf.normalization import sync_raw_pdfs_into_input

    return sync_raw_pdfs_into_input
