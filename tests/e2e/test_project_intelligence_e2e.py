"""End-to-end tests for `buildrail explain`, `buildrail docs generate`,
`buildrail diagram generate`, and `buildrail run project-intelligence`.

Runs the real CLI as a subprocess against small, self-contained temporary
Python repositories — never this repository's own (large) source tree,
never a live Anthropic request.
"""

import json
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "buildrail", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _sample_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "buildrail.toml").write_text('artifact_root = "artifacts"\n', encoding="utf-8")
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (root / "app" / "main.py").write_text(
        '"""Entry point."""\n\n\ndef run():\n    pass\n', encoding="utf-8"
    )


def test_explain_end_to_end(tmp_path: Path) -> None:
    _sample_repo(tmp_path)

    result = _run(["explain"], tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    assert "Architecture summary written to" in result.stdout


def test_docs_generate_end_to_end(tmp_path: Path) -> None:
    _sample_repo(tmp_path)

    result = _run(["docs", "generate"], tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    names = {p.name for p in run_dirs[0].glob("*.md")}
    assert any("project_overview" in n for n in names)
    assert any("module_reference" in n for n in names)
    assert any("development_guide" in n for n in names)


def test_diagram_generate_end_to_end(tmp_path: Path) -> None:
    _sample_repo(tmp_path)

    result = _run(["diagram", "generate"], tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""
    run_dirs = list((tmp_path / "artifacts").iterdir())
    diagram_files = list(run_dirs[0].glob("*diagram*.md"))
    assert len(diagram_files) == 1
    assert "```mermaid" in diagram_files[0].read_text(encoding="utf-8")


def test_run_project_intelligence_end_to_end_and_artifacts_are_inspectable(
    tmp_path: Path,
) -> None:
    _sample_repo(tmp_path)

    pipeline_result = _run(["run", "project-intelligence"], tmp_path)
    assert pipeline_result.returncode == 0, pipeline_result.stdout + pipeline_result.stderr
    assert "Status: PASSED" in pipeline_result.stdout

    run_dirs = list((tmp_path / "artifacts").iterdir())
    assert len(run_dirs) == 1
    run_id = run_dirs[0].name

    inspect_run = _run(["runs", "inspect", run_id], tmp_path)
    assert inspect_run.returncode == 0, inspect_run.stdout + inspect_run.stderr
    assert "pipeline: project-intelligence" in inspect_run.stdout
    assert "step: explain-project" in inspect_run.stdout
    assert "step: generate-docs" in inspect_run.stdout
    assert "step: generate-diagram" in inspect_run.stdout

    meta_files = sorted(run_dirs[0].glob("*.meta.json"))
    assert len(meta_files) == 6
    first_artifact_id = json.loads(meta_files[0].read_text(encoding="utf-8"))["id"]
    inspect_artifact = _run(["artifacts", "inspect", first_artifact_id], tmp_path)
    assert inspect_artifact.returncode == 0, inspect_artifact.stdout + inspect_artifact.stderr
    assert "pipeline: project-intelligence" in inspect_artifact.stdout


def test_explain_handles_a_path_containing_spaces(tmp_path: Path) -> None:
    repo = tmp_path / "my project"
    _sample_repo(repo)

    result = _run(["explain"], repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == ""


def test_explain_reports_syntax_errors_as_warnings_without_crashing(tmp_path: Path) -> None:
    _sample_repo(tmp_path)
    (tmp_path / "broken.py").write_text("def foo(:\n", encoding="utf-8")

    result = _run(["explain"], tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    run_dirs = list((tmp_path / "artifacts").iterdir())
    summary = next(run_dirs[0].glob("*architecture-summary-summary.md"))
    content = summary.read_text(encoding="utf-8")
    assert "syntax_error" in content
