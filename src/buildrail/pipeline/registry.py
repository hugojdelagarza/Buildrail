"""PipelineRegistry: the single source of truth for every runnable pipeline —
built-in (code-backed) and project-local (declarative YAML) alike.

Built-in pipelines (`pre-commit`, `project-intelligence`) keep their real
orchestration logic in `CoreEngine` (`run_pre_commit`, `run_project_intelligence`)
— this registry only *describes* them, the same way it was described in
`buildrail.service.descriptors` before this module existed, so CLI, the
HTTP service, and the frontend all read one shared description instead of
three independently hand-maintained copies. Project-local pipelines
(`.buildrail/pipelines/<name>.yaml`) are fully described *and* executed
generically, since their steps are just an ordered list of existing skills.

Precedence mirrors `buildrail.skills.SkillRegistry`: a project-local
pipeline sharing a built-in's name is a discovery error, never a silent
override.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from buildrail.extensions import project_pipelines_dir
from buildrail.pipeline.errors import (
    DuplicatePipelineError,
    PipelineManifestValidationError,
    PipelineNotFoundError,
)
from buildrail.pipeline.manifest import PipelineManifest, load_pipeline_manifest
from buildrail.skills import SkillNotFoundError, SkillRegistry

PipelineSource = Literal["built-in", "project-local"]
PipelineExecutionKind = Literal["code", "declarative"]


@dataclass(frozen=True)
class PipelineArgument:
    """One optional or required argument a built-in pipeline's run accepts."""

    name: str
    type: str
    required: bool
    description: str


@dataclass(frozen=True)
class PipelineStepDefinition:
    """One step within a pipeline, described uniformly regardless of source."""

    name: str
    skippable: bool
    skip_condition: str | None
    inputs: dict[str, str | bool | int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineDefinition:
    """One pipeline's full description: metadata plus how it's executed."""

    name: str
    version: str
    display_name: str
    description: str
    source: PipelineSource
    execution_kind: PipelineExecutionKind
    requires_provider: bool
    steps: tuple[PipelineStepDefinition, ...]
    arguments: tuple[PipelineArgument, ...] = ()
    path: Path | None = None


_BUILT_IN_PIPELINES: tuple[PipelineDefinition, ...] = (
    PipelineDefinition(
        name="pre-commit",
        version="0.1.0",
        display_name="Pre-Commit",
        description=(
            "Runs verify-project, then review-diff only when there's a Git diff to review."
        ),
        source="built-in",
        execution_kind="code",
        requires_provider=True,
        steps=(
            PipelineStepDefinition(name="verify-project", skippable=False, skip_condition=None),
            PipelineStepDefinition(
                name="review-diff",
                skippable=True,
                skip_condition=(
                    "Skipped if verification failed, --skip-review was set, "
                    "or there are no changes against the resolved base ref."
                ),
            ),
        ),
        arguments=(
            PipelineArgument(
                name="base", type="string", required=False, description="Git ref to diff against."
            ),
            PipelineArgument(
                name="skip_review",
                type="boolean",
                required=False,
                description="Skip review-diff even if changes exist.",
            ),
        ),
    ),
    PipelineDefinition(
        name="project-intelligence",
        version="0.1.0",
        display_name="Project Intelligence",
        description=(
            "Runs explain-project, generate-docs, and generate-diagram sharing one "
            "analysis, one run id, and one run.json."
        ),
        source="built-in",
        execution_kind="code",
        requires_provider=True,
        steps=(
            PipelineStepDefinition(name="explain-project", skippable=False, skip_condition=None),
            PipelineStepDefinition(name="generate-docs", skippable=False, skip_condition=None),
            PipelineStepDefinition(name="generate-diagram", skippable=False, skip_condition=None),
        ),
        arguments=(
            PipelineArgument(
                name="path",
                type="string",
                required=False,
                description="Repository to analyze (default: cwd).",
            ),
            PipelineArgument(
                name="enhance",
                type="boolean",
                required=False,
                description="Enhance generated docs with the configured provider.",
            ),
        ),
    ),
)


class PipelineRegistry:
    """Discovers built-in and project-local pipelines and resolves them by name."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self._project_root = project_root
        self._skill_registry = (
            skill_registry
            if skill_registry is not None
            else SkillRegistry(project_root=project_root)
        )

    def list_pipelines(self) -> tuple[PipelineDefinition, ...]:
        """Return every discovered pipeline: built-ins first (in a fixed order), then
        project-local pipelines sorted by name."""
        definitions = self._all_definitions()
        built_ins = tuple(definitions[d.name] for d in _BUILT_IN_PIPELINES)
        project_local = tuple(
            definitions[name]
            for name in sorted(definitions)
            if definitions[name].source == "project-local"
        )
        return built_ins + project_local

    def get_pipeline(self, name: str) -> PipelineDefinition:
        """Return one pipeline's definition, by name."""
        try:
            return self._all_definitions()[name]
        except KeyError:
            raise PipelineNotFoundError(f"No pipeline named '{name}' is registered.") from None

    def _all_definitions(self) -> dict[str, PipelineDefinition]:
        definitions: dict[str, PipelineDefinition] = {d.name: d for d in _BUILT_IN_PIPELINES}
        if self._project_root is None:
            return definitions

        pipelines_dir = project_pipelines_dir(self._project_root)
        for name, definition in _discover_project_pipelines(
            pipelines_dir, self._skill_registry
        ).items():
            existing = definitions.get(name)
            if existing is not None:
                if existing.source == "built-in":
                    raise DuplicatePipelineError(
                        f"Project-local pipeline '{name}' at {definition.path} has the same name "
                        f"as the built-in pipeline '{name}'. Built-in pipelines cannot be "
                        "overridden in this version of Buildrail — rename the project-local "
                        "pipeline."
                    )
                raise DuplicatePipelineError(
                    f"Duplicate pipeline name '{name}': already registered from {existing.path}, "
                    f"also found at {definition.path}."
                )
            definitions[name] = definition
        return definitions


def _discover_project_pipelines(
    pipelines_dir: Path, skill_registry: SkillRegistry
) -> dict[str, PipelineDefinition]:
    definitions: dict[str, PipelineDefinition] = {}
    if not pipelines_dir.is_dir():
        return definitions

    for manifest_path in sorted(pipelines_dir.glob("*.yaml")):
        manifest = load_pipeline_manifest(manifest_path)
        if manifest.name in definitions:
            raise DuplicatePipelineError(
                f"Duplicate pipeline name '{manifest.name}': already found at "
                f"{definitions[manifest.name].path}, also found at {manifest_path}."
            )
        definitions[manifest.name] = _to_definition(manifest, skill_registry)
    return definitions


def _to_definition(manifest: PipelineManifest, skill_registry: SkillRegistry) -> PipelineDefinition:
    steps = []
    requires_provider = False
    for step in manifest.steps:
        try:
            skill_manifest = skill_registry.get_manifest(step.skill)
        except SkillNotFoundError as exc:
            raise PipelineManifestValidationError(
                f"{manifest.path}: step references unknown skill '{step.skill}'."
            ) from exc
        requires_provider = requires_provider or skill_manifest.requires_provider
        steps.append(
            PipelineStepDefinition(
                name=step.skill,
                skippable=step.condition != "always",
                skip_condition=None if step.condition == "always" else step.condition,
                inputs=dict(step.inputs),
            )
        )

    return PipelineDefinition(
        name=manifest.name,
        version=manifest.version,
        display_name=manifest.name,
        description=manifest.description,
        source="project-local",
        execution_kind="declarative",
        requires_provider=requires_provider,
        steps=tuple(steps),
        path=manifest.path,
    )
