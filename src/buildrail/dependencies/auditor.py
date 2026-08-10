"""Deterministic, offline dependency auditing for a Python repository.

Parses `pyproject.toml` ([project.dependencies] / [project.optional-dependencies],
PEP 621 only — Poetry's [tool.poetry] layout is detected and noted, not parsed)
and `requirements*.txt` files with a small stdlib-only PEP 508 line parser —
never `pip`, never `packaging`, never a network call. Cross-references
declared names against third-party imports observed via `buildrail.analysis`'s
existing AST-based file discovery (which already excludes venvs/build output
and never follows a symlink outside the repository).

This is NOT a vulnerability scanner: it reports structural repository facts
only, never CVE/security claims.
"""

import ast
import re
import sys
import tomllib
from pathlib import Path

from buildrail.analysis import AnalysisError, ProjectAnalysis, analyze_project
from buildrail.dependencies.models import (
    SCHEMA_VERSION,
    ConstraintConflict,
    DeclaredDependency,
    DependencyAudit,
    DependencyAuditWarning,
    DuplicateDeclaration,
    ImportMismatch,
)

__all__ = ["audit_dependencies", "AnalysisError"]

_VCS_PREFIXES = ("git+", "hg+", "svn+", "bzr+")
_DEV_GROUP_TOKENS = ("dev", "development", "test", "tests")
_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")
_EXTRAS_RE = re.compile(r"^\[([^\]]*)\]")
_EXACT_PIN_RE = re.compile(r"^==\s*[^,;\s]+$")
_EGG_FRAGMENT_RE = re.compile(r"#egg=([A-Za-z0-9._-]+)")
_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def audit_dependencies(root: Path, *, analysis: ProjectAnalysis | None = None) -> DependencyAudit:
    """Audit the declared dependencies of the repository at `root`.

    Reuses `analyze_project` (or an already-computed `analysis`, to share one
    analysis across a pipeline the way `explain-project` does) both for its
    repository-identity fields and for the safety-checked file list used to
    scan for third-party imports.
    """
    if analysis is None:
        analysis = analyze_project(root)
    repo_root = Path(analysis.repository_root)

    sources: list[str] = []
    dependencies: list[DeclaredDependency] = []
    warnings: list[DependencyAuditWarning] = []
    build_backend: str | None = None

    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.is_file():
        sources.append("pyproject.toml")
        deps, build_backend, parse_warnings = _parse_pyproject(pyproject_path, repo_root)
        dependencies.extend(deps)
        warnings.extend(parse_warnings)

    visited: set[Path] = set()
    for req_path in sorted(repo_root.glob("requirements*.txt")):
        if not req_path.is_file():
            continue
        sources.append(req_path.relative_to(repo_root).as_posix())
        group = _group_for_requirements_file(req_path.name)
        deps, parse_warnings = _parse_requirements_file(
            req_path, repo_root, group=group, visited=visited
        )
        dependencies.extend(deps)
        warnings.extend(parse_warnings)

    duplicates, conflicts = _find_duplicates_and_conflicts(dependencies)
    third_party_imports = _collect_third_party_imports(analysis, repo_root)
    mismatches = _compare_declared_and_imported(dependencies, third_party_imports)

    return DependencyAudit(
        schema_version=SCHEMA_VERSION,
        repository_name=analysis.repository_name,
        repository_root=analysis.repository_root,
        build_backend=build_backend,
        sources=tuple(sources),
        dependencies=tuple(dependencies),
        duplicates=tuple(duplicates),
        conflicts=tuple(conflicts),
        mismatches=tuple(mismatches),
        observed_third_party_imports=tuple(sorted(third_party_imports)),
        warnings=tuple(warnings),
    )


# --------------------------------------------------------------------------
# pyproject.toml
# --------------------------------------------------------------------------


