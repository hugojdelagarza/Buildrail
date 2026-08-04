"""The verify-project skill: runs Buildrail's deterministic local quality gate.

Provider-free — never imports or references buildrail.providers, and never
receives a real ProviderGateway (the Pipeline Runner passes None for skills
whose manifest declares requires_provider: false). Runs `ruff format
--check`, `ruff check`, `mypy`, and `pytest -v` sequentially against the
run's working directory, stopping at the first failed check, and reports
the results as one verification-report artifact. Executed in-process for
Milestone 1 (docs/skills.md's phasing note); `entrypoint` in skill.yaml
describes the eventual subprocess invocation, not what actually runs today.
"""

import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Literal

from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse

_COMMAND_TIMEOUT_SECONDS = 300
# Deterministic tail-preserving truncation: failures are almost always at the
# end of a tool's output, so keep the last N characters, not the first.
_MAX_OUTPUT_CHARS = 20_000

_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ruff format --check .", (sys.executable, "-m", "ruff", "format", "--check", ".")),
    ("ruff check .", (sys.executable, "-m", "ruff", "check", ".")),
    ("mypy", (sys.executable, "-m", "mypy")),
    ("pytest -v", (sys.executable, "-m", "pytest", "-v")),
)


class _CommandLaunchError(Exception):
    """Raised when a check's command could not be launched at all, or timed out."""


@dataclass(frozen=True)
class _CheckResult:
    name: str
    args: tuple[str, ...]
    exit_code: int
    duration_seconds: float
    stdout: str
    stderr: str
    status: Literal["passed", "failed"]


def run(request: SkillRequest, provider: object | None) -> SkillResponse:
    """Run each configured check in order against the run's working directory."""
    workdir = request.run_context.workdir
    results: list[_CheckResult] = []

    for name, args in _CHECKS:
        try:
            result = _run_command(name, args, cwd=workdir)
        except _CommandLaunchError as exc:
            return SkillResponse(status="failure", outputs={}, error=str(exc))

        results.append(result)
        if result.status == "failed":
            break

    passed = len(results) == len(_CHECKS) and all(r.status == "passed" for r in results)
    failed_check = next((r.name for r in results if r.status == "failed"), None)
    total_duration = sum(r.duration_seconds for r in results)

    output = SkillOutput(
        content=_build_report(results, passed=passed),
        artifact_type="verification-report",
        metadata={
            "passed": passed,
            "checks_passed": sum(1 for r in results if r.status == "passed"),
            "checks_total": len(_CHECKS),
            "failed_check": failed_check,
            "duration_seconds": total_duration,
        },
    )
    return SkillResponse(status="success", outputs={"report": output})


def _run_command(name: str, args: tuple[str, ...], *, cwd: str) -> _CheckResult:
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            args, cwd=cwd, capture_output=True, text=True, timeout=_COMMAND_TIMEOUT_SECONDS
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _CommandLaunchError(f"Could not run '{name}': {exc}") from exc
    duration = time.perf_counter() - start

    status: Literal["passed", "failed"] = "passed" if completed.returncode == 0 else "failed"
    return _CheckResult(
        name=name,
        args=args,
        exit_code=completed.returncode,
        duration_seconds=duration,
        stdout=_truncate(completed.stdout),
        stderr=_truncate(completed.stderr),
        status=status,
    )


def _truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    omitted = len(text) - _MAX_OUTPUT_CHARS
    return f"...[{omitted} characters truncated]...\n{text[-_MAX_OUTPUT_CHARS:]}"


def _build_report(results: list[_CheckResult], *, passed: bool) -> str:
    status_word = "PASSED" if passed else "FAILED"
    passed_count = sum(1 for r in results if r.status == "passed")
    lines = [
        "# Verification Report",
        "",
        f"**Status:** {status_word}",
        f"**Checks:** {passed_count}/{len(_CHECKS)} passed",
        "",
    ]
    for result in results:
        lines.append(f"## {result.name}")
        lines.append("")
        lines.append(f"- Command: `{' '.join(result.args)}`")
        lines.append(f"- Status: {result.status}")
        lines.append(f"- Exit code: {result.exit_code}")
        lines.append(f"- Duration: {result.duration_seconds:.2f}s")
        lines.append("")
        if result.stdout.strip():
            lines.append("### stdout")
            lines.append("")
            lines.append(f"```\n{result.stdout}\n```")
            lines.append("")
        if result.stderr.strip():
            lines.append("### stderr")
            lines.append("")
            lines.append(f"```\n{result.stderr}\n```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
