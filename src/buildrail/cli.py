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

    subparsers.add_parser(
        "verify", help="Run local format/lint/type/test checks and write a verification report."
    )

    skill_parser = subparsers.add_parser("skill", help="Discover and inspect built-in skills.")
    skill_subparsers = skill_parser.add_subparsers(dest="skill_command", required=True)
    skill_subparsers.add_parser("list", help="List discovered skills.")
    inspect_parser = skill_subparsers.add_parser("inspect", help="Show one skill's manifest.")
    inspect_parser.add_argument("name", help="The skill's name.")

    hooks_parser = subparsers.add_parser("hooks", help="Manage the local Git pre-commit hook.")
    hooks_subparsers = hooks_parser.add_subparsers(dest="hooks_command", required=True)
    hooks_subparsers.add_parser("install", help="Install/update the pre-commit hook.")
    hooks_subparsers.add_parser("uninstall", help="Remove the Buildrail-managed hook block.")
    hooks_subparsers.add_parser("status", help="Show whether the hook is installed.")

    runs_parser = subparsers.add_parser("runs", help="Browse local run history.")
    runs_subparsers = runs_parser.add_subparsers(dest="runs_command", required=True)
    runs_list_parser = runs_subparsers.add_parser("list", help="List recent runs.")
    runs_list_parser.add_argument(
        "--limit", type=int, default=20, help="Maximum number of runs to show (default 20)."
    )
    runs_inspect_parser = runs_subparsers.add_parser("inspect", help="Show one run's details.")
    runs_inspect_parser.add_argument("run_id", help="The run's id.")

    artifacts_parser = subparsers.add_parser("artifacts", help="Browse local artifacts.")
    artifacts_subparsers = artifacts_parser.add_subparsers(dest="artifacts_command", required=True)
    artifacts_inspect_parser = artifacts_subparsers.add_parser(
        "inspect", help="Show one artifact's metadata and payload."
    )
    artifacts_inspect_parser.add_argument("artifact_id", help="The artifact's id.")

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
    elif args.command == "verify":
        result = engine.verify_project(Path.cwd())
    elif args.command == "skill":
        if args.skill_command == "list":
            result = engine.list_skills()
        else:
            result = engine.inspect_skill(args.name)
    elif args.command == "hooks":
        if args.hooks_command == "install":
            result = engine.install_hook(Path.cwd())
        elif args.hooks_command == "uninstall":
            result = engine.uninstall_hook(Path.cwd())
        else:
            result = engine.hook_status(Path.cwd())
    elif args.command == "runs":
        if args.runs_command == "list":
            result = engine.list_runs(Path.cwd(), limit=args.limit)
        else:
            result = engine.inspect_run(Path.cwd(), args.run_id)
    elif args.command == "artifacts":
        result = engine.inspect_artifact(Path.cwd(), args.artifact_id)
    else:
        result = engine.run()

    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
