"""Buildrail's local HTTP service: exposes CoreEngine/ArtifactReader over
localhost for a future local frontend. Not a cloud API, not multi-user,
no authentication — see `server.py`'s module docstring."""

from buildrail.service.routes import dispatch
from buildrail.service.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    BuildrailHTTPServer,
    create_server,
    run,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "BuildrailHTTPServer",
    "create_server",
    "dispatch",
    "run",
]
