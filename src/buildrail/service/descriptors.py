"""Static metadata for every single-skill command the local HTTP service
exposes through `POST /commands/{id}` — the single source of truth
`GET /commands` serializes.

Named pipelines (`pre-commit`, `project-intelligence`, and any
project-local pipeline) are described by `buildrail.pipeline.PipelineRegistry`
instead — not duplicated here — so the CLI, this service, and the frontend
all read one shared description of a pipeline's steps
(`buildrail.service.routes._list_pipelines`). Pipelines still execute
through the same `POST /commands/{name}` endpoint as the commands below
(`routes._run_command`); this module's `COMMANDS` only ever describes
genuinely single-skill, non-pipeline commands.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandArgument:
    """One optional or required argument a command endpoint accepts."""

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
