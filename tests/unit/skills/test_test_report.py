import json
from pathlib import Path

from buildrail.providers import ProviderGateway
from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.errors import AuthenticationError
from buildrail.skill_protocol import RunContext, SkillRequest
from buildrail.skills import SkillRegistry

_SKILL_SOURCE = (
    Path(__file__).resolve().parents[3] / "skills" / "test-report" / "skill.py"
).read_text(encoding="utf-8")


def _request(workdir: Path, inputs: dict[str, str] | None = None) -> SkillRequest:
    return SkillRequest(
        protocol_version="1.0",
        run_context=RunContext(run_id="20260804-000000-test", step_index=1, workdir=str(workdir)),
        inputs=inputs or {},
        config={},
    )


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_skill_source_never_imports_a_concrete_provider_adapter_or_core_internals() -> None:
    assert "import buildrail.providers.adapters" not in _SKILL_SOURCE
    assert "from buildrail.providers.adapters" not in _SKILL_SOURCE
    assert "import buildrail.core" not in _SKILL_SOURCE
    assert "from buildrail.core" not in _SKILL_SOURCE


def test_run_reports_success_without_analysis_by_default(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_ok():\n    assert True\n")
    run_test_report = SkillRegistry().resolve("test-report")

    response = run_test_report(_request(tmp_path), None)

    assert response.status == "success"
    report = response.outputs["report"]
    assert "PASSED" in report.content
    assert report.metadata is not None
    assert report.metadata["passed"] is True
    assert report.metadata["analysis_mode"] == "not_requested"
    assert report.usage is None
    assert report.model_used is None


def test_run_produces_both_markdown_and_json_outputs(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_ok():\n    assert True\n")
    run_test_report = SkillRegistry().resolve("test-report")

    response = run_test_report(_request(tmp_path), None)

    assert set(response.outputs) == {"report", "report_json"}
    json_output = response.outputs["report_json"]
    assert json_output.content_type == "application/json"
    data = json.loads(json_output.content)
    assert data["counts"]["passed"] == 1
    assert data["status"] == "passed"


def test_analyze_calls_provider_only_on_failure(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_x.py",
        "def test_ok():\n    assert True\n\ndef test_bad():\n    assert 1 == 2\n",
    )
    run_test_report = SkillRegistry().resolve("test-report")
    gateway = ProviderGateway(FakeProvider())

    response = run_test_report(_request(tmp_path, {"analyze": "true"}), gateway)

    report = response.outputs["report"]
    assert "[fake response]" in report.content
    assert report.metadata is not None
    assert report.metadata["analysis_mode"] == "completed"
    assert report.model_used == "fake-model"
    assert report.usage is not None


def test_analyze_never_calls_provider_when_all_pass(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_ok():\n    assert True\n")
    run_test_report = SkillRegistry().resolve("test-report")
    gateway = ProviderGateway(FakeProvider(error=AuthenticationError("must not be called")))

    response = run_test_report(_request(tmp_path, {"analyze": "true"}), gateway)

    assert response.status == "success"
    report = response.outputs["report"]
    assert report.metadata is not None
    assert report.metadata["analysis_mode"] == "skipped_all_passed"
    assert report.metadata["passed"] is True


def test_analyze_without_a_provider_does_not_fail_the_run(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_bad():\n    assert False\n")
    run_test_report = SkillRegistry().resolve("test-report")

    response = run_test_report(_request(tmp_path, {"analyze": "true"}), None)

    assert response.status == "success"
    report = response.outputs["report"]
    assert report.metadata is not None
    assert report.metadata["analysis_mode"] == "unavailable_no_provider"
    assert report.metadata["passed"] is False
    assert "no provider is configured" in report.content.lower()


def test_provider_error_during_analysis_fails_the_skill(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_bad():\n    assert False\n")
    run_test_report = SkillRegistry().resolve("test-report")
    gateway = ProviderGateway(FakeProvider(error=AuthenticationError("no key")))

    response = run_test_report(_request(tmp_path, {"analyze": "true"}), gateway)

    assert response.status == "failure"
    assert response.error == "no key"
    assert response.outputs == {}


def test_collection_error_is_reported(tmp_path: Path) -> None:
    _write(tmp_path / "test_broken.py", "import nonexistent_module_xyz\n")
    run_test_report = SkillRegistry().resolve("test-report")

    response = run_test_report(_request(tmp_path), None)

    assert response.status == "success"
    report = response.outputs["report"]
    assert report.metadata is not None
    assert report.metadata["status"] == "collection_error"
    assert report.metadata["passed"] is False
    assert "Collection Errors" in report.content


def test_history_produces_a_flaky_signal(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_bad():\n    assert False\n")
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps([{"run_id": "prior-run", "failing_node_ids": []}]), encoding="utf-8"
    )
    run_test_report = SkillRegistry().resolve("test-report")

    response = run_test_report(_request(tmp_path, {"history_json": str(history_path)}), None)

    report = response.outputs["report"]
    assert "Possible Flaky Signals" in report.content
    data = json.loads(response.outputs["report_json"].content)
    assert len(data["flaky_signals"]) == 1
    assert data["flaky_signals"][0]["node_id"] == "test_x.py::test_bad"


def test_missing_history_file_is_ignored(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_ok():\n    assert True\n")
    run_test_report = SkillRegistry().resolve("test-report")

    response = run_test_report(
        _request(tmp_path, {"history_json": str(tmp_path / "nope.json")}), None
    )

    assert response.status == "success"


def test_coverage_is_reported_when_available(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_ok():\n    assert True\n")
    _write(
        tmp_path / "coverage.xml",
        '<coverage line-rate="0.5" lines-covered="5" lines-valid="10"></coverage>',
    )
    run_test_report = SkillRegistry().resolve("test-report")

    response = run_test_report(_request(tmp_path), None)

    report = response.outputs["report"]
    assert "50.0%" in report.content
