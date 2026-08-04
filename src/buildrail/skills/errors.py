"""Errors the Skill Registry raises, presentable by the CLI without a traceback."""


class SkillError(Exception):
    """Base class for all Skill Registry errors."""


class SkillNotFoundError(SkillError):
    """Raised when a requested skill name has no registered manifest."""


class DuplicateSkillError(SkillError):
    """Raised when two skill manifests declare the same name."""


class ManifestError(SkillError):
    """Base class for errors loading or validating a single skill.yaml."""


class ManifestNotFoundError(ManifestError):
    """Raised when a skill directory has no readable skill.yaml."""


class ManifestParseError(ManifestError):
    """Raised when skill.yaml is not valid YAML."""


class ManifestValidationError(ManifestError):
    """Raised when skill.yaml is missing or has invalid required fields."""
