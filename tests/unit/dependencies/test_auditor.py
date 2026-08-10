from pathlib import Path

import pytest

from buildrail.analysis import AnalysisError
from buildrail.dependencies import audit_dependencies


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _pyproject(tmp_path: Path, body: str) -> None:
    _write(tmp_path / "pyproject.toml", body)


def test_pyproject_runtime_dependencies_are_parsed(tmp_path: Path) -> None:
    _pyproject(
        tmp_path,
        '[project]\nname = "x"\ndependencies = ["requests>=2.0,<3", "click==8.1.0"]\n',
    )

    audit = audit_dependencies(tmp_path)

    names = {d.name: d for d in audit.dependencies}
    assert names["requests"].group == "runtime"
    assert names["requests"].version_constraint == ">=2.0,<3"
    assert names["click"].is_pinned is True


def test_dev_and_optional_dependency_groups(tmp_path: Path) -> None:
    _pyproject(
        tmp_path,
        '[project]\nname = "x"\ndependencies = []\n'
        "[project.optional-dependencies]\n"
        'dev = ["pytest>=8"]\n'
        'docs = ["mkdocs>=1"]\n',
    )

    audit = audit_dependencies(tmp_path)

    groups = {d.name: d.group for d in audit.dependencies}
    assert groups["pytest"] == "dev"
    assert groups["mkdocs"] == "docs"


def test_build_backend_is_captured(tmp_path: Path) -> None:
    _pyproject(
        tmp_path,
        '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
        '[project]\nname = "x"\ndependencies = []\n',
    )

    audit = audit_dependencies(tmp_path)

    assert audit.build_backend == "hatchling.build"


def test_requirements_txt_is_parsed(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "requests>=2.0\nclick==8.1.0\n")

    audit = audit_dependencies(tmp_path)

    names = {d.name: d for d in audit.dependencies}
    assert names["requests"].group == "runtime"
    assert names["requests"].source == "requirements.txt"
    assert names["click"].is_pinned is True


def test_requirements_dev_txt_maps_to_dev_group(tmp_path: Path) -> None:
    _write(tmp_path / "requirements-dev.txt", "pytest>=8\n")

    audit = audit_dependencies(tmp_path)

    assert audit.dependencies[0].group == "dev"


def test_unpinned_package_is_not_marked_pinned(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "requests\n")

    audit = audit_dependencies(tmp_path)

    assert audit.dependencies[0].is_pinned is False
    assert audit.dependencies[0].version_constraint is None


