"""Buildrail's CLI entrypoint. All orchestration lives in the Core Engine."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from buildrail.core import CoreEngine


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser for the Buildrail CLI."""
    parser = argparse.ArgumentParser(prog="buildrail")
    subparsers = parser.add_subparsers(dest="command")

    config_parser = subparsers.add_parser("config", help="Manage Buildrail configuration.")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_subparsers.add_parser("validate", help="Validate the project configuration.")

    provider_parser = subparsers.add_parser("provider", help="Inspect the configured provider.")
    provider_subparsers = provider_parser.add_subparsers(dest="provider_command", required=True)
    provider_subparsers.add_parser("check", help="Confirm the configured provider responds.")

    review_parser = subparsers.add_parser(
        "review", help="Review a diff with the review-diff skill."
    )
    review_parser.add_argument("--diff", required=True, type=Path, help="Path to a unified diff.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    engine = CoreEngine()

    if args.command == "config":
        result = engine.validate_config(Path.cwd())
    elif args.command == "provider":
        result = engine.check_provider(Path.cwd())
    elif args.command == "review":
        result = engine.review(Path.cwd(), args.diff)
    else:
        result = engine.run()

    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
