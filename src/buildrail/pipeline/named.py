"""Named pipeline results: the smallest concept for a multi-phase, user-invokable pipeline.

A named pipeline (e.g. "pre-commit") aggregates one or more PipelineRunner
calls that share a single run id into one reportable outcome, with explicit
support for steps that were intentionally skipped — not run, not failed —
because PipelineRunner itself has no notion of "should this step run"; that
decision belongs to the orchestrator (CoreEngine), which knows things
PipelineRunner doesn't (e.g. whether there's a diff to review). This keeps
PipelineRunner's own execution loop unchanged and reusable for any single
phase, named or not.
"""

from dataclasses import dataclass
from typing import Literal

from buildrail.artifacts import ArtifactReference

StepStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class NamedStepOutcome:
    """One step's outcome within a named pipeline run."""

    name: str
    status: StepStatus
    reason: str | None
    artifacts: tuple[ArtifactReference, ...]


@dataclass(frozen=True)
class NamedPipelineResult:
    """The outcome of a full named pipeline run (e.g. pre-commit)."""

    name: str
    run_id: str
    success: bool
    steps: tuple[NamedStepOutcome, ...]
    duration_seconds: float
