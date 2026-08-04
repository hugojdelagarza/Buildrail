"""Protocol types shared between the Core Engine and skills: SkillRequest, SkillResponse.

For Milestone 1's in-process execution (docs/skills.md's phasing note), the
Provider Gateway is passed to a skill as a direct argument rather than via a
`provider_endpoint` on SkillRequest — there's no subprocess boundary yet for
a loopback endpoint to cross. SkillOutput.content holds the produced text
directly rather than a `content_ref` file pointer, since nothing is written
to disk until the Core Engine persists it as an artifact. Both are additive
to replace, not breaking, once a real subprocess transport is built.
"""

from dataclasses import dataclass
from typing import Literal

from buildrail.providers import Usage


@dataclass(frozen=True)
class RunContext:
    """Identifies which run and step a skill is executing within."""

    run_id: str
    step_index: int
    workdir: str


@dataclass(frozen=True)
class SkillRequest:
    """What the Core Engine sends a skill to execute it."""

    protocol_version: str
    run_context: RunContext
    inputs: dict[str, str]
    config: dict[str, object]


@dataclass(frozen=True)
class SkillOutput:
    """A single named output a skill produced."""

    content: str
    artifact_type: str
    # Lets a skill emit a non-Markdown payload (e.g. explain-project's JSON
    # ProjectAnalysis sidecar) — the Artifact Store picks the file extension
    # from this, not from an artifact-type lookup table.
    content_type: str = "text/markdown"
    # A short, human-readable label distinguishing multiple same-artifact-type
    # outputs from one skill (e.g. generate-docs' three documents) for a
    # frontend list view, without parsing the artifact's filename/slug.
    display_name: str | None = None
    model_used: str | None = None
    usage: Usage | None = None
    # Structured facts a caller needs without re-parsing `content` (e.g. verify-project's
    # pass/fail summary for the CLI's exit code) — opaque to the Core Engine otherwise.
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class SkillResponse:
    """What a skill returns after executing a SkillRequest."""

    status: Literal["success", "failure"]
    outputs: dict[str, SkillOutput]
    logs: tuple[str, ...] = ()
    error: str | None = None
