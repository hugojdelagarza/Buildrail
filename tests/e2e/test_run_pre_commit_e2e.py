"""End-to-end test for `buildrail run pre-commit`.

Runs the real CLI against a real temporary Git repository with real (but
tiny, controlled) Python checks and FakeProvider — never this repository's
own source tree, never a live Anthropic request.
"""

import subprocess
import sys
from pathlib import Path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "buildrail", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_run_pre_commit_end_to_end_with_a_real_diff(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text('[tool.mypy]\nfiles = ["main.py"]\n', encoding="utf-8")
    (tmp_path / "main.py").write_text("x: int = 1\n", encoding="utf-8")
    (tmp_path / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "chore: initial commit")

    (tmp_path / "main.py").write_text("x: int = 1\ny: int = 2\n", encoding="utf-8")

    result = _run(["run", "pre-commit", "--base", "HEAD"], tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert "verify-project: passed" in result.stdout
    assert "review-diff: passed" in result.stdout

    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    files = {p.name for p in run_dirs[0].glob("*.md")}
    assert any("verification-report" in name for name in files)
    assert any("review" in name for name in files)

    manifest_path = run_dirs[0] / "run.json"
    assert manifest_path.is_file()
