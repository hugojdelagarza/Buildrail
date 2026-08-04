"""Minimal Git diff collection: the smallest helper the pre-commit pipeline needs.

Invokes Git as argument sequences (never `shell=True`), never mutates the
repository (no add/commit/reset/checkout/clean/push), and distinguishes "not
a repository" from "invalid base ref" from "a real git failure" so callers
can report each clearly. Base-ref resolution prefers an explicit ref, then
the branch's configured upstream, then `HEAD~1`.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(Exception):
    """Base class for all Git diff-collection errors."""


class NotAGitRepositoryError(GitError):
    """Raised when the target directory is not inside a Git repository."""


class InvalidBaseRefError(GitError):
    """Raised when no usable base ref could be resolved or verified."""


class GitCommandError(GitError):
    """Raised when a Git command fails for a reason other than a bad ref."""


@dataclass(frozen=True)
class DiffResult:
    """A unified diff collected between a resolved base ref and the working tree."""

    base_ref: str
    diff_text: str

    @property
    def is_empty(self) -> bool:
        """Return True if the diff contains no changes."""
        return not self.diff_text.strip()


def repository_root(workdir: Path) -> Path:
    """Return the repository's top-level directory, or raise if not a Git repository."""
    result = _run_git(workdir, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        raise NotAGitRepositoryError(f"{workdir} is not inside a Git repository.")
    return Path(result.stdout.strip())


def resolve_base_ref(workdir: Path, explicit_ref: str | None) -> str:
    """Resolve the base ref to diff against: explicit ref, then upstream, then HEAD~1."""
    if explicit_ref:
        _confirm_ref_exists(workdir, explicit_ref)
        return explicit_ref

    upstream = _run_git(workdir, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if upstream.returncode == 0 and upstream.stdout.strip():
        return upstream.stdout.strip()

    head_parent = _run_git(workdir, "rev-parse", "--verify", "HEAD~1")
    if head_parent.returncode == 0:
        return "HEAD~1"

    raise InvalidBaseRefError(
        "Could not resolve a base ref: no --base given, no upstream branch configured, "
        "and HEAD~1 does not exist (is this the repository's first commit?)."
    )


def collect_diff(workdir: Path, base_ref: str) -> DiffResult:
    """Collect a unified diff between base_ref and the current working tree."""
    result = _run_git(workdir, "diff", base_ref)
    if result.returncode != 0:
        raise GitCommandError(result.stderr.strip() or f"'git diff {base_ref}' failed.")
    return DiffResult(base_ref=base_ref, diff_text=result.stdout)


def _confirm_ref_exists(workdir: Path, ref: str) -> None:
    result = _run_git(workdir, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if result.returncode != 0:
        raise InvalidBaseRefError(f"'{ref}' is not a valid Git ref.")


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=["git", *args], returncode=1, stdout="", stderr=str(exc)
        )
