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

    subparsers.add_parser("test-summary", help="Run the test suite and summarize any failures.")

    release_notes_parser = subparsers.add_parser(
        "release-notes", help="Generate release notes from Git history."
    )
    release_notes_parser.add_argument(
        "--from", dest="from_ref", default=None, help="Commit or tag to start from (exclusive)."
    )
    release_notes_parser.add_argument(
        "--to", dest="to_ref", default=None, help="Commit or tag to end at (inclusive)."
    )

    skill_parser = subparsers.add_parser("skill", help="Discover and inspect built-in skills.")
    skill_subparsers = skill_parser.add_subparsers(dest="skill_command", required=True)
    skill_subparsers.add_parser("list", help="List discovered skills.")
    inspect_parser = skill_subparsers.add_parser("inspect", help="Show one skill's manifest.")
    inspect_parser.add_argument("name", help="The skill's name.")

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
    elif args.command == "test-summary":
        result = engine.test_summary(Path.cwd())
    elif args.command == "release-notes":
        result = engine.release_notes(Path.cwd(), from_ref=args.from_ref, to_ref=args.to_ref)
    elif args.command == "skill":
        if args.skill_command == "list":
            result = engine.list_skills()
        else:
            result = engine.inspect_skill(args.name)
    else:
        result = engine.run()

    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
