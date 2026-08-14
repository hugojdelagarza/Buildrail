from pathlib import Path

import pytest

from buildrail.service import dispatch


def _init_project(tmp_path: Path, *, with_provider: bool = False) -> None:
    config = 'provider = "fake"\n' if with_provider else ""
    (tmp_path / "buildrail.toml").write_text(
        f'{config}artifact_root = "artifacts"\n', encoding="utf-8"
    )


def test_run_detail_surfaces_provider_usage_totals_when_enhanced(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")

    dispatch("POST", "/commands/project-intelligence", {"enhance": True}, tmp_path)
    _status, runs_body = dispatch("GET", "/runs", {}, tmp_path)
    run_id = runs_body["runs"][0]["run_id"]

    status, body = dispatch("GET", f"/runs/{run_id}", {}, tmp_path)

    assert status == 200
    assert body["provider_usage_totals"]["model"] == "fake-model"
    assert body["provider_usage_totals"]["provider"] == "fake"


def test_version_returns_expected_fields(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/version", {}, tmp_path)

    assert status == 200
    assert isinstance(body["buildrail_version"], str)
    assert body["api_version"] == "1"
    assert isinstance(body["python_version"], str)
    assert isinstance(body["platform"], str)


def test_version_works_without_a_configured_project(tmp_path: Path) -> None:
    status, _body = dispatch("GET", "/version", {}, tmp_path)

    assert status == 200


def test_commands_lists_all_eight_executable_commands(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/commands", {}, tmp_path)

    assert status == 200
    ids = {c["id"] for c in body["commands"]}
    assert ids == {
        "explain",
        "dependency-audit",
        "docs",
        "diagram",
        "verify",
        "test",
        "pre-commit",
        "project-intelligence",
    }
    for command in body["commands"]:
        assert command["endpoint"] == f"/commands/{command['id']}"
        assert command["method"] == "POST"
        assert isinstance(command["arguments"], list)
        assert isinstance(command["artifact_types"], list)


def test_commands_works_without_a_configured_project(tmp_path: Path) -> None:
    status, _body = dispatch("GET", "/commands", {}, tmp_path)

    assert status == 200


def test_skills_returns_all_built_in_skills_in_deterministic_order(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/skills", {}, tmp_path)

    assert status == 200
    names = [s["name"] for s in body["skills"]]
    assert names == sorted(names)
    assert "review-diff" in names
    review_diff = next(s for s in body["skills"] if s["name"] == "review-diff")
    assert review_diff["requires_provider"] is True
    assert review_diff["source"] == "built-in"
    assert review_diff["project_relative_path"] is None
    assert review_diff["inputs"] == [
        {"name": "diff", "type": "file", "required": True, "description": "Path to a unified diff."}
    ]
    assert review_diff["outputs"] == [{"name": "review", "artifact_type": "review"}]


def test_skills_works_without_a_configured_project(tmp_path: Path) -> None:
    status, _body = dispatch("GET", "/skills", {}, tmp_path)

    assert status == 200


def _write_project_skill(project_root: Path, name: str) -> None:
    skill_dir = project_root / ".buildrail" / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.yaml").write_text(
        f'name: {name}\nversion: 0.1.0\nprotocol_version: "1.0"\n'
        f'description: A test skill.\nentrypoint: "python skill.py"\ninputs: []\n'
        f"outputs:\n  - name: summary\n    artifact_type: {name}\n",
        encoding="utf-8",
    )
    (skill_dir / "skill.py").write_text("def run(request, provider):\n    pass\n", encoding="utf-8")


def test_skills_includes_project_local_skills_with_relative_path(tmp_path: Path) -> None:
    _write_project_skill(tmp_path, "my-skill")

    status, body = dispatch("GET", "/skills", {}, tmp_path)

    assert status == 200
    mine = next(s for s in body["skills"] if s["name"] == "my-skill")
    assert mine["source"] == "project-local"
    assert mine["project_relative_path"] == ".buildrail/skills/my-skill"
    assert str(tmp_path) not in mine["project_relative_path"]


def test_pipelines_returns_pre_commit_and_project_intelligence(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/pipelines", {}, tmp_path)

    assert status == 200
    names = {p["name"] for p in body["pipelines"]}
    assert names == {"pre-commit", "project-intelligence", "quality-gate"}
    pre_commit = next(p for p in body["pipelines"] if p["name"] == "pre-commit")
    step_names = [s["name"] for s in pre_commit["steps"]]
    assert step_names == ["verify-project", "review-diff"]
    assert pre_commit["steps"][0]["skippable"] is False
    assert pre_commit["steps"][1]["skippable"] is True
    assert pre_commit["steps"][1]["skip_condition"] is not None
    assert pre_commit["source"] == "built-in"
    assert pre_commit["execution_kind"] == "code"
    assert pre_commit["project_relative_path"] is None


def test_pipelines_works_without_a_configured_project(tmp_path: Path) -> None:
    status, _body = dispatch("GET", "/pipelines", {}, tmp_path)

    assert status == 200


def test_pipelines_includes_project_local_pipelines(tmp_path: Path) -> None:
    pipelines_dir = tmp_path / ".buildrail" / "pipelines"
    pipelines_dir.mkdir(parents=True)
    (pipelines_dir / "quality.yaml").write_text(
        "name: quality\nversion: 0.1.0\ndescription: x\nsteps:\n  - skill: verify-project\n",
        encoding="utf-8",
    )

    status, body = dispatch("GET", "/pipelines", {}, tmp_path)

    assert status == 200
    quality = next(p for p in body["pipelines"] if p["name"] == "quality")
    assert quality["source"] == "project-local"
    assert quality["execution_kind"] == "declarative"
    assert quality["project_relative_path"] == ".buildrail/pipelines/quality.yaml"
    assert str(tmp_path) not in quality["project_relative_path"]
    assert quality["steps"][0]["inputs"] == {}


def test_project_reports_built_in_and_project_local_extension_counts(tmp_path: Path) -> None:
    _write_project_skill(tmp_path, "my-skill")

    status, body = dispatch("GET", "/project", {}, tmp_path)

    assert status == 200
    assert body["skill_count_built_in"] == 9
    assert body["skill_count_project_local"] == 1
    assert body["skill_count"] == 10
    assert body["pipeline_count_built_in"] == 3
    assert body["pipeline_count_project_local"] == 0


def test_project_degrades_gracefully_without_config(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/project", {}, tmp_path)

    assert status == 200
    assert body["config_status"] == "missing"
    assert body["provider"] is None
    assert body["provider_ready"] is False
    assert body["recent_run_count"] == 0
    assert body["latest_run"] is None
    assert body["statistics"] is None
    assert body["skill_count"] == 9
    assert body["pipeline_count"] == 3


def test_project_reports_ok_status_with_valid_config(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("GET", "/project", {}, tmp_path)

    assert status == 200
    assert body["config_status"] == "ok"
    assert body["provider"] == "fake"
    assert body["provider_ready"] is True
    assert body["artifact_root"] == "artifacts"


def test_project_reflects_recent_runs_and_statistics(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=False)
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    dispatch("POST", "/commands/explain", {}, tmp_path)

    status, body = dispatch("GET", "/project", {}, tmp_path)

    assert status == 200
    assert body["recent_run_count"] == 1
    assert body["latest_run"]["status"] == "success"
    assert body["statistics"] is not None
    assert body["statistics"]["python_files"] == 1


def test_project_never_exposes_credentials(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("GET", "/project", {}, tmp_path)

    assert status == 200
    serialized = str(body)
    assert "ANTHROPIC_API_KEY" not in serialized
    assert "sk-ant" not in serialized


def test_config_degrades_gracefully_without_config(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert body == {
        "status": "missing",
        "configured": False,
        "provider": None,
        "anthropic_model": None,
        "artifact_root": None,
        "credential_available": False,
        "error": None,
    }


def test_config_reports_fake_provider_as_always_available(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert body["configured"] is True
    assert body["provider"] == "fake"
    assert body["credential_available"] is True


def test_config_reports_anthropic_unavailable_without_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "buildrail.toml").write_text(
        'provider = "anthropic"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )

    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert body["provider"] == "anthropic"
    assert body["credential_available"] is False


def test_config_never_returns_the_api_key(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert "credential_available" in body
    assert isinstance(body["credential_available"], bool)
    assert "api_key" not in body
    assert "credential_value" not in body
