"""Buildrail's test execution layer: runs pytest, normalizes its result, and reads
optional local history/coverage — shared by the `test-report`/`test-summary` skills,
`CoreEngine`, and (indirectly, via the JSON artifact) the frontend Testing page.
"""

from buildrail.testing.coverage import detect_coverage
from buildrail.testing.history import (
    HistoryEntry,
    flaky_signals_from_history,
    gather_recent_failure_history,
    history_from_dict,
    history_to_dict,
)
from buildrail.testing.models import (
    SCHEMA_VERSION,
    AnalysisMode,
    CollectionError,
    CoverageSummary,
    FlakySignal,
    TestCounts,
    TestFailure,
    TestReport,
    TestStatus,
    test_report_from_dict,
    to_dict,
)
from buildrail.testing.runner import run_pytest

__all__ = [
    "SCHEMA_VERSION",
    "AnalysisMode",
    "CollectionError",
    "CoverageSummary",
    "FlakySignal",
    "HistoryEntry",
    "TestCounts",
    "TestFailure",
    "TestReport",
    "TestStatus",
    "detect_coverage",
    "flaky_signals_from_history",
    "gather_recent_failure_history",
    "history_from_dict",
    "history_to_dict",
    "run_pytest",
    "test_report_from_dict",
    "to_dict",
]