def _parse_pyproject(
    path: Path, repo_root: Path
) -> tuple[list[DeclaredDependency], str | None, list[DependencyAuditWarning]]:
    rel_source = path.relative_to(repo_root).as_posix()
    warnings: list[DependencyAuditWarning] = []
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        warnings.append(
            DependencyAuditWarning(kind="parse_error", path=rel_source, message=str(exc))
        )
        return [], None, warnings

    build_backend = None
    build_system = raw.get("build-system")
    if isinstance(build_system, dict):
        backend = build_system.get("build-backend")
        if isinstance(backend, str):
            build_backend = backend

    project = raw.get("project")
    deps: list[DeclaredDependency] = []
    if not isinstance(project, dict):
        tool = raw.get("tool")
        if isinstance(tool, dict) and isinstance(tool.get("poetry"), dict):
            warnings.append(
                DependencyAuditWarning(
                    kind="unsupported_format",
                    path=rel_source,
                    message="Poetry-style [tool.poetry] dependencies are not parsed in this "
                    "milestone; only PEP 621 [project] dependencies are supported.",
                )
            )
        return deps, build_backend, warnings

    for item in project.get("dependencies", []) or []:
        dep, warning = _build_dependency(item, group="runtime", source=rel_source)
        if warning:
            warnings.append(warning)
        if dep:
            deps.append(dep)

    optional = project.get("optional-dependencies")
    if isinstance(optional, dict):
        for group_name, items in optional.items():
            if not isinstance(items, list):
                continue
            group = "dev" if str(group_name).lower() in _DEV_GROUP_TOKENS else str(group_name)
            for item in items:
                dep, warning = _build_dependency(
                    item, group=group, source=rel_source, context=f"[{group_name}]"
                )
                if warning:
                    warnings.append(warning)
                if dep:
                    deps.append(dep)

    return deps, build_backend, warnings


def _build_dependency(
    item: object, *, group: str, source: str, context: str = ""
) -> tuple[DeclaredDependency | None, DependencyAuditWarning | None]:
    if not isinstance(item, str):
        return None, DependencyAuditWarning(
            kind="malformed_dependency",
            path=source,
            message=f"non-string dependency entry {context}: {item!r}".strip(),
        )
    spec = _parse_requirement_spec(item)
    if spec is None:
        return None, DependencyAuditWarning(
            kind="malformed_dependency",
            path=source,
            message=f"could not parse requirement {context}: {item!r}".strip(),
        )
    return (
        DeclaredDependency(
            name=spec.name,
            raw=item.strip(),
            group=group,
            source=source,
            version_constraint=spec.constraint,
            is_pinned=_is_pinned(spec),
            is_vcs=spec.is_vcs,
            is_url=spec.is_url,
            is_editable=False,
            is_local_path=spec.is_local_path,
        ),
        None,
    )


# --------------------------------------------------------------------------
# requirements*.txt
# --------------------------------------------------------------------------


def _group_for_requirements_file(filename: str) -> str:
    stem = filename[:-4] if filename.lower().endswith(".txt") else filename
    stem_lower = stem.lower()
    if stem_lower == "requirements":
        return "runtime"
    if any(token in stem_lower for token in _DEV_GROUP_TOKENS):
        return "dev"
    cleaned = re.sub(r"requirements?", "", stem_lower).strip("-_")
    return cleaned or "runtime"


def _strip_inline_comment(line: str) -> str:
    if line.lstrip().startswith("#"):
        return ""
    idx = line.find(" #")
    return line[:idx] if idx != -1 else line


