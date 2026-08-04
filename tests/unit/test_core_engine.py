import subprocess
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
