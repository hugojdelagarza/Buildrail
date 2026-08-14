from pathlib import Path

import pytest

from buildrail.pipeline import (
    PipelineManifestNotFoundError,
    PipelineManifestParseError,
    PipelineManifestValidationError,
)
from buildrail.pipeline.manifest import load_pipeline_manifest


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_parses_a_minimal_valid_manifest(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "quality.yaml",
        "name: quality\nversion: 0.1.0\ndescription: Verify and review.\nsteps:\n"
        "  - skill: verify-project\n",
    )

    manifest = load_pipeline_manifest(path)

    assert manifest.name == "quality"
    assert manifest.version == "0.1.0"
    assert manifest.description == "Verify and review."
    assert len(manifest.steps) == 1
    assert manifest.steps[0].skill == "verify-project"
    assert manifest.steps[0].condition == "always"
    assert manifest.steps[0].inputs == {}


def test_parses_conditions_and_inputs(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "quality.yaml",
        "name: quality\nversion: 0.1.0\ndescription: x\nsteps:\n"
        "  - skill: verify-project\n"
        "  - skill: review-diff\n"
        "    condition: changes_exist\n"
        "    inputs:\n"
        "      diff: changes.patch\n"
        "      retries: 2\n"
        "      verbose: true\n",
    )

    manifest = load_pipeline_manifest(path)

    assert manifest.steps[0].condition == "always"
    second = manifest.steps[1]
    assert second.skill == "review-diff"
    assert second.condition == "changes_exist"
    assert second.inputs == {"diff": "changes.patch", "retries": 2, "verbose": True}


def test_missing_file_raises_not_found(tmp_path: Path) -> None:
    with pytest.raises(PipelineManifestNotFoundError):
        load_pipeline_manifest(tmp_path / "missing.yaml")


def test_malformed_yaml_raises_parse_error(tmp_path: Path) -> None:
    path = _write(tmp_path / "broken.yaml", "name: [unclosed\n")

    with pytest.raises(PipelineManifestParseError):
        load_pipeline_manifest(path)


def test_non_mapping_yaml_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path / "list.yaml", "- just\n- a\n- list\n")

    with pytest.raises(PipelineManifestValidationError, match="mapping"):
        load_pipeline_manifest(path)


def test_missing_name_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "no-name.yaml",
        "version: 0.1.0\ndescription: x\nsteps:\n  - skill: verify-project\n",
    )

    with pytest.raises(PipelineManifestValidationError, match="name"):
        load_pipeline_manifest(path)


def test_missing_version_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "no-version.yaml",
        "name: quality\ndescription: x\nsteps:\n  - skill: verify-project\n",
    )

    with pytest.raises(PipelineManifestValidationError, match="version"):
        load_pipeline_manifest(path)


def test_empty_steps_list_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path / "empty.yaml", "name: quality\nversion: 0.1.0\nsteps: []\n")

    with pytest.raises(PipelineManifestValidationError, match="steps"):
        load_pipeline_manifest(path)


def test_missing_steps_field_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path / "no-steps.yaml", "name: quality\nversion: 0.1.0\n")

    with pytest.raises(PipelineManifestValidationError, match="steps"):
        load_pipeline_manifest(path)


def test_malformed_step_missing_skill_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad-step.yaml",
        "name: quality\nversion: 0.1.0\nsteps:\n  - condition: always\n",
    )

    with pytest.raises(PipelineManifestValidationError, match="skill"):
        load_pipeline_manifest(path)


def test_unsupported_condition_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad-condition.yaml",
        "name: quality\nversion: 0.1.0\nsteps:\n"
        "  - skill: verify-project\n    condition: on_full_moon\n",
    )

    with pytest.raises(PipelineManifestValidationError, match="condition"):
        load_pipeline_manifest(path)


def test_step_with_a_list_input_value_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad-input.yaml",
        "name: quality\nversion: 0.1.0\nsteps:\n"
        "  - skill: verify-project\n    inputs:\n      items:\n        - a\n        - b\n",
    )

    with pytest.raises(PipelineManifestValidationError, match="input"):
        load_pipeline_manifest(path)


def test_step_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "bad-step-shape.yaml",
        "name: quality\nversion: 0.1.0\nsteps:\n  - just-a-string\n",
    )

    with pytest.raises(PipelineManifestValidationError, match="mapping"):
        load_pipeline_manifest(path)
