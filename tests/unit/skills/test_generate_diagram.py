from pathlib import Path

from buildrail.skill_protocol import RunContext, SkillRequest
from buildrail.skills import SkillRegistry

_SKILL_SOURCE = (
    Path(__file__).resolve().parents[3] / "skills" / "generate-diagram" / "skill.py"
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
    assert "subprocess" not in _SKILL_SOURCE


def test_run_produces_a_valid_mermaid_module_dependency_diagram(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", "from pkg.b import x\n")
    _write(tmp_path / "pkg" / "b.py", "x = 1\n")
    run_diagram = SkillRegistry().resolve("generate-diagram")

    response = run_diagram(_request({"repository_path": str(tmp_path)}), None)

    assert response.status == "success"
    content = response.outputs["diagrams"].content
    assert "```mermaid" in content
    assert "graph TD" in content
    assert "m_pkg_a" in content
    assert "m_pkg_b" in content
    assert "m_pkg_a --> m_pkg_b" in content


def test_node_ids_are_stable_across_runs(tmp_path: Path) -> None:
    _write(tmp_path / "mod.py", "x = 1\n")
    run_diagram = SkillRegistry().resolve("generate-diagram")

    first = run_diagram(_request({"repository_path": str(tmp_path)}), None)
    second = run_diagram(_request({"repository_path": str(tmp_path)}), None)

    assert first.outputs["diagrams"].content == second.outputs["diagrams"].content


def test_labels_are_escaped_for_special_characters(tmp_path: Path) -> None:
    _write(
        tmp_path / "skills" / "weird-skill" / "skill.yaml",
        "name: 'weird\"skill'\n"
        "version: 0.1.0\n"
        "requires_provider: false\n"
        "outputs:\n"
        "  - name: out\n"
        "    artifact_type: weird-artifact\n",
    )
    run_diagram = SkillRegistry().resolve("generate-diagram")

    response = run_diagram(_request({"repository_path": str(tmp_path)}), None)

    content = response.outputs["diagrams"].content
    # The label's embedded double quote must be replaced so it never breaks
    # out of the mermaid `["..."]` node syntax.
    assert '["skill: weird\'skill"]' in content
    assert content.count('"') % 2 == 0


def test_module_graph_groups_by_package_when_over_the_node_limit(tmp_path: Path) -> None:
    for i in range(45):
        _write(tmp_path / f"mod_{i}.py", "x = 1\n")
    run_diagram = SkillRegistry().resolve("generate-diagram")

    response = run_diagram(_request({"repository_path": str(tmp_path)}), None)

    content = response.outputs["diagrams"].content
    assert "exceed the" in content
    assert "grouped by top-level package" in content
    assert "mod_0" not in content


def test_buildrail_runtime_diagram_appears_only_when_skills_or_pipelines_exist(
    tmp_path: Path,
) -> None:
    run_diagram = SkillRegistry().resolve("generate-diagram")
    _write(tmp_path / "main.py", "x = 1\n")

    response_without = run_diagram(_request({"repository_path": str(tmp_path)}), None)
    assert "Buildrail Runtime" not in response_without.outputs["diagrams"].content

    _write(
        tmp_path / "skills" / "my-skill" / "skill.yaml",
        "name: my-skill\nversion: 0.1.0\nrequires_provider: false\n"
        "outputs:\n  - name: out\n    artifact_type: my-artifact\n",
    )
    response_with = run_diagram(_request({"repository_path": str(tmp_path)}), None)
    content = response_with.outputs["diagrams"].content
    assert "Buildrail Runtime" in content
    assert "Skill to Artifact" in content
    assert "my-skill" in content
    assert "my-artifact" in content


def test_run_rejects_unsupported_formats(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "x = 1\n")
    run_diagram = SkillRegistry().resolve("generate-diagram")

    response = run_diagram(_request({"repository_path": str(tmp_path), "format": "svg"}), None)

    assert response.status == "failure"
    assert "svg" in (response.error or "")


def test_run_makes_no_network_calls_and_never_executes_mermaid(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "x = 1\n")
    run_diagram = SkillRegistry().resolve("generate-diagram")

    response = run_diagram(_request({"repository_path": str(tmp_path)}), None)

    assert response.status == "success"
    assert "exec(" not in _SKILL_SOURCE
    assert "eval(" not in _SKILL_SOURCE


def test_run_fails_cleanly_without_a_repository_path() -> None:
    run_diagram = SkillRegistry().resolve("generate-diagram")

    response = run_diagram(_request({}), None)

    assert response.status == "failure"
