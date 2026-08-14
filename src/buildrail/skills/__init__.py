"""Buildrail's Skill Registry: discovery, manifest loading, and resolution of built-in skills."""

from buildrail.skills.errors import (
    DuplicateSkillError,
    ManifestError,
    ManifestNotFoundError,
    ManifestParseError,
    ManifestValidationError,
    SkillError,
    SkillNotFoundError,
)
from buildrail.skills.registry import (
    DEFAULT_SKILLS_DIR,
    SkillManifest,
    SkillManifestInput,
    SkillManifestOutput,
    SkillRegistry,
    SkillSource,
)
from buildrail.skills.scaffold import SkillScaffoldError, create_skill

__all__ = [
    "DEFAULT_SKILLS_DIR",
    "DuplicateSkillError",
    "ManifestError",
    "ManifestNotFoundError",
    "ManifestParseError",
    "ManifestValidationError",
    "SkillError",
    "SkillManifest",
    "SkillManifestInput",
    "SkillManifestOutput",
    "SkillNotFoundError",
    "SkillRegistry",
    "SkillScaffoldError",
    "SkillSource",
    "create_skill",
]
