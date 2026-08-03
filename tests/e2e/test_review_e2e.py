import subprocess
import sys
from pathlib import Path


def test_review_succeeds_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )
    diff_path = tmp_path / "changes.patch"
    diff_path.write_text("--- a/example.py\n+++ b/example.py\n+print('hello')\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "buildrail", "review", "--diff", str(diff_path)],
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
    assert list(run_dirs[0].glob("001-review-*.md"))
