from pathlib import Path

from buildrail.providers import ProviderGateway
from buildrail.providers.adapters.fake import FakeProvider
from buildrail.skill_loader import load_skill
from buildrail.skill_protocol import RunContext, SkillRequest

_SKILL_SOURCE = (
    Path(__file__).resolve().parents[3] / "skills" / "review-diff" / "skill.py"
).read_text(encoding="utf-8")


def _request(diff_path: Path) -> SkillRequest:
    return SkillRequest(
        protocol_version="1.0",
        run_context=RunContext(
            run_id="20260803-000000-test", step_index=1, workdir=str(diff_path.parent)
        ),
        inputs={"diff": str(diff_path)},
        config={},
    )


def test_skill_source_never_imports_a_provider_adapter_or_core_internals() -> None:
    assert "FakeProvider" not in _SKILL_SOURCE
    assert "providers.adapters" not in _SKILL_SOURCE
    assert "buildrail.core" not in _SKILL_SOURCE


def test_run_returns_success_with_a_structured_review(tmp_path: Path) -> None:
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text(
        "--- a/foo.py\n+++ b/foo.py\n@@\n-old line\n+new line\n+another new line\n",
        encoding="utf-8",
    )
    run_review = load_skill("review-diff")
    gateway = ProviderGateway(FakeProvider())

    response = run_review(_request(diff_path), gateway)

    assert response.status == "success"
    output = response.outputs["review"]
    assert "[fake response]" in output.content
    assert "Files changed: 1" in output.content
    assert "Lines added: 2" in output.content
    assert "Lines removed: 1" in output.content
    assert output.model_used == "fake-model"
    assert output.usage is not None


def test_run_returns_failure_when_diff_file_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "does-not-exist.patch"
    run_review = load_skill("review-diff")
    gateway = ProviderGateway(FakeProvider())

    response = run_review(_request(missing_path), gateway)

    assert response.status == "failure"
    assert response.error is not None
    assert response.outputs == {}
