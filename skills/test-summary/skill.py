"""The test-summary skill: runs pytest and summarizes any failures via the Provider Gateway.

Provider-neutral — only imports buildrail.providers' public Gateway and
request/response types, never a concrete adapter. Executed in-process for
Milestone 1 (docs/skills.md's phasing note); `entrypoint` in skill.yaml
describes the eventual subprocess invocation, not what actually runs today.
The provider is only invoked when pytest reports a failure — a clean run
never spends a request.
"""

import subprocess
import sys
from dataclasses import dataclass

from buildrail.providers import Message, ProviderError, ProviderGateway, ProviderRequest, TextPart
from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse

_MAX_FAILURE_CHARS = 4000


@dataclass(frozen=True)
class _TestReport:
    all_passed: bool
    summary_line: str
    failed_tests: tuple[str, ...]
    failure_text: str


def run(request: SkillRequest, provider: ProviderGateway) -> SkillResponse:
    """Run pytest in the run's working directory and summarize any failures."""
    workdir = request.run_context.workdir

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short", "-rf"],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except OSError as exc:
        return SkillResponse(status="failure", outputs={}, error=f"Could not run pytest: {exc}")

    report = _parse_pytest_output(completed.stdout, completed.returncode)

    if report.all_passed:
        content = _build_success_report(report)
        output = SkillOutput(content=content, artifact_type="test-summary")
        return SkillResponse(status="success", outputs={"summary": output})

    provider_request = ProviderRequest(
        messages=(
            Message(
                role="user",
                content=(TextPart(text=_build_prompt(report)),),
            ),
        )
    )

    try:
        provider_response = provider.complete(provider_request)
    except ProviderError as exc:
        return SkillResponse(status="failure", outputs={}, error=str(exc))

    content = _build_failure_report(report, provider_response.content)
    output = SkillOutput(
        content=content,
        artifact_type="test-summary",
        model_used=provider_response.model_used,
        usage=provider_response.usage,
    )
    return SkillResponse(status="success", outputs={"summary": output})


def _parse_pytest_output(stdout: str, returncode: int) -> _TestReport:
    lines = stdout.splitlines()
    non_empty = [line for line in lines if line.strip()]
    summary_line = non_empty[-1].strip("= ").strip() if non_empty else ""

    if returncode == 0:
        return _TestReport(
            all_passed=True, summary_line=summary_line, failed_tests=(), failure_text=""
        )

    failed_tests = tuple(line.strip() for line in lines if line.startswith("FAILED "))
    failure_text = stdout[-_MAX_FAILURE_CHARS:]
    return _TestReport(
        all_passed=False,
        summary_line=summary_line,
        failed_tests=failed_tests,
        failure_text=failure_text,
    )


def _build_prompt(report: _TestReport) -> str:
    failed_list = "\n".join(report.failed_tests) or "(no FAILED lines captured)"
    return (
        "Summarize why these pytest tests failed, in a few concise sentences:\n\n"
        f"Failing tests:\n{failed_list}\n\n"
        f"Output:\n{report.failure_text}"
    )


def _build_success_report(report: _TestReport) -> str:
    return f"# Test Summary\n\nAll tests passed.\n\n## pytest Result\n\n{report.summary_line}\n"


def _build_failure_report(report: _TestReport, provider_summary: str) -> str:
    failed_list = "\n".join(f"- {name}" for name in report.failed_tests) or (
        "- (no FAILED lines captured)"
    )
    return (
        "# Test Summary\n\n"
        "## AI Summary\n\n"
        f"{provider_summary}\n\n"
        "## pytest Result\n\n"
        f"{report.summary_line}\n\n"
        "## Failing Tests\n\n"
        f"{failed_list}\n\n"
        "## Failure Output\n\n"
        f"```\n{report.failure_text}\n```\n"
    )
