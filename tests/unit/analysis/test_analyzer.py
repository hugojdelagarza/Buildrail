from pathlib import Path

import pytest

from buildrail.analysis import AnalysisError, EntryPoint, analyze_project


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_analyze_discovers_a_simple_package_and_its_module(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "mod.py", "def foo():\n    pass\n")

    analysis = analyze_project(tmp_path)

    assert {m.dotted_name for m in analysis.modules} == {"pkg", "pkg.mod"}
    package = next(p for p in analysis.packages if p.dotted_name == "pkg")
    assert package.modules == ("pkg.mod",)


def test_analyze_handles_src_layout_packages(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "app" / "__init__.py", "")
    _write(tmp_path / "src" / "app" / "main.py", "def run():\n    pass\n")

    analysis = analyze_project(tmp_path)

    assert "app.main" in {m.dotted_name for m in analysis.modules}
    assert "app" in {p.dotted_name for p in analysis.packages}


def test_analyze_reads_entry_points_and_python_requires_from_pyproject(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        '[project]\nname = "x"\nrequires-python = ">=3.11"\n\n'
        '[project.scripts]\nmytool = "app.main:run"\n',
    )
    _write(tmp_path / "app" / "__init__.py", "")
    _write(tmp_path / "app" / "main.py", "def run():\n    pass\n")

    analysis = analyze_project(tmp_path)

    assert analysis.python_requires == ">=3.11"
    assert analysis.entry_points == (
        EntryPoint(name="mytool", target="app.main:run", kind="console_script"),
    )


