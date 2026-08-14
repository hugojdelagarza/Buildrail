from pathlib import Path

import pytest

from buildrail.pipeline import PipelineRegistry, PipelineScaffoldError, create_pipeline


def test_creates_a_valid_project_local_pipeline(tmp_path: Path) -> None:
    path = create_pipeline(tmp_path, "quality")

    assert path == tmp_path / ".buildrail" / "pipelines" / "quality.yaml"
    assert path.is_file()


def test_default_template_is_discoverable_and_runnable_shape(tmp_path: Path) -> None:
    create_pipeline(tmp_path, "quality")
    registry = PipelineRegistry(project_root=tmp_path)

    definition = registry.get_pipeline("quality")

    assert definition.steps[0].name == "verify-project"
    assert definition.requires_provider is False


def test_custom_description_and_steps_are_used(tmp_path: Path) -> None:
    create_pipeline(
        tmp_path,
        "review-flow",
        description="Reviews changes.",
        steps=[("verify-project", "always"), ("review-diff", "changes_exist")],
    )
    registry = PipelineRegistry(project_root=tmp_path)

    definition = registry.get_pipeline("review-flow")

    assert definition.description == "Reviews changes."
    assert [s.name for s in definition.steps] == ["verify-project", "review-diff"]
    assert definition.steps[1].skip_condition == "changes_exist"


def test_description_with_yaml_special_characters_round_trips_safely(tmp_path: Path) -> None:
    tricky = 'Runs: "quality" checks & more'
    create_pipeline(tmp_path, "quality", description=tricky)
    registry = PipelineRegistry(project_root=tmp_path)

    assert registry.get_pipeline("quality").description == tricky


def test_ordered_steps_are_preserved(tmp_path: Path) -> None:
    create_pipeline(
        tmp_path,
        "ordered",
        steps=[
            ("verify-project", "always"),
            ("explain-project", "always"),
            ("dependency-audit", "always"),
        ],
    )
    registry = PipelineRegistry(project_root=tmp_path)

    definition = registry.get_pipeline("ordered")

    assert [s.name for s in definition.steps] == [
        "verify-project",
        "explain-project",
        "dependency-audit",
    ]


def test_duplicate_pipeline_name_is_refused_without_overwriting(tmp_path: Path) -> None:
    create_pipeline(tmp_path, "quality")
    original = (tmp_path / ".buildrail" / "pipelines" / "quality.yaml").read_text(encoding="utf-8")

    with pytest.raises(PipelineScaffoldError, match="already exists"):
        create_pipeline(tmp_path, "quality", description="different")

    unchanged = (tmp_path / ".buildrail" / "pipelines" / "quality.yaml").read_text(encoding="utf-8")
    assert unchanged == original


@pytest.mark.parametrize(
    "bad_name", ["", "Quality", "quality_check", "../escape", "quality/check", "quality check"]
)
def test_invalid_names_are_rejected(tmp_path: Path, bad_name: str) -> None:
    with pytest.raises(PipelineScaffoldError):
        create_pipeline(tmp_path, bad_name)


def test_path_traversal_attempt_does_not_escape_the_pipelines_directory(tmp_path: Path) -> None:
    with pytest.raises(PipelineScaffoldError):
        create_pipeline(tmp_path, "../../evil")

    assert not (tmp_path.parent.parent / "evil.yaml").exists()


def test_unsupported_condition_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PipelineScaffoldError, match="condition"):
        create_pipeline(tmp_path, "quality", steps=[("verify-project", "on_full_moon")])


def test_empty_steps_list_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PipelineScaffoldError):
        create_pipeline(tmp_path, "quality", steps=[])


def test_step_with_empty_skill_name_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(PipelineScaffoldError):
        create_pipeline(tmp_path, "quality", steps=[("", "always")])