def test_duplicate_declaration_is_reported(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = ["requests>=2.0"]\n')
    _write(tmp_path / "requirements.txt", "requests>=2.0\n")

    audit = audit_dependencies(tmp_path)

    assert len(audit.duplicates) == 1
    assert audit.duplicates[0].name == "requests"
    assert len(audit.duplicates[0].occurrences) == 2


def test_conflicting_exact_pins_are_reported(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = ["click==8.1.0"]\n')
    _write(tmp_path / "requirements.txt", "click==8.0.0\n")

    audit = audit_dependencies(tmp_path)

    assert len(audit.conflicts) == 1
    assert audit.conflicts[0].name == "click"
    assert set(audit.conflicts[0].constraints) == {"==8.1.0", "==8.0.0"}


def test_matching_duplicate_pins_are_not_a_conflict(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = ["click==8.1.0"]\n')
    _write(tmp_path / "requirements.txt", "click==8.1.0\n")

    audit = audit_dependencies(tmp_path)

    assert len(audit.duplicates) == 1
    assert audit.conflicts == ()


def test_vcs_dependency_is_classified(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "git+https://github.com/org/repo.git@main#egg=repo\n")

    audit = audit_dependencies(tmp_path)

    dep = audit.dependencies[0]
    assert dep.is_vcs is True
    assert dep.name == "repo"


def test_direct_url_dependency_is_classified(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "https://example.com/pkg-1.0-py3-none-any.whl\n")

    audit = audit_dependencies(tmp_path)

    dep = audit.dependencies[0]
    assert dep.is_url is True
    assert dep.is_vcs is False


def test_editable_dependency_is_classified(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "-e ./local-package\n")

    audit = audit_dependencies(tmp_path)

    dep = audit.dependencies[0]
    assert dep.is_editable is True
    assert dep.is_local_path is True


def test_local_path_dependency_is_classified(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "./vendor/mylib\n")

    audit = audit_dependencies(tmp_path)

    dep = audit.dependencies[0]
    assert dep.is_local_path is True
    assert dep.is_editable is False


def test_local_imports_are_compared_with_declarations(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = ["requests"]\n')
    _write(tmp_path / "app.py", "import requests\nimport click\n")

    audit = audit_dependencies(tmp_path)

    mismatch_names = {m.name: m.kind for m in audit.mismatches}
    assert mismatch_names.get("click") == "imported_not_declared"
    assert "requests" not in {m.name for m in audit.mismatches if m.kind == "declared_not_observed"}


def test_stdlib_imports_are_excluded_from_observations(tmp_path: Path) -> None:
    _write(tmp_path / "app.py", "import os\nimport json\nfrom pathlib import Path\n")

    audit = audit_dependencies(tmp_path)

    assert "os" not in audit.observed_third_party_imports
    assert "json" not in audit.observed_third_party_imports
    assert "pathlib" not in audit.observed_third_party_imports


def test_ambiguous_import_mapping_is_conservative(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = ["pyyaml"]\n')
    _write(tmp_path / "app.py", "import yaml\n")

    audit = audit_dependencies(tmp_path)

    kinds = {(m.name, m.kind) for m in audit.mismatches}
    assert ("pyyaml", "declared_not_observed") in kinds
    assert ("yaml", "imported_not_declared") in kinds
    for mismatch in audit.mismatches:
        assert "uncertain" in mismatch.note.lower() or "may differ" in mismatch.note.lower()


def test_malformed_dependency_declaration_produces_a_warning_not_a_crash(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = [123]\n')

    audit = audit_dependencies(tmp_path)

    assert audit.dependencies == ()
    assert any(w.kind == "malformed_dependency" for w in audit.warnings)


def test_project_with_no_dependencies(tmp_path: Path) -> None:
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = []\n')

    audit = audit_dependencies(tmp_path)

    assert audit.dependencies == ()
    assert audit.duplicates == ()
    assert audit.conflicts == ()


def test_project_with_no_declaration_files_at_all(tmp_path: Path) -> None:
    _write(tmp_path / "app.py", "x = 1\n")

    audit = audit_dependencies(tmp_path)

    assert audit.sources == ()
    assert audit.dependencies == ()


def test_path_containing_spaces(tmp_path: Path) -> None:
    project = tmp_path / "my project"
    _pyproject(project, '[project]\nname = "x"\ndependencies = ["requests"]\n')

    audit = audit_dependencies(project)

    assert audit.dependencies[0].name == "requests"


def test_auditor_module_never_references_providers(tmp_path: Path) -> None:
    import buildrail.dependencies.auditor as auditor_module

    source = Path(auditor_module.__file__).read_text(encoding="utf-8")
    assert "buildrail.providers" not in source
    assert "ProviderGateway" not in source

    # Auditing a project that merely *declares* "anthropic" as a dependency
    # must not construct a real provider or require ANTHROPIC_API_KEY.
    _pyproject(tmp_path, '[project]\nname = "x"\ndependencies = ["anthropic"]\n')
    audit = audit_dependencies(tmp_path)
    assert audit.dependencies[0].name == "anthropic"


def test_audit_raises_analysis_error_for_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError):
        audit_dependencies(tmp_path / "does-not-exist")


def test_recursive_requirements_reference_is_followed(tmp_path: Path) -> None:
    _write(tmp_path / "requirements.txt", "-r requirements-base.txt\nclick\n")
    _write(tmp_path / "requirements-base.txt", "requests\n")

    audit = audit_dependencies(tmp_path)

    names = {d.name for d in audit.dependencies}
    assert names == {"requests", "click"}


def test_recursive_requirements_reference_outside_repo_is_skipped(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _write(project / "requirements.txt", "-r ../outside.txt\nclick\n")
    _write(tmp_path / "outside.txt", "requests\n")

    audit = audit_dependencies(project)

    names = {d.name for d in audit.dependencies}
    assert names == {"click"}
    assert any(w.kind == "unresolved_reference" for w in audit.warnings)
