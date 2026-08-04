"""Buildrail's Artifact Store: typed, immutable, checksum-verified run output."""

from buildrail.artifacts.errors import (
    ArtifactAccessError,
    ArtifactNotFoundError,
    ArtifactReadError,
    ChecksumMismatchError,
    InvalidIdentifierError,
    InvalidLimitError,
    MalformedMetadataError,
    RunNotFoundError,
)
from buildrail.artifacts.ids import Clock, IdGenerator, SystemClock, SystemIdGenerator
from buildrail.artifacts.reader import (
    ArtifactDetail,
    ArtifactPayload,
    ArtifactReader,
    RunDetail,
    RunSummary,
)
from buildrail.artifacts.store import ArtifactReference, ArtifactStore

__all__ = [
    "ArtifactAccessError",
    "ArtifactDetail",
    "ArtifactNotFoundError",
    "ArtifactPayload",
    "ArtifactReadError",
    "ArtifactReader",
    "ArtifactReference",
    "ArtifactStore",
    "ChecksumMismatchError",
    "Clock",
    "IdGenerator",
    "InvalidIdentifierError",
    "InvalidLimitError",
    "MalformedMetadataError",
    "RunDetail",
    "RunNotFoundError",
    "RunSummary",
    "SystemClock",
    "SystemIdGenerator",
]
