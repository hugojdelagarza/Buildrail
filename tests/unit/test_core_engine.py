import json
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

import pytest

from buildrail.artifacts import ArtifactReference
from buildrail.core import CoreEngine, Result
from buildrail.pipeline import PipelineContext, PipelineResult, PipelineStepResult
from buildrail.skill_protocol import SkillOutput, SkillResponse


def test_run_returns_a_successful_placeholder_result() -> None:
    engine = CoreEngine()

    result = engine.run()

    assert isinstance(result, Result)
    assert result.success is True
    assert result.message == "Buildrail initialized."


def test_validate_config_returns_success_result(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.validate_config(tmp_path)

    assert result.success is True
    assert result.message == "Configuration is valid."


def test_validate_config_returns_failure_result_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.validate_config(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_init_config_creates_a_minimal_config_file(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.init_config(tmp_path)

    assert result.success is True
    written = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert 'provider = "fake"' in written
    assert 'artifact_root = "artifacts"' in written


def test_init_config_defaults_to_the_fake_provider(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.init_config(tmp_path)

    assert result.success is True
    assert "provider='fake'" in result.message


def test_init_config_accepts_an_explicit_provider(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.init_config(tmp_path, provider="anthropic")

    assert result.success is True
    written = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert 'provider = "anthropic"' in written


def test_init_config_refuses_to_overwrite_an_existing_config(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "anthropic"\nartifact_root = "custom"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.init_config(tmp_path)

    assert result.success is False
    assert "already exists" in result.message
    # The existing file must be untouched, not silently reset to defaults.
    assert (tmp_path / "buildrail.toml").read_text(encoding="utf-8") == (
        'provider = "anthropic"\nartifact_root = "custom"\n'
    )


def test_init_config_rejects_an_unsupported_provider(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.init_config(tmp_path, provider="openai")

    assert result.success is False
    assert "unsupported provider" in result.message.lower()
    assert not (tmp_path / "buildrail.toml").exists()


def test_update_config_creates_a_config_when_none_exists(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.update_config(tmp_path, {"provider": "fake"})

    assert result.success is True
    written = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert 'provider = "fake"' in written
    assert 'artifact_root = "artifacts"' in written


def test_update_config_partially_updates_an_existing_config(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.update_config(tmp_path, {"provider": "anthropic"})

    assert result.success is True
    written = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert 'provider = "anthropic"' in written
    # artifact_root was not part of the update and must be preserved.
    assert 'artifact_root = "artifacts"' in written


def test_update_config_rejects_an_unsupported_provider(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.update_config(tmp_path, {"provider": "openai"})

    assert result.success is False
    assert "unsupported provider" in result.message.lower()
    assert not (tmp_path / "buildrail.toml").exists()


def test_update_config_rejects_an_artifact_root_that_escapes_the_project(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.update_config(tmp_path, {"artifact_root": "../../etc"})

    assert result.success is False
    assert "within the project" in result.message
    assert not (tmp_path / "buildrail.toml").exists()


def test_update_config_rejects_an_absolute_artifact_root(tmp_path: Path) -> None:
    engine = CoreEngine()
    escape_target = str(tmp_path.parent)

    result = engine.update_config(tmp_path, {"artifact_root": escape_target})

    assert result.success is False
    assert "within the project" in result.message


def test_update_config_rejects_unknown_fields(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.update_config(tmp_path, {"provider": "fake", "anthropic_api_key": "sk-ant-x"})

    assert result.success is False
    assert "anthropic_api_key" in result.message
    assert not (tmp_path / "buildrail.toml").exists()


def test_update_config_never_writes_a_rejected_api_key_field(tmp_path: Path) -> None:
    engine = CoreEngine()

    engine.update_config(tmp_path, {"api_key": "sk-ant-super-secret"})

    assert not (tmp_path / "buildrail.toml").exists()


def test_update_config_cannot_inject_extra_toml_via_artifact_root(tmp_path: Path) -> None:
    engine = CoreEngine()
    malicious = 'artifacts"\nprovider = "anthropic'

    result = engine.update_config(tmp_path, {"provider": "fake", "artifact_root": malicious})

    assert result.success is True
    from buildrail.config import load_config

    reloaded = load_config(tmp_path)
    # The injected text must round-trip as inert string content, not as a
    # second `provider` key that would silently switch providers.
    assert reloaded.provider == "fake"
    assert reloaded.artifact_root == malicious


def test_update_config_sets_anthropic_model(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.update_config(
        tmp_path, {"provider": "anthropic", "anthropic_model": "claude-opus-5"}
    )

    assert result.success is True
    written = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert 'anthropic_model = "claude-opus-5"' in written


def test_check_provider_returns_success_result_for_fake_provider(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.check_provider(tmp_path)

    assert result.success is True
    assert "fake" in result.message.lower()


def test_check_provider_returns_failure_result_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.check_provider(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_review_returns_failure_when_diff_file_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.review(tmp_path, tmp_path / "missing.patch")

    assert result.success is False
    assert "No diff file found" in result.message


def test_review_returns_failure_when_config_missing(tmp_path: Path) -> None:
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    engine = CoreEngine()

    result = engine.review(tmp_path, diff_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_review_writes_artifact_and_succeeds_with_fake_provider(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    engine = CoreEngine()

    result = engine.review(tmp_path, diff_path)

    assert result.success is True
    assert "fake" in result.message.lower()

    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    review_files = list(run_dirs[0].glob("001-review-*.md"))
    assert len(review_files) == 1
    meta_files = list(run_dirs[0].glob("001-review-*.meta.json"))
    assert len(meta_files) == 1
    assert (run_dirs[0] / "run.json").is_file()


def test_review_delegates_to_the_pipeline_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    captured_contexts: list[PipelineContext] = []

    class _StubPipelineRunner:
        def __init__(self, gateway: object, store: object) -> None:
            del gateway, store

        def run(self, context: PipelineContext) -> PipelineResult:
            captured_contexts.append(context)
            output = SkillOutput(content="stub review", artifact_type="review")
            reference = ArtifactReference(
                id="stub-id",
                run_id=context.run_id,
                content_path=tmp_path / "stub.md",
                metadata_path=tmp_path / "stub.meta.json",
            )
            response = SkillResponse(status="success", outputs={"review": output})
            return PipelineResult(
                success=True,
                steps=(
                    PipelineStepResult(
                        skill="review-diff", response=response, artifacts=(reference,)
                    ),
                ),
            )

    monkeypatch.setattr("buildrail.core.engine.PipelineRunner", _StubPipelineRunner)
    engine = CoreEngine()

    result = engine.review(tmp_path, diff_path)

    assert result.success is True
    assert "stub.md" in result.message
    assert len(captured_contexts) == 1
    assert captured_contexts[0].inputs == {"diff": str(diff_path.resolve())}
    assert captured_contexts[0].provider_name == "fake"


def _completed(returncode: int, stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["pytest"], returncode=returncode, stdout=stdout, stderr=""
    )


def test_test_summary_returns_failure_result_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.test_summary(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_test_summary_writes_artifact_when_tests_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(0, "3 passed in 0.02s\n"))
    engine = CoreEngine()

    result = engine.test_summary(tmp_path)

    assert result.success is True
    assert "Test summary written to" in result.message
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    summary_files = list(run_dirs[0].glob("001-test-summary-*.md"))
    assert len(summary_files) == 1
    assert "All tests passed" in summary_files[0].read_text(encoding="utf-8")


def test_test_summary_summarizes_failures_with_fake_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    stdout = "F\nshort test summary info\nFAILED tests/test_x.py::test_y - assert False\n1 failed\n"
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(1, stdout))
    engine = CoreEngine()

    result = engine.test_summary(tmp_path)

    assert result.success is True
    assert "fake" in result.message.lower()
    run_dirs = list((tmp_path / "artifacts").iterdir())
    content = list(run_dirs[0].glob("001-test-summary-*.md"))[0].read_text(encoding="utf-8")
    assert "[fake response]" in content
    assert "FAILED tests/test_x.py::test_y" in content


def test_list_skills_includes_both_built_in_skills() -> None:
    engine = CoreEngine()

    result = engine.list_skills()

    assert result.success is True
    assert "review-diff" in result.message
    assert "test-summary" in result.message


def test_inspect_skill_returns_manifest_details_for_review_diff() -> None:
    engine = CoreEngine()

    result = engine.inspect_skill("review-diff")

    assert result.success is True
    assert "name: review-diff" in result.message
    assert "protocol_version: 1.0" in result.message


def test_inspect_skill_fails_without_traceback_for_unknown_skill() -> None:
    engine = CoreEngine()

    result = engine.inspect_skill("does-not-exist")

    assert result.success is False
    assert "does-not-exist" in result.message


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo_with_commits(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "chore: initial commit")
    _git(repo, "tag", "v0.1.0")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "-q", "-m", "feat: add a feature")


def test_release_notes_returns_failure_result_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.release_notes(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_release_notes_writes_artifact_with_fake_provider(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    _init_repo_with_commits(tmp_path)
    engine = CoreEngine()

    result = engine.release_notes(tmp_path)

    assert result.success is True
    assert "Release notes written to" in result.message
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    notes_files = list(run_dirs[0].glob("001-release-notes-*.md"))
    assert len(notes_files) == 1
    content = notes_files[0].read_text(encoding="utf-8")
    assert "add a feature" in content


def test_release_notes_returns_failure_when_not_a_git_repository(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.release_notes(tmp_path)

    assert result.success is False


def test_verify_project_returns_failure_result_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.verify_project(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_verify_project_succeeds_when_all_checks_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(0, "ok\n"))
    engine = CoreEngine()

    result = engine.verify_project(tmp_path)

    assert result.success is True
    assert "PASSED" in result.message
    assert "4/4 checks passed" in result.message
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    report_files = list(run_dirs[0].glob("001-verification-report-*.md"))
    assert len(report_files) == 1


def test_verify_project_fails_when_a_check_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")

    def _fake_run(args: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "mypy" in args:
            return _completed(1, "error: bad type")
        return _completed(0, "")

    monkeypatch.setattr("subprocess.run", _fake_run)
    engine = CoreEngine()

    result = engine.verify_project(tmp_path)

    assert result.success is False
    assert "FAILED" in result.message
    assert "mypy" in result.message
    run_dirs = list((tmp_path / "artifacts").iterdir())
    report_files = list(run_dirs[0].glob("001-verification-report-*.md"))
    assert len(report_files) == 1


def test_verify_project_never_constructs_a_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: _completed(0, ""))

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("create_provider must not be called for verify-project")

    monkeypatch.setattr("buildrail.core.engine.create_provider", _fail_if_called)
    engine = CoreEngine()

    result = engine.verify_project(tmp_path)

    assert result.success is True


def test_install_hook_delegates_to_hook_manager(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    engine = CoreEngine()

    result = engine.install_hook(tmp_path)

    assert result.success is True
    assert "Installed" in result.message
    assert (tmp_path / ".git" / "hooks" / "pre-commit").is_file()


def test_install_hook_reports_not_a_git_repository_without_traceback(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.install_hook(tmp_path)

    assert result.success is False
    assert "Git repository" in result.message


def test_uninstall_hook_delegates_to_hook_manager(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    engine = CoreEngine()
    engine.install_hook(tmp_path)

    result = engine.uninstall_hook(tmp_path)

    assert result.success is True
    assert "Removed" in result.message
    assert not (tmp_path / ".git" / "hooks" / "pre-commit").is_file()


def test_hook_status_reports_not_installed(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    engine = CoreEngine()

    result = engine.hook_status(tmp_path)

    assert result.success is True
    assert "Not installed" in result.message


def test_hook_status_reports_installed(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    engine = CoreEngine()
    engine.install_hook(tmp_path)

    result = engine.hook_status(tmp_path)

    assert result.success is True
    assert "Installed" in result.message


def test_hook_status_reports_malformed_block_as_failure(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(
        "#!/bin/sh\n"
        "# BEGIN BUILDRAIL MANAGED BLOCK\n"
        "echo one\n"
        "# BEGIN BUILDRAIL MANAGED BLOCK\n"
        "echo two\n"
        "# END BUILDRAIL MANAGED BLOCK\n",
        encoding="utf-8",
    )
    engine = CoreEngine()

    result = engine.hook_status(tmp_path)

    assert result.success is False
    assert "Duplicate" in result.message


def _create_review_artifact(tmp_path: Path) -> str:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    engine = CoreEngine()
    result = engine.review(tmp_path, diff_path)
    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    return run_dir.name


def test_list_runs_reports_no_runs_found(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    engine = CoreEngine()

    result = engine.list_runs(tmp_path)

    assert result.success is True
    assert "No runs found" in result.message


def test_list_runs_shows_a_created_run(tmp_path: Path) -> None:
    run_id = _create_review_artifact(tmp_path)
    engine = CoreEngine()

    result = engine.list_runs(tmp_path)

    assert result.success is True
    assert run_id in result.message
    assert "status=success" in result.message
    assert "types=review" in result.message


def test_list_runs_rejects_invalid_limit(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    engine = CoreEngine()

    result = engine.list_runs(tmp_path, limit=0)

    assert result.success is False
    assert "limit" in result.message.lower()


def test_inspect_run_returns_details(tmp_path: Path) -> None:
    run_id = _create_review_artifact(tmp_path)
    engine = CoreEngine()

    result = engine.inspect_run(tmp_path, run_id)

    assert result.success is True
    assert f"run_id: {run_id}" in result.message
    assert "type: review" in result.message
    assert "produced_by: review-diff (0.1.0)" in result.message


def test_inspect_run_fails_for_unknown_run(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    engine = CoreEngine()

    result = engine.inspect_run(tmp_path, "20260101-000000-000000")

    assert result.success is False
    assert "No run named" in result.message


def test_inspect_artifact_returns_metadata_and_payload(tmp_path: Path) -> None:
    run_id = _create_review_artifact(tmp_path)
    artifact_id = f"{run_id}/001-review-review"
    engine = CoreEngine()

    result = engine.inspect_artifact(tmp_path, artifact_id)

    assert result.success is True
    assert f"id: {artifact_id}" in result.message
    assert "checksum: sha256:" in result.message
    assert "--- payload ---" in result.message
    assert "Diff Review" in result.message


def test_inspect_artifact_truncates_large_payloads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("buildrail.core.engine._MAX_PAYLOAD_DISPLAY_CHARS", 10)
    run_id = _create_review_artifact(tmp_path)
    artifact_id = f"{run_id}/001-review-review"
    engine = CoreEngine()

    result = engine.inspect_artifact(tmp_path, artifact_id)

    assert result.success is True
    assert "truncated" in result.message


def test_inspect_artifact_fails_for_unknown_artifact(tmp_path: Path) -> None:
    run_id = _create_review_artifact(tmp_path)
    engine = CoreEngine()

    result = engine.inspect_artifact(tmp_path, f"{run_id}/999-nope-nope")

    assert result.success is False
    assert "No artifact named" in result.message


def test_inspect_artifact_rejects_path_traversal(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    engine = CoreEngine()

    result = engine.inspect_artifact(tmp_path, "../secret/x")

    assert result.success is False
    assert "Invalid" in result.message


def test_list_runs_uses_custom_artifact_root(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "custom-out"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    engine = CoreEngine()
    engine.review(tmp_path, diff_path)

    result = engine.list_runs(tmp_path)

    assert result.success is True
    assert "status=success" in result.message
    assert (tmp_path / "custom-out").is_dir()
    assert not (tmp_path / "artifacts").exists()


def _init_precommit_repo(tmp_path: Path, *, with_provider: bool = True) -> None:
    config = 'provider = "fake"\n' if with_provider else ""
    (tmp_path / "buildrail.toml").write_text(
        f'{config}artifact_root = "artifacts"\n', encoding="utf-8"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "chore: initial commit")


def _mock_verify_checks(monkeypatch: pytest.MonkeyPatch, *, fail_check: str | None = None) -> None:
    """Mock only verify-project's checks (ruff/mypy/pytest); real git calls pass through."""
    real_run = subprocess.run

    def _run(args: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        args_list = list(args)
        if args_list and args_list[0] == "git":
            result: subprocess.CompletedProcess[str] = real_run(args_list, **kwargs)  # type: ignore[call-overload]
            return result
        if fail_check and fail_check in args_list:
            return subprocess.CompletedProcess(
                args=args_list, returncode=1, stdout="check failed", stderr=""
            )
        return subprocess.CompletedProcess(args=args_list, returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("subprocess.run", _run)


def test_run_pre_commit_verify_passes_diff_exists_review_passes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _mock_verify_checks(monkeypatch)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path, base_ref="HEAD")

    assert result.success is True
    assert "verify-project: passed" in result.message
    assert "review-diff: passed" in result.message
    assert "tokens:" in result.message
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    names = [p.name for p in run_dirs[0].glob("*.md")]
    assert any("verification-report" in n for n in names)
    assert any("review" in n for n in names)


def test_run_pre_commit_stops_when_verification_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _mock_verify_checks(monkeypatch, fail_check="mypy")

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("create_provider must not be called when verification fails")

    monkeypatch.setattr("buildrail.core.engine.create_provider", _fail_if_called)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path, base_ref="HEAD")

    assert result.success is False
    assert "verify-project: failed" in result.message
    assert "review-diff" not in result.message


def test_run_pre_commit_skips_review_when_diff_is_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    _mock_verify_checks(monkeypatch)

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("create_provider must not be called for an empty diff")

    monkeypatch.setattr("buildrail.core.engine.create_provider", _fail_if_called)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path, base_ref="HEAD")

    assert result.success is True
    assert "review-diff: skipped" in result.message
    assert "no changes" in result.message


def test_run_pre_commit_skip_review_flag_skips_review_and_provider(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _mock_verify_checks(monkeypatch)

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("create_provider must not be called when --skip-review is set")

    monkeypatch.setattr("buildrail.core.engine.create_provider", _fail_if_called)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path, base_ref="HEAD", skip_review=True)

    assert result.success is True
    assert "review-diff: skipped (--skip-review was set)" in result.message


def test_run_pre_commit_fails_cleanly_when_provider_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path, with_provider=False)
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _mock_verify_checks(monkeypatch)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path, base_ref="HEAD")

    assert result.success is False
    assert "verify-project: passed" in result.message
    assert "No provider configured" in result.message
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    assert list(run_dirs[0].glob("*verification-report*"))


def test_run_pre_commit_fails_for_invalid_base_ref(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    _mock_verify_checks(monkeypatch)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path, base_ref="does-not-exist")

    assert result.success is False
    assert "not a valid Git ref" in result.message


def test_run_pre_commit_fails_when_not_a_git_repository(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path)

    assert result.success is False
    assert "Git repository" in result.message


def test_run_pre_commit_falls_back_to_head_parent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "feat: add b")
    _mock_verify_checks(monkeypatch)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path)

    assert result.success is True
    assert "review-diff: passed" in result.message


def test_run_pre_commit_prefers_upstream_branch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_precommit_repo(repo)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "HEAD:main")
    (repo / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _mock_verify_checks(monkeypatch)
    engine = CoreEngine()

    result = engine.run_pre_commit(repo)

    assert result.success is True
    assert "review-diff: passed" in result.message


def test_run_pre_commit_writes_ordered_steps_and_usage_to_run_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_precommit_repo(tmp_path)
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _mock_verify_checks(monkeypatch)
    engine = CoreEngine()

    result = engine.run_pre_commit(tmp_path, base_ref="HEAD")

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert manifest["pipeline"] == "pre-commit"
    assert manifest["status"] == "success"
    assert [s["name"] for s in manifest["pipeline_steps"]] == ["verify-project", "review-diff"]
    assert manifest["provider_usage_totals"]["model"] == "fake-model"

    meta_files = list(run_dir.glob("*.meta.json"))
    assert len(meta_files) == 2
    for meta_file in meta_files:
        assert json.loads(meta_file.read_text(encoding="utf-8"))["pipeline"] == "pre-commit"


def _init_config(tmp_path: Path, *, with_provider: bool = True) -> None:
    config = 'provider = "fake"\n' if with_provider else ""
    (tmp_path / "buildrail.toml").write_text(
        f'{config}artifact_root = "artifacts"\n', encoding="utf-8"
    )


def _sample_python_project(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "main.py").write_text(
        '"""Entry point."""\n\n\ndef run():\n    pass\n', encoding="utf-8"
    )
    return repo


def test_explain_project_writes_summary_and_analysis_artifacts(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.explain_project(tmp_path, path=str(repo))

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    assert list(run_dir.glob("*architecture-summary-summary.md"))
    assert list(run_dir.glob("*architecture-summary-analysis.json"))


def test_explain_project_defaults_to_project_root_when_no_path_given(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    engine = CoreEngine()

    result = engine.explain_project(tmp_path)

    assert result.success is True


def test_explain_project_fails_cleanly_for_a_missing_repository(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    engine = CoreEngine()

    result = engine.explain_project(tmp_path, path=str(tmp_path / "does-not-exist"))

    assert result.success is False


def test_explain_project_rejects_a_null_byte_in_path(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    engine = CoreEngine()

    result = engine.explain_project(tmp_path, path=str(tmp_path) + "\x00evil")

    assert result.success is False
    assert "null byte" in result.message


def test_dependency_audit_writes_summary_and_data_artifacts(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["requests>=2.0"]\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.dependency_audit(tmp_path, path=str(repo))

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    assert list(run_dir.glob("*dependency-audit-summary.md"))
    assert list(run_dir.glob("*dependency-audit-audit.json"))


def test_dependency_audit_defaults_to_project_root_when_no_path_given(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    (tmp_path / "main.py").write_text("x = 1\n", encoding="utf-8")
    engine = CoreEngine()

    result = engine.dependency_audit(tmp_path)

    assert result.success is True


def test_dependency_audit_fails_cleanly_for_a_missing_repository(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    engine = CoreEngine()

    result = engine.dependency_audit(tmp_path, path=str(tmp_path / "does-not-exist"))

    assert result.success is False


def test_dependency_audit_fails_cleanly_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.dependency_audit(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_dependency_audit_never_constructs_a_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "app"\ndependencies = ["anthropic"]\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.dependency_audit(tmp_path, path=str(repo))

    assert result.success is True


def test_docs_generate_writes_three_documentation_artifacts_without_a_provider(
    tmp_path: Path,
) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.docs_generate(tmp_path, path=str(repo))

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    names = [p.name for p in run_dir.glob("*.md")]
    assert any("project_overview" in n for n in names)
    assert any("module_reference" in n for n in names)
    assert any("development_guide" in n for n in names)


def test_docs_generate_enhance_fails_cleanly_without_a_configured_provider(
    tmp_path: Path,
) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.docs_generate(tmp_path, path=str(repo), enhance=True)

    assert result.success is False
    assert "No provider configured" in result.message


def test_docs_generate_enhance_uses_the_fake_provider_and_marks_metadata(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=True)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.docs_generate(tmp_path, path=str(repo), enhance=True)

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    meta_files = list(run_dir.glob("*documentation*.meta.json"))
    assert len(meta_files) == 3
    for meta_file in meta_files:
        metadata = json.loads(meta_file.read_text(encoding="utf-8"))
        assert metadata["provider_usage"]["model"] == "fake-model"


def test_docs_generate_writes_real_files_when_output_is_given(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.docs_generate(tmp_path, path=str(repo), output="docs/generated")

    assert result.success is True
    generated = repo / "docs" / "generated"
    assert (generated / "project-overview.md").is_file()
    assert (generated / "module-reference.md").is_file()
    assert (generated / "development-guide.md").is_file()
    assert "Generated by Buildrail" in (generated / "project-overview.md").read_text(
        encoding="utf-8"
    )


def test_docs_generate_output_collision_fails_safely_without_writing(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    generated = repo / "docs" / "generated"
    generated.mkdir(parents=True)
    (generated / "project-overview.md").write_text("existing content", encoding="utf-8")
    engine = CoreEngine()

    result = engine.docs_generate(tmp_path, path=str(repo), output="docs/generated")

    assert result.success is False
    assert "existing" in result.message.lower() or "overwrite" in result.message.lower()
    assert (generated / "project-overview.md").read_text(encoding="utf-8") == "existing content"
    assert not (tmp_path / "artifacts").exists()


def test_docs_generate_rejects_an_output_path_escaping_the_repository_root(
    tmp_path: Path,
) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.docs_generate(tmp_path, path=str(repo), output="../../escape")

    assert result.success is False
    assert "escapes" in result.message


def test_diagram_generate_writes_a_diagram_artifact(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.diagram_generate(tmp_path, path=str(repo))

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    assert list(run_dir.glob("*diagram*.md"))


def test_diagram_generate_rejects_unsupported_formats(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.diagram_generate(tmp_path, path=str(repo), format="svg")

    assert result.success is False


def test_run_project_intelligence_shares_one_run_id_and_analysis(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.run_project_intelligence(tmp_path, path=str(repo))

    assert result.success is True
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    manifest = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
    assert manifest["pipeline"] == "project-intelligence"
    assert [s["name"] for s in manifest["pipeline_steps"]] == [
        "explain-project",
        "generate-docs",
        "generate-diagram",
    ]
    assert len(manifest["artifacts"]) == 6


def test_run_project_intelligence_with_enhance_aggregates_provider_usage(
    tmp_path: Path,
) -> None:
    _init_config(tmp_path, with_provider=True)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.run_project_intelligence(tmp_path, path=str(repo), enhance=True)

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert manifest["provider_usage_totals"]["model"] == "fake-model"
    assert manifest["provider_usage_totals"]["input_tokens"] > 0


def test_run_project_intelligence_without_enhance_has_no_provider_usage(
    tmp_path: Path,
) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    result = engine.run_project_intelligence(tmp_path, path=str(repo))

    assert result.success is True
    run_dir = next((tmp_path / "artifacts").iterdir())
    manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert "provider_usage_totals" not in manifest


def test_run_project_intelligence_cleans_up_its_temp_analysis_file(tmp_path: Path) -> None:
    _init_config(tmp_path, with_provider=False)
    repo = _sample_python_project(tmp_path)
    engine = CoreEngine()

    before = set(Path(tempfile.gettempdir()).glob("buildrail-analysis-*"))
    engine.run_project_intelligence(tmp_path, path=str(repo))
    after = set(Path(tempfile.gettempdir()).glob("buildrail-analysis-*"))

    assert after == before
