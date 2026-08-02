"""The Core Engine: Buildrail's single orchestration entry point."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    """The outcome of a single Core Engine invocation."""

    success: bool
    message: str


class CoreEngine:
    """Owns orchestration; the CLI's only entry point into Buildrail's core logic."""

    def run(self) -> Result:
        """Execute the current orchestration step and return its outcome."""
        return Result(success=True, message="Buildrail initialized.")
