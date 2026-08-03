from pathlib import Path

from buildrail.core import CoreEngine, Result


def test_run_returns_a_successful_placeholder_result() -> None:
    engine = CoreEngine()

    result = engine.run()

    assert isinstance(result, Result)
    assert result.success is True
    assert result.message == "Buildrail initialized."


def test_validate_config_returns_success_result(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.validate_config(tmp_path)

    assert result.success is True
    assert result.message == "Configuration is valid."


def test_validate_config_returns_failure_result_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.validate_config(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message


def test_check_provider_returns_success_result_for_fake_provider(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    engine = CoreEngine()

    result = engine.check_provider(tmp_path)

    assert result.success is True
    assert "fake" in result.message.lower()


def test_check_provider_returns_failure_result_when_config_missing(tmp_path: Path) -> None:
    engine = CoreEngine()

    result = engine.check_provider(tmp_path)

    assert result.success is False
    assert "No configuration file found" in result.message
