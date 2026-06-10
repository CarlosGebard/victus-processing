---
id: VICTUS-CONTRACTS-SYNC-OPERATIONS
title: Contract Synchronization Operations
status: source-of-truth
updated_at: 2026-06-10
related_components:
  - ops.scripts.contracts
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - operations
  - contracts
  - synchronization
---

# Contract Synchronization

`contracts` synchronizes subscribed fundamental contract Markdown files from the
central Victus documentation repository into this repository.

The sync destination is:

```text
docs/contracts/fundamental/
```

The synchronized files are not authored directly in this repository. The local
script owns the source repository, source registry, and subscribed contract list.
Operators run the sync utility, validate the result, and review the generated
lock file before committing documentation changes.

## Operational Model

The synchronization flow is intentionally file-based and deterministic:

1. `ops/scripts/contracts.py` declares the central source repository, source
   registry, source contract root, and required contract versions.
2. `contracts sync` clones or updates the source repository in
   `.cache/victus-contracts/`.
3. The source registry maps each `(contract_id, version)` to a Markdown source
   path in the central checkout.
4. Matching Markdown files are copied into `docs/contracts/fundamental/` while
   preserving their path below the central `docs/contracts/` directory.
5. `docs/contracts/fundamental/contracts.lock.json` records the source commit,
   destination paths, and SHA-256 checksums.

Current local source configuration in `ops/scripts/contracts.py` points at:

```python
SOURCE_REPO = "/home/carlos/victus/victus-docs"
SOURCE_REGISTRY = Path("docs/contracts/_registry/contracts.registry.yml")
SOURCE_CONTRACTS_ROOT = Path("docs/contracts")
```

The same utility also supports a remote Git source such as
`git@github.com:carlos/victus-docs.git`.

## CLI Usage

```bash
uv run contracts list
uv run contracts sync
uv run contracts validate
```

Optional path flags:

```bash
uv run contracts \
  --contracts-dir docs/contracts/fundamental \
  --cache-dir .cache/victus-contracts \
  sync
```

Commands:

- `contracts list`: prints subscribed contract ids and required versions.
- `contracts sync`: clones or updates the source repository, copies subscribed
  Markdown contracts into `docs/contracts/fundamental/`, and writes the lock file.
- `contracts validate`: verifies subscriptions, registry entries, lock entries,
  destination paths, and checksums.

## Normal Sync Procedure

Use this procedure when central contracts changed or when this repository needs
to subscribe to another fundamental contract.

1. Inspect current subscriptions:

   ```bash
   uv run contracts list
   ```

2. Edit `ops/scripts/contracts.py` only when the source repository, registry
   path, source contract root, or subscribed contracts must change.

3. Synchronize from the configured source:

   ```bash
   uv run contracts sync
   ```

4. Validate the synchronized files and lock file:

   ```bash
   uv run contracts validate
   ```

5. Review the diff before committing:

   ```bash
   git diff -- docs/contracts/fundamental docs/300-CONTRACTS.md docs/operations/contracts-sync.md
   ```

Expected sync output lists each synchronized contract and destination path.
Expected validation output lists each locked contract and checksum.

## Script-Owned Subscription Configuration

There is no local subscription YAML file. The operational configuration lives in
`ops/scripts/contracts.py`:

```python
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
```

Operational notes:

- `SOURCE_REPO` is passed to `git clone` for first use and updated with
  `git fetch --depth 1 origin` plus `git pull --ff-only` on later runs.
- `SOURCE_REGISTRY` must be a relative path inside the source checkout.
- `SOURCE_CONTRACTS_ROOT` defines the central path prefix removed before writing
  into `docs/contracts/fundamental/`.
- Duplicate subscribed `contract_id` values fail validation.
- The script-owned subscription list is local policy; the central registry is
  the contract catalog.

## Source Registry

The source registry may be a top-level list or an object containing
`contracts`.

```yaml
contracts:
  - contract_id: victus.scientific.paper
    version: v1
    path: docs/contracts/scientific/paper.md

  - contract_id: victus.scientific.canonical_evidence
    version: v1
    path: docs/contracts/scientific/canonical-evidence.md
```

Required registry fields:

- `contract_id`
- `version`
- `path`

## Lock File

Path:

```text
docs/contracts/fundamental/contracts.lock.json
```

Example:

```json
{
  "synced_at": "2026-06-10T12:00:00+00:00",
  "source_commit": "4f34f3a9a86b7a1e8a24d604cb2d9c3d1d5d3a11",
  "contracts": [
    {
      "contract_id": "victus.scientific.paper",
      "version": "v1",
      "source_path": "docs/contracts/scientific/paper.md",
      "destination_path": "docs/contracts/fundamental/scientific/paper.md",
      "checksum": "sha256:8f5b2f4b1e3a9e9d0c0c5f1e9c7a2d8c4b7f1d0a2e3c4b5a6d7e8f9a0b1c2d3e"
    }
  ]
}
```

The lock file is generated by `contracts sync`. Operators should not hand-edit
it except to resolve a failed merge with the same content that a clean sync would
produce.

Lock fields:

- `synced_at`: UTC sync timestamp.
- `source_commit`: central source checkout commit used for the sync.
- `contracts[].source_path`: source Markdown path from the central registry.
- `contracts[].destination_path`: local synchronized path.
- `contracts[].checksum`: SHA-256 checksum of the local copied file.

## Validation Behavior

Validation repeats steps 1-3, then verifies:

- every subscribed contract exists in the source registry;
- each required version is present;
- the lock file matches subscriptions;
- each locked source path still matches the registry;
- every destination path remains inside `docs/contracts/fundamental/`;
- each contract file checksum matches the lock.

Run validation after every sync and before preparing a commit that changes
fundamental contracts.

## Failure and Recovery

- **Source repository cannot be cloned or fetched:** verify local path or Git
  remote access, then rerun `uv run contracts sync`.
- **Cache path exists but is not a Git checkout:** move or remove the specific
  directory under `.cache/victus-contracts/`, then rerun sync.
- **Required contract version not found:** update the subscription to an
  available version in `ops/scripts/contracts.py` or add the missing
  contract/version to the central registry.
- **Registry path mismatch during validation:** rerun sync after confirming the
  central registry change is intentional.
- **Checksum mismatch:** rerun sync. If the mismatch remains, inspect whether
  synchronized files were edited locally.
- **Destination path collision:** resolve the collision in the central registry
  paths or subscription set before syncing again.

The sync operation is idempotent for the same source commit and subscriptions.
Rerunning `contracts sync` overwrites synchronized Markdown files under
`docs/contracts/fundamental/` and rewrites `contracts.lock.json`.

## Safety Rules

- Sync writes only under the configured contracts directory.
- The default contracts directory is `docs/contracts/fundamental/`.
- Source registry paths must be relative and must stay inside the source
  checkout.
- Destination paths preserve the central path below `docs/contracts/`.
- Duplicate subscribed `contract_id` values fail.
- Duplicate `(contract_id, version)` source registry entries fail.
- Missing required versions fail.
- Destination path collisions fail.

## Operational Boundaries

This document owns the procedure for synchronizing and validating fundamental
contracts in this repository.

It does not define the contract content itself. Fundamental contract semantics
live in the central documentation repository and are copied locally under
`docs/contracts/fundamental/`. Repository-local implementation contracts live
under `docs/contracts/local/`.
