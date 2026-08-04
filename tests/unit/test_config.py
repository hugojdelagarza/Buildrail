from pathlib import Path

import pytest

from buildrail.config import (
    BuildrailConfig,
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    load_config,
)


def _write_config(tmp_path: Path, content: str) -> None:
    (tmp_path / "buildrail.toml").write_text(content, encoding="utf-8")


def test_load_config_returns_valid_config(tmp_path: Path) -> None:
    _write_config(tmp_path, 'provider = "fake"\nartifact_root = "artifacts"\n')

    config = load_config(tmp_path)

    assert config == BuildrailConfig(provider="fake", artifact_root="artifacts")


def test_load_config_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(ConfigNotFoundError):
        load_config(tmp_path)


def test_load_config_raises_on_malformed_toml(tmp_path: Path) -> None:
    _write_config(tmp_path, "this is not [valid toml")

    with pytest.raises(ConfigParseError):
        load_config(tmp_path)


def test_load_config_raises_when_provider_missing(tmp_path: Path) -> None:
    _write_config(tmp_path, 'artifact_root = "artifacts"\n')

    with pytest.raises(ConfigValidationError, match="provider"):
        load_config(tmp_path)


def test_load_config_raises_when_artifact_root_missing(tmp_path: Path) -> None:
    _write_config(tmp_path, 'provider = "fake"\n')

    with pytest.raises(ConfigValidationError, match="artifact_root"):
        load_config(tmp_path)


def test_load_config_raises_on_unsupported_provider(tmp_path: Path) -> None:
    _write_config(tmp_path, 'provider = "openai"\nartifact_root = "artifacts"\n')

    with pytest.raises(ConfigValidationError, match="unsupported provider"):
        load_config(tmp_path)


def test_load_config_accepts_anthropic_provider(tmp_path: Path) -> None:
    _write_config(tmp_path, 'provider = "anthropic"\nartifact_root = "artifacts"\n')

    config = load_config(tmp_path)

    assert config.provider == "anthropic"
    assert config.anthropic_model is None


def test_load_config_reads_custom_anthropic_model(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        'provider = "anthropic"\nartifact_root = "artifacts"\nanthropic_model = "claude-opus-5"\n',
    )

    config = load_config(tmp_path)

    assert config.anthropic_model == "claude-opus-5"


def test_load_config_raises_when_anthropic_model_not_a_string(tmp_path: Path) -> None:
    _write_config(
        tmp_path, 'provider = "anthropic"\nartifact_root = "artifacts"\nanthropic_model = 5\n'
    )

    with pytest.raises(ConfigValidationError, match="anthropic_model"):
        load_config(tmp_path)


def test_load_config_raises_when_provider_not_a_string(tmp_path: Path) -> None:
    _write_config(tmp_path, 'provider = 5\nartifact_root = "artifacts"\n')

    with pytest.raises(ConfigValidationError, match="provider"):
        load_config(tmp_path)


def test_load_config_raises_when_artifact_root_not_a_string(tmp_path: Path) -> None:
    _write_config(tmp_path, 'provider = "fake"\nartifact_root = 5\n')

    with pytest.raises(ConfigValidationError, match="artifact_root"):
        load_config(tmp_path)
