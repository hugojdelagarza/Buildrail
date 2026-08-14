"""The pytest execution layer: runs pytest through argument sequences (never `shell=True`,
never an arbitrary shell string) and normalizes its result into a `TestReport`.

**Structured output, without a new dependency — the tradeoff, made explicit.** pytest ships
two machine-readable options out of the box: JUnit XML (`--junitxml`) and its own one-line
final summary (e.g. "3 passed, 1 failed, 1 skipped, 1 xfailed in 0.12s"). Neither alone is
enough: JUnit XML folds `xfail` into `skipped` and (in the common, non-strict case) folds
`xpass` into a plain passing testcase, so `xfailed`/`xpassed` can't be recovered from the XML
alone; the summary line has no per-test detail (node ids, failure text). We combine both —
JUnit XML for failing/errored test node ids and truncated failure text, the summary line
(parsed with one small, fixed-vocabulary regex over `\\d+ <category>` tokens, not "colorful"
terminal output — subprocess capture always disables color, and this is pytest's own stable,
documented summary format) for the authoritative pass/fail/skip/xfail/xpass/error counts. A
plugin such as `pytest-json-report` would give one fully structured source instead of two, at
the cost of a new dependency for every project that runs `buildrail test` — not justified for
a count breakdown this cheap to parse deterministically.

Never runs a real subprocess with `shell=True`, never interpolates user-controlled strings
into a shell command, and never runs anything outside the requested `workdir`.
"""

import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from buildrail.artifacts.ids import Clock, SystemClock
from buildrail.testing.models import (
    SCHEMA_VERSION,
    CollectionError,
    TestCounts,
    TestFailure,
    TestReport,
    TestStatus,
)

_DEFAULT_TIMEOUT_SECONDS = 300.0
_MAX_STDOUT_CHARS = 8_000
_MAX_STDERR_CHARS = 4_000
_MAX_FAILURE_MESSAGE_CHARS = 2_000
_MAX_FAILURES_LISTED = 50

_SUMMARY_TOKEN_RE = re.compile(
    r"(\d+)\s+(passed|failed|skipped|xfailed|xpassed|error|errors|warnings|deselected)\b"
)
_SUMMARY_CATEGORY_ALIASES = {"error": "errors", "errors": "errors"}
_IGNORED_SUMMARY_CATEGORIES = {"warnings", "deselected"}

_BASE_COMMAND: tuple[str, ...] = (sys.executable, "-m", "pytest", "-q", "--tb=short")


