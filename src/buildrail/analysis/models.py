"""ProjectAnalysis: the typed, serializable output of the deterministic project analyzer.

Every field is a plain dataclass of strings/ints/bools/tuples so the whole
model round-trips through `to_dict`/`from_dict` and `json.dumps` without a
custom encoder — this is the normalized payload `explain-project` writes as
a sidecar artifact and that `generate-docs`/`generate-diagram` consume
without re-analyzing the repository (see `analyzer.analyze_project`).
"""

from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class FunctionInfo:
    """One public, module-level function."""

    name: str
    docstring: str | None


@dataclass(frozen=True)
class ClassInfo:
    """One public, module-level class."""

    name: str
    docstring: str | None


@dataclass(frozen=True)
class ModuleInfo:
    """One discovered Python module."""

    dotted_name: str
    file_path: str
    docstring: str | None
    classes: tuple[ClassInfo, ...]
    functions: tuple[FunctionInfo, ...]
    imports: tuple[str, ...]
    lines: int


@dataclass(frozen=True)
class PackageNode:
    """One discovered Python package (a directory with an `__init__.py`)."""

    dotted_name: str
    modules: tuple[str, ...]
    subpackages: tuple[str, ...]


@dataclass(frozen=True)
class EntryPoint:
    """One `[project.scripts]` entry point declared in `pyproject.toml`."""

    name: str
    target: str
    kind: str


@dataclass(frozen=True)
class CliCommand:
    """One CLI (sub)command deterministically discovered from `argparse` calls."""

    command: str
    description: str | None
    source_module: str | None


@dataclass(frozen=True)
class SkillInfo:
    """One built-in Buildrail skill discovered from a `skill.yaml` manifest."""

    name: str
    version: str
    description: str
    requires_provider: bool
    artifact_types: tuple[str, ...]


@dataclass(frozen=True)
class PipelineInfo:
    """One named Buildrail pipeline, discovered from a `run_<name>` orchestration function."""

    name: str
    steps: tuple[str, ...]


@dataclass(frozen=True)
class TestLayout:
    """Where a repository's tests live."""

    test_directories: tuple[str, ...]
    test_files: tuple[str, ...]


@dataclass(frozen=True)
class ProjectTooling:
    """Which quality/test tools a repository's `pyproject.toml` configures."""

    has_ruff: bool
    has_mypy: bool
    has_pytest: bool


@dataclass(frozen=True)
class ProjectStatistics:
    """Approximate size statistics for a repository."""

    python_files: int
    modules: int
    classes: int
    functions: int
    test_files: int
    lines_of_python: int


@dataclass(frozen=True)
class AnalysisWarning:
    """One non-fatal issue encountered while analyzing (bad syntax, unreadable file, ...)."""

    kind: str
    path: str
    message: str


@dataclass(frozen=True)
class ProjectAnalysis:
    """The normalized, deterministic analysis of one Python repository."""

    schema_version: str
    repository_name: str
    repository_root: str
    python_requires: str | None
    build_system: str | None
    entry_points: tuple[EntryPoint, ...]
    cli_commands: tuple[CliCommand, ...]
    packages: tuple[PackageNode, ...]
    modules: tuple[ModuleInfo, ...]
    skills: tuple[SkillInfo, ...]
    pipelines: tuple[PipelineInfo, ...]
    artifact_types: tuple[str, ...]
    test_layout: TestLayout
    tooling: ProjectTooling
    statistics: ProjectStatistics
    warnings: tuple[AnalysisWarning, ...]


def to_dict(analysis: ProjectAnalysis) -> dict[str, Any]:
    """Convert a ProjectAnalysis into a plain, JSON-serializable dict."""

    def _seq(items: tuple[Any, ...]) -> list[Any]:
        return [_value(item) for item in items]

    def _value(item: Any) -> Any:
        if hasattr(item, "__dataclass_fields__"):
            return {field: _value(getattr(item, field)) for field in item.__dataclass_fields__}
        if isinstance(item, tuple):
            return _seq(item)
        return item

    return _value(analysis)  # type: ignore[no-any-return]


def analysis_from_dict(data: dict[str, Any]) -> ProjectAnalysis:
    """Reconstruct a ProjectAnalysis from the dict produced by `to_dict`."""
    return ProjectAnalysis(
        schema_version=data["schema_version"],
        repository_name=data["repository_name"],
        repository_root=data["repository_root"],
        python_requires=data["python_requires"],
        build_system=data["build_system"],
        entry_points=tuple(EntryPoint(**item) for item in data["entry_points"]),
        cli_commands=tuple(CliCommand(**item) for item in data["cli_commands"]),
        packages=tuple(
            PackageNode(
                dotted_name=item["dotted_name"],
                modules=tuple(item["modules"]),
                subpackages=tuple(item["subpackages"]),
            )
            for item in data["packages"]
        ),
        modules=tuple(
            ModuleInfo(
                dotted_name=item["dotted_name"],
                file_path=item["file_path"],
                docstring=item["docstring"],
                classes=tuple(ClassInfo(**c) for c in item["classes"]),
                functions=tuple(FunctionInfo(**f) for f in item["functions"]),
                imports=tuple(item["imports"]),
                lines=item["lines"],
            )
            for item in data["modules"]
        ),
        skills=tuple(
            SkillInfo(
                name=item["name"],
                version=item["version"],
                description=item["description"],
                requires_provider=item["requires_provider"],
                artifact_types=tuple(item["artifact_types"]),
            )
            for item in data["skills"]
        ),
        pipelines=tuple(
            PipelineInfo(name=item["name"], steps=tuple(item["steps"]))
            for item in data["pipelines"]
        ),
        artifact_types=tuple(data["artifact_types"]),
        test_layout=TestLayout(
            test_directories=tuple(data["test_layout"]["test_directories"]),
            test_files=tuple(data["test_layout"]["test_files"]),
        ),
        tooling=ProjectTooling(**data["tooling"]),
        statistics=ProjectStatistics(**data["statistics"]),
        warnings=tuple(AnalysisWarning(**item) for item in data["warnings"]),
    )
