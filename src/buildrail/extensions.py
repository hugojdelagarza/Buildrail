"""Shared constants and safety helpers for project-local Buildrail extensions.

Project-local skills (`.buildrail/skills/<name>/`) and pipelines
(`.buildrail/pipelines/<name>.yaml`) are discovered by `buildrail.skills`
and `buildrail.pipeline` respectively, and scaffolded by `CoreEngine`.
This module owns only the shared directory layout and name validation
both sides need — not discovery, execution, or scaffolding content.

Project-local skills execute code from the repository they're found in.
Buildrail does not sandbox them; they run with the same trust as any
other file in the repository. Only use project-local skills from
repositories you trust.
"""

import re
from pathlib import Path

PROJECT_EXTENSIONS_DIRNAME = ".buildrail"
SKILLS_SUBDIRNAME = "skills"
PIPELINES_SUBDIRNAME = "pipelines"

# Lowercase, hyphenated identifiers only — the same shape as Buildrail's own
# built-in skill/pipeline names (review-diff, project-intelligence). This is
# a whitelist, not a blacklist: it rejects path separators, "..", leading
# dots, and empty/blank values by construction, not by enumerating them.
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class InvalidExtensionNameError(ValueError):
    """Raised when a project-local skill/pipeline name fails validation."""


def validate_extension_name(name: str, *, label: str = "name") -> str:
    """Validate a project-local skill/pipeline name is a safe, simple identifier.

    This is what stands between a user-supplied name and a filesystem
    path, so it must reject anything that isn't an unambiguous identifier
    — not just values that "look like" traversal attempts.
    """
    if not isinstance(name, str) or not _NAME_PATTERN.match(name):
        raise InvalidExtensionNameError(
            f"Invalid {label} '{name}': must be lowercase letters, digits, and hyphens, "
            "starting with a letter (e.g. 'api-review')."
        )
    return name


def project_extensions_root(project_root: Path) -> Path:
    """Return `<project_root>/.buildrail`."""
    return project_root / PROJECT_EXTENSIONS_DIRNAME


def project_skills_dir(project_root: Path) -> Path:
    """Return `<project_root>/.buildrail/skills`."""
    return project_extensions_root(project_root) / SKILLS_SUBDIRNAME


def project_pipelines_dir(project_root: Path) -> Path:
    """Return `<project_root>/.buildrail/pipelines`."""
    return project_extensions_root(project_root) / PIPELINES_SUBDIRNAME
