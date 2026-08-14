import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

import buildrail.cli as cli_module
from buildrail.cli import main
from buildrail.core import Result


def test_main_prints_expected_output_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert captured.out == "Buildrail initialized.\n"
    assert exit_code == 0


def test_main_delegates_to_core_engine_and_reflects_its_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_engine = Mock()
    fake_engine.run.return_value = Result(success=False, message="fake failure")
    monkeypatch.setattr(cli_module, "CoreEngine", lambda: fake_engine)

    exit_code = main([])

    captured = capsys.readouterr()
    assert captured.out == "fake failure\n"
    assert exit_code == 1


def test_init_creates_a_minimal_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init"])

    captured = capsys.readouterr()
    assert "Created buildrail.toml" in captured.out
    assert captured.err == ""
    assert exit_code == 0
    written = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert 'provider = "fake"' in written


def test_init_accepts_an_explicit_provider(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "--provider", "anthropic"])

    assert exit_code == 0
    written = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert 'provider = "anthropic"' in written


def test_init_rejects_an_unsupported_provider_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        main(["init", "--provider", "openai"])


def test_init_fails_without_a_traceback_when_config_already_exists(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init"])

    captured = capsys.readouterr()
    assert "already exists" in captured.out
    assert captured.err == ""
    assert exit_code == 1


def test_config_validate_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["config", "validate"])

    captured = capsys.readouterr()
    assert captured.out == "Configuration is valid.\n"
    assert captured.err == ""
    assert exit_code == 0


def test_config_validate_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["config", "validate"])

    captured = capsys.readouterr()
    assert "No configuration file found" in captured.out
    assert captured.err == ""
    assert exit_code == 1


def test_provider_check_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["provider", "check"])

    captured = capsys.readouterr()
    assert "fake" in captured.out.lower()
    assert captured.err == ""
    assert exit_code == 0


def test_provider_check_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["provider", "check"])

    captured = capsys.readouterr()
    assert "No configuration file found" in captured.out
    assert captured.err == ""
    assert exit_code == 1


