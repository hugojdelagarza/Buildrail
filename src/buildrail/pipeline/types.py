"""Pipeline data types: PipelineContext, PipelineStepResult, PipelineResult."""

from dataclasses import dataclass

from buildrail.artifacts import ArtifactReference
from buildrail.skill_protocol import SkillResponse


@dataclass(frozen=True)
class PipelineContext:
    """What a pipeline run needs, independent of which skills it executes."""

    run_id: str
    workdir: str
    inputs: dict[str, str]
    # None for provider-free skills (e.g. verify-project), which never construct a provider.
    provider_name: str | None = None


@dataclass(frozen=True)
class PipelineStepResult:
    """The outcome of running one skill within a pipeline."""

    skill: str
    response: SkillResponse
    artifacts: tuple[ArtifactReference, ...]


@dataclass(frozen=True)
class PipelineResult:
    """The outcome of a full pipeline run."""

    success: bool
    steps: tuple[PipelineStepResult, ...]
    error: str | None = None
