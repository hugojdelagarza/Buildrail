"""Hook management: installs, removes, and inspects Buildrail's Git pre-commit hook.

Owns Git discovery and hook-file mutation only — no dependency on
ProviderGateway, SkillRegistry, PipelineRunner, or ArtifactStore. Locates the
repository's *effective* hooks directory via `git rev-parse --git-path
hooks`, which already accounts for a custom `core.hooksPath`, rather than
assuming `.git/hooks`. The managed block is plain POSIX `sh` (portable to
Git for Windows' bundled sh.exe and Unix-like systems); it is appended to
any pre-existing hook content rather than replacing it, so a hand-written
hook is never silently discarded.
"""

import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from buildrail.hooks.errors import (
    HooksDirectoryError,
    MalformedManagedBlockError,
    NotAGitRepositoryError,
)

_HOOK_NAME = "pre-commit"
_BEGIN_MARKER = "# BEGIN BUILDRAIL MANAGED BLOCK"
_END_MARKER = "# END BUILDRAIL MANAGED BLOCK"


@dataclass(frozen=True)
class InstallResult:
    """The outcome of `buildrail hooks install`."""

    action: Literal["installed", "updated", "already_installed"]
    hook_path: Path


@dataclass(frozen=True)
class UninstallResult:
    """The outcome of `buildrail hooks uninstall`."""

    action: Literal["removed_file", "removed_block", "not_installed"]
    hook_path: Path


@dataclass(frozen=True)
class StatusResult:
    """The outcome of `buildrail hooks status`."""

    state: Literal["installed", "not_installed"]
    hook_path: Path


def install(project_root: Path) -> InstallResult:
    """Create or update the managed pre-commit hook, preserving any existing content."""
    hook_path = _resolve_hook_path(project_root)
    content = _read_hook(hook_path)
    markers = _find_markers(content)
    new_block = _managed_block()

    if markers is not None:
        begin, end = markers
        lines = content.splitlines(keepends=True)
        current_block = "".join(lines[begin : end + 1])
        if current_block == new_block:
            return InstallResult(action="already_installed", hook_path=hook_path)
        new_content = "".join(lines[:begin] + [new_block] + lines[end + 1 :])
        _atomic_write(hook_path, new_content, executable=True)
        return InstallResult(action="updated", hook_path=hook_path)

    if not content.strip():
        new_content = "#!/bin/sh\n" + new_block
    else:
        separator = "" if content.endswith("\n") else "\n"
        new_content = content + separator + new_block
    _atomic_write(hook_path, new_content, executable=True)
    return InstallResult(action="installed", hook_path=hook_path)


def uninstall(project_root: Path) -> UninstallResult:
    """Remove only the Buildrail-managed block, preserving any unrelated hook content."""
    hook_path = _resolve_hook_path(project_root)
    if not hook_path.is_file():
        return UninstallResult(action="not_installed", hook_path=hook_path)

    content = _read_hook(hook_path)
    markers = _find_markers(content)
    if markers is None:
        return UninstallResult(action="not_installed", hook_path=hook_path)

    begin, end = markers
    lines = content.splitlines(keepends=True)
    remaining = "".join(lines[:begin] + lines[end + 1 :])

    if _is_harmless_leftover(remaining):
        try:
            hook_path.unlink()
        except OSError as exc:
            raise HooksDirectoryError(f"Could not remove hook file at {hook_path}: {exc}") from exc
        return UninstallResult(action="removed_file", hook_path=hook_path)

    _atomic_write(hook_path, remaining, executable=True)
    return UninstallResult(action="removed_block", hook_path=hook_path)


def status(project_root: Path) -> StatusResult:
    """Report whether the Buildrail-managed hook is currently installed."""
    hook_path = _resolve_hook_path(project_root)
    if not hook_path.is_file():
        return StatusResult(state="not_installed", hook_path=hook_path)

    content = _read_hook(hook_path)
    markers = _find_markers(content)
    if markers is None:
        return StatusResult(state="not_installed", hook_path=hook_path)
    return StatusResult(state="installed", hook_path=hook_path)


def _managed_block() -> str:
    return (
        f"{_BEGIN_MARKER}\n"
        "# Managed by `buildrail hooks install` — do not edit by hand.\n"
        "# Remove with `buildrail hooks uninstall`.\n"
        "repo_root=$(git rev-parse --show-toplevel) || exit 1\n"
        'cd "$repo_root" || exit 1\n'
        'echo "Buildrail: running pre-commit verification (buildrail verify)..."\n'
        "buildrail verify\n"
        "exit $?\n"
        f"{_END_MARKER}\n"
    )


def _find_markers(content: str) -> tuple[int, int] | None:
    """Return (begin_line, end_line) indices for one well-formed marker pair, or None."""
    lines = content.splitlines()
    begins = [i for i, line in enumerate(lines) if line.strip() == _BEGIN_MARKER]
    ends = [i for i, line in enumerate(lines) if line.strip() == _END_MARKER]

    if not begins and not ends:
        return None
    if len(begins) > 1 or len(ends) > 1:
        raise MalformedManagedBlockError(
            "Duplicate Buildrail managed-block markers found in the pre-commit hook."
        )
    if len(begins) != len(ends):
        raise MalformedManagedBlockError(
            "Unterminated Buildrail managed-block markers found in the pre-commit hook."
        )
    begin, end = begins[0], ends[0]
    if end <= begin:
        raise MalformedManagedBlockError(
            "Buildrail managed-block markers are out of order in the pre-commit hook."
        )
    return begin, end


def _is_harmless_leftover(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#!"):
            return False
    return True


def _resolve_hook_path(project_root: Path) -> Path:
    root_result = _run_git(project_root, "rev-parse", "--show-toplevel")
    if root_result.returncode != 0:
        raise NotAGitRepositoryError(f"{project_root} is not inside a Git repository.")

    hooks_result = _run_git(project_root, "rev-parse", "--git-path", "hooks")
    if hooks_result.returncode != 0:
        raise HooksDirectoryError("Could not locate the repository's hooks directory.")

    hooks_dir = Path(hooks_result.stdout.strip())
    if not hooks_dir.is_absolute():
        hooks_dir = (project_root / hooks_dir).resolve()

    if hooks_dir.exists() and not hooks_dir.is_dir():
        raise HooksDirectoryError(f"{hooks_dir} exists but is not a directory.")

    return hooks_dir / _HOOK_NAME


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=30)
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=["git", *args], returncode=1, stdout="", stderr=str(exc)
        )


def _read_hook(hook_path: Path) -> str:
    if not hook_path.is_file():
        return ""
    try:
        with hook_path.open(encoding="utf-8", newline="") as hook_file:
            return hook_file.read()
    except OSError as exc:
        raise HooksDirectoryError(f"Could not read hook file at {hook_path}: {exc}") from exc


def _atomic_write(path: Path, content: str, *, executable: bool) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(path.name + ".buildrail-tmp")
        tmp_path.write_text(content, encoding="utf-8", newline="")
        if executable:
            mode = tmp_path.stat().st_mode
            tmp_path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        tmp_path.replace(path)
    except OSError as exc:
        raise HooksDirectoryError(f"Could not write hook file at {path}: {exc}") from exc
