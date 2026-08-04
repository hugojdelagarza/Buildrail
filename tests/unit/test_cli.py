import subprocess
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


def test_review_succeeds(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/x.py\n+++ b/x.py\n+new line\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["review", "--diff", str(diff_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "fake" in captured.out.lower()


def test_review_fails_without_traceback_when_diff_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    exit_code = main(["review", "--diff", "missing.patch"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No diff file found" in captured.out


def test_test_summary_succeeds_when_tests_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout="2 passed in 0.01s\n", stderr=""
        ),
    )

    exit_code = main(["test-summary"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "Test summary written to" in captured.out


def test_test_summary_succeeds_when_tests_fail(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(
            args=["pytest"],
            returncode=1,
            stdout="FAILED tests/test_x.py::test_y - boom\n1 failed\n",
            stderr="",
        ),
    )

    exit_code = main(["test-summary"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "fake" in captured.out.lower()


def test_test_summary_fails_without_traceback_when_config_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(["test-summary"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "No configuration file found" in captured.out


def test_skill_list_prints_both_built_in_skills(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["skill", "list"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "review-diff" in captured.out
    assert "test-summary" in captured.out


def test_skill_inspect_prints_manifest_details(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["skill", "inspect", "review-diff"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert "name: review-diff" in captured.out
    assert "protocol_version: 1.0" in captured.out


def test_skill_inspect_fails_without_traceback_for_unknown_skill(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["skill", "inspect", "does-not-exist"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err == ""
    assert "does-not-exist" in captured.out
