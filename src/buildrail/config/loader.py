"""Load, validate, and write Buildrail's project-local configuration file."""

import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "buildrail.toml"
DEFAULT_ARTIFACT_ROOT = "artifacts"
DEFAULT_PROVIDER = "fake"

_SUPPORTED_PROVIDERS = frozenset({"fake", "anthropic"})
_REQUIRED_FIELDS = ("artifact_root",)


class ConfigError(Exception):
    """Base class for configuration errors the CLI can present without a traceback."""


class ConfigNotFoundError(ConfigError):
    """Raised when no configuration file exists at the expected location."""


class ConfigParseError(ConfigError):
    """Raised when the configuration file is not valid TOML."""


class ConfigValidationError(ConfigError):
    """Raised when parsed configuration fails schema validation."""


@dataclass(frozen=True)
class BuildrailConfig:
    """Buildrail's validated project-local configuration."""

    artifact_root: str
    # Optional: only commands/skills that actually call a provider (review,
    # test-summary, release-notes) require this to be set; provider-free
    # commands like `buildrail verify` work without it.
    provider: str | None = None
    anthropic_model: str | None = None


def load_config(project_root: Path) -> BuildrailConfig:
    """Load and validate the project's configuration file, raising ConfigError on failure."""
    config_path = project_root / CONFIG_FILENAME
    if not config_path.is_file():
        raise ConfigNotFoundError(f"No configuration file found at {config_path}.")

    try:
        with config_path.open("rb") as config_file:
            raw = tomllib.load(config_file)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigParseError(f"{CONFIG_FILENAME} is not valid TOML: {exc}") from exc

    return validate(raw)


def validate(raw: dict[str, Any]) -> BuildrailConfig:
    """Validate a raw configuration mapping and return a `BuildrailConfig`.

    Shared by `load_config` (parsing an existing file) and the config write
    path (validating fields before they're ever written to disk) — the
    validation rules must never diverge between reading and writing.
    """
    for field in _REQUIRED_FIELDS:
        if field not in raw:
            raise ConfigValidationError(f"{CONFIG_FILENAME} is missing required field '{field}'.")

    provider = raw.get("provider")
    if provider is not None:
        if not isinstance(provider, str) or not provider:
            raise ConfigValidationError(
                f"{CONFIG_FILENAME}: 'provider' must be a non-empty string."
            )
        if provider not in _SUPPORTED_PROVIDERS:
            supported = ", ".join(sorted(_SUPPORTED_PROVIDERS))
            raise ConfigValidationError(
                f"{CONFIG_FILENAME}: unsupported provider '{provider}'. "
                f"Supported providers: {supported}."
            )

    artifact_root = raw["artifact_root"]
    if not isinstance(artifact_root, str) or not artifact_root:
        raise ConfigValidationError(
            f"{CONFIG_FILENAME}: 'artifact_root' must be a non-empty string."
        )

    anthropic_model = raw.get("anthropic_model")
    if anthropic_model is not None and (
        not isinstance(anthropic_model, str) or not anthropic_model
    ):
        raise ConfigValidationError(
            f"{CONFIG_FILENAME}: 'anthropic_model' must be a non-empty string."
        )

    return BuildrailConfig(
        provider=provider, artifact_root=artifact_root, anthropic_model=anthropic_model
    )


def ensure_artifact_root_within_project(project_root: Path, artifact_root: str) -> None:
    """Raise ValueError if `artifact_root` would resolve outside `project_root`.

    Catches both `../..` traversal and an absolute path substituting the
    project root entirely (`Path.__truediv__` discards the left side when the
    right side is already absolute, so this one check covers both).
    """
    resolved_root = project_root.resolve()
    candidate = (resolved_root / artifact_root).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError(
            f"'artifact_root' must stay within the project directory, got '{artifact_root}'."
        )


def _escape_toml_string(value: str) -> str:
    """Escape a value for embedding in a TOML basic string.

    Buildrail only ever writes a small, fixed set of known keys with
    programmatically-validated string values — never raw TOML from a
    caller — but values themselves (e.g. `artifact_root`) are still
    arbitrary strings, so quotes/backslashes/control characters must be
    escaped to prevent them from injecting additional TOML keys.
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def _render_toml(config: BuildrailConfig) -> str:
    """Render a `BuildrailConfig` as minimal TOML text."""
    lines = []
    if config.provider is not None:
        lines.append(f'provider = "{_escape_toml_string(config.provider)}"')
    lines.append(f'artifact_root = "{_escape_toml_string(config.artifact_root)}"')
    if config.anthropic_model is not None:
        lines.append(f'anthropic_model = "{_escape_toml_string(config.anthropic_model)}"')
    return "\n".join(lines) + "\n"


def write_config(project_root: Path, config: BuildrailConfig) -> None:
    """Atomically write `config` to this project's `buildrail.toml`.

    Writes to a temp file in the same directory first, then renames it into
    place — a same-filesystem rename is atomic on both POSIX and Windows, so
    a crash or concurrent read never observes a partially-written file.
    """
    config_path = project_root / CONFIG_FILENAME
    text = _render_toml(config)

    fd, tmp_name = tempfile.mkstemp(prefix=".buildrail-toml-", dir=project_root)
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        tmp_path.replace(config_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