def _parse_requirements_file(
    path: Path, repo_root: Path, *, group: str, visited: set[Path]
) -> tuple[list[DeclaredDependency], list[DependencyAuditWarning]]:
    deps: list[DeclaredDependency] = []
    warnings: list[DependencyAuditWarning] = []
    resolved = path.resolve()
    if resolved in visited:
        return deps, warnings
    visited.add(resolved)

    rel_source = path.relative_to(repo_root).as_posix()
    try:
        raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        warnings.append(
            DependencyAuditWarning(kind="parse_error", path=rel_source, message=str(exc))
        )
        return deps, warnings

    resolved_root = repo_root.resolve()
    for raw_line in raw_lines:
        line = _strip_inline_comment(raw_line).strip()
        if not line:
            continue

        if line.startswith(("-r ", "--requirement ")):
            target = line.split(None, 1)[1].strip()
            target_path = (path.parent / target).resolve()
            try:
                target_path.relative_to(resolved_root)
            except ValueError:
                warnings.append(
                    DependencyAuditWarning(
                        kind="unresolved_reference",
                        path=rel_source,
                        message=f"-r target '{target}' is outside the repository; skipped.",
                    )
                )
                continue
            if target_path.is_file():
                nested_deps, nested_warnings = _parse_requirements_file(
                    target_path, repo_root, group=group, visited=visited
                )
                deps.extend(nested_deps)
                warnings.extend(nested_warnings)
            else:
                warnings.append(
                    DependencyAuditWarning(
                        kind="unresolved_reference",
                        path=rel_source,
                        message=f"-r target '{target}' was not found.",
                    )
                )
            continue

        editable = False
        if line.startswith(("-e ", "--editable ")):
            editable = True
            line = line.split(None, 1)[1].strip()
        if line.startswith("-"):
            continue  # another pip option (--index-url, -c, ...) — not a dependency

        spec = _parse_requirement_spec(line)
        if spec is None:
            warnings.append(
                DependencyAuditWarning(
                    kind="malformed_dependency",
                    path=rel_source,
                    message=f"could not parse requirement line: {raw_line.strip()!r}",
                )
            )
            continue

        deps.append(
            DeclaredDependency(
                name=spec.name,
                raw=line,
                group=group,
                source=rel_source,
                version_constraint=spec.constraint,
                is_pinned=False if editable else _is_pinned(spec),
                is_vcs=spec.is_vcs,
                is_url=spec.is_url,
                is_editable=editable,
                is_local_path=spec.is_local_path or (editable and not (spec.is_vcs or spec.is_url)),
            )
        )
    return deps, warnings


# --------------------------------------------------------------------------
# Shared PEP 508-ish requirement-spec parsing (stdlib only)
# --------------------------------------------------------------------------


class _ParsedSpec:
    __slots__ = ("name", "constraint", "is_vcs", "is_url", "is_local_path")

    def __init__(
        self, name: str, constraint: str | None, is_vcs: bool, is_url: bool, is_local_path: bool
    ) -> None:
        self.name = name
        self.constraint = constraint
        self.is_vcs = is_vcs
        self.is_url = is_url
        self.is_local_path = is_local_path


def _looks_like_location(text: str) -> bool:
    lowered = text.lower()
    if lowered.startswith(_VCS_PREFIXES):
        return True
    if lowered.startswith(("http://", "https://", "file://")):
        return True
    if text.startswith(("./", "../", "/", "~")):
        return True
    return bool(_DRIVE_PATH_RE.match(text))


def _classify_location(text: str) -> tuple[bool, bool, bool]:
    """Returns (is_vcs, is_url, is_local_path) for a location string."""
    lowered = text.lower()
    if lowered.startswith(_VCS_PREFIXES):
        return True, False, False
    if lowered.startswith(("http://", "https://")):
        return False, True, False
    return False, False, True  # file://, bare path, drive path


def _name_from_location(text: str) -> str:
    egg_match = _EGG_FRAGMENT_RE.search(text)
    if egg_match:
        return egg_match.group(1)
    without_fragment = text.split("#", 1)[0]
    path_part = without_fragment
    if "://" in path_part:
        scheme_end = path_part.find("://")
        at_positions = [i for i, c in enumerate(path_part) if c == "@" and i > scheme_end]
        if at_positions:
            path_part = path_part[: max(at_positions)]
    tail = re.split(r"[\\/]", path_part.rstrip("/\\"))[-1]
    tail = re.sub(r"\.(git|whl|tar\.gz|zip)$", "", tail)
    return tail or text


