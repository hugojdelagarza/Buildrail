"""End-to-end test for `buildrail hooks install`.

Runs the real CLI against a freshly created temporary Git repository —
never against this actual repository — and inspects the resulting hook
script on disk.
"""

import subprocess
import sys
from pathlib import Path


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_hooks_install_writes_a_working_managed_hook(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")

    result = subprocess.run(
        [sys.executable, "-m", "buildrail", "hooks", "install"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Installed" in result.stdout

    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook_path.is_file()
    content = hook_path.read_text(encoding="utf-8")
    assert content.startswith("#!/bin/sh")
    assert "# BEGIN BUILDRAIL MANAGED BLOCK" in content
    assert "buildrail verify" in content
    assert "# END BUILDRAIL MANAGED BLOCK" in content
