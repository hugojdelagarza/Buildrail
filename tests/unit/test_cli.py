from pathlib import Path
from unittest.mock import Mock

import pytest

import buildrail.cli as cli_module
from buildrail.cli import main
from buildrail.core import Result


def test_main_prints_expected_output_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert captured.out == "Buildrail initialized.\n"
    assert exit_code == 0


def test_main_delegates_to_core_engine_and_reflects_its_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_engine = Mock()
    fake_engine.run.return_value = Result(success=False, message="fake failure")
    monkeypatch.setattr(cli_module, "CoreEngine", lambda: fake_engine)

    exit_code = main([])

    captured = capsys.readouterr()
    assert captured.out == "fake failure\n"
    assert exit_code == 1


def test_config_validate_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["config", "validate"])

    captured = capsys.readouterr()
    assert captured.out == "Configuration is valid.\n"
    assert captured.err == ""
    assert exit_code == 0


def test_config_validate_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["config", "validate"])

    captured = capsys.readouterr()
    assert "No configuration file found" in captured.out
    assert captured.err == ""
    assert exit_code == 1


def test_provider_check_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["provider", "check"])

    captured = capsys.readouterr()
    assert "fake" in captured.out.lower()
    assert captured.err == ""
    assert exit_code == 0


def test_provider_check_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["provider", "check"])

    captured = capsys.readouterr()
    assert "No configuration file found" in captured.out
    assert captured.err == ""
    assert exit_code == 1
