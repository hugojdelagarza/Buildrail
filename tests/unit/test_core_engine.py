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
