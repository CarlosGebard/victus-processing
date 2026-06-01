---
id: VICTUS-PROCESSING-GHCR-RUNBOOK
title: Victus Processing GitHub Container Registry Runbook
status: source-of-truth
updated_at: 2026-05-27
owners:
  - architecture
tags:
  - operations
  - runbook
  - containers
---

# GitHub Container Registry

## Purpose

Build and publish the `victus-processing` CLI image to GitHub Container Registry.

## Image

```bash
ghcr.io/OWNER/REPOSITORY
```

Replace `OWNER/REPOSITORY` with the GitHub repository slug.

## Local Build

```bash
docker build -t victus-processing:local .
docker run --rm victus-processing:local --help
```

Run with project data mounted:

```bash
docker run --rm \
  --env LITELLM_API_KEY \
  --env SEMANTIC_SCHOLAR_API_KEY \
  --volume "$PWD/data:/app/data" \
  victus-processing:local data-layout create --dry-run
```

## GitHub Actions Publish

The workflow `.github/workflows/publish-container.yml`:

- runs smoke tests on pull requests and pushes;
- builds the Docker image on pull requests;
- publishes to `ghcr.io` on pushes to `main` and version tags matching `v*`.

Required repository settings:

- Actions enabled.
- Workflow permissions allow package writes.
- `GITHUB_TOKEN` can publish packages.

No repository secret is required for GHCR publishing from the same repository.

## Pull And Run

```bash
docker pull ghcr.io/OWNER/REPOSITORY:main
docker run --rm ghcr.io/OWNER/REPOSITORY:main --help
```

For tagged releases:

```bash
docker pull ghcr.io/OWNER/REPOSITORY:0.1.0
docker run --rm ghcr.io/OWNER/REPOSITORY:0.1.0 --help
```

## Rollback

Deploy the previous known-good tag or SHA tag:

```bash
docker pull ghcr.io/OWNER/REPOSITORY:sha-OLD_SHA
docker run --rm ghcr.io/OWNER/REPOSITORY:sha-OLD_SHA --help
```

If a bad package was published, remove or mark it private from the GitHub
Packages UI after consumers are moved back to a known-good tag.

## Operational Notes

- Do not bake `data/` or secrets into images.
- Provide runtime credentials through environment variables or the deployment
  secret manager.
- The image defaults to `victus-processing --help`; pass CLI arguments after the
  image name.
- The package currently installs all project console scripts, but the default
  command avoids optional bridge commands unless explicitly invoked.
