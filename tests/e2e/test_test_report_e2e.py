"""End-to-end tests for `buildrail test` — real CLI subprocess, real pytest execution
against a temporary project, real (Fake) provider only when explicitly requested.
"""

import subprocess
import sys
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "buildrail", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _init_project(tmp_path: Path, *, provider: str | None = "fake") -> None:
    config = f'provider = "{provider}"\n' if provider else ""
    (tmp_path / "buildrail.toml").write_text(
        f'{config}artifact_root = "artifacts"\n', encoding="utf-8"
    )


def test_test_command_succeeds_end_to_end_when_tests_pass(tmp_path: Path) -> None:
    _init_project(tmp_path)
    (tmp_path / "test_sample.py").write_text(
        "def test_always_passes():\n    assert True\n", encoding="utf-8"
    )

    result = _run(["test"], tmp_path)

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Tests PASSED" in result.stdout

    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "001-test-report-report.md").is_file()
    assert (run_dirs[0] / "001-test-report-report_json.json").is_file()


def test_test_command_exits_nonzero_end_to_end_when_a_test_fails(tmp_path: Path) -> None:
    _init_project(tmp_path)
    (tmp_path / "test_sample.py").write_text(
        "def test_fails():\n    assert False\n", encoding="utf-8"
    )

    result = _run(["test"], tmp_path)

    assert result.returncode == 1
    assert result.stderr == ""
    assert "Tests FAILED" in result.stdout


def test_test_command_analyze_with_fake_provider_end_to_end(tmp_path: Path) -> None:
    _init_project(tmp_path)
    (tmp_path / "test_sample.py").write_text(
        "def test_fails():\n    assert False\n", encoding="utf-8"
    )

    result = _run(["test", "--analyze"], tmp_path)

    assert result.returncode == 1
    assert "AI failure analysis included" in result.stdout
    run_dirs = list((tmp_path / "artifacts").iterdir())
    content = (run_dirs[0] / "001-test-report-report.md").read_text(encoding="utf-8")
    assert "[fake response]" in content


def test_test_command_analyze_without_provider_never_calls_a_real_api(tmp_path: Path) -> None:
    _init_project(tmp_path, provider=None)
    (tmp_path / "test_sample.py").write_text(
        "def test_fails():\n    assert False\n", encoding="utf-8"
    )

    result = _run(["test", "--analyze"], tmp_path)

    # Reflects the actual test result, not analysis availability.
    assert result.returncode == 1
    assert "no provider is configured" in result.stdout.lower()


def test_test_command_artifacts_are_inspectable(tmp_path: Path) -> None:
    _init_project(tmp_path)
    (tmp_path / "test_sample.py").write_text(
        "def test_always_passes():\n    assert True\n", encoding="utf-8"
    )
    _run(["test"], tmp_path)
    run_id = next((tmp_path / "artifacts").iterdir()).name

    runs_result = _run(["runs", "inspect", run_id], tmp_path)
    assert runs_result.returncode == 0
    assert "type: test-report" in runs_result.stdout

    artifact_result = _run(
        ["artifacts", "inspect", f"{run_id}/001-test-report-report_json"], tmp_path
    )
    assert artifact_result.returncode == 0
    assert "content_type: application/json" in artifact_result.stdout


def test_test_summary_still_works_alongside_the_new_test_command(tmp_path: Path) -> None:
    _init_project(tmp_path)
    (tmp_path / "test_sample.py").write_text(
        "def test_always_passes():\n    assert True\n", encoding="utf-8"
    )

    test_result = _run(["test"], tmp_path)
    summary_result = _run(["test-summary"], tmp_path)

    assert test_result.returncode == 0
    assert summary_result.returncode == 0
    assert "Test summary written to" in summary_result.stdout


def test_quality_gate_pipeline_end_to_end(tmp_path: Path) -> None:
    _init_project(tmp_path, provider=None)
    (tmp_path / "test_sample.py").write_text(
        "def test_always_passes():\n    assert True\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        "[tool.ruff]\nline-length = 100\n[tool.mypy]\nignore_missing_imports = true\n",
        encoding="utf-8",
    )

    result = _run(["run", "quality-gate"], tmp_path)

    assert result.returncode in (0, 1)  # verify-project's own checks may reasonably fail here
    assert "Pipeline: quality-gate" in result.stdout
    assert "verify-project:" in result.stdout