def _parse_requirement_spec(raw: str) -> _ParsedSpec | None:
    text = raw.strip()
    if not text:
        return None
    if ";" in text:
        text = text.split(";", 1)[0].strip()
    if not text:
        return None

    if _looks_like_location(text):
        is_vcs, is_url, is_local_path = _classify_location(text)
        return _ParsedSpec(_name_from_location(text), text, is_vcs, is_url, is_local_path)

    match = _NAME_RE.match(text)
    if not match:
        return None
    name = match.group(1)
    rest = text[match.end() :].strip()
    if rest.startswith("["):
        extras_match = _EXTRAS_RE.match(rest)
        if extras_match:
            rest = rest[extras_match.end() :].strip()
    if rest.startswith("@"):
        target = rest[1:].strip()
        is_vcs, is_url, is_local_path = _classify_location(target)
        return _ParsedSpec(name, target, is_vcs, is_url, is_local_path)
    return _ParsedSpec(name, rest or None, False, False, False)


def _is_pinned(spec: _ParsedSpec) -> bool:
    if spec.is_vcs or spec.is_url or spec.is_local_path or not spec.constraint:
        return False
    return bool(_EXACT_PIN_RE.match(spec.constraint.strip()))


# --------------------------------------------------------------------------
# Duplicates / conflicts
# --------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _find_duplicates_and_conflicts(
    deps: list[DeclaredDependency],
) -> tuple[list[DuplicateDeclaration], list[ConstraintConflict]]:
    by_name: dict[str, list[DeclaredDependency]] = {}
    for dep in deps:
        by_name.setdefault(_normalize_name(dep.name), []).append(dep)

    duplicates: list[DuplicateDeclaration] = []
    conflicts: list[ConstraintConflict] = []
    for normalized in sorted(by_name):
        group = by_name[normalized]
        if len(group) < 2:
            continue
        occurrences = tuple(f"{dep.source} ({dep.group}): {dep.raw}" for dep in group)
        duplicates.append(DuplicateDeclaration(name=group[0].name, occurrences=occurrences))

        pins = sorted(
            {dep.version_constraint for dep in group if dep.is_pinned and dep.version_constraint}
        )
        if len(pins) > 1:
            conflicts.append(
                ConstraintConflict(
                    name=group[0].name,
                    constraints=tuple(pins),
                    note="Multiple exact version pins disagree for this dependency.",
                )
            )
    return duplicates, conflicts


# --------------------------------------------------------------------------
# Import cross-reference
# --------------------------------------------------------------------------


def _collect_third_party_imports(analysis: ProjectAnalysis, repo_root: Path) -> set[str]:
    local_names = {module.dotted_name.split(".")[0] for module in analysis.modules}
    local_names |= {package.dotted_name.split(".")[0] for package in analysis.packages}
    stdlib_names = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)

    third_party: set[str] = set()
    for module in analysis.modules:
        file_path = repo_root / module.file_path
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top and top not in local_names and top not in stdlib_names:
                        third_party.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.level and node.level > 0:
                    continue
                if node.module:
                    top = node.module.split(".")[0]
                    if top and top not in local_names and top not in stdlib_names:
                        third_party.add(top)
    return third_party


def _compare_declared_and_imported(
    deps: list[DeclaredDependency], observed: set[str]
) -> list[ImportMismatch]:
    # Location-derived names (VCS/URL/local path) are excluded from the
    # comparison — they're a best-effort guess at a name, not a declared
    # distribution name, and including them would only add noise.
    declared = {_normalize_name(dep.name): dep.name for dep in deps if not _is_location_only(dep)}
    observed_normalized = {_normalize_name(name): name for name in observed}

    mismatches: list[ImportMismatch] = []
    for normalized, original in sorted(declared.items()):
        if normalized not in observed_normalized:
            mismatches.append(
                ImportMismatch(
                    name=original,
                    kind="declared_not_observed",
                    note="Not observed in analyzed imports (import name may differ from "
                    "distribution name; mapping uncertain).",
                )
            )
    for normalized, original in sorted(observed_normalized.items()):
        if normalized not in declared:
            mismatches.append(
                ImportMismatch(
                    name=original,
                    kind="imported_not_declared",
                    note="Possible undeclared dependency — mapping between import name and "
                    "distribution name is uncertain.",
                )
            )
    return mismatches


def _is_location_only(dep: DeclaredDependency) -> bool:
    return dep.is_vcs or dep.is_url or dep.is_local_path
