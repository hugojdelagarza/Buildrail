"""The test-report skill: runs the project's pytest suite via `buildrail.testing.run_pytest`
and produces a structured Markdown report plus a JSON sidecar.

Provider-neutral, like generate-docs — only imports buildrail.providers' public Gateway and
request/response types, never a concrete adapter, and only ever calls the provider when the
caller explicitly opts in (`inputs["analyze"] == "true"`) AND there are failures/errors to
explain. Unlike generate-docs' --enhance, requesting analysis with no provider configured is
never a skill failure — the deterministic report is always produced; only `analysis_mode`
records that analysis could not run. A clean run never spends a request, `--analyze` or not.
"""

import dataclasses
import json
from pathlib import Path

from buildrail.providers import (
    Message,
    ProviderError,
    ProviderGateway,
    ProviderRequest,
    TextPart,
    Usage,
)
from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse
from buildrail.testing import (
    TestReport,
    detect_coverage,
    flaky_signals_from_history,
    history_from_dict,
    run_pytest,
    to_dict,
)
from buildrail.testing.models import CollectionError, CoverageSummary, FlakySignal, TestFailure

_MAX_PROMPT_FAILURES = 10


def run(request: SkillRequest, provider: ProviderGateway | None) -> SkillResponse:
    """Run pytest, optionally analyze failures, and produce a test-report artifact."""
    workdir = Path(request.run_context.workdir)
    report = run_pytest(workdir)
    report = dataclasses.replace(report, coverage=detect_coverage(workdir))
    report = _apply_history(report, request.inputs.get("history_json"))

    analyze_requested = request.inputs.get("analyze") == "true"
    has_failures = report.counts.failed > 0 or report.counts.errors > 0
    if analyze_requested and has_failures:
        if provider is None:
            report = dataclasses.replace(report, analysis_mode="unavailable_no_provider")
        else:
            try:
                report = _analyze_failures(report, provider)
            except ProviderError as exc:
                return SkillResponse(status="failure", outputs={}, error=str(exc))
    elif analyze_requested:
        report = dataclasses.replace(report, analysis_mode="skipped_all_passed")

    markdown_output = SkillOutput(
        content=_build_report(report),
        artifact_type="test-report",
        display_name="test-report",
        model_used=report.analysis_model,
        usage=_usage(report),
        metadata=_metadata(report),
    )
    json_output = SkillOutput(
        content=json.dumps(to_dict(report), indent=2, sort_keys=True) + "\n",
        artifact_type="test-report",
        content_type="application/json",
        display_name="test-report-data",
    )
    return SkillResponse(
        status="success", outputs={"report": markdown_output, "report_json": json_output}
    )


