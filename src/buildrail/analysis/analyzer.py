"""Deterministic, offline analysis of a Python repository.

Uses only filesystem traversal, `ast.parse`, and lenient TOML/YAML reads of
`pyproject.toml`, `buildrail.toml`, and `skills/*/skill.yaml` — never regex
as the primary parser, never `import`/execution of analyzed code. Designed
for Python repositories generally; Buildrail-specific facts (skills,
pipelines, artifact types) are populated only when those files exist, and
are simply empty for a plain Python project.

Safety: rejects null bytes, resolves `root` once and refuses to descend
into directories outside it, and never follows a symlink (file or
directory) whose resolved target escapes `root`.
"""

import ast
import os
import tomllib
from pathlib import Path

import yaml

from buildrail.analysis.errors import AnalysisError
from buildrail.analysis.models import (
    SCHEMA_VERSION,
    AnalysisWarning,
    ClassInfo,
    CliCommand,
    EntryPoint,
    FunctionInfo,
    ModuleInfo,
    PackageNode,
    PipelineInfo,
    ProjectAnalysis,
    ProjectStatistics,
    ProjectTooling,
    SkillInfo,
    TestLayout,
)

_EXCLUDED_DIR_NAMES = frozenset(
    {
        "venv",
        "env",
        "ENV",
        "__pycache__",
        "artifacts",
        "build",
        "dist",
        "node_modules",
        "site-packages",
    }
)
_TEST_DIR_NAMES = frozenset({"tests", "test"})
_MANIFEST_FILENAME = "skill.yaml"


def analyze_project(root: Path) -> ProjectAnalysis:
    """Analyze one Python repository rooted at `root` and return its ProjectAnalysis."""
    if "\x00" in str(root):
        raise AnalysisError("Repository path contains a null byte.")
    try:
        resolved_root = root.resolve(strict=True)
    except OSError as exc:
        raise AnalysisError(f"Could not resolve repository path {root}: {exc}") from exc
    if not resolved_root.is_dir():
        raise AnalysisError(f"{resolved_root} is not a directory.")

    warnings: list[AnalysisWarning] = []
    files = _discover_python_files(resolved_root, warnings)

    module_map: dict[str, Path] = {}
    for file_path in files:
        module_map[_dotted_name(file_path)] = file_path
    local_prefixes = _local_prefixes(module_map)

    trees: dict[str, tuple[ast.Module, str, str]] = {}
    for dotted, file_path in module_map.items():
        rel_path = file_path.relative_to(resolved_root).as_posix()
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            warnings.append(
                AnalysisWarning(kind="unreadable_file", path=rel_path, message=str(exc))
            )
            continue
        try:
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError as exc:
            warnings.append(AnalysisWarning(kind="syntax_error", path=rel_path, message=str(exc)))
            continue
        trees[dotted] = (tree, rel_path, source)

    modules: list[ModuleInfo] = []
    for dotted in sorted(trees):
        tree, rel_path, source = trees[dotted]
        classes, functions = _top_level_definitions(tree)
        imports, import_warnings = _extract_imports(tree, dotted, local_prefixes, rel_path)
        warnings.extend(import_warnings)
        modules.append(
            ModuleInfo(
                dotted_name=dotted,
                file_path=rel_path,
                docstring=_first_line(ast.get_docstring(tree)),
                classes=tuple(classes),
                functions=tuple(functions),
                imports=tuple(sorted(imports)),
                lines=len(source.splitlines()),
            )
        )

    packages = _build_package_tree(module_map)
    cli_commands = _extract_cli_commands(trees)
    pipelines = _extract_pipelines(trees)
    test_layout = _build_test_layout(resolved_root, files)

    python_requires, build_system, entry_points, tooling = _read_pyproject(resolved_root)
    skills, skill_artifact_types = _read_skills(resolved_root, warnings)
    code_artifact_types = _extract_artifact_type_literals(trees)
    artifact_types = tuple(sorted(skill_artifact_types | code_artifact_types))

    statistics = ProjectStatistics(
        python_files=len(files),
        modules=len(modules),
        classes=sum(len(m.classes) for m in modules),
        functions=sum(len(m.functions) for m in modules),
        test_files=len(test_layout.test_files),
        lines_of_python=sum(m.lines for m in modules),
    )

    return ProjectAnalysis(
        schema_version=SCHEMA_VERSION,
        repository_name=resolved_root.name,
        repository_root=str(resolved_root),
        python_requires=python_requires,
        build_system=build_system,
        entry_points=entry_points,
        cli_commands=tuple(cli_commands),
        packages=packages,
        modules=tuple(modules),
        skills=skills,
        pipelines=pipelines,
        artifact_types=artifact_types,
        test_layout=test_layout,
        tooling=tooling,
        statistics=statistics,
        warnings=tuple(warnings),
    )


