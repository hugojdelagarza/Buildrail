import subprocess
import sys
from pathlib import Path


def test_config_validate_succeeds_end_to_end(tmp_path: Path) -> None:
    (tmp_path / "buildrail.toml").write_text(
        'provider = "fake"\nartifact_root = "artifacts"\n', encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, "-m", "buildrail", "config", "validate"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "Configuration is valid."
    assert result.stderr == ""
