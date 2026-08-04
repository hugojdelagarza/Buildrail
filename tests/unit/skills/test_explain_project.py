import json
from pathlib import Path

from buildrail.skill_protocol import RunContext, SkillRequest
from buildrail.skills import SkillRegistry

_SKILL_SOURCE = (
    Path(__file__).resolve().parents[3] / "skills" / "explain-project" / "skill.py"
).read_text(encoding="utf-8")


def _request(inputs: dict[str, str]) -> SkillRequest:
    return SkillRequest(
        protocol_version="1.0",
        run_context=RunContext(run_id="20260804-000000-test", step_index=1, workdir="."),
        inputs=inputs,
        config={},
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_skill_source_never_imports_a_provider_adapter_or_core_internals() -> None:
    assert "import buildrail.providers" not in _SKILL_SOURCE
    assert "from buildrail.providers" not in _SKILL_SOURCE
    assert "import buildrail.core" not in _SKILL_SOURCE
    assert "from buildrail.core" not in _SKILL_SOURCE


def test_run_produces_a_markdown_summary_and_json_analysis(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "mod.py", '"""Doc."""\n\n\nclass Thing:\n    """A thing."""\n')
    run_explain = SkillRegistry().resolve("explain-project")

    response = run_explain(_request({"repository_path": str(tmp_path)}), None)

    assert response.status == "success"
    summary = response.outputs["summary"]
    assert summary.artifact_type == "architecture-summary"
    assert summary.content_type == "text/markdown"
    assert "# Architecture Summary" in summary.content
    assert "pkg.mod" in summary.content
    assert "Thing" in summary.content

    analysis_output = response.outputs["analysis"]
    assert analysis_output.content_type == "application/json"
    data = json.loads(analysis_output.content)
    assert data["repository_name"] == tmp_path.name


def test_run_never_receives_or_needs_a_provider(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "x = 1\n")
    run_explain = SkillRegistry().resolve("explain-project")

    response = run_explain(_request({"repository_path": str(tmp_path)}), None)

    assert response.status == "success"


def test_run_fails_cleanly_without_a_repository_path() -> None:
    run_explain = SkillRegistry().resolve("explain-project")

    response = run_explain(_request({}), None)

    assert response.status == "failure"
    assert response.error is not None


def test_run_fails_cleanly_for_a_missing_repository() -> None:
    run_explain = SkillRegistry().resolve("explain-project")

    response = run_explain(_request({"repository_path": "/does/not/exist"}), None)

    assert response.status == "failure"


def test_run_reuses_a_precomputed_analysis_json_without_reanalyzing(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "x = 1\n")
    run_explain = SkillRegistry().resolve("explain-project")
    first = run_explain(_request({"repository_path": str(tmp_path)}), None)
    analysis_json_path = tmp_path / "analysis.json"
    analysis_json_path.write_text(first.outputs["analysis"].content, encoding="utf-8")

    (tmp_path / "second.py").write_text("y = 2\n", encoding="utf-8")
    response = run_explain(
        _request({"repository_path": str(tmp_path), "analysis_json": str(analysis_json_path)}),
        None,
    )

    assert response.status == "success"
    assert "second" not in response.outputs["summary"].content


def test_run_includes_warnings_and_reading_order_sections(tmp_path: Path) -> None:
    _write(tmp_path / "broken.py", "def foo(:\n")
    _write(tmp_path / "main.py", "import broken\n")
    run_explain = SkillRegistry().resolve("explain-project")

    response = run_explain(_request({"repository_path": str(tmp_path)}), None)

    content = response.outputs["summary"].content
    assert "## Analysis Warnings" in content
    assert "syntax_error" in content
    assert "## Suggested Reading Order" in content


def test_run_does_not_claim_dead_code_or_design_judgments(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "x = 1\n")
    run_explain = SkillRegistry().resolve("explain-project")

    response = run_explain(_request({"repository_path": str(tmp_path)}), None)

    content = response.outputs["summary"].content.lower()
    assert "dead code" not in content
    assert "bad design" not in content
