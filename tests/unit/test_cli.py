from unittest.mock import Mock

import pytest

import buildrail.cli as cli_module
from buildrail.cli import main
from buildrail.core import Result


def test_main_prints_expected_output_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main()

    captured = capsys.readouterr()
    assert captured.out == "Buildrail initialized.\n"
    assert exit_code == 0


def test_main_delegates_to_core_engine_and_reflects_its_result(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_engine = Mock()
    fake_engine.run.return_value = Result(success=False, message="fake failure")
    monkeypatch.setattr(cli_module, "CoreEngine", lambda: fake_engine)

    exit_code = main()

    captured = capsys.readouterr()
    assert captured.out == "fake failure\n"
    assert exit_code == 1
