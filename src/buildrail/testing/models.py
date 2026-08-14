"""TestReport: the typed, serializable output of Buildrail's test execution layer.

Mirrors `buildrail.dependencies.models`' and `buildrail.analysis.models`' round-trip
pattern — plain dataclasses of strings/ints/floats/bools/tuples so the whole model
round-trips through `to_dict`/`test_report_from_dict` and `json.dumps` without a
custom encoder. This is the normalized payload the `test-report` skill writes as a
JSON sidecar artifact, and what the CLI, frontend, and any future CI integration
all consume instead of re-parsing pytest output.
"""

from dataclasses import dataclass
from typing import Any, Literal

SCHEMA_VERSION = "1.0"

TestStatus = Literal[
    "passed",
    "failed",
    "no_tests_collected",
    "collection_error",
    "internal_error",
    "unavailable",
    "timeout",
]

AnalysisMode = Literal[
    "not_requested",
    "skipped_all_passed",
    "completed",
    "unavailable_no_provider",
]


@dataclass(frozen=True)
class TestCounts:
    """The mutually-exclusive outcome counts pytest reports for one run."""

    total: int
    passed: int
    failed: int
    skipped: int
    xfailed: int
    xpassed: int
    errors: int


@dataclass(frozen=True)
class TestFailure:
    """One failing or errored test, with a concise, truncated excerpt."""

    node_id: str
    outcome: str  # "failed" | "error"
    message: str


@dataclass(frozen=True)
class CollectionError:
    """One error that prevented tests from even being collected (e.g. an ImportError)."""

    location: str
    message: str


@dataclass(frozen=True)
class CoverageSummary:
    """A summary read from an already-generated coverage report. Never fabricated."""

    source: str  # relative filename, e.g. "coverage.xml"
    line_rate: float  # 0.0-1.0
    lines_covered: int | None
    lines_valid: int | None


@dataclass(frozen=True)
class FlakySignal:
    """A conservative, non-certain signal that a test's outcome varies across recent runs."""

    node_id: str
    note: str


@dataclass(frozen=True)
class TestReport:
    """The normalized, deterministic-first result of running a project's test suite."""

    schema_version: str
    framework: str
    command: tuple[str, ...]
    status: TestStatus
    exit_code: int | None
    started_at: str
    duration_seconds: float
    counts: TestCounts
    failures: tuple[TestFailure, ...]
    collection_errors: tuple[CollectionError, ...]
    stdout_excerpt: str
    stderr_excerpt: str
    coverage: CoverageSummary | None
    flaky_signals: tuple[FlakySignal, ...]
    analysis_mode: AnalysisMode
    analysis_text: str | None
    analysis_model: str | None
    analysis_input_tokens: int | None
    analysis_output_tokens: int | None


def to_dict(report: TestReport) -> dict[str, Any]:
    """Convert a TestReport into a plain, JSON-serializable dict."""

    def _seq(items: tuple[Any, ...]) -> list[Any]:
        return [_value(item) for item in items]

    def _value(item: Any) -> Any:
        if hasattr(item, "__dataclass_fields__"):
            return {field: _value(getattr(item, field)) for field in item.__dataclass_fields__}
        if isinstance(item, tuple):
            return _seq(item)
        return item

    return _value(report)  # type: ignore[no-any-return]


def test_report_from_dict(data: dict[str, Any]) -> TestReport:
    """Reconstruct a TestReport from the dict produced by `to_dict`."""
    counts_data = data["counts"]
    coverage_data = data.get("coverage")
    return TestReport(
        schema_version=data["schema_version"],
        framework=data["framework"],
        command=tuple(data["command"]),
        status=data["status"],
        exit_code=data["exit_code"],
        started_at=data["started_at"],
        duration_seconds=data["duration_seconds"],
        counts=TestCounts(**counts_data),
        failures=tuple(TestFailure(**item) for item in data["failures"]),
        collection_errors=tuple(CollectionError(**item) for item in data["collection_errors"]),
        stdout_excerpt=data["stdout_excerpt"],
        stderr_excerpt=data["stderr_excerpt"],
        coverage=CoverageSummary(**coverage_data) if coverage_data is not None else None,
        flaky_signals=tuple(FlakySignal(**item) for item in data.get("flaky_signals", ())),
        analysis_mode=data["analysis_mode"],
        analysis_text=data.get("analysis_text"),
        analysis_model=data.get("analysis_model"),
        analysis_input_tokens=data.get("analysis_input_tokens"),
        analysis_output_tokens=data.get("analysis_output_tokens"),
    )
