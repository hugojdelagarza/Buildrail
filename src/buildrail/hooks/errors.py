"""Errors the hook-management module raises, presentable by the CLI without a traceback."""


class HookError(Exception):
    """Base class for all hook-management errors."""


class NotAGitRepositoryError(HookError):
    """Raised when the target directory is not inside a Git repository."""


class HooksDirectoryError(HookError):
    """Raised when the repository's hooks directory cannot be located, created, or written to."""


class MalformedManagedBlockError(HookError):
    """Raised when the Buildrail managed-block markers are duplicated, nested, or unterminated."""
