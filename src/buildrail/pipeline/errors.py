"""Errors the Pipeline Registry raises, presentable by the CLI without a traceback."""


class PipelineError(Exception):
    """Base class for all Pipeline Registry errors."""


class PipelineNotFoundError(PipelineError):
    """Raised when a requested pipeline name has no registered definition."""


class DuplicatePipelineError(PipelineError):
    """Raised when two pipeline definitions declare the same name."""


class PipelineManifestError(PipelineError):
    """Base class for errors loading or validating a single project-local pipeline manifest."""


class PipelineManifestNotFoundError(PipelineManifestError):
    """Raised when a pipeline manifest file cannot be read."""


class PipelineManifestParseError(PipelineManifestError):
    """Raised when a pipeline manifest is not valid YAML."""


class PipelineManifestValidationError(PipelineManifestError):
    """Raised when a pipeline manifest is missing or has invalid required fields,
    references an unknown skill, or uses an unsupported condition value."""
