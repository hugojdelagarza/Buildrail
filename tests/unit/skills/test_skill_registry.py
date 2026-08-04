from pathlib import Path

import pytest

from buildrail.skills import (
    DEFAULT_SKILLS_DIR,
    DuplicateSkillError,
    ManifestParseError,
    ManifestValidationError,
    SkillNotFoundError,
    SkillRegistry,
)

_VALID_MANIFEST = """\
name: {name}
version: 0.1.0
protocol_version: "1.0"
description: A test skill.
entrypoint: "python skill.py"
inputs: []
outputs:
  - name: result
    artifact_type: result
"""


def _write_skill(
    skills_dir: Path, dirname: str, yaml_text: str, *, with_entrypoint: bool = True
) -> None:
    skill_dir = skills_dir / dirname
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.yaml").write_text(yaml_text, encoding="utf-8")
    if with_entrypoint:
        (skill_dir / "skill.py").write_text(
            "def run(request, provider):\n    pass\n", encoding="utf-8"
        )


def test_default_registry_discovers_all_built_in_skills() -> None:
    registry = SkillRegistry()

    manifests = registry.list_skills()

    assert [m.name for m in manifests] == [
        "release-notes",
        "review-diff",
        "test-summary",
        "verify-project",
    ]


def test_list_skills_is_deterministic() -> None:
    registry = SkillRegistry()

    first = registry.list_skills()
    second = registry.list_skills()

    assert first == second


def test_get_manifest_returns_validated_fields_for_review_diff() -> None:
    registry = SkillRegistry()

    manifest = registry.get_manifest("review-diff")

    assert manifest.name == "review-diff"
    assert manifest.version == "0.1.0"
    assert manifest.protocol_version == "1.0"
    assert manifest.entrypoint == "python skill.py"
    assert manifest.requires_provider is True
    assert manifest.path == DEFAULT_SKILLS_DIR / "review-diff"


def test_get_manifest_returns_validated_fields_for_test_summary() -> None:
    registry = SkillRegistry()

    manifest = registry.get_manifest("test-summary")

    assert manifest.name == "test-summary"
    assert manifest.protocol_version == "1.0"
    assert manifest.requires_provider is True


def test_get_manifest_returns_validated_fields_for_release_notes() -> None:
    registry = SkillRegistry()

    manifest = registry.get_manifest("release-notes")

    assert manifest.name == "release-notes"
    assert manifest.protocol_version == "1.0"
    assert manifest.requires_provider is True


def test_get_manifest_returns_validated_fields_for_verify_project() -> None:
    registry = SkillRegistry()

    manifest = registry.get_manifest("verify-project")

    assert manifest.name == "verify-project"
    assert manifest.protocol_version == "1.0"
    assert manifest.requires_provider is False


def test_resolve_review_diff_returns_a_callable_run_function() -> None:
    registry = SkillRegistry()

    run_review = registry.resolve("review-diff")

    assert callable(run_review)


def test_resolve_test_summary_returns_a_callable_run_function() -> None:
    registry = SkillRegistry()

    run_test_summary = registry.resolve("test-summary")

    assert callable(run_test_summary)


def test_resolve_release_notes_returns_a_callable_run_function() -> None:
    registry = SkillRegistry()

    run_release_notes = registry.resolve("release-notes")

    assert callable(run_release_notes)


def test_resolve_verify_project_returns_a_callable_run_function() -> None:
    registry = SkillRegistry()

    run_verify_project = registry.resolve("verify-project")

    assert callable(run_verify_project)


def test_get_manifest_raises_for_unknown_skill() -> None:
    registry = SkillRegistry()

    with pytest.raises(SkillNotFoundError, match="nonexistent"):
        registry.get_manifest("nonexistent")


def test_resolve_raises_for_unknown_skill() -> None:
    registry = SkillRegistry()

    with pytest.raises(SkillNotFoundError, match="nonexistent"):
        registry.resolve("nonexistent")


def test_duplicate_skill_names_are_rejected(tmp_path: Path) -> None:
    _write_skill(tmp_path, "skill-a", _VALID_MANIFEST.format(name="dup"))
    _write_skill(tmp_path, "skill-b", _VALID_MANIFEST.format(name="dup"))
    registry = SkillRegistry(tmp_path)

    with pytest.raises(DuplicateSkillError, match="dup"):
        registry.list_skills()


def test_malformed_yaml_is_rejected(tmp_path: Path) -> None:
    _write_skill(tmp_path, "broken", "name: [unclosed\n")
    registry = SkillRegistry(tmp_path)

    with pytest.raises(ManifestParseError):
        registry.list_skills()


def test_unsupported_protocol_version_is_rejected(tmp_path: Path) -> None:
    manifest = _VALID_MANIFEST.format(name="future").replace(
        'protocol_version: "1.0"', 'protocol_version: "2.0"'
    )
    _write_skill(tmp_path, "future-skill", manifest)
    registry = SkillRegistry(tmp_path)

    with pytest.raises(ManifestValidationError, match="protocol_version"):
        registry.list_skills()


def test_missing_entrypoint_field_is_rejected(tmp_path: Path) -> None:
    manifest = (
        "name: no-entrypoint\n"
        "version: 0.1.0\n"
        'protocol_version: "1.0"\n'
        "description: Missing entrypoint.\n"
        "inputs: []\n"
        "outputs:\n"
        "  - name: result\n"
        "    artifact_type: result\n"
    )
    _write_skill(tmp_path, "no-entrypoint", manifest)
    registry = SkillRegistry(tmp_path)

    with pytest.raises(ManifestValidationError, match="entrypoint"):
        registry.list_skills()


def test_resolve_fails_when_entrypoint_file_is_missing(tmp_path: Path) -> None:
    _write_skill(tmp_path, "ghost", _VALID_MANIFEST.format(name="ghost"), with_entrypoint=False)
    registry = SkillRegistry(tmp_path)

    with pytest.raises(ManifestValidationError, match="ghost"):
        registry.resolve("ghost")


def test_directories_without_a_manifest_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "__pycache__").mkdir()
    _write_skill(tmp_path, "real-skill", _VALID_MANIFEST.format(name="real-skill"))
    registry = SkillRegistry(tmp_path)

    manifests = registry.list_skills()

    assert [m.name for m in manifests] == ["real-skill"]