def run_pytest(
    workdir: Path, *, timeout: float = _DEFAULT_TIMEOUT_SECONDS, clock: Clock | None = None
) -> TestReport:
    """Run pytest in `workdir` and return a normalized, deterministic TestReport.

    Never raises for an expected failure mode (test failures, collection errors,
    a timeout, a missing pytest install) — each becomes a distinct `status`.
    `coverage`, `flaky_signals`, and the AI-analysis fields are always empty/
    "not_requested" here; callers that want them fill them in afterward with
    `dataclasses.replace`, since this function only ever runs pytest.
    """
    active_clock = clock or SystemClock()
    started_at = active_clock.utcnow().isoformat()

    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="buildrail-test-") as tmp_dir:
        junit_path = Path(tmp_dir) / "junit.xml"
        full_command = (*_BASE_COMMAND, f"--junitxml={junit_path}")

        try:
            completed = subprocess.run(
                full_command, cwd=workdir, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            duration = time.perf_counter() - start
            return _placeholder_report(
                status="timeout",
                exit_code=None,
                started_at=started_at,
                duration_seconds=duration,
                stderr_excerpt=f"pytest did not finish within {timeout:.0f}s.",
            )
        except OSError as exc:
            duration = time.perf_counter() - start
            return _placeholder_report(
                status="unavailable",
                exit_code=None,
                started_at=started_at,
                duration_seconds=duration,
                stderr_excerpt=f"Could not run pytest: {exc}",
            )

        duration = time.perf_counter() - start

        if _looks_like_missing_pytest(completed.returncode, completed.stderr):
            return _placeholder_report(
                status="unavailable",
                exit_code=completed.returncode,
                started_at=started_at,
                duration_seconds=duration,
                stderr_excerpt=_truncate(
                    completed.stderr.strip() or "pytest is not available.", _MAX_STDERR_CHARS
                ),
            )

        summary_counts = _parse_summary_counts(completed.stdout)
        failures, collection_errors = _parse_junit(junit_path) if junit_path.is_file() else ([], [])

    counts = TestCounts(
        total=sum(
            summary_counts.get(key, 0)
            for key in ("passed", "failed", "skipped", "xfailed", "xpassed", "errors")
        ),
        passed=summary_counts.get("passed", 0),
        failed=summary_counts.get("failed", 0),
        skipped=summary_counts.get("skipped", 0),
        xfailed=summary_counts.get("xfailed", 0),
        xpassed=summary_counts.get("xpassed", 0),
        errors=summary_counts.get("errors", 0),
    )

    return TestReport(
        schema_version=SCHEMA_VERSION,
        framework="pytest",
        command=_BASE_COMMAND,
        status=_status_from_exit_code(completed.returncode),
        exit_code=completed.returncode,
        started_at=started_at,
        duration_seconds=duration,
        counts=counts,
        failures=tuple(failures[:_MAX_FAILURES_LISTED]),
        collection_errors=tuple(collection_errors),
        stdout_excerpt=_truncate(completed.stdout, _MAX_STDOUT_CHARS),
        stderr_excerpt=_truncate(completed.stderr, _MAX_STDERR_CHARS),
        coverage=None,
        flaky_signals=(),
        analysis_mode="not_requested",
        analysis_text=None,
        analysis_model=None,
        analysis_input_tokens=None,
        analysis_output_tokens=None,
    )


def _placeholder_report(
    *,
    status: TestStatus,
    exit_code: int | None,
    started_at: str,
    duration_seconds: float,
    stderr_excerpt: str,
) -> TestReport:
    zero_counts = TestCounts(total=0, passed=0, failed=0, skipped=0, xfailed=0, xpassed=0, errors=0)
    return TestReport(
        schema_version=SCHEMA_VERSION,
        framework="pytest",
        command=_BASE_COMMAND,
        status=status,
        exit_code=exit_code,
        started_at=started_at,
        duration_seconds=duration_seconds,
        counts=zero_counts,
        failures=(),
        collection_errors=(),
        stdout_excerpt="",
        stderr_excerpt=stderr_excerpt,
        coverage=None,
        flaky_signals=(),
        analysis_mode="not_requested",
        analysis_text=None,
        analysis_model=None,
        analysis_input_tokens=None,
        analysis_output_tokens=None,
    )


def _looks_like_missing_pytest(returncode: int, stderr: str) -> bool:
    if returncode == 0:
        return False
    lowered = stderr.lower()
    return "no module named" in lowered and "pytest" in lowered


def _status_from_exit_code(returncode: int) -> TestStatus:
    if returncode == 0:
        return "passed"
    if returncode == 1:
        return "failed"
    if returncode == 2:
        return "collection_error"
    if returncode == 5:
        return "no_tests_collected"
    return "internal_error"  # 3 (internal error), 4 (usage error), or anything unexpected


def _parse_summary_counts(stdout: str) -> dict[str, int]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return {}
    summary_line = lines[-1]
    counts: dict[str, int] = {}
    for match in _SUMMARY_TOKEN_RE.finditer(summary_line):
        category = _SUMMARY_CATEGORY_ALIASES.get(match.group(2), match.group(2))
        if category in _IGNORED_SUMMARY_CATEGORIES:
            continue
        counts[category] = counts.get(category, 0) + int(match.group(1))
    return counts


def _parse_junit(path: Path) -> tuple[list[TestFailure], list[CollectionError]]:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return [], []

    if root.tag == "testsuites":
        suites = list(root.findall("testsuite"))
    elif root.tag == "testsuite":
        suites = [root]
    else:
        suites = []

    failures: list[TestFailure] = []
    collection_errors: list[CollectionError] = []
    for suite in suites:
        for testcase in suite.findall("testcase"):
            classname = testcase.get("classname", "")
            name = testcase.get("name", "")
            node_id = _node_id(classname, name)

            failure_el = testcase.find("failure")
            if failure_el is not None:
                message = _truncate(
                    (failure_el.text or failure_el.get("message") or "").strip(),
                    _MAX_FAILURE_MESSAGE_CHARS,
                )
                failures.append(TestFailure(node_id=node_id, outcome="failed", message=message))
                continue

            error_el = testcase.find("error")
            if error_el is not None:
                raw_message = (error_el.text or error_el.get("message") or "").strip()
                message = _truncate(raw_message, _MAX_FAILURE_MESSAGE_CHARS)
                failures.append(TestFailure(node_id=node_id, outcome="error", message=message))
                collection_errors.append(CollectionError(location=node_id, message=message))

    return failures, collection_errors


def _node_id(classname: str, name: str) -> str:
    """Best-effort reconstruction of pytest's own `path.py::name` node id from JUnit XML's
    `classname` (which JUnit XML gives as a dotted module path, not a file path — pytest's
    JUnit writer doesn't include the file extension). Plain-function tests (this project's
    own convention, per docs/testing.md) round-trip exactly; a `unittest.TestCase` subclass
    would render its class name as a path segment rather than `::ClassName`, which is a
    known, accepted limitation rather than something worth a parsing heuristic here.
    """
    if not classname:
        return name
    return f"{classname.replace('.', '/')}.py::{name}"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"...[{omitted} characters truncated]...\n{text[-limit:]}"
