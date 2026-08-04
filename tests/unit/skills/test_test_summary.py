import subprocess
from pathlib import Path

import pytest

from buildrail.providers import ProviderGateway
from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.errors import AuthenticationError
from buildrail.skill_protocol import RunContext, SkillRequest
from buildrail.skills import SkillRegistry

_SKILL_SOURCE = (
    Path(__file__).resolve().parents[3] / "skills" / "test-summary" / "skill.py"
).read_text(encoding="utf-8")


def _request(workdir: Path) -> SkillRequest:
    return SkillRequest(
        protocol_version="1.0",
        run_context=RunContext(run_id="20260804-000000-test", step_index=1, workdir=str(workdir)),
        inputs={},
        config={},
    )


def _completed(returncode: int, stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["pytest"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_skill_source_never_imports_a_provider_adapter_or_core_internals() -> None:
    assert "FakeProvider" not in _SKILL_SOURCE
    assert "providers.adapters" not in _SKILL_SOURCE
    assert "buildrail.core" not in _SKILL_SOURCE


def test_run_reports_success_without_calling_the_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(0, "2 passed in 0.01s\n"))
    run_test_summary = SkillRegistry().resolve("test-summary")
    gateway = ProviderGateway(FakeProvider(error=AuthenticationError("must not be called")))

    response = run_test_summary(_request(tmp_path), gateway)

    assert response.status == "success"
    output = response.outputs["summary"]
    assert "All tests passed" in output.content
    assert output.model_used is None
    assert output.usage is None


def test_run_summarizes_failures_via_the_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    stdout = (
        "F\n"
        "=================================== FAILURES ===================================\n"
        "___ test_foo ___\n"
        "assert 1 == 2\n"
        "=========================== short test summary info ============================\n"
        "FAILED tests/test_foo.py::test_foo - assert 1 == 2\n"
        "1 failed in 0.01s\n"
    )
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(1, stdout))
    run_test_summary = SkillRegistry().resolve("test-summary")
    gateway = ProviderGateway(FakeProvider())

    response = run_test_summary(_request(tmp_path), gateway)

    assert response.status == "success"
    output = response.outputs["summary"]
    assert "[fake response]" in output.content
    assert "FAILED tests/test_foo.py::test_foo" in output.content
    assert output.model_used == "fake-model"
    assert output.usage is not None


def test_run_returns_failure_when_provider_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: _completed(1, "FAILED tests/test_foo.py::test_foo - boom\n1 failed\n"),
    )
    run_test_summary = SkillRegistry().resolve("test-summary")
    gateway = ProviderGateway(FakeProvider(error=AuthenticationError("no key")))

    response = run_test_summary(_request(tmp_path), gateway)

    assert response.status == "failure"
    assert response.error == "no key"
    assert response.outputs == {}


def test_run_returns_failure_when_pytest_cannot_be_executed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("pytest not found")

    monkeypatch.setattr("subprocess.run", _raise)
    run_test_summary = SkillRegistry().resolve("test-summary")
    gateway = ProviderGateway(FakeProvider())

    response = run_test_summary(_request(tmp_path), gateway)

    assert response.status == "failure"
    assert response.error is not None
    assert "pytest not found" in response.error
    assert response.outputs == {}
