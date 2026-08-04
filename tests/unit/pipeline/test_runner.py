from pathlib import Path

from buildrail.artifacts import ArtifactStore
from buildrail.pipeline import PipelineContext, PipelineRunner
from buildrail.providers import ProviderGateway
from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.errors import AuthenticationError
from buildrail.skill_protocol import SkillOutput, SkillResponse


def _write_diff(tmp_path: Path) -> Path:
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    return diff_path


def _context(tmp_path: Path, diff_path: Path, run_id: str) -> PipelineContext:
    return PipelineContext(
        run_id=run_id,
        workdir=str(tmp_path),
        inputs={"diff": str(diff_path)},
        provider_name="fake",
    )


def test_run_executes_single_step_and_writes_artifact(tmp_path: Path) -> None:
    diff_path = _write_diff(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    runner = PipelineRunner(ProviderGateway(FakeProvider()), store)

    result = runner.run(_context(tmp_path, diff_path, "20260804-000000-test"))

    assert result.success is True
    assert len(result.steps) == 1
    step = result.steps[0]
    assert step.skill == "review-diff"
    assert step.response.status == "success"
    assert len(step.artifacts) == 1
    reference = step.artifacts[0]
    assert reference.content_path.is_file()
    assert "[fake response]" in reference.content_path.read_text(encoding="utf-8")


def test_run_stops_and_reports_error_when_a_skill_fails(tmp_path: Path) -> None:
    missing_diff = tmp_path / "missing.patch"
    store = ArtifactStore(tmp_path / "artifacts")
    runner = PipelineRunner(ProviderGateway(FakeProvider()), store)

    result = runner.run(_context(tmp_path, missing_diff, "20260804-000001-test"))

    assert result.success is False
    assert result.error is not None
    assert len(result.steps) == 1
    assert result.steps[0].response.status == "failure"
    assert result.steps[0].artifacts == ()
    assert list((tmp_path / "artifacts").glob("**/*.md")) == []


def test_run_surfaces_provider_errors_as_pipeline_failure(tmp_path: Path) -> None:
    diff_path = _write_diff(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    gateway = ProviderGateway(FakeProvider(error=AuthenticationError("missing key")))
    runner = PipelineRunner(gateway, store)

    result = runner.run(_context(tmp_path, diff_path, "20260804-000002-test"))

    assert result.success is False
    assert result.error == "missing key"
    assert result.steps[0].artifacts == ()


def test_run_is_deterministic_for_the_same_diff(tmp_path: Path) -> None:
    diff_path = _write_diff(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    runner = PipelineRunner(ProviderGateway(FakeProvider()), store)

    first = runner.run(_context(tmp_path, diff_path, "20260804-000003-test"))
    second = runner.run(_context(tmp_path, diff_path, "20260804-000004-test"))

    assert (
        first.steps[0].response.outputs["review"].content
        == second.steps[0].response.outputs["review"].content
    )


def test_run_resolves_steps_through_the_injected_registry_not_hardcoded_loading(
    tmp_path: Path,
) -> None:
    diff_path = _write_diff(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    resolved: list[str] = []

    class _StubRegistry:
        def resolve(self, name: str):  # type: ignore[no-untyped-def]
            resolved.append(name)

            def _run(request: object, gateway: object) -> SkillResponse:
                return SkillResponse(
                    status="success",
                    outputs={"review": SkillOutput(content="stub", artifact_type="review")},
                )

            return _run

    runner = PipelineRunner(ProviderGateway(FakeProvider()), store, registry=_StubRegistry())  # type: ignore[arg-type]

    result = runner.run(_context(tmp_path, diff_path, "20260804-000005-test"))

    assert resolved == ["review-diff"]
    assert result.success is True
    assert result.steps[0].response.outputs["review"].content == "stub"


def test_run_executes_a_provider_free_skill_without_a_gateway(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    received: list[object] = []

    class _StubRegistry:
        def resolve(self, name: str):  # type: ignore[no-untyped-def]
            def _run(request: object, gateway: object) -> SkillResponse:
                received.append(gateway)
                return SkillResponse(
                    status="success",
                    outputs={"report": SkillOutput(content="ok", artifact_type="report")},
                )

            return _run

    runner = PipelineRunner(
        None,
        store,
        steps=("verify-project",),
        registry=_StubRegistry(),  # type: ignore[arg-type]
    )
    context = PipelineContext(run_id="20260804-000006-test", workdir=str(tmp_path), inputs={})

    result = runner.run(context)

    assert received == [None]
    assert result.success is True
    assert result.steps[0].response.outputs["report"].content == "ok"
