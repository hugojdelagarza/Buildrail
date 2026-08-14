import subprocess
from pathlib import Path

import pytest

from buildrail.testing import run_pytest


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_all_tests_pass(tmp_path: Path) -> None:
    _write(tmp_path / "test_x.py", "def test_ok():\n    assert True\n")

    report = run_pytest(tmp_path)

    assert report.status == "passed"
    assert report.exit_code == 0
    assert report.counts.total == 1
    assert report.counts.passed == 1
    assert report.counts.failed == 0
    assert report.failures == ()


def test_one_failure(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_x.py",
        "def test_ok():\n    assert True\n\ndef test_bad():\n    assert 1 == 2\n",
    )

    report = run_pytest(tmp_path)

    assert report.status == "failed"
    assert report.exit_code == 1
    assert report.counts.passed == 1
    assert report.counts.failed == 1
    assert len(report.failures) == 1
    assert report.failures[0].node_id == "test_x.py::test_bad"
    assert report.failures[0].outcome == "failed"
    assert "assert 1 == 2" in report.failures[0].message


def test_multiple_failures(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_x.py",
        "def test_a():\n    assert False\n\ndef test_b():\n    assert 1 == 2\n",
    )

    report = run_pytest(tmp_path)

    assert report.counts.failed == 2
    node_ids = {f.node_id for f in report.failures}
    assert node_ids == {"test_x.py::test_a", "test_x.py::test_b"}


def test_skipped_test(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_x.py",
        "import pytest\n\ndef test_skipped():\n    pytest.skip('nope')\n",
    )

    report = run_pytest(tmp_path)

    assert report.status == "passed"
    assert report.counts.skipped == 1
    assert report.counts.total == 1


def test_xfail(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_x.py",
        "import pytest\n\n@pytest.mark.xfail\ndef test_expected_fail():\n    assert False\n",
    )

    report = run_pytest(tmp_path)

    assert report.status == "passed"
    assert report.counts.xfailed == 1
    assert report.counts.failed == 0


def test_xpass(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_x.py",
        "import pytest\n\n@pytest.mark.xfail\ndef test_unexpected_pass():\n    assert True\n",
    )

    report = run_pytest(tmp_path)

    assert report.counts.xpassed == 1


def test_collection_error_from_import_failure(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_broken.py",
        "import this_module_does_not_exist_anywhere\n\ndef test_x():\n    assert True\n",
    )

    report = run_pytest(tmp_path)

    assert report.status == "collection_error"
    assert report.exit_code == 2
    assert report.counts.errors == 1
    assert len(report.collection_errors) == 1
    assert "ModuleNotFoundError" in report.collection_errors[0].message


def test_syntax_error_is_a_collection_error(tmp_path: Path) -> None:
    _write(tmp_path / "test_broken.py", "def test_x(:\n    pass\n")

    report = run_pytest(tmp_path)

    assert report.status == "collection_error"
    assert report.counts.errors == 1


def test_no_tests_collected(tmp_path: Path) -> None:
    _write(tmp_path / "conftest.py", "# no tests here\n")

    report = run_pytest(tmp_path)

    assert report.status == "no_tests_collected"
    assert report.exit_code == 5
    assert report.counts.total == 0


def test_pytest_executable_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("pytest not found")

    monkeypatch.setattr("subprocess.run", _raise)

    report = run_pytest(tmp_path)

    assert report.status == "unavailable"
    assert report.exit_code is None
    assert "pytest not found" in report.stderr_excerpt


def test_missing_pytest_module_is_reported_as_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["python", "-m", "pytest"],
            returncode=1,
            stdout="",
            stderr="C:\\python.exe: No module named pytest\n",
        )

    monkeypatch.setattr("subprocess.run", _fake_run)

    report = run_pytest(tmp_path)

    assert report.status == "unavailable"


def test_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=1.0)

    monkeypatch.setattr("subprocess.run", _raise)

    report = run_pytest(tmp_path, timeout=1.0)

    assert report.status == "timeout"
    assert report.exit_code is None
    assert report.counts.total == 0


def test_path_with_spaces(tmp_path: Path) -> None:
    project = tmp_path / "my project dir"
    project.mkdir()
    _write(project / "test_x.py", "def test_ok():\n    assert True\n")

    report = run_pytest(project)

    assert report.status == "passed"
    assert report.counts.passed == 1


def test_large_failure_message_is_truncated(tmp_path: Path) -> None:
    _write(
        tmp_path / "test_x.py",
        "def test_bad():\n    message = 'A' * 10000 + 'TAIL-MARKER'\n    assert False, message\n",
    )

    report = run_pytest(tmp_path)

    assert len(report.failures) == 1
    message = report.failures[0].message
    assert "TAIL-MARKER" in message
    assert "characters truncated" in message
    assert "A" * 10000 not in message


def test_large_stdout_is_truncated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    huge_stdout = "A" * 30_000 + "\nTAIL-MARKER\n1 passed in 0.01s\n"

    def _fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["pytest"], returncode=0, stdout=huge_stdout, stderr=""
        )

    monkeypatch.setattr("subprocess.run", _fake_run)

    report = run_pytest(tmp_path)

    assert len(report.stdout_excerpt) <= 8_100
    assert "TAIL-MARKER" in report.stdout_excerpt
    assert "A" * 30_000 not in report.stdout_excerpt
    # The summary line is still parsed correctly from the (truncated-safe) tail.
    assert report.counts.passed == 1
