---
id: VICTUS-PROCESSING-CONFIGURATION-AND-CLI-CONTRACT
title: Victus Processing Configuration and CLI Contract
status: source-of-truth
updated_at: 2026-06-05
related_components:
  - src.cli
  - src.workspace.config
  - src.infrastructure.llm
  - ops.scripts.infisical_env
  - config
related_docs:
  - VICTUS-PROCESSING-CONTRACTS
tags:
  - contracts
  - configuration
  - cli
---

# Configuration and CLI Contract

## 1. Purpose

This contract governs configuration loading, path resolution, environment
loading, and the public CLI command surface.

## 2. Scope

Covered:

- `config/*.yaml` loading;
- optional root `config.yaml` overrides;
- `.env` loading into process environment;
- repository-relative path resolution;
- public `victus-processing` command groups.
- public `victus-infisical-env` helper command.

Not covered:

- vendor-side API behavior;
- shell aliases or external orchestration;
- deployment-specific secret management outside this repository.

## 3. Guarantees

- Configuration defaults are loaded from sorted `config/*.yaml` files.
- Optional root `config.yaml` overrides domain config after `config/*.yaml`.
- Config files must contain YAML mappings.
- Nested mappings merge recursively; scalar and list values replace previous
  values.
- Relative configured paths resolve from `src.workspace.config.ROOT_DIR`.
- Absolute configured paths remain absolute.
- `.env` is loaded from the repository root during workspace config import.
- `.env` values do not overwrite existing environment variables.
- `get_env_or_config()` gives environment variables precedence over config.
- LiteLLM and Langfuse settings are environment-driven infrastructure concerns.
- Infisical may populate the process environment or `.env`; loaded values still
  follow the same precedence rules above.
- Prompt registry runtime variables are `PROMPT_LABEL`, `PROMPTS_LOCAL_DIR`,
  and `DEFAULT_LLM_MODEL`.
- `pdf_processing.max_tokens` controls the output token budget for local
  `pdf-processing run` Markdown-to-JSON prompts. `null` means the request does
  not send an explicit `max_tokens` value and relies on provider/model defaults.
- Langfuse Prompt Management credentials are `LANGFUSE_PUBLIC_KEY`,
  `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST`.

## 4. Public CLI Surface

The stable command groups are:

```text
victus-processing metadata-extraction
victus-processing metadata-to-pdf
victus-processing pdf-processing
victus-processing evidence-extraction
victus-processing testing-pipeline
victus-processing bridge
victus-processing data-layout
victus-infisical-env
```

Stable subcommands currently used by operators and agents:

```text
metadata-extraction explore
metadata-extraction from-doi
metadata-extraction seed-dois
metadata-to-pdf generate-bib
metadata-to-pdf normalize-pdfs
pdf-processing run
pdf-processing markdown
evidence-extraction run
testing-pipeline run
data-layout create
victus-infisical-env export
victus-infisical-env run
```

These names are compatibility boundaries. Do not rename or remove them unless a
task explicitly asks for a public API change and updates docs/tests in the same
change.

## 5. Inputs and Outputs

- `metadata-extraction explore` reads exploration config and DOI seed queues.
- `metadata-extraction from-doi` requires `--doi` and writes one metadata JSON.
- `metadata-extraction seed-dois` writes seed DOI queues for configured profiles.
- `metadata-to-pdf generate-bib` writes BibTeX from metadata or an explicit CSV.
- `metadata-to-pdf normalize-pdfs` copies or skips PDFs based on DOI/PDF
  relation data.
- `pdf-processing run` writes final structured paper artifacts.
- `pdf-processing markdown` writes `paper.md` and markdown status only.
- `testing-pipeline run` runs the PDF-processing and evidence chain under
  `data/testing/<paper_id>/`, including `source.pdf`, `paper.md`,
  `markdown_batches/`, `paper.processed.json`, `paper.final.json`, and
  evidence artifacts.
- `evidence-extraction run` writes `trimmed.json`, `experiment_map.json`, and
  `canonical_evidence.json` from processed paper JSON inputs.
- `data-layout create` ensures required runtime directories exist.
- `victus-infisical-env export` writes Infisical secrets in dotenv-compatible
  formats.
- `victus-infisical-env run` executes a command with Infisical secrets injected.

## 6. Failure Expectations

- Missing required files or directories should fail explicitly with a clear CLI
  error.
- Missing provider credentials should fail only for model-mediated stages that
  require an LLM request.
- CLI commands should preserve existing output files when their documented
  skip/force/overwrite behavior says so.
- Bridge commands may be unavailable when optional bridge modules are absent;
  this must fail with an explicit message.

## 7. Related Documents

- [Contracts](../300-CONTRACTS.md)
- [Data Layout](data-layout.md)
- [Stage Handoffs](stage-handoffs.md)
- [CLI operations](../operations/cli.md)
