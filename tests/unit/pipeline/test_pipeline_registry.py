from pathlib import Path

import pytest

from buildrail.pipeline import (
    DuplicatePipelineError,
    PipelineError,
    PipelineManifestValidationError,
    PipelineNotFoundError,
    PipelineRegistry,
)


def _write_pipeline(project_root: Path, filename: str, text: str) -> None:
    pipelines_dir = project_root / ".buildrail" / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)
    (pipelines_dir / filename).write_text(text, encoding="utf-8")


_QUALITY = "name: quality\nversion: 0.1.0\ndescription: x\nsteps:\n  - skill: verify-project\n"


def test_no_project_root_lists_only_built_ins() -> None:
    registry = PipelineRegistry()

    names = [d.name for d in registry.list_pipelines()]

    assert names == ["pre-commit", "project-intelligence"]


def test_built_ins_have_code_execution_kind_and_no_path() -> None:
    registry = PipelineRegistry()

    pre_commit = registry.get_pipeline("pre-commit")

    assert pre_commit.source == "built-in"
    assert pre_commit.execution_kind == "code"
    assert pre_commit.path is None
    assert len(pre_commit.steps) == 2


def test_project_local_pipeline_is_discovered(tmp_path: Path) -> None:
    _write_pipeline(tmp_path, "quality.yaml", _QUALITY)
    registry = PipelineRegistry(project_root=tmp_path)

    names = [d.name for d in registry.list_pipelines()]

    assert names == ["pre-commit", "project-intelligence", "quality"]


def test_project_local_pipeline_has_declarative_execution_kind(tmp_path: Path) -> None:
    _write_pipeline(tmp_path, "quality.yaml", _QUALITY)
    registry = PipelineRegistry(project_root=tmp_path)

    quality = registry.get_pipeline("quality")

    assert quality.source == "project-local"
    assert quality.execution_kind == "declarative"
    assert quality.path == tmp_path / ".buildrail" / "pipelines" / "quality.yaml"
    assert quality.steps[0].name == "verify-project"


def test_requires_provider_is_derived_from_referenced_skills(tmp_path: Path) -> None:
    text = "name: review-only\nversion: 0.1.0\ndescription: x\nsteps:\n  - skill: review-diff\n"
    _write_pipeline(tmp_path, "review-only.yaml", text)
    registry = PipelineRegistry(project_root=tmp_path)

    definition = registry.get_pipeline("review-only")

    assert definition.requires_provider is True


def test_provider_free_pipeline_reports_requires_provider_false(tmp_path: Path) -> None:
    _write_pipeline(tmp_path, "quality.yaml", _QUALITY)
    registry = PipelineRegistry(project_root=tmp_path)

    definition = registry.get_pipeline("quality")

    assert definition.requires_provider is False


def test_unknown_skill_reference_is_rejected(tmp_path: Path) -> None:
    text = "name: broken\nversion: 0.1.0\ndescription: x\nsteps:\n  - skill: nonexistent\n"
    _write_pipeline(tmp_path, "broken.yaml", text)
    registry = PipelineRegistry(project_root=tmp_path)

    with pytest.raises(PipelineManifestValidationError, match="nonexistent"):
        registry.list_pipelines()


def test_duplicate_project_local_pipeline_names_are_rejected(tmp_path: Path) -> None:
    _write_pipeline(tmp_path, "a.yaml", _QUALITY)
    _write_pipeline(tmp_path, "b.yaml", _QUALITY)
    registry = PipelineRegistry(project_root=tmp_path)

    with pytest.raises(DuplicatePipelineError, match="quality"):
        registry.list_pipelines()


def test_project_local_pipeline_colliding_with_a_built_in_name_fails_clearly(
    tmp_path: Path,
) -> None:
    text = "name: pre-commit\nversion: 0.1.0\ndescription: x\nsteps:\n  - skill: verify-project\n"
    _write_pipeline(tmp_path, "pre-commit.yaml", text)
    registry = PipelineRegistry(project_root=tmp_path)

    with pytest.raises(DuplicatePipelineError, match="built-in"):
        registry.list_pipelines()


def test_get_pipeline_raises_for_unknown_name(tmp_path: Path) -> None:
    registry = PipelineRegistry(project_root=tmp_path)

    with pytest.raises(PipelineNotFoundError, match="nonexistent"):
        registry.get_pipeline("nonexistent")


def test_list_pipelines_is_deterministic(tmp_path: Path) -> None:
    _write_pipeline(tmp_path, "quality.yaml", _QUALITY)
    registry = PipelineRegistry(project_root=tmp_path)

    first = registry.list_pipelines()
    second = registry.list_pipelines()

    assert first == second


def test_missing_pipelines_directory_does_not_error(tmp_path: Path) -> None:
    registry = PipelineRegistry(project_root=tmp_path)

    names = [d.name for d in registry.list_pipelines()]

    assert names == ["pre-commit", "project-intelligence"]


def test_project_root_containing_spaces(tmp_path: Path) -> None:
    project_root = tmp_path / "my project"
    _write_pipeline(project_root, "quality.yaml", _QUALITY)
    registry = PipelineRegistry(project_root=project_root)

    definition = registry.get_pipeline("quality")

    assert definition.source == "project-local"


def test_generic_pipeline_error_base_class_covers_all_registry_errors() -> None:
    assert issubclass(DuplicatePipelineError, PipelineError)
    assert issubclass(PipelineNotFoundError, PipelineError)
    assert issubclass(PipelineManifestValidationError, PipelineError)
