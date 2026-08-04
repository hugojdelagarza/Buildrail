"""Errors the project analyzer raises, presentable by the CLI without a traceback."""


class AnalysisError(Exception):
    """Raised when a repository cannot be analyzed at all (bad path, not a directory)."""
