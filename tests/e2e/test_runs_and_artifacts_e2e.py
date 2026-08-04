"""End-to-end test for the artifact-browsing commands.

Creates a real artifact through `buildrail review` (FakeProvider, fully
offline), then inspects it through `buildrail runs list`, `buildrail runs
inspect`, and `buildrail artifacts inspect` — all as real subprocesses
against a temporary project.
"""

import subprocess
import sys
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "buildrail", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_runs_and_artifacts_browsing_after_a_real_review(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/example.py\n+++ b/example.py\n+print('hi')\n", encoding="utf-8")

    review_result = _run(["review", "--diff", str(diff_path)], tmp_path)
    assert review_result.returncode == 0

    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    run_id = run_dirs[0].name

    list_result = _run(["runs", "list"], tmp_path)
    assert list_result.returncode == 0
    assert run_id in list_result.stdout
    assert "types=review" in list_result.stdout

    inspect_run_result = _run(["runs", "inspect", run_id], tmp_path)
    assert inspect_run_result.returncode == 0
    assert f"run_id: {run_id}" in inspect_run_result.stdout
    assert "type: review" in inspect_run_result.stdout

    artifact_id = f"{run_id}/001-review-review"
    inspect_artifact_result = _run(["artifacts", "inspect", artifact_id], tmp_path)
    assert inspect_artifact_result.returncode == 0
    assert f"id: {artifact_id}" in inspect_artifact_result.stdout
    assert "checksum: sha256:" in inspect_artifact_result.stdout
    assert "--- payload ---" in inspect_artifact_result.stdout
