"""Static metadata for every command and named pipeline the local HTTP service
exposes — the single source of truth `GET /commands` and `GET /pipelines`
serialize. Buildrail's two named pipelines (`pre-commit`,
`project-intelligence`) are implemented as `CoreEngine` methods with their
step sequence inlined at the call site (see `core/engine.py`); this module
does not change that — it is a hand-written, deliberately minimal
*description* of that existing behavior for API consumers, not a new
execution mechanism. If a pipeline's real steps ever diverge from what's
described here, update this module alongside `core/engine.py` in the same
change, the same way any other doc/code pair in this codebase stays in sync.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandArgument:
    """One optional or required argument a command/pipeline endpoint accepts."""

    name: str
    type: str
    required: bool
    description: str


@dataclass(frozen=True)
class CommandDescriptor:
    """One command executable through `POST /commands/{id}`."""

    id: str
    display_name: str
    description: str
    endpoint: str
    requires_provider: bool
    accepts_arguments: bool
    arguments: tuple[CommandArgument, ...]
    artifact_types: tuple[str, ...]
    category: str


@dataclass(frozen=True)
class PipelineStepDescriptor:
    """One step within a named pipeline."""

    name: str
    skippable: bool
    skip_condition: str | None


@dataclass(frozen=True)
class PipelineDescriptor:
    """One named pipeline executable through `POST /commands/{name}`."""

    name: str
    display_name: str
    description: str
    steps: tuple[PipelineStepDescriptor, ...]
    requires_provider: bool
    arguments: tuple[CommandArgument, ...]


_PATH_ARG = CommandArgument(
    name="path", type="string", required=False, description="Repository to analyze (default: cwd)."
)

COMMANDS: tuple[CommandDescriptor, ...] = (
    CommandDescriptor(
        id="explain",
        display_name="Explain Project",
        description="Deterministically summarize a repository's architecture. No provider.",
        endpoint="/commands/explain",
        requires_provider=False,
        accepts_arguments=True,
        arguments=(_PATH_ARG,),
        artifact_types=("architecture-summary",),
        category="analysis",
    ),
    CommandDescriptor(
        id="dependency-audit",
        display_name="Dependency Audit",
        description=(
            "Deterministically audit declared dependencies against local imports. No provider."
        ),
        endpoint="/commands/dependency-audit",
        requires_provider=False,
        accepts_arguments=True,
        arguments=(_PATH_ARG,),
        artifact_types=("dependency-audit",),
        category="analysis",
    ),
    CommandDescriptor(
        id="docs",
        display_name="Generate Docs",
        description="Generate deterministic Markdown docs; optionally enhanced by a provider.",
        endpoint="/commands/docs",
        requires_provider=False,
        accepts_arguments=True,
        arguments=(
            _PATH_ARG,
            CommandArgument(
                name="output",
                type="string",
                required=False,
                description="Also write the docs into the project at this relative path.",
            ),
            CommandArgument(
                name="enhance",
                type="boolean",
                required=False,
                description="Enhance each document with the configured provider.",
            ),
        ),
        artifact_types=("documentation",),
        category="analysis",
    ),
    CommandDescriptor(
        id="diagram",
        display_name="Generate Diagram",
        description="Generate deterministic Mermaid diagram source. No provider.",
        endpoint="/commands/diagram",
        requires_provider=False,
        accepts_arguments=True,
        arguments=(
            _PATH_ARG,
            CommandArgument(
                name="format",
                type="string",
                required=False,
                description="Diagram format. Only 'mermaid' is supported.",
            ),
        ),
        artifact_types=("diagram",),
        category="analysis",
    ),
    CommandDescriptor(
        id="verify",
        display_name="Verify",
        description="Run the local quality gate (format, lint, types, tests). No provider.",
        endpoint="/commands/verify",
        requires_provider=False,
        accepts_arguments=False,
        arguments=(),
        artifact_types=("verification-report",),
        category="quality",
    ),
    CommandDescriptor(
        id="pre-commit",
        display_name="Run Pre-Commit",
        description="Run verify-project, then review-diff when there's a Git diff to review.",
        endpoint="/commands/pre-commit",
        requires_provider=True,
        accepts_arguments=True,
        arguments=(
            CommandArgument(
                name="base", type="string", required=False, description="Git ref to diff against."
            ),
            CommandArgument(
                name="skip_review",
                type="boolean",
                required=False,
                description="Skip review-diff even if changes exist.",
            ),
        ),
        artifact_types=("verification-report", "review"),
        category="pipeline",
    ),
    CommandDescriptor(
        id="project-intelligence",
        display_name="Run Project Intelligence",
        description="Run explain-project, generate-docs, and generate-diagram on one analysis.",
        endpoint="/commands/project-intelligence",
        requires_provider=True,
        accepts_arguments=True,
        arguments=(
            _PATH_ARG,
            CommandArgument(
                name="enhance",
                type="boolean",
                required=False,
                description="Enhance generated docs with the configured provider.",
            ),
        ),
        artifact_types=("architecture-summary", "documentation", "diagram"),
        category="pipeline",
    ),
)

PIPELINES: tuple[PipelineDescriptor, ...] = (
    PipelineDescriptor(
        name="pre-commit",
        display_name="Pre-Commit",
        description="Runs verify-project, then review-diff only when there's a Git diff to review.",
        steps=(
            PipelineStepDescriptor(name="verify-project", skippable=False, skip_condition=None),
            PipelineStepDescriptor(
                name="review-diff",
                skippable=True,
                skip_condition=(
                    "Skipped if verification failed, --skip-review was set, "
                    "or there are no changes against the resolved base ref."
                ),
            ),
        ),
        requires_provider=True,
        arguments=(
            CommandArgument(
                name="base", type="string", required=False, description="Git ref to diff against."
            ),
            CommandArgument(
                name="skip_review",
                type="boolean",
                required=False,
                description="Skip review-diff even if changes exist.",
            ),
        ),
    ),
    PipelineDescriptor(
        name="project-intelligence",
        display_name="Project Intelligence",
        description=(
            "Runs explain-project, generate-docs, and generate-diagram sharing one "
            "analysis, one run id, and one run.json."
        ),
        steps=(
            PipelineStepDescriptor(name="explain-project", skippable=False, skip_condition=None),
            PipelineStepDescriptor(name="generate-docs", skippable=False, skip_condition=None),
            PipelineStepDescriptor(name="generate-diagram", skippable=False, skip_condition=None),
        ),
        requires_provider=True,
        arguments=(
            _PATH_ARG,
            CommandArgument(
                name="enhance",
                type="boolean",
                required=False,
                description="Enhance generated docs with the configured provider.",
            ),
        ),
    ),
)
