import subprocess
import sys
from pathlib import Path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_release_notes_succeeds_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "-q", "-m", "chore: initial commit")
    _git(tmp_path, "tag", "v0.1.0")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")
    _git(tmp_path, "add", "b.txt")
    _git(tmp_path, "commit", "-q", "-m", "feat: add a feature")

    result = subprocess.run(
        [sys.executable, "-m", "buildrail", "release-notes"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert (tmp_path / "artifacts").is_dir()
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    notes_files = list(run_dirs[0].glob("001-release-notes-*.md"))
    assert len(notes_files) == 1
    content = notes_files[0].read_text(encoding="utf-8")
    assert "## Features" in content
    assert "add a feature" in content
