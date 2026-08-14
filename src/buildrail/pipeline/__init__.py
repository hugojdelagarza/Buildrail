"""Buildrail's Pipeline Runner: sequential orchestration of skills, plus the
Pipeline Registry: discovery of built-in and project-local pipelines."""

from buildrail.pipeline.errors import (
    DuplicatePipelineError,
    PipelineError,
    PipelineManifestError,
    PipelineManifestNotFoundError,
    PipelineManifestParseError,
    PipelineManifestValidationError,
    PipelineNotFoundError,
)
from buildrail.pipeline.manifest import (
    SUPPORTED_CONDITIONS,
    PipelineManifest,
    PipelineStepManifest,
    load_pipeline_manifest,
)
from buildrail.pipeline.named import NamedPipelineResult, NamedStepOutcome, StepStatus
from buildrail.pipeline.registry import (
    PipelineArgument,
    PipelineDefinition,
    PipelineExecutionKind,
    PipelineRegistry,
    PipelineSource,
    PipelineStepDefinition,
)
from buildrail.pipeline.runner import PipelineRunner
from buildrail.pipeline.scaffold import PipelineScaffoldError, create_pipeline
from buildrail.pipeline.types import PipelineContext, PipelineResult, PipelineStepResult

__all__ = [
    "SUPPORTED_CONDITIONS",
    "DuplicatePipelineError",
    "NamedPipelineResult",
    "NamedStepOutcome",
    "PipelineArgument",
    "PipelineContext",
    "PipelineDefinition",
    "PipelineError",
    "PipelineExecutionKind",
    "PipelineManifest",
    "PipelineManifestError",
    "PipelineManifestNotFoundError",
    "PipelineManifestParseError",
    "PipelineManifestValidationError",
    "PipelineNotFoundError",
    "PipelineRegistry",
    "PipelineResult",
    "PipelineRunner",
    "PipelineScaffoldError",
    "PipelineSource",
    "PipelineStepDefinition",
    "PipelineStepManifest",
    "PipelineStepResult",
    "StepStatus",
    "create_pipeline",
    "load_pipeline_manifest",
]