def suggested_reading_order(analysis: ProjectAnalysis) -> tuple[str, ...]:
    """Return module dotted names in a deterministic, entry-point-first reading order."""
    imports_by_module = {m.dotted_name: m.imports for m in analysis.modules}
    known = set(imports_by_module)

    starting_points: list[str] = []
    for entry in analysis.entry_points:
        module_part = entry.target.split(":", 1)[0]
        if module_part in known and module_part not in starting_points:
            starting_points.append(module_part)
    for command in analysis.cli_commands:
        source_module = command.source_module
        if (
            source_module is not None
            and source_module in known
            and source_module not in starting_points
        ):
            starting_points.append(source_module)
    if not starting_points:
        starting_points = sorted(known)

    visited: list[str] = []
    seen: set[str] = set()

    def _visit(dotted: str) -> None:
        if dotted in seen or dotted not in known:
            return
        seen.add(dotted)
        visited.append(dotted)
        for imported in sorted(imports_by_module.get(dotted, ())):
            _visit(imported)

    for start in starting_points:
        _visit(start)
    for remaining in sorted(known - seen):
        _visit(remaining)
    return tuple(visited)


def _discover_python_files(root: Path, warnings: list[AnalysisWarning]) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames if not d.startswith(".") and d not in _EXCLUDED_DIR_NAMES
        )
        current = Path(dirpath)
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            file_path = current / filename
            if file_path.is_symlink():
                try:
                    target = file_path.resolve(strict=True)
                except OSError:
                    continue
                if not target.is_relative_to(root):
                    continue
            files.append(file_path)
    return files


def _dotted_name(file_path: Path) -> str:
    stem = file_path.stem
    parts: list[str] = [] if stem == "__init__" else [stem]
    current = file_path.parent
    while (current / "__init__.py").is_file():
        parts.append(current.name)
        current = current.parent
    return ".".join(reversed(parts))


def _local_prefixes(module_map: dict[str, Path]) -> set[str]:
    prefixes: set[str] = set()
    for dotted in module_map:
        parts = dotted.split(".")
        for i in range(1, len(parts) + 1):
            prefixes.add(".".join(parts[:i]))
    return prefixes


def _first_line(docstring: str | None) -> str | None:
    if not docstring:
        return None
    first = docstring.strip().splitlines()[0].strip()
    return first or None


def _top_level_definitions(tree: ast.Module) -> tuple[list[ClassInfo], list[FunctionInfo]]:
    classes: list[ClassInfo] = []
    functions: list[FunctionInfo] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(
                ClassInfo(name=node.name, docstring=_first_line(ast.get_docstring(node)))
            )
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith(
            "_"
        ):
            functions.append(
                FunctionInfo(name=node.name, docstring=_first_line(ast.get_docstring(node)))
            )
    return classes, functions


