from pathlib import Path

import pytest

from buildrail.skills import SkillRegistry, SkillScaffoldError, create_skill


def test_creates_a_valid_project_local_skill(tmp_path: Path) -> None:
    skill_dir = create_skill(tmp_path, "api-review")

    assert skill_dir == tmp_path / ".buildrail" / "skills" / "api-review"
    assert (skill_dir / "skill.yaml").is_file()
    assert (skill_dir / "skill.py").is_file()


def test_generated_manifest_is_discoverable_and_valid(tmp_path: Path) -> None:
    create_skill(tmp_path, "api-review")
    registry = SkillRegistry(project_root=tmp_path)

    manifest = registry.get_manifest("api-review")

    assert manifest.name == "api-review"
    assert manifest.protocol_version == "1.0"
    assert manifest.source == "project-local"
    assert manifest.requires_provider is False


def test_generated_skill_executes_and_produces_a_valid_response(tmp_path: Path) -> None:
    create_skill(tmp_path, "api-review")
    registry = SkillRegistry(project_root=tmp_path)

    run_skill = registry.resolve("api-review")
    from buildrail.skill_protocol import RunContext, SkillRequest

    response = run_skill(
        SkillRequest(
            protocol_version="1.0",
            run_context=RunContext(run_id="r1", step_index=1, workdir=str(tmp_path)),
            inputs={},
            config={},
        ),
        None,
    )

    assert response.status == "success"
    assert "summary" in response.outputs
    assert response.outputs["summary"].artifact_type == "api-review"


def test_requires_provider_option_generates_a_provider_using_template(tmp_path: Path) -> None:
    create_skill(tmp_path, "needs-ai", requires_provider=True)
    registry = SkillRegistry(project_root=tmp_path)

    manifest = registry.get_manifest("needs-ai")

    assert manifest.requires_provider is True
    source = (tmp_path / ".buildrail" / "skills" / "needs-ai" / "skill.py").read_text(
        encoding="utf-8"
    )
    assert "ProviderGateway" in source
    assert "anthropic" not in source.lower()


def test_custom_description_is_used(tmp_path: Path) -> None:
    create_skill(tmp_path, "api-review", description="Reviews API changes.")
    registry = SkillRegistry(project_root=tmp_path)

    manifest = registry.get_manifest("api-review")

    assert manifest.description == "Reviews API changes."


def test_description_with_yaml_special_characters_round_trips_safely(tmp_path: Path) -> None:
    tricky = 'Reviews: "api" changes & more'
    create_skill(tmp_path, "api-review", description=tricky)
    registry = SkillRegistry(project_root=tmp_path)

    manifest = registry.get_manifest("api-review")

    assert manifest.description == tricky


def test_duplicate_skill_name_is_refused_without_overwriting(tmp_path: Path) -> None:
    create_skill(tmp_path, "api-review")
    original = (tmp_path / ".buildrail" / "skills" / "api-review" / "skill.py").read_text(
        encoding="utf-8"
    )

    with pytest.raises(SkillScaffoldError, match="already exists"):
        create_skill(tmp_path, "api-review", description="different")

    unchanged = (tmp_path / ".buildrail" / "skills" / "api-review" / "skill.py").read_text(
        encoding="utf-8"
    )
    assert unchanged == original


@pytest.mark.parametrize(
    "bad_name",
    ["", "Api-Review", "api_review", "../escape", "api/review", "api review", "-leading-hyphen"],
)
def test_invalid_names_are_rejected(tmp_path: Path, bad_name: str) -> None:
    with pytest.raises(SkillScaffoldError):
        create_skill(tmp_path, bad_name)


def test_path_traversal_attempt_does_not_escape_the_skills_directory(tmp_path: Path) -> None:
    with pytest.raises(SkillScaffoldError):
        create_skill(tmp_path, "../../evil")

    assert not (tmp_path.parent.parent / "evil").exists()


def test_empty_description_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(SkillScaffoldError):
        create_skill(tmp_path, "api-review", description="")
