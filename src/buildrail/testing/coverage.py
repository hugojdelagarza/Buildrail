"""Reads an already-generated Cobertura `coverage.xml`, if one exists. Never invokes
`coverage.py` or any other tool — Buildrail does not generate coverage data itself in
this milestone, it only reports what a project has already produced locally.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from buildrail.testing.models import CoverageSummary

_COVERAGE_FILENAME = "coverage.xml"


def detect_coverage(project_root: Path) -> CoverageSummary | None:
    """Return a CoverageSummary parsed from `<project_root>/coverage.xml`, or None."""
    coverage_path = project_root / _COVERAGE_FILENAME
    if not coverage_path.is_file():
        return None

    try:
        root = ET.parse(coverage_path).getroot()
    except (ET.ParseError, OSError):
        return None

    if root.tag != "coverage":
        return None

    line_rate_raw = root.get("line-rate")
    if line_rate_raw is None:
        return None
    try:
        line_rate = float(line_rate_raw)
    except ValueError:
        return None

    return CoverageSummary(
        source=_COVERAGE_FILENAME,
        line_rate=line_rate,
        lines_covered=_optional_int(root.get("lines-covered")),
        lines_valid=_optional_int(root.get("lines-valid")),
    )


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