def _extract_imports(
    tree: ast.Module, module_dotted: str, local_prefixes: set[str], rel_path: str
) -> tuple[set[str], list[AnalysisWarning]]:
    imports: set[str] = set()
    warnings: list[AnalysisWarning] = []
    package_dotted = module_dotted.rsplit(".", 1)[0] if "." in module_dotted else ""

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in local_prefixes:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                base_parts = package_dotted.split(".") if package_dotted else []
                up = node.level - 1
                if up > len(base_parts):
                    warnings.append(
                        AnalysisWarning(
                            kind="unresolved_import",
                            path=rel_path,
                            message=(
                                f"relative import '{'.' * node.level}{node.module or ''}' "
                                "goes above the repository root."
                            ),
                        )
                    )
                    continue
                base_parts = base_parts[: len(base_parts) - up] if up else base_parts
                base = ".".join(base_parts)
                if node.module:
                    target = f"{base}.{node.module}" if base else node.module
                    if target in local_prefixes:
                        imports.add(target)
                    else:
                        warnings.append(
                            AnalysisWarning(
                                kind="unresolved_import",
                                path=rel_path,
                                message=f"could not resolve relative import '{target}'.",
                            )
                        )
                else:
                    # `from . import name1, name2` — each name may be a submodule of
                    # `base`, or a symbol re-exported from `base`'s own __init__.py.
                    resolved_any = False
                    for alias in node.names:
                        candidate = f"{base}.{alias.name}" if base else alias.name
                        if candidate in local_prefixes:
                            imports.add(candidate)
                            resolved_any = True
                    if not resolved_any:
                        if base and base in local_prefixes:
                            imports.add(base)
                        else:
                            names = ", ".join(alias.name for alias in node.names)
                            warnings.append(
                                AnalysisWarning(
                                    kind="unresolved_import",
                                    path=rel_path,
                                    message=(
                                        f"could not resolve relative import "
                                        f"'{'.' * node.level}{{{names}}}'."
                                    ),
                                )
                            )
            elif node.module and node.module in local_prefixes:
                imports.add(node.module)
    return imports, warnings


def _build_package_tree(module_map: dict[str, Path]) -> tuple[PackageNode, ...]:
    package_names = {dotted for dotted, path in module_map.items() if path.stem == "__init__"}
    children: dict[str, set[str]] = {name: set() for name in package_names}
    subpackages: dict[str, set[str]] = {name: set() for name in package_names}

    for dotted, path in module_map.items():
        if path.stem == "__init__":
            continue
        parent = dotted.rsplit(".", 1)[0] if "." in dotted else ""
        if parent in children:
            children[parent].add(dotted)

    for name in package_names:
        parent = name.rsplit(".", 1)[0] if "." in name else ""
        if parent in subpackages:
            subpackages[parent].add(name)

    return tuple(
        PackageNode(
            dotted_name=name,
            modules=tuple(sorted(children[name])),
            subpackages=tuple(sorted(subpackages[name])),
        )
        for name in sorted(package_names)
    )


def _build_test_layout(root: Path, files: list[Path]) -> TestLayout:
    test_dirs: set[str] = set()
    test_files: list[str] = []
    for file_path in files:
        rel = file_path.relative_to(root)
        if any(part in _TEST_DIR_NAMES for part in rel.parts[:-1]):
            for i, part in enumerate(rel.parts[:-1]):
                if part in _TEST_DIR_NAMES:
                    test_dirs.add(Path(*rel.parts[: i + 1]).as_posix())
        if file_path.name.startswith("test_") or file_path.name.endswith("_test.py"):
            test_files.append(rel.as_posix())
    return TestLayout(
        test_directories=tuple(sorted(test_dirs)), test_files=tuple(sorted(test_files))
    )


def _read_pyproject(
    root: Path,
) -> tuple[str | None, str | None, tuple[EntryPoint, ...], ProjectTooling]:
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        return None, None, (), ProjectTooling(has_ruff=False, has_mypy=False, has_pytest=False)
    try:
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None, None, (), ProjectTooling(has_ruff=False, has_mypy=False, has_pytest=False)

    project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
    python_requires = project.get("requires-python")
    python_requires = python_requires if isinstance(python_requires, str) else None

    build_system_table = data.get("build-system", {})
    build_backend = (
        build_system_table.get("build-backend") if isinstance(build_system_table, dict) else None
    )
    build_backend = build_backend if isinstance(build_backend, str) else None

    scripts = project.get("scripts", {}) if isinstance(project.get("scripts"), dict) else {}
    entry_points = tuple(
        EntryPoint(name=name, target=target, kind="console_script")
        for name, target in sorted(scripts.items())
        if isinstance(target, str)
    )

    tool = data.get("tool", {}) if isinstance(data.get("tool"), dict) else {}
    tooling = ProjectTooling(
        has_ruff="ruff" in tool,
        has_mypy="mypy" in tool,
        has_pytest="pytest" in tool
        or any(
            p.name in _TEST_DIR_NAMES
            for p in root.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        ),
    )
    return python_requires, build_backend, entry_points, tooling


