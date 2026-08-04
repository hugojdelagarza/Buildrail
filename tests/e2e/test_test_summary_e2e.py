import subprocess
import sys
from pathlib import Path


def test_test_summary_succeeds_end_to_end_when_tests_pass(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    (tmp_path / "test_sample.py").write_text(
        "def test_always_passes():\n    assert True\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, "-m", "buildrail", "test-summary"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert (tmp_path / "artifacts").is_dir()
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    summary_files = list(run_dirs[0].glob("001-test-summary-*.md"))
    assert len(summary_files) == 1
    assert "All tests passed" in summary_files[0].read_text(encoding="utf-8")


def test_test_summary_succeeds_end_to_end_when_a_test_fails(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    (tmp_path / "test_sample.py").write_text(
        "def test_fails():\n    assert False\n", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, "-m", "buildrail", "test-summary"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    run_dirs = list((tmp_path / "artifacts").iterdir())
    summary_files = list(run_dirs[0].glob("001-test-summary-*.md"))
    content = summary_files[0].read_text(encoding="utf-8")
    assert "[fake response]" in content
    assert "test_fails" in content