def test_analyze_resolves_local_absolute_import_relationships(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", "from pkg.b import thing\n")
    _write(tmp_path / "pkg" / "b.py", "thing = 1\n")

    analysis = analyze_project(tmp_path)

    module_a = next(m for m in analysis.modules if m.dotted_name == "pkg.a")
    assert module_a.imports == ("pkg.b",)


def test_analyze_resolves_local_relative_import_relationships(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", "from . import b\n")
    _write(tmp_path / "pkg" / "b.py", "thing = 1\n")

    analysis = analyze_project(tmp_path)

    module_a = next(m for m in analysis.modules if m.dotted_name == "pkg.a")
    assert module_a.imports == ("pkg.b",)


def test_analyze_warns_on_relative_import_above_repository_root(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", "from .. import outside\n")

    analysis = analyze_project(tmp_path)

    assert any(w.kind == "unresolved_import" for w in analysis.warnings)


def test_analyze_does_not_warn_on_external_absolute_imports(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "import os\nimport sys\n")

    analysis = analyze_project(tmp_path)

    assert analysis.warnings == ()


def test_analyze_extracts_public_classes_functions_and_docstrings(tmp_path: Path) -> None:
    _write(
        tmp_path / "mod.py",
        '"""Module doc."""\n\n\n'
        'class Foo:\n    """Foo doc."""\n\n\n'
        'def bar():\n    """Bar doc."""\n\n\n'
        "def _hidden():\n    pass\n",
    )

    analysis = analyze_project(tmp_path)

    module = analysis.modules[0]
    assert module.docstring == "Module doc."
    assert [c.name for c in module.classes] == ["Foo"]
    assert module.classes[0].docstring == "Foo doc."
    assert [f.name for f in module.functions] == ["bar"]
    assert module.functions[0].docstring == "Bar doc."


def test_analyze_reports_test_layout_and_statistics(tmp_path: Path) -> None:
    _write(tmp_path / "tests" / "test_foo.py", "def test_ok():\n    assert True\n")
    _write(tmp_path / "main.py", "x = 1\n")

    analysis = analyze_project(tmp_path)

    assert analysis.test_layout.test_directories == ("tests",)
    assert analysis.test_layout.test_files == ("tests/test_foo.py",)
    assert analysis.statistics.test_files == 1
    assert analysis.statistics.python_files == 2


def test_analyze_records_syntax_error_warning_and_skips_the_module(tmp_path: Path) -> None:
    _write(tmp_path / "broken.py", "def foo(:\n    pass\n")
    _write(tmp_path / "ok.py", "x = 1\n")

    analysis = analyze_project(tmp_path)

    assert any(w.kind == "syntax_error" and w.path == "broken.py" for w in analysis.warnings)
    assert {m.dotted_name for m in analysis.modules} == {"ok"}
    assert analysis.statistics.python_files == 2


def test_analyze_records_unreadable_file_warning_for_invalid_encoding(tmp_path: Path) -> None:
    (tmp_path / "bad_encoding.py").write_bytes(b"\xff\xfe\x00\x01\x02")

    analysis = analyze_project(tmp_path)

    assert any(w.kind == "unreadable_file" for w in analysis.warnings)


def test_analyze_excludes_venv_pycache_git_and_artifacts_directories(tmp_path: Path) -> None:
    _write(tmp_path / ".venv" / "lib" / "sitepkg.py", "x = 1\n")
    _write(tmp_path / "__pycache__" / "cached.py", "x = 1\n")
    _write(tmp_path / ".git" / "hooks" / "hook.py", "x = 1\n")
    _write(tmp_path / "artifacts" / "20260101-000000-abc" / "generated.py", "x = 1\n")
    _write(tmp_path / "real.py", "x = 1\n")

    analysis = analyze_project(tmp_path)

    assert {m.dotted_name for m in analysis.modules} == {"real"}


def test_analyze_ignores_symlinks_escaping_the_repository_root(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}_outside"
    outside.mkdir()
    _write(outside / "secret.py", "SECRET = 1\n")
    repo = tmp_path / "repo"
    _write(repo / "real.py", "x = 1\n")

    try:
        (repo / "escape.py").symlink_to(outside / "secret.py")
    except OSError:
        pytest.skip("Creating symlinks is not permitted in this environment.")

    analysis = analyze_project(repo)

    assert {m.dotted_name for m in analysis.modules} == {"real"}


def test_analyze_orders_modules_deterministically_by_dotted_name(tmp_path: Path) -> None:
    _write(tmp_path / "zeta.py", "x = 1\n")
    _write(tmp_path / "alpha.py", "x = 1\n")
    _write(tmp_path / "mid.py", "x = 1\n")

    analysis = analyze_project(tmp_path)

    assert [m.dotted_name for m in analysis.modules] == ["alpha", "mid", "zeta"]


def test_analyze_is_repeatable_and_produces_identical_results(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "a.py", "from pkg.b import x\n")
    _write(tmp_path / "pkg" / "b.py", "x = 1\n")

    first = analyze_project(tmp_path)
    second = analyze_project(tmp_path)

    assert first == second


def test_analyze_works_in_a_path_containing_spaces(tmp_path: Path) -> None:
    repo = tmp_path / "my project"
    _write(repo / "main.py", "def run():\n    pass\n")

    analysis = analyze_project(repo)

    assert analysis.modules[0].dotted_name == "main"
    assert analysis.repository_root == str(repo.resolve())


def test_analyze_raises_for_a_missing_path(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError):
        analyze_project(tmp_path / "does-not-exist")


def test_analyze_raises_for_a_null_byte_in_the_path(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError):
        analyze_project(Path(str(tmp_path) + "\x00evil"))


def test_analyze_raises_when_path_is_not_a_directory(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")

    with pytest.raises(AnalysisError):
        analyze_project(file_path)


def test_analyze_extracts_nested_cli_commands_using_the_declared_prog_name(tmp_path: Path) -> None:
    _write(
        tmp_path / "cli.py",
        "import argparse\n\n"
        "def build() -> argparse.ArgumentParser:\n"
        '    parser = argparse.ArgumentParser(prog="mytool")\n'
        '    subparsers = parser.add_subparsers(dest="command")\n'
        '    group_parser = subparsers.add_parser("group", help="A group.")\n'
        '    group_subparsers = group_parser.add_subparsers(dest="group_command")\n'
        '    group_subparsers.add_parser("action", help="An action.")\n'
        '    subparsers.add_parser("simple", help="A simple command.")\n'
        "    return parser\n",
    )

    analysis = analyze_project(tmp_path)

    commands = {c.command: c.description for c in analysis.cli_commands}
    assert commands["mytool group action"] == "An action."
    assert commands["mytool simple"] == "A simple command."


def test_analyze_omits_program_prefix_when_prog_is_not_declared(tmp_path: Path) -> None:
    _write(
        tmp_path / "cli.py",
        "import argparse\n\n"
        "parser = argparse.ArgumentParser()\n"
        'subparsers = parser.add_subparsers(dest="command")\n'
        'subparsers.add_parser("simple")\n',
    )

    analysis = analyze_project(tmp_path)

    assert analysis.cli_commands[0].command == "simple"


def test_analyze_discovers_pipeline_steps_across_a_helper_function(tmp_path: Path) -> None:
    _write(
        tmp_path / "engine.py",
        "class Engine:\n"
        "    def run_release(self, store):\n"
        '        PipelineRunner(None, store, steps=("build",)).run(None)\n'
        "        self._run_release_publish(store)\n\n"
        "    def _run_release_publish(self, store):\n"
        '        PipelineRunner(None, store, steps=("publish",)).run(None)\n',
    )

    analysis = analyze_project(tmp_path)

    assert len(analysis.pipelines) == 1
    pipeline = analysis.pipelines[0]
    assert pipeline.name == "release"
    assert pipeline.steps == ("build", "publish")


def test_analyze_discovers_skills_from_manifests(tmp_path: Path) -> None:
    _write(
        tmp_path / "skills" / "my-skill" / "skill.yaml",
        "name: my-skill\n"
        "version: 0.1.0\n"
        'description: "Does a thing."\n'
        "requires_provider: false\n"
        "outputs:\n"
        "  - name: out\n"
        "    artifact_type: my-artifact\n",
    )

    analysis = analyze_project(tmp_path)

    assert len(analysis.skills) == 1
    skill = analysis.skills[0]
    assert skill.name == "my-skill"
    assert skill.artifact_types == ("my-artifact",)
    assert analysis.artifact_types == ("my-artifact",)