def _apply_history(report: TestReport, history_json_path: str | None) -> TestReport:
    if not history_json_path:
        return report
    try:
        data = json.loads(Path(history_json_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return report
    if not isinstance(data, list):
        return report

    history = history_from_dict(data)
    current_failing = tuple(f.node_id for f in report.failures)
    signals = flaky_signals_from_history(current_failing, history)
    return dataclasses.replace(report, flaky_signals=signals)


def _usage(report: TestReport) -> Usage | None:
    if report.analysis_input_tokens is None or report.analysis_output_tokens is None:
        return None
    return Usage(
        input_tokens=report.analysis_input_tokens,
        output_tokens=report.analysis_output_tokens,
        total_tokens=report.analysis_input_tokens + report.analysis_output_tokens,
    )


def _metadata(report: TestReport) -> dict[str, object]:
    return {
        "status": report.status,
        "passed": report.status == "passed",
        "total": report.counts.total,
        "passed_count": report.counts.passed,
        "failed_count": report.counts.failed,
        "skipped_count": report.counts.skipped,
        "xfailed_count": report.counts.xfailed,
        "xpassed_count": report.counts.xpassed,
        "errors_count": report.counts.errors,
        "duration_seconds": report.duration_seconds,
        "exit_code": report.exit_code,
        "analysis_mode": report.analysis_mode,
    }


def _analyze_failures(report: TestReport, provider: ProviderGateway) -> TestReport:
    provider_request = ProviderRequest(
        messages=(Message(role="user", content=(TextPart(text=_build_prompt(report)),)),)
    )
    response = provider.complete(provider_request)
    return dataclasses.replace(
        report,
        analysis_mode="completed",
        analysis_text=response.content,
        analysis_model=response.model_used,
        analysis_input_tokens=response.usage.input_tokens,
        analysis_output_tokens=response.usage.output_tokens,
    )


def _build_prompt(report: TestReport) -> str:
    failures_text = (
        "\n\n".join(
            f"- {f.node_id} ({f.outcome}):\n{f.message}"
            for f in report.failures[:_MAX_PROMPT_FAILURES]
        )
        or "(no failure detail captured)"
    )
    return (
        "Summarize why these pytest tests failed, in a few concise sentences. "
        "Group related failures if they share a likely root cause.\n\n"
        f"Failing tests:\n{failures_text}"
    )


def _build_report(report: TestReport) -> str:
    status_word = report.status.replace("_", " ").upper()
    lines = [
        "# Test Report",
        "",
        f"**Status:** {status_word}",
        f"**Framework:** {report.framework}",
        f"**Command:** `{' '.join(report.command)}`",
        f"**Duration:** {report.duration_seconds:.2f}s",
        "",
        "## Counts",
        "",
        f"- Total: {report.counts.total}",
        f"- Passed: {report.counts.passed}",
        f"- Failed: {report.counts.failed}",
        f"- Skipped: {report.counts.skipped}",
        f"- XFailed: {report.counts.xfailed}",
        f"- XPassed: {report.counts.xpassed}",
        f"- Errors: {report.counts.errors}",
        "",
    ]
    lines.extend(_failures_section(report.failures))
    lines.extend(_collection_errors_section(report.collection_errors))
    lines.extend(_flaky_section(report.flaky_signals))
    lines.extend(_coverage_section(report.coverage))
    lines.extend(_analysis_section(report))
    lines.extend(_limitations_section())
    return "\n".join(lines).rstrip() + "\n"


def _failures_section(failures: tuple[TestFailure, ...]) -> list[str]:
    lines = ["## Failing Tests", ""]
    if not failures:
        lines.append("_None._")
        lines.append("")
        return lines
    for failure in failures:
        lines.append(f"### `{failure.node_id}` ({failure.outcome})")
        lines.append("")
        lines.append(f"```\n{failure.message}\n```")
        lines.append("")
    return lines


def _collection_errors_section(errors: tuple[CollectionError, ...]) -> list[str]:
    if not errors:
        return []
    lines = ["## Collection Errors", ""]
    for error in errors:
        lines.append(f"### `{error.location}`")
        lines.append("")
        lines.append(f"```\n{error.message}\n```")
        lines.append("")
    return lines


def _flaky_section(signals: tuple[FlakySignal, ...]) -> list[str]:
    if not signals:
        return []
    lines = ["## Possible Flaky Signals", ""]
    for signal in signals:
        lines.append(f"- `{signal.node_id}` — {signal.note}")
    lines.append("")
    return lines


def _coverage_section(coverage: CoverageSummary | None) -> list[str]:
    lines = ["## Coverage", ""]
    if coverage is None:
        lines.append("_Not available — no `coverage.xml` found at the project root._")
        lines.append("")
        return lines
    percent = coverage.line_rate * 100
    lines.append(f"- Line coverage: {percent:.1f}% (from `{coverage.source}`)")
    if coverage.lines_covered is not None and coverage.lines_valid is not None:
        lines.append(f"- Lines covered: {coverage.lines_covered}/{coverage.lines_valid}")
    lines.append("")
    return lines


def _analysis_section(report: TestReport) -> list[str]:
    lines = ["## AI Failure Analysis", ""]
    if report.analysis_mode == "not_requested":
        lines.append("_Not requested (`--analyze` was not set)._")
    elif report.analysis_mode == "skipped_all_passed":
        lines.append("_Skipped — no failures or errors to analyze._")
    elif report.analysis_mode == "unavailable_no_provider":
        lines.append("_Analysis was requested but no provider is configured. Deterministic")
        lines.append("test results above are unaffected._")
    elif report.analysis_mode == "completed":
        lines.append(report.analysis_text or "")
    lines.append("")
    return lines


def _limitations_section() -> list[str]:
    return [
        "## Limitations",
        "",
        "- AI analysis, when requested, only explains already-deterministic failures — it "
        "never changes pass/fail status.",
        "- Possible flaky signals are conservative and non-certain: a test not failing in a "
        "recent run is not proof it always passes.",
        "- Coverage is only shown when a `coverage.xml` already exists at the project root; "
        "Buildrail does not run coverage tooling itself.",
        "",
    ]
