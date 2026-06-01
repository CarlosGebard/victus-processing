from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _base_args(args: argparse.Namespace) -> list[str]:
    command = ["infisical"]
    if args.project_id:
        command.append(f"--projectId={args.project_id}")
    if args.env:
        command.append(f"--env={args.env}")
    if args.path:
        command.append(f"--path={args.path}")
    return command


def _require_infisical() -> None:
    if shutil.which("infisical") is None:
        raise SystemExit("infisical CLI not found. Install it and authenticate before running this script.")


def export_env(args: argparse.Namespace) -> int:
    _require_infisical()
    command = _base_args(args) + ["export", f"--format={args.format}"]
    if args.output:
        command.append(f"--output-file={args.output}")
    result = subprocess.run(command, check=False)
    return result.returncode


def run_with_env(args: argparse.Namespace) -> int:
    _require_infisical()
    if not args.command:
        raise SystemExit("run requires a command after --")
    command = _base_args(args) + ["run", "--", *args.command]
    result = subprocess.run(command, check=False)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load Victus Processing environment variables from Infisical.")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    export_parser = subparsers.add_parser("export", help="Export Infisical secrets as dotenv content or file.")
    _add_infisical_args(export_parser)
    export_parser.add_argument(
        "--format",
        choices=("dotenv", "dotenv-export", "json", "yaml"),
        default="dotenv",
        help="Infisical export format.",
    )
    export_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output file, for example .env.",
    )
    export_parser.set_defaults(handler=export_env)

    run_parser = subparsers.add_parser("run", help="Run a command with Infisical secrets injected.")
    _add_infisical_args(run_parser)
    run_parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --.")
    run_parser.set_defaults(handler=run_with_env)

    return parser


def _add_infisical_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env", default="dev", help="Infisical environment slug.")
    parser.add_argument("--path", default="/", help="Infisical secret path.")
    parser.add_argument("--project-id", default=None, help="Infisical project id when not configured locally.")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
