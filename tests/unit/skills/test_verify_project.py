import subprocess
from pathlib import Path

import pytest

from buildrail.skill_protocol import RunContext, SkillRequest
from buildrail.skills import SkillRegistry

_SKILL_SOURCE = (
    Path(__file__).resolve().parents[3] / "skills" / "verify-project" / "skill.py"
).read_text(encoding="utf-8")


def _request(workdir: Path) -> SkillRequest:
    return SkillRequest(
        protocol_version="1.0",
        run_context=RunContext(run_id="20260804-000000-test", step_index=1, workdir=str(workdir)),
        inputs={},
        config={},
    )


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["cmd"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_skill_source_never_imports_a_provider_adapter_or_core_internals() -> None:
    assert "import buildrail.providers" not in _SKILL_SOURCE
    assert "from buildrail.providers" not in _SKILL_SOURCE
    assert "import buildrail.core" not in _SKILL_SOURCE
    assert "from buildrail.core" not in _SKILL_SOURCE


def test_run_reports_success_when_all_checks_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(0, "ok\n"))
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    assert response.status == "success"
    output = response.outputs["report"]
    assert output.metadata is not None
    assert output.metadata["passed"] is True
    assert output.metadata["checks_passed"] == 4
    assert output.metadata["checks_total"] == 4
    assert output.metadata["failed_check"] is None
    assert "PASSED" in output.content
    assert "ruff format --check ." in output.content
    assert "pytest -v" in output.content


def test_run_stops_after_format_check_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []

    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(args))
        if "format" in args:
            return _completed(1, stderr="would reformat main.py")
        return _completed(0)

    monkeypatch.setattr("subprocess.run", _fake_run)
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    output = response.outputs["report"]
    assert output.metadata is not None
    assert output.metadata["passed"] is False
    assert output.metadata["checks_passed"] == 0
    assert output.metadata["failed_check"] == "ruff format --check ."
    assert len(calls) == 1


def test_run_stops_after_lint_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(args))
        if "check" in args and "format" not in args:
            return _completed(1, stdout="F401 unused import")
        return _completed(0)

    monkeypatch.setattr("subprocess.run", _fake_run)
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    output = response.outputs["report"]
    assert output.metadata is not None
    assert output.metadata["checks_passed"] == 1
    assert output.metadata["failed_check"] == "ruff check ."
    assert len(calls) == 2


def test_run_stops_after_mypy_failure_before_pytest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[str, ...]] = []

    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(tuple(args))
        if "mypy" in args:
            return _completed(1, stdout="error: Incompatible types")
        return _completed(0)

    monkeypatch.setattr("subprocess.run", _fake_run)
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    output = response.outputs["report"]
    assert output.metadata is not None
    assert output.metadata["checks_passed"] == 2
    assert output.metadata["failed_check"] == "mypy"
    assert not any("pytest" in call for call in calls)


def test_run_reports_pytest_failure_as_a_failed_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "pytest" in args:
            return _completed(1, stdout="1 failed, 2 passed")
        return _completed(0)

    monkeypatch.setattr("subprocess.run", _fake_run)
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    assert response.status == "success"
    output = response.outputs["report"]
    assert output.metadata is not None
    assert output.metadata["passed"] is False
    assert output.metadata["checks_passed"] == 3
    assert output.metadata["failed_check"] == "pytest -v"
    assert "1 failed, 2 passed" in output.content


def test_run_returns_failure_when_a_command_cannot_be_launched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("ruff not found")

    monkeypatch.setattr("subprocess.run", _raise)
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    assert response.status == "failure"
    assert response.error is not None
    assert "ruff not found" in response.error
    assert response.outputs == {}


def test_run_captures_stdout_and_stderr_in_the_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "format" in args:
            return _completed(1, stdout="STDOUT-MARKER", stderr="STDERR-MARKER")
        return _completed(0)

    monkeypatch.setattr("subprocess.run", _fake_run)
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    content = response.outputs["report"].content
    assert "STDOUT-MARKER" in content
    assert "STDERR-MARKER" in content


def test_run_measures_duration_deterministically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ticks = iter([0.0, 1.5, 1.5, 3.5, 3.5, 4.0, 4.0, 4.25])
    monkeypatch.setattr("time.perf_counter", lambda: next(ticks))
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(0))
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    output = response.outputs["report"]
    assert output.metadata is not None
    assert output.metadata["duration_seconds"] == pytest.approx(1.5 + 2.0 + 0.5 + 0.25)
    assert "Duration: 1.50s" in output.content


def test_run_truncates_unreasonably_large_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    huge_output = "A" * 30_000 + "TAIL-MARKER"

    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "format" in args:
            return _completed(1, stdout=huge_output)
        return _completed(0)

    monkeypatch.setattr("subprocess.run", _fake_run)
    run_verify = SkillRegistry().resolve("verify-project")

    response = run_verify(_request(tmp_path), None)

    content = response.outputs["report"].content
    assert "TAIL-MARKER" in content
    assert "characters truncated" in content
    assert "A" * 30_000 not in content
