"""Load and validate Buildrail's project-local configuration file."""

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_FILENAME = "buildrail.toml"

_SUPPORTED_PROVIDERS = frozenset({"fake", "anthropic"})
_REQUIRED_FIELDS = ("provider", "artifact_root")


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

    provider: str
    artifact_root: str
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

    return _validate(raw)


def _validate(raw: dict[str, Any]) -> BuildrailConfig:
    for field in _REQUIRED_FIELDS:
        if field not in raw:
            raise ConfigValidationError(f"{CONFIG_FILENAME} is missing required field '{field}'.")

    provider = raw["provider"]
    if not isinstance(provider, str) or not provider:
        raise ConfigValidationError(f"{CONFIG_FILENAME}: 'provider' must be a non-empty string.")
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
