"""The test-summary skill: runs pytest and summarizes any failures via the Provider Gateway.

Provider-neutral — only imports buildrail.providers' public Gateway and
request/response types, never a concrete adapter. Executed in-process for
Milestone 1 (docs/skills.md's phasing note); `entrypoint` in skill.yaml
describes the eventual subprocess invocation, not what actually runs today.
The provider is only invoked when pytest reports a failure — a clean run
never spends a request.

Shares its pytest execution with the `test-report` skill via
`buildrail.testing.run_pytest` rather than parsing pytest output a second,
independent way (docs/roadmap.md Phase 7). Unlike test-report, this skill
always analyzes on failure (no `--analyze` gate) and produces a single
Markdown artifact — its original, narrower contract, preserved as-is.
"""

from pathlib import Path

from buildrail.providers import Message, ProviderError, ProviderGateway, ProviderRequest, TextPart
from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse
from buildrail.testing import TestReport, run_pytest
from buildrail.testing.models import TestFailure


def run(request: SkillRequest, provider: ProviderGateway) -> SkillResponse:
    """Run pytest in the run's working directory and summarize any failures."""
    report = run_pytest(Path(request.run_context.workdir))

    if report.status in ("unavailable", "timeout"):
        return SkillResponse(status="failure", outputs={}, error=report.stderr_excerpt)

    if report.status == "passed":
        content = _build_success_report(report)
        output = SkillOutput(content=content, artifact_type="test-summary")
        return SkillResponse(status="success", outputs={"summary": output})

    provider_request = ProviderRequest(
        messages=(Message(role="user", content=(TextPart(text=_build_prompt(report)),)),)
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


def _build_prompt(report: TestReport) -> str:
    failed_list = "\n".join(f.node_id for f in report.failures) or "(no failure detail captured)"
    return (
        "Summarize why these pytest tests failed, in a few concise sentences:\n\n"
        f"Failing tests:\n{failed_list}\n\n"
        f"Output:\n{report.stdout_excerpt}"
    )


def _build_success_report(report: TestReport) -> str:
    summary_line = _summary_line(report)
    return f"# Test Summary\n\nAll tests passed.\n\n## pytest Result\n\n{summary_line}\n"


def _build_failure_report(report: TestReport, provider_summary: str) -> str:
    failed_list = "\n".join(f"- {_failed_line(f)}" for f in report.failures) or (
        "- (no FAILED lines captured)"
    )
    summary_line = _summary_line(report)
    return (
        "# Test Summary\n\n"
        "## AI Summary\n\n"
        f"{provider_summary}\n\n"
        "## pytest Result\n\n"
        f"{summary_line}\n\n"
        "## Failing Tests\n\n"
        f"{failed_list}\n\n"
        "## Failure Output\n\n"
        f"```\n{report.stdout_excerpt[-4000:]}\n```\n"
    )


def _failed_line(failure: TestFailure) -> str:
    return f"FAILED {failure.node_id}"


def _summary_line(report: TestReport) -> str:
    lines = [line for line in report.stdout_excerpt.splitlines() if line.strip()]
    return lines[-1].strip("= ").strip() if lines else ""
