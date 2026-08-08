from pathlib import Path

import pytest

from buildrail.service import dispatch


def _init_project(tmp_path: Path, *, with_provider: bool = False) -> None:
    config = 'provider = "fake"\n' if with_provider else ""
    (tmp_path / "buildrail.toml").write_text(
        f'{config}artifact_root = "artifacts"\n', encoding="utf-8"
    )
    (tmp_path / "main.py").write_text('"""Sample."""\n\n\ndef run():\n    pass\n', encoding="utf-8")


def test_health_returns_ok_and_a_version(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/health", {}, tmp_path)

    assert status == 200
    assert body["status"] == "ok"
    assert isinstance(body["version"], str)


def test_health_does_not_require_a_configured_project(tmp_path: Path) -> None:
    status, _body = dispatch("GET", "/health", {}, tmp_path)

    assert status == 200


def test_runs_list_is_empty_for_a_fresh_project(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("GET", "/runs", {}, tmp_path)

    assert status == 200
    assert body == {"runs": []}


def test_runs_list_fails_cleanly_when_config_missing(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/runs", {}, tmp_path)

    assert status == 500
    assert "error" in body


def test_get_run_returns_404_for_an_unknown_run(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("GET", "/runs/20260101-000000-abcdef", {}, tmp_path)

    assert status == 404
    assert "error" in body


def test_get_artifact_returns_404_for_an_unknown_artifact(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("GET", "/artifacts/20260101-000000-abcdef/001-review-x", {}, tmp_path)

    assert status == 404


def test_get_artifact_returns_400_for_an_invalid_identifier(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("GET", "/artifacts/../secret", {}, tmp_path)

    assert status == 400
    assert "error" in body


def test_unmatched_route_returns_404(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("GET", "/does-not-exist", {}, tmp_path)

    assert status == 404


def test_command_explain_writes_a_run_discoverable_via_runs_list(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/explain", {}, tmp_path)
    assert status == 200
    assert body["success"] is True
    assert "written to" in body["message"]

    runs_status, runs_body = dispatch("GET", "/runs", {}, tmp_path)
    assert runs_status == 200
    assert len(runs_body["runs"]) == 1


def test_command_explain_accepts_an_explicit_path(tmp_path: Path) -> None:
    _init_project(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    (other / "x.py").write_text("x = 1\n", encoding="utf-8")

    status, body = dispatch("POST", "/commands/explain", {"path": str(other)}, tmp_path)

    assert status == 200
    assert body["success"] is True


def test_command_docs_generate_succeeds_offline(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/docs", {}, tmp_path)

    assert status == 200
    assert body["success"] is True


def test_command_diagram_generate_succeeds_offline(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/diagram", {}, tmp_path)

    assert status == 200
    assert body["success"] is True


def test_command_verify_runs_without_a_body(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/verify", {}, tmp_path)

    assert status == 200
    assert isinstance(body["success"], bool)


def test_command_pre_commit_reports_failure_outside_a_git_repository(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/pre-commit", {}, tmp_path)

    assert status == 200
    assert body["success"] is False
    assert "Git repository" in body["message"]


def test_command_project_intelligence_succeeds_offline(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/project-intelligence", {}, tmp_path)

    assert status == 200
    assert body["success"] is True
    assert "project-intelligence" in body["message"]


def test_command_project_intelligence_enhance_fails_cleanly_without_a_provider(
    tmp_path: Path,
) -> None:
    _init_project(tmp_path, with_provider=False)

    status, body = dispatch("POST", "/commands/project-intelligence", {"enhance": True}, tmp_path)

    assert status == 200
    assert body["success"] is False
    assert "No provider configured" in body["message"]


def test_command_project_intelligence_enhance_uses_the_fake_provider(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("POST", "/commands/project-intelligence", {"enhance": True}, tmp_path)

    assert status == 200
    assert body["success"] is True


def test_unknown_command_returns_404(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/does-not-exist", {}, tmp_path)

    assert status == 404


def test_command_rejects_a_non_object_body(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/explain", None, tmp_path)

    assert status == 400
    assert "JSON object" in body["error"]


def test_command_rejects_a_non_string_path(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/explain", {"path": 123}, tmp_path)

    assert status == 400
    assert "error" in body


def test_command_rejects_a_non_boolean_enhance_flag(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("POST", "/commands/docs", {"enhance": "yes"}, tmp_path)

    assert status == 400


def test_get_run_and_get_artifact_expose_pipeline_steps_and_display_names(
    tmp_path: Path,
) -> None:
    _init_project(tmp_path)
    dispatch("POST", "/commands/project-intelligence", {}, tmp_path)
    _status, runs_body = dispatch("GET", "/runs", {}, tmp_path)
    run_id = runs_body["runs"][0]["run_id"]

    run_status, run_body = dispatch("GET", f"/runs/{run_id}", {}, tmp_path)

    assert run_status == 200
    assert run_body["pipeline"] == "project-intelligence"
    step_names = [s["name"] for s in run_body["pipeline_steps"]]
    assert step_names == ["explain-project", "generate-docs", "generate-diagram"]

    json_artifact = next(
        a for a in run_body["artifacts"] if a["content_type"] == "application/json"
    )
    artifact_status, artifact_body = dispatch(
        "GET", f"/artifacts/{json_artifact['id']}", {}, tmp_path
    )

    assert artifact_status == 200
    assert artifact_body["display_name"] == "project-analysis"
    assert isinstance(artifact_body["content_json"], dict)
    assert artifact_body["content_json"]["repository_name"] == tmp_path.name


def test_markdown_artifact_has_no_content_json(tmp_path: Path) -> None:
    _init_project(tmp_path)
    dispatch("POST", "/commands/explain", {}, tmp_path)
    _status, runs_body = dispatch("GET", "/runs", {}, tmp_path)
    run_id = runs_body["runs"][0]["run_id"]
    _run_status, run_body = dispatch("GET", f"/runs/{run_id}", {}, tmp_path)
    markdown_artifact = next(
        a for a in run_body["artifacts"] if a["content_type"] == "text/markdown"
    )

    status, body = dispatch("GET", f"/artifacts/{markdown_artifact['id']}", {}, tmp_path)

    assert status == 200
    assert body["content_json"] is None
    assert isinstance(body["content"], str)


def test_runs_list_limit_is_honored_via_query_string(tmp_path: Path) -> None:
    _init_project(tmp_path)
    dispatch("POST", "/commands/explain", {}, tmp_path)
    dispatch("POST", "/commands/explain", {}, tmp_path)

    status, body = dispatch("GET", "/runs?limit=1", {}, tmp_path)

    assert status == 200
    assert len(body["runs"]) == 1


def test_runs_list_rejects_a_non_integer_limit(tmp_path: Path) -> None:
    _init_project(tmp_path)

    status, body = dispatch("GET", "/runs?limit=abc", {}, tmp_path)

    assert status == 400


@pytest.mark.parametrize("method", ["GET", "DELETE", "PUT"])
def test_wrong_method_on_a_command_route_returns_404(tmp_path: Path, method: str) -> None:
    _init_project(tmp_path)

    status, _body = dispatch(method, "/commands/explain", {}, tmp_path)

    assert status == 404


def test_get_config_reports_missing_when_no_config_file_exists(tmp_path: Path) -> None:
    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert body["status"] == "missing"
    assert body["configured"] is False
    assert body["provider"] is None
    assert body["error"] is None


def test_get_config_reports_invalid_for_malformed_toml(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text("this is not [valid toml", encoding="utf-8")

    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert body["status"] == "invalid"
    assert body["configured"] is False
    assert isinstance(body["error"], str)


def test_get_config_reports_invalid_for_an_unsupported_provider(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "openai"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )

    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert body["status"] == "invalid"
    assert "unsupported provider" in body["error"].lower()


def test_get_config_reports_ok_for_a_valid_configured_project(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert body["status"] == "ok"
    assert body["configured"] is True
    assert body["provider"] == "fake"


def test_get_config_never_exposes_environment_variables_or_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-never-appear")
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("GET", "/config", {}, tmp_path)

    assert status == 200
    assert "sk-ant-should-never-appear" not in str(body)


def test_put_config_creates_a_config_on_a_fresh_project(tmp_path: Path) -> None:
    status, body = dispatch("PUT", "/config", {"provider": "fake"}, tmp_path)

    assert status == 200
    assert body["status"] == "ok"
    assert body["provider"] == "fake"
    assert (tmp_path / "buildrail.toml").exists()


def test_put_config_updates_an_existing_config(tmp_path: Path) -> None:
    _init_project(tmp_path, with_provider=True)

    status, body = dispatch("PUT", "/config", {"provider": "anthropic"}, tmp_path)

    assert status == 200
    assert body["provider"] == "anthropic"


def test_put_config_rejects_an_unsupported_provider(tmp_path: Path) -> None:
    status, body = dispatch("PUT", "/config", {"provider": "openai"}, tmp_path)

    assert status == 400
    assert "error" in body
    assert not (tmp_path / "buildrail.toml").exists()


def test_put_config_rejects_an_artifact_root_that_escapes_the_project(tmp_path: Path) -> None:
    status, body = dispatch("PUT", "/config", {"artifact_root": "../escape"}, tmp_path)

    assert status == 400
    assert "error" in body


def test_put_config_rejects_unknown_fields(tmp_path: Path) -> None:
    status, body = dispatch(
        "PUT", "/config", {"provider": "fake", "anthropic_api_key": "sk-ant-x"}, tmp_path
    )

    assert status == 400
    assert "anthropic_api_key" in body["error"]
    assert not (tmp_path / "buildrail.toml").exists()


def test_put_config_rejects_a_non_object_body(tmp_path: Path) -> None:
    status, body = dispatch("PUT", "/config", None, tmp_path)

    assert status == 400
    assert "JSON object" in body["error"]


def test_put_config_does_not_require_an_existing_configured_project(tmp_path: Path) -> None:
    # This is the onboarding path: no buildrail.toml exists yet at all.
    status, _body = dispatch("PUT", "/config", {"provider": "fake"}, tmp_path)

    assert status == 200


@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_wrong_method_on_the_config_route_returns_404(tmp_path: Path, method: str) -> None:
    _init_project(tmp_path)

    status, _body = dispatch(method, "/config", {}, tmp_path)

    assert status == 404
