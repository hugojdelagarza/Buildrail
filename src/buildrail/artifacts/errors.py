"""Errors the Artifact Reader raises, presentable by the CLI without a traceback."""


class ArtifactReadError(Exception):
    """Base class for all artifact/run browsing errors."""


class InvalidIdentifierError(ArtifactReadError):
    """Raised when a run or artifact id is malformed or attempts path traversal."""


class InvalidLimitError(ArtifactReadError):
    """Raised when a requested run-listing limit is zero, negative, or unreasonably large."""


class RunNotFoundError(ArtifactReadError):
    """Raised when a run id has no corresponding run directory."""


class ArtifactNotFoundError(ArtifactReadError):
    """Raised when an artifact id has no corresponding metadata."""


class MalformedMetadataError(ArtifactReadError):
    """Raised when run.json or an artifact's .meta.json is invalid JSON or missing fields."""


class ChecksumMismatchError(ArtifactReadError):
    """Raised when an artifact's stored checksum does not match its actual content."""


class ArtifactAccessError(ArtifactReadError):
    """Raised when an expected run/artifact file cannot be read (missing payload, I/O error)."""
