"""Buildrail's Git hook management: install/uninstall/status for the local pre-commit hook."""

from buildrail.hooks.errors import (
    HookError,
    HooksDirectoryError,
    MalformedManagedBlockError,
    NotAGitRepositoryError,
)
from buildrail.hooks.manager import (
    InstallResult,
    StatusResult,
    UninstallResult,
    install,
    status,
    uninstall,
)

__all__ = [
    "HookError",
    "HooksDirectoryError",
    "InstallResult",
    "MalformedManagedBlockError",
    "NotAGitRepositoryError",
    "StatusResult",
    "UninstallResult",
    "install",
    "status",
    "uninstall",
]
