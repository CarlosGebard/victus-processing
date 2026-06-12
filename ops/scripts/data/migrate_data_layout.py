from __future__ import annotations

import argparse
import filecmp
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from src.workspace.pipeline_context import PipelineRunContext


@dataclass(frozen=True)
class CopyPlan:
    source: Path
    target: Path
    category: str


@dataclass(frozen=True)
class Conflict:
    source: Path
    target: Path
    reason: str
    category: str


@dataclass(frozen=True)
class Unresolved:
    path: Path
    reason: str


@dataclass(frozen=True)
class MigrationPlan:
    copies: tuple[CopyPlan, ...]
    conflicts: tuple[Conflict, ...]
    unresolved: tuple[Unresolved, ...]


def build_plan(root: Path) -> MigrationPlan:
    root = root.resolve()
    copies: list[CopyPlan] = []
    conflicts: list[Conflict] = []
    unresolved: list[Unresolved] = []

    _plan_many(
        copies,
        conflicts,
        root / "data/runtime/02-pdfs/active",
        root / "data/artifacts/pdfs",
        "*.pdf",
        "active_pdf",
    )
    _plan_markdown(copies, conflicts, root)
    _scan_unresolved(unresolved, root)
    return MigrationPlan(copies=tuple(copies), conflicts=tuple(conflicts), unresolved=tuple(unresolved))


def apply_plan(plan: MigrationPlan) -> None:
    if plan.conflicts:
        raise SystemExit("Refusing to apply while conflicts exist. Resolve conflicts first.")
    for item in plan.copies:
        item.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item.source, item.target)


def print_plan(plan: MigrationPlan, *, root: Path, limit: int) -> None:
    print("Data layout migration plan")
    print(f"- copies:     {len(plan.copies)}")
    print(f"- conflicts:  {len(plan.conflicts)}")
    print(f"- unresolved: {len(plan.unresolved)}")

    _print_section("Copies", (f"{item.category}: {_rel(item.source, root)} -> {_rel(item.target, root)}" for item in plan.copies), limit)
    _print_section(
        "Conflicts",
        (
            f"{item.category}: {_rel(item.source, root)} -> {_rel(item.target, root)} ({item.reason})"
            for item in plan.conflicts
        ),
        limit,
    )
    _print_section("Unresolved legacy data", (f"{_rel(item.path, root)} ({item.reason})" for item in plan.unresolved), limit)


