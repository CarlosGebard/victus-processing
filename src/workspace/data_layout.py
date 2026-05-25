#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from src.workspace import config as ctx


def create_data_layout() -> tuple[Path, ...]:
    created_dirs: list[Path] = []
    for directory in ctx.get_data_layout_dirs():
        directory.mkdir(parents=True, exist_ok=True)
        created_dirs.append(directory)
    return tuple(created_dirs)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crea o inspecciona la estructura canonica de directorios bajo data/."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra los directorios requeridos sin crearlos.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    created_dirs = tuple(ctx.get_data_layout_dirs()) if args.dry_run else create_data_layout()

    print("Data layout dry-run" if args.dry_run else "Data layout ensured")
    for directory in created_dirs:
        print(f"- {ctx.display_path(directory)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
