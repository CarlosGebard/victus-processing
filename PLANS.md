# Pipeline Interface Rename Plan

## Goal

Make the public CLI and operations documentation use the 1.0.0 pipeline names:
`metadata-extraction`, `metadata-to-pdf`, `pdf-processing`,
`evidence-extraction`, and `testing-pipeline`.

## Scope

- Rename public CLI groups to match pipeline stages.
- Move evidence and testing out of `pdf-processing`.
- Keep runtime artifact directories unchanged.
- Update smoke tests and operations/contracts docs that reference CLI commands.
- Do not rename Python modules or data directories in this pass.

## Assumptions

- Version 1.0.0 can break old CLI names.
- Old names should not remain as documented aliases.
- Runtime paths like `data/runtime/03-pdf_processing` and `data/runtime/04-evidence`
  stay stable.

## Steps

1. Completed: update CLI parser groups.
   - Legacy metadata group becomes `metadata-extraction`.
   - Legacy bibliography and PDF normalization groups become `metadata-to-pdf`.
   - `pdf-processing` keeps Markdown/PDF structuring only.
   - Legacy evidence subcommand becomes `evidence-extraction run`.
   - Legacy testing subcommand becomes `testing-pipeline run`.

2. Completed: update tests.
   - Smoke tests assert new top-level commands.
   - Existing command handlers are covered through new routes.

3. Completed: update docs.
   - Operations CLI reference.
   - Pipeline operations docs.
   - Contracts mentioning public CLI surface.

4. Completed: validate.
   - `uv run pytest tests/test_cli_smoke.py tests/test_prompt_registry.py tests/test_evidence_extraction.py -q`
   - `uv run victus-processing --help`
   - targeted `--help` for new pipeline command groups.

5. Completed: align application folders with pipeline names.
   - `src/application/metadata` becomes `src/application/metadata_extraction`.
   - `src/application/pdf_extraction` becomes `src/application/metadata_to_pdf`.
   - Evidence modules move out of `src/application/pdf_processing`.
   - Testing helpers move out of `src/application/pdf_processing`.
   - `pdf_processing` keeps only PDF-to-Markdown/structured-paper code.

6. Completed: align prompt folders and prompt names with pipeline names.
   - Metadata selector prompts live under `src/prompts/metadata_extraction/`.
   - Markdown structuring prompts live under `src/prompts/pdf_processing/`.
   - Evidence prompts live under `src/prompts/evidence_extraction/`.
   - The mapper prompt is `results_scope_mapper`, because it maps result
     scopes rather than generic experiment scopes.
   - Root prompt files and `src/prompts/local/` legacy prompt copies are removed.

## Risks

- External scripts using old command names will break.
- Docs may retain stale command examples if not searched carefully.
- `metadata-to-pdf` combines two previous groups, so help text must be explicit.

---

# Testing Artifact Collection Plan

## Goal

Run the complete paper pipeline in per-paper testing folders so paper review is
fast and local, ending at `canonical_evidence.json`.

## Scope

- Add a focused `testing-pipeline run` CLI operation.
- Run Docling, Markdown structuring, experiment mapping, and evidence
  extraction under `data/testing/<paper_id>/`.
- Copy `source.pdf` into the same folder for review.
- Use `data/testing` as the configured testing root.
- Keep runtime `02-pdfs` and `03-pdf_processing` layout unchanged.

## Assumptions

- Active PDFs are named `<paper_id>.pdf`.
- Missing selected PDFs should fail explicitly.

## Steps

1. Add small helpers for selected testing PDFs and `source.pdf` copies.
2. Expose the full pipeline as `victus-processing testing-pipeline run`.
3. Update testing config and data-layout directory creation.
4. Add focused tests for source copy behavior, CLI availability, and pipeline
   routing.
5. Update CLI operations and CLI contract docs.

## Validation

```bash
uv run pytest tests/test_pdf_processing.py tests/test_cli_smoke.py -q
```

## Risks

- Existing dirty runtime data may have papers with only one artifact; those
  should be skipped with explicit status output.
- Copying large PDFs duplicates disk usage under `data/testing`.

---

# Evidence Packetization Plan

## Goal

Make canonical evidence extraction consume explicit scope packets derived from
`experiment_map`, so each experiment scope becomes one extraction pass with the
exact blocks needed for that pass.

## Scope

- Keep `results_scope_mapper` responsible for selecting all relevant
  `source_block_ids` for each scope.
- Add deterministic packet construction after experiment-map validation.
- Pass packetized scope inputs to canonical evidence extraction instead of one
  global block list.
- Persist packet artifacts for review and debugging.
- Update prompts and contracts to define scope packets as the handoff from
  experiment mapping to canonical evidence.

## Assumptions

- `experiment_map.source_block_ids` is the authoritative packet membership.
- A packet may include methods, population/context, intervention/exposure,
  comparator/control, measurement, results, tables/figures, and relevant
  discussion blocks when the mapper explicitly selected them.
- A block may appear in multiple packets when the map duplicates it across
  scopes.
- Canonical evidence extraction should not use blocks outside the current
  packet.

## Steps

1. Introduce `build_experiment_packets(trimmed, experiment_map)`.
   - Input: trimmed metadata/blocks plus validated experiment map.
   - Output: ordered packets with `scope_index`, `scope_label`, `scope_kind`,
     `scope_basis`, `source_block_ids`, and `blocks`.
   - Validation: packet ids must reference existing blocks and each packet must
     contain at least one block.

2. Update evidence orchestration.
   - Write `experiment_packets.json` after `experiment_map.json`.
   - Call canonical evidence extraction once per packet.
   - Aggregate validated canonical evidence and unextracted items into the final
     `canonical_evidence.json`.
   - Validate every support block id against the current packet and the full
     trimmed block id set.

3. Update canonical evidence prompt input.
   - Replace global `blocks + experiment_map` framing with a single
     `experiment_packet`.
   - State that each call is one extraction pass for one scope.
   - Require all populated fields and support ids to come only from packet
     blocks.

4. Update contracts and operations docs.
   - Update experiment-map contract to define scope membership as packet
     membership.
   - Update stage handoffs to replace the old "no intermediate packet object"
     rule.
   - Update artifact schema docs for `experiment_packets.json`.

5. Add focused tests.
   - Packet construction preserves scope order and block order.
   - Canonical extraction is called once per packet.
   - Evidence support ids outside the current packet fail validation.
   - Existing trimming, mapping, and CLI behavior remain stable.

## Validation

```bash
uv run pytest tests/test_evidence_extraction.py tests/test_cli_smoke.py
uv run pytest
```

## Risks

- More LLM calls: one canonical extraction call per experiment packet.
- Over-fragmented maps will produce over-fragmented evidence passes.
- Under-complete maps will still miss context; the mapper prompt must clearly
  require complete packet membership.
