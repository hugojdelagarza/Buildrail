"""Buildrail's CLI entrypoint. All orchestration lives in the Core Engine."""

from buildrail.core import CoreEngine


def main() -> int:
    """Run the CLI and return a process exit code."""
    engine = CoreEngine()
    result = engine.run()
    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