def test_review_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["review", "--diff", str(diff_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "fake" in captured.out.lower()


def test_review_fails_without_traceback_when_diff_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["review", "--diff", "missing.patch"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No diff file found" in captured.out


def test_test_summary_succeeds_when_tests_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout="2 passed in 0.01s\n", stderr=""
        ),
    )

    exit_code = main(["test-summary"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Test summary written to" in captured.out


def test_test_summary_succeeds_when_tests_fail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"],
            returncode=1,
            stdout="FAILED tests/test_x.py::test_y - boom\n1 failed\n",
            stderr="",
        ),
    )

    exit_code = main(["test-summary"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "fake" in captured.out.lower()


def test_test_summary_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["test-summary"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No configuration file found" in captured.out


def test_skill_list_prints_all_built_in_skills(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["skill", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "review-diff" in captured.out
    assert "test-summary" in captured.out
    assert "release-notes" in captured.out
    assert "verify-project" in captured.out


def test_skill_inspect_prints_manifest_details(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["skill", "inspect", "review-diff"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "name: review-diff" in captured.out
    assert "protocol_version: 1.0" in captured.out


def test_skill_inspect_fails_without_traceback_for_unknown_skill(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["skill", "inspect", "does-not-exist"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "does-not-exist" in captured.out


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_release_notes_succeeds_with_commits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "feat: add a feature")

    exit_code = main(["release-notes"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Release notes written to" in captured.out


def test_release_notes_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["release-notes"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No configuration file found" in captured.out


def test_verify_succeeds_when_all_checks_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["cmd"], returncode=0, stdout="", stderr=""
        ),
    )

    exit_code = main(["verify"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "PASSED" in captured.out


def test_verify_fails_with_nonzero_exit_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "format" in args:
            return subprocess.CompletedProcess(
                args=list(args), returncode=1, stdout="", stderr="would reformat"
            )
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    exit_code = main(["verify"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "FAILED" in captured.out


def test_verify_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["verify"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No configuration file found" in captured.out


def test_hooks_install_succeeds_in_a_git_repository(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["hooks", "install"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Installed" in captured.out


def test_hooks_install_fails_without_traceback_outside_a_git_repository(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["hooks", "install"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "Git repository" in captured.out


def test_hooks_status_reports_not_installed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["hooks", "status"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Not installed" in captured.out


def test_hooks_uninstall_after_install_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    main(["hooks", "install"])

    exit_code = main(["hooks", "uninstall"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Removed" in captured.out


def test_runs_list_reports_no_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["runs", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "No runs found" in captured.out


def test_runs_list_rejects_invalid_limit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["runs", "list", "--limit", "0"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "limit" in captured.out.lower()


def test_runs_inspect_and_artifacts_inspect_after_a_real_review(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    main(["review", "--diff", str(diff_path)])
    run_id = next((tmp_path / "artifacts").iterdir()).name

    exit_code = main(["runs", "inspect", run_id])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert f"run_id: {run_id}" in captured.out

    exit_code = main(["artifacts", "inspect", f"{run_id}/001-review-review"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "--- payload ---" in captured.out


def test_runs_inspect_fails_without_traceback_for_unknown_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["runs", "inspect", "20260101-000000-000000"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No run named" in captured.out


def test_artifacts_inspect_rejects_path_traversal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["artifacts", "inspect", "../secret/x"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "Invalid" in captured.out


def _mock_verify_checks_for_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock only verify-project's checks (ruff/mypy/pytest); real git calls pass through."""
    real_run = subprocess.run

    def _run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "git":
            result: subprocess.CompletedProcess[str] = real_run(args, **kwargs)  # type: ignore[call-overload]
            return result
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", _run)


def _init_precommit_repo(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "chore: initial commit")


def test_run_pre_commit_succeeds_with_diff_and_review(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _mock_verify_checks_for_cli(monkeypatch)

    exit_code = main(["run", "pre-commit", "--base", "HEAD"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "verify-project: passed" in captured.out
    assert "review-diff: passed" in captured.out


def test_run_pre_commit_skip_review_flag(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    _mock_verify_checks_for_cli(monkeypatch)

    exit_code = main(["run", "pre-commit", "--base", "HEAD", "--skip-review"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "review-diff: skipped (--skip-review was set)" in captured.out


def test_run_pre_commit_fails_without_traceback_outside_a_git_repository(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["run", "pre-commit"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "Git repository" in captured.out


def _init_python_project(tmp_path: Path, *, with_provider: bool = False) -> None:
    config = 'provider = "fake"\n' if with_provider else ""
    (tmp_path / "buildrail.toml").write_text(
        f'{config}artifact_root = "artifacts"\n', encoding="utf-8"
    )
    (tmp_path / "main.py").write_text('"""Entry."""\n\n\ndef run():\n    pass\n', encoding="utf-8")


def test_explain_writes_a_summary_and_prints_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["explain"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Architecture summary written to" in captured.out


def test_dependency_audit_writes_a_report_and_prints_success(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["dependency-audit"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Dependency audit written to" in captured.out


def test_dependency_audit_fails_without_a_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["dependency-audit"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No configuration file found" in captured.out


def test_explain_accepts_an_explicit_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    other_repo = tmp_path / "other"
    other_repo.mkdir()
    (other_repo / "main.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["explain", "--path", str(other_repo)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""


def test_docs_generate_succeeds_offline_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["docs", "generate"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Documentation written to" in captured.out


def test_docs_generate_enhance_fails_without_traceback_when_provider_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path, with_provider=False)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["docs", "generate", "--enhance"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No provider configured" in captured.out


def test_docs_generate_output_collision_fails_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    generated = tmp_path / "docs" / "generated"
    generated.mkdir(parents=True)
    (generated / "project-overview.md").write_text("existing", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["docs", "generate", "--output", "docs/generated"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""


def test_diagram_generate_succeeds_offline_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["diagram", "generate"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Diagram written to" in captured.out


def test_diagram_generate_rejects_unsupported_formats(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["diagram", "generate", "--format", "svg"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""


def test_run_project_intelligence_succeeds_and_shares_one_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["run", "project-intelligence"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Pipeline: project-intelligence" in captured.out
    assert "explain-project: passed" in captured.out
    assert "generate-docs: passed" in captured.out
    assert "generate-diagram: passed" in captured.out


def test_run_project_intelligence_enhance_uses_fake_provider(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path, with_provider=True)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["run", "project-intelligence", "--enhance"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Provider: fake/fake-model" in captured.out


def test_serve_delegates_to_the_service_module_with_parsed_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[Path, str, int]] = []

    def _fake_run(project_root: Path, *, host: str, port: int) -> int:
        calls.append((project_root, host, port))
        return 0

    monkeypatch.setattr(cli_module, "run_service", _fake_run)

    exit_code = main(["serve", "--host", "0.0.0.0", "--port", "9999"])

    assert exit_code == 0
    assert calls == [(Path.cwd(), "0.0.0.0", 9999)]


def test_serve_uses_default_host_and_port_when_not_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int]] = []

    def _fake_run(project_root: Path, *, host: str, port: int) -> int:
        calls.append((host, port))
        return 0

    monkeypatch.setattr(cli_module, "run_service", _fake_run)

    main(["serve"])

    assert calls == [("127.0.0.1", 8787)]


def test_serve_propagates_the_service_module_exit_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module, "run_service", lambda project_root, *, host, port: 1)

    exit_code = main(["serve"])

    assert exit_code == 1


# --- Project-local extensions: init, skill create, pipeline create/list/inspect, run ---


def test_init_scaffolds_project_extensions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init"])

    assert exit_code == 0
    assert (tmp_path / ".buildrail" / "skills").is_dir()
    assert (tmp_path / ".buildrail" / "pipelines").is_dir()


def test_init_extensions_flag_works_without_a_config_file(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["init", "--extensions"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "buildrail.toml" not in captured.out
    assert not (tmp_path / "buildrail.toml").exists()
    assert (tmp_path / ".buildrail" / "skills").is_dir()


def test_skill_create_scaffolds_a_project_local_skill(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["skill", "create", "api-review"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "api-review" in captured.out
    assert (tmp_path / ".buildrail" / "skills" / "api-review" / "skill.yaml").is_file()


def test_skill_create_requires_provider_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["skill", "create", "needs-ai", "--requires-provider"])

    assert exit_code == 0
    manifest = (tmp_path / ".buildrail" / "skills" / "needs-ai" / "skill.yaml").read_text(
        encoding="utf-8"
    )
    assert "requires_provider: true" in manifest


def test_skill_create_fails_cleanly_for_an_invalid_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["skill", "create", "Not Valid"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""


def test_skill_create_is_immediately_visible_to_skill_list(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["skill", "create", "api-review"])
    capsys.readouterr()

    exit_code = main(["skill", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "api-review" in captured.out
    assert "[project-local]" in captured.out


def test_skill_inspect_shows_a_project_relative_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["skill", "create", "api-review"])
    capsys.readouterr()

    exit_code = main(["skill", "inspect", "api-review"])

    captured = capsys.readouterr()
    assert exit_code == 0
    normalized = captured.out.replace("\\", "/")
    assert ".buildrail/skills/api-review" in normalized
    assert str(tmp_path) not in captured.out


def test_pipeline_create_scaffolds_a_project_local_pipeline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["pipeline", "create", "quality"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "quality" in captured.out
    assert (tmp_path / ".buildrail" / "pipelines" / "quality.yaml").is_file()


def test_pipeline_create_fails_cleanly_for_an_invalid_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["pipeline", "create", "Not Valid"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""


def test_pipeline_list_shows_built_ins_and_project_local(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    main(["pipeline", "create", "quality"])
    capsys.readouterr()

    exit_code = main(["pipeline", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "pre-commit" in captured.out
    assert "project-intelligence" in captured.out
    assert "quality" in captured.out
    assert "[project-local]" in captured.out


def test_pipeline_inspect_shows_steps(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["pipeline", "inspect", "pre-commit"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "verify-project" in captured.out
    assert "review-diff" in captured.out


def test_pipeline_list_fails_cleanly_without_a_traceback_for_a_malformed_manifest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    pipelines_dir = tmp_path / ".buildrail" / "pipelines"
    pipelines_dir.mkdir(parents=True)
    (pipelines_dir / "broken.yaml").write_text("name: [unclosed\n", encoding="utf-8")

    exit_code = main(["pipeline", "list"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "broken.yaml" in captured.out


def test_run_generic_dispatches_project_local_pipelines_through_the_registry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".buildrail" / "pipelines").mkdir(parents=True)
    (tmp_path / ".buildrail" / "pipelines" / "quality.yaml").write_text(
        "name: quality\nversion: 0.1.0\ndescription: x\nsteps:\n  - skill: verify-project\n",
        encoding="utf-8",
    )
    _mock_verify_checks_for_cli(monkeypatch)

    exit_code = main(["run", "quality"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Pipeline: quality" in captured.out


def test_run_unknown_pipeline_name_fails_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _init_python_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["run", "nonexistent-pipeline"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "nonexistent-pipeline" in captured.out
