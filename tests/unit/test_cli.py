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
