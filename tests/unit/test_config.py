from pathlib import Path

import pytest

from buildrail.config import (
    BuildrailConfig,
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    ensure_artifact_root_within_project,
    load_config,
    validate,
    write_config,
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


def test_load_config_accepts_missing_provider(tmp_path: Path) -> None:
    _write_config(tmp_path, 'artifact_root = "artifacts"\n')

    config = load_config(tmp_path)

    assert config.provider is None


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


def test_validate_accepts_a_raw_dict_directly() -> None:
    config = validate({"provider": "fake", "artifact_root": "artifacts"})

    assert config == BuildrailConfig(provider="fake", artifact_root="artifacts")


def test_write_config_creates_a_readable_file(tmp_path: Path) -> None:
    config = BuildrailConfig(provider="fake", artifact_root="artifacts")

    write_config(tmp_path, config)

    assert load_config(tmp_path) == config


def test_write_config_overwrites_an_existing_file(tmp_path: Path) -> None:
    _write_config(tmp_path, 'provider = "fake"\nartifact_root = "old"\n')

    write_config(tmp_path, BuildrailConfig(provider="anthropic", artifact_root="new"))

    assert load_config(tmp_path) == BuildrailConfig(provider="anthropic", artifact_root="new")


def test_write_config_omits_absent_optional_fields(tmp_path: Path) -> None:
    write_config(tmp_path, BuildrailConfig(provider=None, artifact_root="artifacts"))

    text = (tmp_path / "buildrail.toml").read_text(encoding="utf-8")
    assert "provider" not in text
    assert "anthropic_model" not in text


def test_write_config_leaves_no_leftover_temp_files(tmp_path: Path) -> None:
    write_config(tmp_path, BuildrailConfig(provider="fake", artifact_root="artifacts"))

    remaining = list(tmp_path.iterdir())
    assert remaining == [tmp_path / "buildrail.toml"]


def test_write_config_escapes_quotes_and_backslashes_in_string_values(tmp_path: Path) -> None:
    tricky = 'weird"value\\with\\backslashes'
    config = BuildrailConfig(provider="fake", artifact_root=tricky)

    write_config(tmp_path, config)

    assert load_config(tmp_path).artifact_root == tricky


def test_ensure_artifact_root_within_project_accepts_a_relative_path(tmp_path: Path) -> None:
    ensure_artifact_root_within_project(tmp_path, "artifacts")
    ensure_artifact_root_within_project(tmp_path, "nested/artifacts")


def test_ensure_artifact_root_within_project_rejects_parent_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="within the project"):
        ensure_artifact_root_within_project(tmp_path, "../outside")


def test_ensure_artifact_root_within_project_rejects_an_absolute_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="within the project"):
        ensure_artifact_root_within_project(tmp_path, str(tmp_path.parent))
