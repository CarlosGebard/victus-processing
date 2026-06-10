from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


LEGACY_PATHS = (
    "data/runtime/03-pdf_processing",
    "data/runtime/04-evidence",
    "data/testing",
    "data/registry/unmapped_pdfs.jsonl",
)


@dataclass(frozen=True)
class ArchivePlanItem:
    source: Path
    target: Path


def build_archive_plan(root: Path, *, date: str | None = None) -> tuple[ArchivePlanItem, ...]:
    root = root.resolve()
    archive_date = date or datetime.now(timezone.utc).date().isoformat()
    archive_root = root / "data/legacy/archive" / archive_date
    items: list[ArchivePlanItem] = []
    for relative in LEGACY_PATHS:
        source = root / relative
        if source.exists():
            items.append(ArchivePlanItem(source=source, target=archive_root / relative.removeprefix("data/")))
    return tuple(items)


def apply_archive_plan(plan: tuple[ArchivePlanItem, ...]) -> None:
    for item in plan:
        if item.target.exists():
            raise SystemExit(f"Refusing to overwrite archive target: {item.target}")
        item.target.parent.mkdir(parents=True, exist_ok=True)
        if item.source.is_dir():
            shutil.copytree(item.source, item.target)
            if not item.target.is_dir():
                raise SystemExit(f"Archive copy failed: {item.target}")
            shutil.rmtree(item.source)
            continue
        shutil.copy2(item.source, item.target)
        if not item.target.is_file():
            raise SystemExit(f"Archive copy failed: {item.target}")
        item.source.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Archive legacy runtime paths without deleting them.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--date", default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Print archive plan without moving files.")
    mode.add_argument("--apply", action="store_true", help="Move legacy paths into data/legacy/archive/{date}/.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    plan = build_archive_plan(args.root.expanduser().resolve(), date=args.date)
    print("Legacy runtime cleanup plan")
    print(f"- archive_items: {len(plan)}")
    for item in plan:
        print(f"  - {item.source} -> {item.target}")
    if args.apply:
        apply_archive_plan(plan)
        print("\nArchived legacy runtime paths.")
    else:
        print("\nDry run only. Use --apply to archive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
