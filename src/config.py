from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DATA_CANDIDATES_DIR = DATA_DIR / "candidates"
DATA_CANDIDATES_ACTIVE_DIR = DATA_CANDIDATES_DIR / "active"
DATA_CANDIDATES_DISCARDED_DIR = DATA_CANDIDATES_DIR / "discarded"
DATA_PAPERS_DIR = DATA_DIR / "papers"
DATA_INPUTS_DIR = DATA_DIR / "inputs"
DATA_INPUT_SEEDS_DIR = DATA_INPUTS_DIR / "seeds"
DATA_INPUT_RULES_DIR = DATA_INPUTS_DIR / "rules"
DATA_INPUT_IMPORTS_DIR = DATA_INPUTS_DIR / "imports"
DATA_REGISTRY_DIR = DATA_DIR / "registry"
DATA_RUNTIME_DIR = DATA_DIR / "runtime"
DATA_RUNTIME_PDF_RETRIEVAL_DIR = DATA_RUNTIME_DIR / "pdf_retrieval"
DATA_RUNTIME_PDFS_DIR = DATA_RUNTIME_DIR / "pdfs"
DATA_RUNTIME_DOCLING_DIR = DATA_RUNTIME_DIR / "docling"
DATA_RUNTIME_CLAIMS_DIR = DATA_RUNTIME_DIR / "claims"
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
PRE_INGESTION_PAPERS_CSV = DATA_INPUT_IMPORTS_DIR / "papers.csv"
PRE_INGESTION_CANDIDATE_TERMS_CSV = DATA_INPUT_IMPORTS_DIR / "candidate_terms_top500.csv"
PRE_INGESTION_GENERATED_DRAFT_TOPICS_YAML = PRE_INGESTION_EDITABLE_DIR / "draft_topics.generated.yaml"
PRE_INGESTION_TOPICS_YAML = PRE_INGESTION_EDITABLE_DIR / "topics.yaml"
PRE_INGESTION_DRAFT_TOPICS_YAML = PRE_INGESTION_TOPICS_YAML
PRE_INGESTION_BOOTSTRAP_RULES_YAML = PRE_INGESTION_EDITABLE_DIR / "bootstrap_rules.yaml"
PRE_INGESTION_AUDIT_DIR = DATA_REPORTS_AUDITS_DIR / "pre_ingestion"
CONFIG_FILE = ROOT_DIR / "config.yaml"
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
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_pipeline_paths(config: dict[str, Any] | None = None) -> dict[str, Path]:
    cfg = config if config is not None else get_config()

    storage_cfg = cfg.get("storage") or {}
    docling_cfg = cfg.get("docling_ingestion") or {}
    llm_claims_cfg = cfg.get("llm_to_claim") or {}

    metadata_dir = resolve_project_path(
        storage_cfg.get("papers_dir"),
        DATA_CANDIDATES_ACTIVE_DIR,
    )
    discarded_dir = resolve_project_path(
        storage_cfg.get("discarded_dir"),
        DATA_CANDIDATES_DISCARDED_DIR,
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
    claims_input_dir = resolve_project_path(
        llm_claims_cfg.get("input_dir"),
        docling_heuristics_dir,
    )
    claims_output_dir = resolve_project_path(
        llm_claims_cfg.get("output_dir"),
        DATA_RUNTIME_CLAIMS_DIR,
    )

    return {
        "metadata_dir": metadata_dir,
        "discarded_dir": discarded_dir,
        "registry_dir": registry_dir,
        "raw_pdf_dir": raw_pdf_dir,
        "unmatched_pdf_dir": unmatched_pdf_dir,
        "docling_input_dir": docling_input_dir,
        "docling_heuristics_dir": docling_heuristics_dir,
        "claims_input_dir": claims_input_dir,
        "claims_output_dir": claims_output_dir,
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
    testing_claims_dir = resolve_project_path(
        testing_cfg.get("claims_output_dir"),
        testing_root_dir / "claims",
    )

    return {
        "testing_root_dir": testing_root_dir,
        "testing_docling_dir": testing_docling_dir,
        "testing_claims_dir": testing_claims_dir,
    }


def get_exploration_seed_doi_file(config: dict[str, Any] | None = None) -> Path:
    cfg = config if config is not None else get_config()
    exploration_cfg = cfg.get("exploration") or {}
    return resolve_project_path(
        exploration_cfg.get("seed_doi_file"),
        DATA_INPUT_SEEDS_DIR / "seed_dois.txt",
    )


def get_exploration_completed_seed_doi_file(config: dict[str, Any] | None = None) -> Path:
    cfg = config if config is not None else get_config()
    exploration_cfg = cfg.get("exploration") or {}
    return resolve_project_path(
        exploration_cfg.get("completed_seed_doi_file"),
        DATA_INPUT_SEEDS_DIR / "explored_seed_dois.txt",
    )


def get_claims_auto_approve_max_tokens(config: dict[str, Any] | None = None) -> int:
    cfg = config if config is not None else get_config()
    claims_cfg = cfg.get("llm_to_claim") or {}
    return int(claims_cfg.get("auto_approve_max_tokens", 7000))


def get_data_layout_dirs() -> tuple[Path, ...]:
    return (
        DATA_DIR,
        DATA_SOURCES_DIR,
        DATA_STAGES_DIR,
        DATA_CANDIDATES_DIR,
        DATA_CANDIDATES_ACTIVE_DIR,
        DATA_CANDIDATES_DISCARDED_DIR,
        DATA_PAPERS_DIR,
        DATA_INPUTS_DIR,
        DATA_INPUT_SEEDS_DIR,
        DATA_INPUT_RULES_DIR,
        DATA_INPUT_IMPORTS_DIR,
        DATA_REGISTRY_DIR,
        DATA_RUNTIME_DIR,
        DATA_RUNTIME_PDF_RETRIEVAL_DIR,
        DATA_RUNTIME_PDFS_DIR,
        DATA_RUNTIME_DOCLING_DIR,
        DATA_RUNTIME_CLAIMS_DIR,
        DATA_RUNTIME_TMP_DIR,
        DATA_RUNTIME_LOGS_DIR,
        DATA_RUNTIME_QUEUES_DIR,
        DATA_REPORTS_DIR,
        DATA_REPORTS_AUDITS_DIR,
        DATA_REPORTS_EXPORTS_DIR,
        DATA_ARCHIVE_DIR,
        DATA_ARCHIVE_LEGACY_DIR,
        DATA_ARCHIVE_EXPERIMENTS_DIR,
        CSV_DIR,
        ANALYTICS_DIR,
        CORPUS_INFO_DIR,
        METADATA_RULES_DIR,
        PDF_RETRIEVAL_DIR,
        PRE_INGESTION_EDITABLE_DIR,
        PRE_INGESTION_DIR,
        PRE_INGESTION_AUDIT_DIR,
        METADATA_DIR,
        DOCLING_INPUT_DIR,
        UNMATCHED_PDF_DIR,
        DOCLING_HEURISTICS_DIR,
        CLAIMS_OUTPUT_DIR,
        REGISTRY_DIR,
        RAW_PDF_DIR,
        TESTING_ROOT_DIR,
        TESTING_DOCLING_DIR,
        TESTING_CLAIMS_DIR,
    )


def get_env_or_config(
    env_name: str,
    *config_path: str,
    default: str | None = None,
    config: dict[str, Any] | None = None,
) -> str | None:
    env_value = os.getenv(env_name)
    if env_value:
        return env_value

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
CLAIMS_INPUT_DIR = PATHS["claims_input_dir"]
CLAIMS_OUTPUT_DIR = PATHS["claims_output_dir"]
REGISTRY_DIR = PATHS["registry_dir"]
RAW_PDF_DIR = PATHS["raw_pdf_dir"]
UNMATCHED_PDF_DIR = PATHS["unmatched_pdf_dir"]
EXPLORATION_SEED_DOI_FILE = get_exploration_seed_doi_file(CONFIG)
EXPLORATION_COMPLETED_SEED_DOI_FILE = get_exploration_completed_seed_doi_file(CONFIG)
TESTING_PATHS = get_testing_paths(CONFIG)
TESTING_ROOT_DIR = TESTING_PATHS["testing_root_dir"]
TESTING_DOCLING_DIR = TESTING_PATHS["testing_docling_dir"]
TESTING_CLAIMS_DIR = TESTING_PATHS["testing_claims_dir"]

LLM_CLAIMS_CFG = CONFIG.get("llm_to_claim") or {}
LLM_CLAIMS_MODEL = str(LLM_CLAIMS_CFG.get("model", "gpt-5-mini"))
LLM_CLAIMS_MAX = int(LLM_CLAIMS_CFG.get("max_claims", 10))
LLM_CLAIMS_TEMPERATURE = float(LLM_CLAIMS_CFG.get("temperature", 0.0))
LLM_CLAIMS_AUTO_APPROVE_MAX_TOKENS = get_claims_auto_approve_max_tokens(CONFIG)

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
def resolve_docling_v2_pipeline_runner() -> Callable[..., dict[str, Any]]:
    from src.docling.converter import convert_pdf_for_pipeline

    return convert_pdf_for_pipeline


@lru_cache(maxsize=1)
def resolve_raw_pdf_sync() -> Callable[[Path, Path, Path, Path | None], tuple[int, int]]:
    from src.pdf.normalization import sync_raw_pdfs_into_input

    return sync_raw_pdfs_into_input


@lru_cache(maxsize=1)
def resolve_claims_flow() -> Callable[..., tuple[int, int, int]]:
    from src.claims.extraction import run_claim_extraction_flow

    return run_claim_extraction_flow