def _read_skills(
    root: Path, warnings: list[AnalysisWarning]
) -> tuple[tuple[SkillInfo, ...], set[str]]:
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return (), set()

    skills: list[SkillInfo] = []
    artifact_types: set[str] = set()
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        manifest_path = skill_dir / _MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue
        rel_path = manifest_path.relative_to(root).as_posix()
        try:
            raw_text = manifest_path.read_text(encoding="utf-8")
            raw = yaml.safe_load(raw_text)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            warnings.append(
                AnalysisWarning(kind="unreadable_file", path=rel_path, message=str(exc))
            )
            continue
        if not isinstance(raw, dict):
            warnings.append(
                AnalysisWarning(
                    kind="unreadable_file", path=rel_path, message="manifest is not a YAML mapping."
                )
            )
            continue

        name = raw.get("name")
        if not isinstance(name, str) or not name:
            continue
        outputs = raw.get("outputs", [])
        output_types = tuple(
            sorted(
                {
                    o["artifact_type"]
                    for o in outputs
                    if isinstance(o, dict) and isinstance(o.get("artifact_type"), str)
                }
            )
        )
        artifact_types.update(output_types)
        skills.append(
            SkillInfo(
                name=name,
                version=raw.get("version", "") if isinstance(raw.get("version"), str) else "",
                description=raw.get("description", "")
                if isinstance(raw.get("description"), str)
                else "",
                requires_provider=bool(raw.get("requires_provider", False)),
                artifact_types=output_types,
            )
        )
    return tuple(skills), artifact_types


