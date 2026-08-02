import pytest

from buildrail.cli import main


def test_main_prints_expected_output_and_succeeds(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main()

    captured = capsys.readouterr()
    assert captured.out == "Buildrail initialized.\n"
    assert exit_code == 0
