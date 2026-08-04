"""End-to-end test for `buildrail verify`.

Runs the real ruff/mypy/pytest checks (not mocked) against a deliberately
tiny, self-contained temporary project — never against this repository's
own (large, slow) source tree — so the run stays fast and deterministic
while still exercising the real subprocess-spawning code path.
"""

import subprocess
import sys
from pathlib import Path


def test_verify_succeeds_end_to_end_on_a_minimal_project(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.mypy]\nfiles = ["main.py"]\n', encoding="utf-8")
    (tmp_path / "main.py").write_text("x: int = 1\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "buildrail", "verify"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert "PASSED" in result.stdout
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    report_files = list(run_dirs[0].glob("001-verification-report-*.md"))
    assert len(report_files) == 1
    content = report_files[0].read_text(encoding="utf-8")
    assert "**Status:** PASSED" in content
    assert "ruff format --check ." in content
    assert "pytest -v" in content