def _extract_artifact_type_literals(trees: dict[str, tuple[ast.Module, str, str]]) -> set[str]:
    found: set[str] = set()
    for tree, _rel_path, _source in trees.values():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (
                        kw.arg == "artifact_type"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        found.add(kw.value.value)
    return found


def _find_prog_name(tree: ast.Module) -> str | None:
    """Return the literal `prog=` passed to `argparse.ArgumentParser(...)`, if any."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        is_argument_parser_call = (
            isinstance(func, ast.Attribute) and func.attr == "ArgumentParser"
        ) or (isinstance(func, ast.Name) and func.id == "ArgumentParser")
        if not is_argument_parser_call:
            continue
        for kw in node.keywords:
            if (
                kw.arg == "prog"
                and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
            ):
                return kw.value.value
    return None


def _extract_cli_commands(trees: dict[str, tuple[ast.Module, str, str]]) -> list[CliCommand]:
    commands: dict[str, CliCommand] = {}

    for dotted, (tree, _rel_path, _source) in trees.items():
        prog = _find_prog_name(tree)
        subparsers_owner: dict[str, str] = {}
        parser_command_name: dict[str, str] = {}
        parser_parent_subparsers: dict[str, str] = {}
        raw_leaves: list[tuple[str, str, str | None]] = []

        for node in ast.walk(tree):
            call: ast.Call
            target_name: str | None
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Call)
            ):
                call = node.value
                target_name = node.targets[0].id
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                target_name = None
            else:
                continue

            if not isinstance(call.func, ast.Attribute) or not isinstance(
                call.func.value, ast.Name
            ):
                continue
            owner_name = call.func.value.id
            attr = call.func.attr

            if attr == "add_subparsers" and target_name:
                subparsers_owner[target_name] = owner_name
            elif (
                attr == "add_parser"
                and call.args
                and isinstance(call.args[0], ast.Constant)
                and isinstance(call.args[0].value, str)
            ):
                name_literal = call.args[0].value
                description = None
                for kw in call.keywords:
                    if (
                        kw.arg == "help"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        description = kw.value.value
                if target_name:
                    parser_command_name[target_name] = name_literal
                    parser_parent_subparsers[target_name] = owner_name
                raw_leaves.append((owner_name, name_literal, description))

        for owner_name, name_literal, description in raw_leaves:
            path = _ancestor_path(
                owner_name, subparsers_owner, parser_command_name, parser_parent_subparsers
            ) + (name_literal,)
            command = f"{prog} {' '.join(path)}" if prog else " ".join(path)
            if command not in commands:
                commands[command] = CliCommand(
                    command=command, description=description, source_module=dotted
                )

    return sorted(commands.values(), key=lambda c: c.command)


def _ancestor_path(
    subparsers_var: str,
    subparsers_owner: dict[str, str],
    parser_command_name: dict[str, str],
    parser_parent_subparsers: dict[str, str],
    _seen: frozenset[str] = frozenset(),
) -> tuple[str, ...]:
    if subparsers_var in _seen:
        return ()
    owner_parser_var = subparsers_owner.get(subparsers_var)
    if owner_parser_var is None:
        return ()
    owner_name = parser_command_name.get(owner_parser_var)
    if owner_name is None:
        return ()
    grandparent = parser_parent_subparsers.get(owner_parser_var)
    if grandparent is None:
        return (owner_name,)
    return _ancestor_path(
        grandparent,
        subparsers_owner,
        parser_command_name,
        parser_parent_subparsers,
        _seen | {subparsers_var},
    ) + (owner_name,)


def _iter_in_source_order(node: ast.AST) -> "list[ast.AST]":
    """Pre-order DFS over an AST node's descendants, approximating source/execution order
    (unlike `ast.walk`, which is breadth-first and would scramble step ordering)."""
    ordered = [node]
    for child in ast.iter_child_nodes(node):
        ordered.extend(_iter_in_source_order(child))
    return ordered


def _collect_pipeline_steps(
    func: ast.FunctionDef, functions_by_name: dict[str, ast.FunctionDef], visited: set[str]
) -> list[str]:
    if func.name in visited:
        return []
    visited.add(func.name)
    steps: list[str] = []
    for call in _iter_in_source_order(func):
        if not isinstance(call, ast.Call):
            continue
        if isinstance(call.func, ast.Name) and call.func.id == "PipelineRunner":
            for kw in call.keywords:
                if kw.arg == "steps" and isinstance(kw.value, ast.Tuple | ast.List):
                    for element in kw.value.elts:
                        if isinstance(element, ast.Constant) and isinstance(element.value, str):
                            steps.append(element.value)
            continue
        called_name = None
        if isinstance(call.func, ast.Attribute):
            called_name = call.func.attr
        elif isinstance(call.func, ast.Name):
            called_name = call.func.id
        if called_name and called_name in functions_by_name:
            steps.extend(
                _collect_pipeline_steps(functions_by_name[called_name], functions_by_name, visited)
            )
    return steps


def _extract_pipelines(trees: dict[str, tuple[ast.Module, str, str]]) -> tuple[PipelineInfo, ...]:
    """Find `run_<name>` functions/methods and the ordered `PipelineRunner(steps=...)`
    literals reachable from them, following same-module helper calls one level deep
    (e.g. a `run_pre_commit` that delegates its second phase to `_run_pre_commit_review`)."""
    pipelines: dict[str, list[str]] = {}
    for tree, _rel_path, _source in trees.values():
        functions_by_name: dict[str, ast.FunctionDef] = {
            node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }

        for name, func in sorted(functions_by_name.items()):
            if not name.startswith("run_") or name == "run_":
                continue
            steps = _collect_pipeline_steps(func, functions_by_name, set())
            if steps:
                pipeline_name = name[len("run_") :].replace("_", "-")
                pipelines.setdefault(pipeline_name, steps)
    return tuple(
        PipelineInfo(name=name, steps=tuple(steps)) for name, steps in sorted(pipelines.items())
    )