def write_report(plan: MigrationPlan, path: Path, *, root: Path) -> None:
    payload = {
        "copies": [
            {
                "category": item.category,
                "source": _rel(item.source, root),
                "target": _rel(item.target, root),
            }
            for item in plan.copies
        ],
        "conflicts": [
            {
                "category": item.category,
                "source": _rel(item.source, root),
                "target": _rel(item.target, root),
                "reason": item.reason,
            }
            for item in plan.conflicts
        ],
        "unresolved": [
            {
                "path": _rel(item.path, root),
                "reason": item.reason,
            }
            for item in plan.unresolved
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _plan_many(
    copies: list[CopyPlan],
    conflicts: list[Conflict],
    source_dir: Path,
    target_dir: Path,
    pattern: str,
    category: str,
) -> None:
    if not source_dir.exists():
        return
    for source in sorted(source_dir.glob(pattern)):
        if source.is_file():
            _plan_copy(copies, conflicts, source, target_dir / source.name, category)


def _plan_markdown(copies: list[CopyPlan], conflicts: list[Conflict], root: Path) -> None:
    source_root = root / "data/runtime/03-pdf_processing"
    target_dir = root / "data/artifacts/markdown"
    if not source_root.exists():
        return
    for source in sorted(source_root.glob("*/paper.md")):
        paper_id = source.parent.name
        _plan_copy(copies, conflicts, source, target_dir / f"{paper_id}.md", "markdown")


def _plan_exact_file(
    copies: list[CopyPlan],
    conflicts: list[Conflict],
    source: Path,
    target: Path,
    category: str,
) -> None:
    if source.exists() and source.is_file():
        _plan_copy(copies, conflicts, source, target, category)


def _plan_copy(
    copies: list[CopyPlan],
    conflicts: list[Conflict],
    source: Path,
    target: Path,
    category: str,
) -> None:
    if target.exists():
        if target.is_file() and filecmp.cmp(source, target, shallow=False):
            return
        conflicts.append(Conflict(source=source, target=target, reason="target_exists_with_different_content", category=category))
        return
    copies.append(CopyPlan(source=source, target=target, category=category))


def _scan_unresolved(unresolved: list[Unresolved], root: Path) -> None:
    unresolved_specs = (
        (root / "data/papers", "*/*", "legacy_paper_bundle_needs_manual_classification"),
        (root / "data/runtime/03-pdf_processing", "*/paper.processed.json", "needs_structured_blocks_jsonl_promotion"),
        (root / "data/runtime/03-pdf_processing", "*/paper.final.json", "compatibility_output_not_in_new_layout"),
        (root / "data/runtime/03-pdf_processing", "*/raw_batches/*.json", "needs_debug_raw_batches_jsonl_conversion"),
        (root / "data/runtime/03-pdf_processing", "*/raw_batches/*.failed.json", "needs_debug_failed_batches_jsonl_conversion"),
        (root / "data/runtime/04-evidence", "*/*.json", "needs_lake_evidence_jsonl_promotion"),
        (root / "data/testing", "*", "legacy_testing_layout"),
        (root / "data/registry", "unmapped_pdfs.jsonl", "no_target_in_current_contract"),
    )
    for base, pattern, reason in unresolved_specs:
        if not base.exists():
            continue
        for path in sorted(base.glob(pattern)):
            if path.exists():
                unresolved.append(Unresolved(path=path, reason=reason))


def _print_section(title: str, rows: object, limit: int) -> None:
    print(f"\n{title}:")
    count = 0
    for row in rows:
        if count >= limit:
            print(f"  ... truncated after {limit}")
            return
        print(f"  - {row}")
        count += 1
    if count == 0:
        print("  - none")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit and migrate legacy data/ into the target Victus data layout.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root.")
    parser.add_argument("--apply", action="store_true", help="Copy non-conflicting files into the new layout.")
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report path.")
    parser.add_argument("--limit", type=int, default=40, help="Rows to print per section.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.expanduser().resolve()
    context = PipelineRunContext.start(
        pipeline_name="data-layout-migration",
        pipeline_version="v1",
        execution_mode="backfill" if args.apply else "stage_only",
        process_name="victus.processing.data_layout_migration",
        input_scope={"root": root.as_posix(), "apply": bool(args.apply)},
        created_by="ops.scripts.data.migrate_data_layout",
        lake_dir=root / "data/lake",
        runtime_runs_dir=root / "data/runtime/runs",
    )

    try:
        plan_attempt = context.stage_attempt(stage="data_layout.plan")
        plan_attempt.event(
            event_type="stage_started",
            severity="info",
            status="started",
            message="Data layout migration planning started",
            action="plan.started",
        )
        plan = build_plan(root)
        plan_attempt.event(
            event_type="stage_succeeded",
            severity="info",
            status="succeeded",
            message="Data layout migration planning completed",
            action="plan.completed",
            metadata={
                "copies": len(plan.copies),
                "conflicts": len(plan.conflicts),
                "unresolved": len(plan.unresolved),
            },
        )

        if plan.conflicts:
            conflict_attempt = context.stage_attempt(stage="data_layout.conflict_detection")
            conflict_attempt.event(
                event_type="warning",
                severity="warning",
                status="warning",
                message="Data layout migration conflicts detected",
                action="conflicts.detected",
                metadata={"count": len(plan.conflicts)},
            )

        if plan.unresolved:
            unresolved_attempt = context.stage_attempt(stage="data_layout.unresolved_detection")
            unresolved_attempt.event(
                event_type="routing_decision",
                severity="info",
                status="succeeded",
                message="Legacy data remains outside the target layout",
                action="unresolved.detected",
                metadata={"count": len(plan.unresolved)},
            )

        print_plan(plan, root=root, limit=max(1, args.limit))
        if args.report:
            report_path = args.report.expanduser().resolve()
            write_report(plan, report_path, root=root)
            report_attempt = context.stage_attempt(stage="data_layout.report")
            report_attempt.event(
                event_type="artifact_created",
                severity="info",
                status="succeeded",
                message="Data layout migration report written",
                action="report.written",
                artifact_path=report_path.as_posix(),
                metadata={"report_path": report_path.as_posix()},
            )
            print(f"\nReport written: {args.report}")
        if args.apply:
            copy_attempt = context.stage_attempt(stage="data_layout.copy")
            copy_attempt.event(
                event_type="stage_started",
                severity="info",
                status="started",
                message="Data layout migration copy started",
                action="copy.started",
                metadata={"planned_copies": len(plan.copies)},
            )
            apply_plan(plan)
            copy_attempt.event(
                event_type="stage_succeeded",
                severity="info",
                status="succeeded",
                message="Data layout migration copy completed",
                action="copy.completed",
                metadata={"copied": len(plan.copies)},
            )
            print("\nApplied non-conflicting copy plan.")

        status = "failed" if plan.conflicts else "succeeded"
        context.finish(status=status, summary={"copies": len(plan.copies), "conflicts": len(plan.conflicts), "unresolved": len(plan.unresolved)})
        return 1 if plan.conflicts else 0
    except Exception as exc:
        context.fail(stage="data_layout.plan", error=exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
