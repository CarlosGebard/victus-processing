from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONTRACTS_DIR = Path("docs/contracts/fundamental")
DEFAULT_CACHE_DIR = Path(".cache/victus-contracts")
LOCK_FILENAME = "contracts.lock.json"
SOURCE_REPO = "/home/carlos/victus/victus-docs"
SOURCE_REGISTRY = Path("docs/contracts/_registry/contracts.registry.yml")
SOURCE_CONTRACTS_ROOT = Path("docs/contracts")
SUBSCRIPTIONS = (
    ("victus.scientific.paper", "v1"),
    ("victus.scientific.structured_block", "v1"),
    ("victus.scientific.paper_classification", "v1"),
    ("victus.scientific.experiment_map", "v1"),
    ("victus.scientific.canonical_evidence", "v1"),
    ("victus.orchestration.pipeline_run", "v1"),
    ("victus.orchestration.pipeline_event", "v1"),
    ("victus.storage.layout", "v1"),
    ("victus.storage.artifact_manifest", "v1"),
    ("victus.process.paper_classification", "v1"),
)


class ContractSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class Subscription:
    contract_id: str
    required_version: str


@dataclass(frozen=True)
class RegistryEntry:
    contract_id: str
    version: str
    path: Path


@dataclass(frozen=True)
class SyncConfig:
    repo_root: Path
    contracts_dir: Path
    cache_dir: Path
    source_repo: str = SOURCE_REPO
    source_registry: Path = SOURCE_REGISTRY
    source_contracts_root: Path = SOURCE_CONTRACTS_ROOT
    subscriptions: tuple[tuple[str, str], ...] = SUBSCRIPTIONS


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = SyncConfig(
        repo_root=args.repo_root.expanduser().resolve(),
        contracts_dir=args.contracts_dir.expanduser(),
        cache_dir=args.cache_dir.expanduser(),
    )
    try:
        if args.command == "sync":
            result = sync_contracts(config)
            print(f"Synced {len(result)} contract(s) into {display_path(config.repo_root, config.contracts_dir)}")
            for item in result:
                print(f"- {item['contract_id']} {item['version']} -> {item['destination_path']}")
            return 0
        if args.command == "validate":
            result = validate_contracts(config)
            print(f"Validated {len(result)} contract(s)")
            for item in result:
                print(f"- {item['contract_id']} {item['version']} {item['checksum']}")
            return 0
        if args.command == "list":
            result = list_contracts(config)
            for item in result:
                print(f"{item.contract_id} {item.required_version}")
            return 0
    except ContractSyncError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contracts",
        description="Synchronize subscribed Victus contract markdown files.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Subscriber repository root.")
    parser.add_argument(
        "--contracts-dir",
        type=Path,
        default=DEFAULT_CONTRACTS_DIR,
        help="Contract destination, relative to --repo-root unless absolute.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help="Source repository cache directory, relative to --repo-root unless absolute.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync", help="Synchronize subscribed contracts.")
    subparsers.add_parser("validate", help="Validate subscriptions, registry, lock file, and checksums.")
    subparsers.add_parser("list", help="List subscribed contract ids and versions.")
    return parser


def sync_contracts(config: SyncConfig) -> list[dict[str, Any]]:
    subscriptions = parse_subscriptions(config.subscriptions)
    checkout = ensure_source_checkout(config, config.source_repo)
    registry_path = resolve_source_path(checkout, config.source_registry)
    registry = load_registry(registry_path)
    source_commit = git_output(["git", "rev-parse", "HEAD"], cwd=checkout)
    contracts_dir = resolve_under_repo(config.repo_root, config.contracts_dir)
    contracts_dir.mkdir(parents=True, exist_ok=True)

    lock_contracts: list[dict[str, Any]] = []
    used_destinations: dict[Path, Path] = {}
    for subscription in subscriptions:
        entry = resolve_registry_entry(registry, subscription)
        source_path = resolve_source_path(checkout, entry.path)
        if not source_path.is_file():
            raise ContractSyncError(f"Contract source file not found: {source_path}")
        destination = safe_contract_destination(contracts_dir, entry.path, config.source_contracts_root)
        existing_source = used_destinations.get(destination)
        if existing_source is not None and existing_source != source_path:
            raise ContractSyncError(f"Duplicate destination path: {destination.relative_to(contracts_dir)}")
        used_destinations[destination] = source_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
        checksum = sha256_file(destination)
        lock_contracts.append(
            {
                "contract_id": entry.contract_id,
                "version": entry.version,
                "source_path": normalize_posix(entry.path),
                "destination_path": normalize_posix(destination.relative_to(config.repo_root)),
                "checksum": checksum,
            }
        )

    lock = {
        "synced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_commit": source_commit,
        "contracts": lock_contracts,
    }
    write_json(contracts_dir / LOCK_FILENAME, lock)
    return lock_contracts


def validate_contracts(config: SyncConfig) -> list[dict[str, Any]]:
    subscriptions = parse_subscriptions(config.subscriptions)
    checkout = ensure_source_checkout(config, config.source_repo)
    registry = load_registry(resolve_source_path(checkout, config.source_registry))
    for subscription in subscriptions:
        resolve_registry_entry(registry, subscription)

    contracts_dir = resolve_under_repo(config.repo_root, config.contracts_dir)
    lock_path = contracts_dir / LOCK_FILENAME
    if not lock_path.exists():
        raise ContractSyncError(f"Lock file not found: {lock_path}")
    lock = load_json_file(lock_path)
    contracts = lock.get("contracts")
    if not isinstance(contracts, list):
        raise ContractSyncError("contracts.lock.json must contain contracts list")

    expected = {(item.contract_id, item.required_version) for item in subscriptions}
    locked = set()
    for item in contracts:
        if not isinstance(item, dict):
            raise ContractSyncError("Lock contracts must be objects")
        contract_id = str_required(item, "contract_id")
        version = str_required(item, "version")
        source_path = Path(str_required(item, "source_path"))
        destination_path = Path(str_required(item, "destination_path"))
        checksum = str_required(item, "checksum")
        locked.add((contract_id, version))
        resolve_registry_entry(registry, Subscription(contract_id, version), expected_path=source_path)
        destination = resolve_under_repo(config.repo_root, destination_path)
        ensure_inside_directory(destination, contracts_dir)
        if not destination.is_file():
            raise ContractSyncError(f"Contract missing: {destination}")
        actual_checksum = sha256_file(destination)
        if actual_checksum != checksum:
            raise ContractSyncError(f"Checksum mismatch for {destination}: {actual_checksum} != {checksum}")
    if locked != expected:
        raise ContractSyncError(f"Lock contracts do not match subscriptions: expected={sorted(expected)} locked={sorted(locked)}")
    return contracts


def list_contracts(config: SyncConfig) -> list[Subscription]:
    return parse_subscriptions(config.subscriptions)


def parse_subscriptions(raw_items: tuple[tuple[str, str], ...]) -> list[Subscription]:
    subscriptions: list[Subscription] = []
    seen: set[str] = set()
    for contract_id, required_version in raw_items:
        if not contract_id.strip() or not required_version.strip():
            raise ContractSyncError("Each subscription must define contract_id and required_version")
        if contract_id in seen:
            raise ContractSyncError(f"Duplicate subscribed contract_id: {contract_id}")
        seen.add(contract_id)
        subscriptions.append(Subscription(contract_id=contract_id.strip(), required_version=required_version.strip()))
    return subscriptions


def load_registry(path: Path) -> dict[tuple[str, str], RegistryEntry]:
    if not path.exists():
        raise ContractSyncError(f"Source registry not found: {path}")
    payload = load_yaml_file(path)
    if isinstance(payload, dict) and isinstance(payload.get("contracts"), list):
        raw_items = payload["contracts"]
    elif isinstance(payload, list):
        raw_items = payload
    else:
        raise ContractSyncError("Source registry must be a list or contain contracts list")

    registry: dict[tuple[str, str], RegistryEntry] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ContractSyncError("Registry entries must be objects")
        entry = RegistryEntry(
            contract_id=str_required(item, "contract_id"),
            version=str_required(item, "version"),
            path=Path(str_required(item, "path")),
        )
        key = (entry.contract_id, entry.version)
        if key in registry:
            raise ContractSyncError(f"Duplicate registry entry: {entry.contract_id} {entry.version}")
        registry[key] = entry
    return registry


def resolve_registry_entry(
    registry: dict[tuple[str, str], RegistryEntry],
    subscription: Subscription,
    *,
    expected_path: Path | None = None,
) -> RegistryEntry:
    key = (subscription.contract_id, subscription.required_version)
    entry = registry.get(key)
    if entry is None:
        raise ContractSyncError(
            f"Required contract version not found: {subscription.contract_id} {subscription.required_version}"
        )
    if expected_path is not None and normalize_posix(entry.path) != normalize_posix(expected_path):
        raise ContractSyncError(
            f"Registry path mismatch for {entry.contract_id} {entry.version}: "
            f"{normalize_posix(entry.path)} != {normalize_posix(expected_path)}"
        )
    return entry


def ensure_source_checkout(config: SyncConfig, source_repo: str) -> Path:
    cache_root = resolve_under_repo(config.repo_root, config.cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    checkout = cache_root / source_cache_name(source_repo)
    if (checkout / ".git").exists():
        git_output(["git", "fetch", "--depth", "1", "origin"], cwd=checkout)
        git_output(["git", "pull", "--ff-only"], cwd=checkout)
        return checkout
    if checkout.exists():
        raise ContractSyncError(f"Cache path exists but is not a git checkout: {checkout}")
    git_output(["git", "clone", "--depth", "1", source_repo, str(checkout)], cwd=config.repo_root)
    return checkout


def source_cache_name(source_repo: str) -> str:
    digest = hashlib.sha256(source_repo.encode("utf-8")).hexdigest()[:12]
    name = source_repo.rstrip("/").split("/")[-1].removesuffix(".git") or "source"
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in name)
    return f"{safe}-{digest}"


def safe_contract_destination(contracts_dir: Path, source_path: Path, source_contracts_root: Path) -> Path:
    try:
        relative_path = source_path.relative_to(source_contracts_root)
    except ValueError as exc:
        raise ContractSyncError(f"Contract path is outside source contracts root: {source_path}") from exc
    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        raise ContractSyncError(f"Invalid contract path: {source_path}")
    destination = (contracts_dir / relative_path).resolve()
    ensure_inside_directory(destination, contracts_dir)
    return destination


def resolve_source_path(checkout: Path, registry_path: Path) -> Path:
    if registry_path.is_absolute():
        raise ContractSyncError(f"Source path must be relative: {registry_path}")
    source_path = (checkout / registry_path).resolve()
    ensure_inside_directory(source_path, checkout)
    return source_path


def resolve_under_repo(repo_root: Path, path: Path) -> Path:
    resolved = path if path.is_absolute() else repo_root / path
    return resolved.resolve()


def ensure_inside_directory(path: Path, directory: Path) -> None:
    resolved_directory = directory.resolve()
    try:
        path.resolve().relative_to(resolved_directory)
    except ValueError as exc:
        raise ContractSyncError(f"Path escapes allowed directory: {path}") from exc


def load_yaml_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def str_required(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractSyncError(f"Missing required string field: {key}")
    return value.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def normalize_posix(path: Path) -> str:
    return path.as_posix()


def display_path(repo_root: Path, path: Path) -> str:
    resolved = resolve_under_repo(repo_root, path)
    try:
        return normalize_posix(resolved.relative_to(repo_root))
    except ValueError:
        return normalize_posix(resolved)


def git_output(args: list[str], *, cwd: Path) -> str:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ContractSyncError(f"Git command failed: {' '.join(args)}\n{exc.stderr.strip()}") from exc
    return result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
