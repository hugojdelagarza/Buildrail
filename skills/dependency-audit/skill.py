"""The dependency-audit skill: deterministically audits a Python repository's
declared dependencies (pyproject.toml, requirements*.txt) and cross-references
them against locally observed imports.

Provider-free — never imports or references buildrail.providers, and never
receives a real ProviderGateway. Makes no network requests, never executes
analyzed code or pip/poetry/uv, and never claims CVE/security coverage: this
is a structural declaration audit, not a vulnerability scanner.
"""

import json
from pathlib import Path

from buildrail.analysis import AnalysisError, analysis_from_dict
from buildrail.dependencies import DeclaredDependency, DependencyAudit, audit_dependencies, to_dict
from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse


def run(request: SkillRequest, provider: object | None) -> SkillResponse:
    """Audit the requested repository's dependencies and produce a dependency-audit artifact."""
    repository_path = request.inputs.get("repository_path")
    if not repository_path:
        return SkillResponse(status="failure", outputs={}, error="No repository_path provided.")

    analysis_json_path = request.inputs.get("analysis_json")
    try:
        analysis = None
        if analysis_json_path:
            data = json.loads(Path(analysis_json_path).read_text(encoding="utf-8"))
            analysis = analysis_from_dict(data)
        audit = audit_dependencies(Path(repository_path), analysis=analysis)
    except (AnalysisError, OSError, json.JSONDecodeError, KeyError) as exc:
        return SkillResponse(
            status="failure", outputs={}, error=f"Could not audit dependencies: {exc}"
        )

    summary_output = SkillOutput(
        content=_build_summary(audit),
        artifact_type="dependency-audit",
        display_name="dependency-audit-summary",
    )
    audit_output = SkillOutput(
        content=json.dumps(to_dict(audit), indent=2, sort_keys=True) + "\n",
        artifact_type="dependency-audit",
        content_type="application/json",
        display_name="dependency-audit-data",
    )
    return SkillResponse(
        status="success", outputs={"summary": summary_output, "audit": audit_output}
    )


def _build_summary(audit: DependencyAudit) -> str:
    lines: list[str] = [f"# Dependency Audit: {audit.repository_name}", ""]
    lines.extend(_summary_section(audit))
    lines.extend(_sources_section(audit))
    lines.extend(_group_section(audit, "Runtime Dependencies", "runtime"))
    lines.extend(_group_section(audit, "Development Dependencies", "dev"))
    lines.extend(_optional_groups_section(audit))
    lines.extend(_special_section(audit))
    lines.extend(_duplicates_section(audit))
    lines.extend(_conflicts_section(audit))
    lines.extend(_mismatches_section(audit))
    lines.extend(_warnings_section(audit))
    lines.extend(_limitations_section())
    return "\n".join(lines).rstrip() + "\n"


def _summary_section(audit: DependencyAudit) -> list[str]:
    total = len(audit.dependencies)
    runtime = sum(1 for d in audit.dependencies if d.group == "runtime")
    dev = sum(1 for d in audit.dependencies if d.group == "dev")
    optional = total - runtime - dev
    pinned = sum(1 for d in audit.dependencies if d.is_pinned)
    special = sum(1 for d in audit.dependencies if d.is_vcs or d.is_url or d.is_local_path)
    unpinned = total - pinned - special
    lines = [
        "## Summary",
        "",
        f"- Total declarations: {total}",
        f"- Runtime: {runtime}, Development: {dev}, Optional groups: {optional}",
        f"- Pinned (exact version): {pinned}, Unpinned: {unpinned}, Local/VCS/URL: {special}",
        f"- Duplicate declarations: {len(audit.duplicates)}",
        f"- Constraint conflicts: {len(audit.conflicts)}",
        f"- Declaration/import mismatches: {len(audit.mismatches)}",
    ]
    if audit.build_backend:
        lines.append(f"- Build backend: `{audit.build_backend}`")
    lines.append("")
    return lines


def _sources_section(audit: DependencyAudit) -> list[str]:
    lines = ["## Dependency Sources", ""]
    if not audit.sources:
        lines.append("_No dependency declaration files found._")
        lines.append("")
        return lines
    for source in audit.sources:
        lines.append(f"- `{source}`")
    lines.append("")
    return lines


def _format_dependency(dep: DeclaredDependency) -> str:
    parts = [f"`{dep.raw}`"]
    tags = []
    if dep.is_pinned:
        tags.append("pinned")
    if dep.is_editable:
        tags.append("editable")
    if dep.is_vcs:
        tags.append("vcs")
    if dep.is_url:
        tags.append("url")
    if dep.is_local_path:
        tags.append("local path")
    if tags:
        parts.append(f"({', '.join(tags)})")
    parts.append(f"— {dep.source}")
    return " ".join(parts)


def _group_section(audit: DependencyAudit, title: str, group: str) -> list[str]:
    deps = [d for d in audit.dependencies if d.group == group]
    lines = [f"## {title}", ""]
    if not deps:
        lines.append("_None declared._")
        lines.append("")
        return lines
    for dep in deps:
        lines.append(f"- {_format_dependency(dep)}")
    lines.append("")
    return lines


def _optional_groups_section(audit: DependencyAudit) -> list[str]:
    group_names = sorted({d.group for d in audit.dependencies if d.group not in ("runtime", "dev")})
    if not group_names:
        return []
    lines = ["## Optional Dependency Groups", ""]
    for group_name in group_names:
        lines.append(f"### `{group_name}`")
        for dep in audit.dependencies:
            if dep.group == group_name:
                lines.append(f"- {_format_dependency(dep)}")
        lines.append("")
    return lines


def _special_section(audit: DependencyAudit) -> list[str]:
    special = [d for d in audit.dependencies if d.is_vcs or d.is_url or d.is_local_path]
    if not special:
        return []
    lines = ["## Local / VCS / URL Dependencies", ""]
    for dep in special:
        lines.append(f"- {_format_dependency(dep)}")
    lines.append("")
    return lines


def _duplicates_section(audit: DependencyAudit) -> list[str]:
    lines = ["## Duplicate Declarations", ""]
    if not audit.duplicates:
        lines.append("_None found._")
        lines.append("")
        return lines
    for duplicate in audit.duplicates:
        lines.append(f"- `{duplicate.name}`:")
        for occurrence in duplicate.occurrences:
            lines.append(f"  - {occurrence}")
    lines.append("")
    return lines


def _conflicts_section(audit: DependencyAudit) -> list[str]:
    lines = ["## Constraint Conflicts", ""]
    if not audit.conflicts:
        lines.append("_None found._")
        lines.append("")
        return lines
    for conflict in audit.conflicts:
        constraints = ", ".join(f"`{c}`" for c in conflict.constraints)
        lines.append(f"- `{conflict.name}`: {constraints} — {conflict.note}")
    lines.append("")
    return lines


def _mismatches_section(audit: DependencyAudit) -> list[str]:
    lines = ["## Possible Declaration / Import Mismatches", ""]
    if not audit.mismatches:
        lines.append("_None found._")
        lines.append("")
        return lines
    declared_not_observed = [m for m in audit.mismatches if m.kind == "declared_not_observed"]
    imported_not_declared = [m for m in audit.mismatches if m.kind == "imported_not_declared"]
    if declared_not_observed:
        lines.append("### Declared but not observed in imports")
        lines.append("")
        for mismatch in declared_not_observed:
            lines.append(f"- `{mismatch.name}` — {mismatch.note}")
        lines.append("")
    if imported_not_declared:
        lines.append("### Imported but no obvious declared dependency")
        lines.append("")
        for mismatch in imported_not_declared:
            lines.append(f"- `{mismatch.name}` — {mismatch.note}")
        lines.append("")
    return lines


def _warnings_section(audit: DependencyAudit) -> list[str]:
    lines = ["## Warnings", ""]
    if not audit.warnings:
        lines.append("_No warnings._")
        lines.append("")
        return lines
    for warning in audit.warnings:
        lines.append(f"- [{warning.kind}] `{warning.path}`: {warning.message}")
    lines.append("")
    return lines


def _limitations_section() -> list[str]:
    return [
        "## Limitations",
        "",
        "- This is a declaration audit, not a vulnerability/CVE scanner — it does not "
        "check any package against a security database.",
        "- Only PEP 621 `[project]` dependencies are parsed from `pyproject.toml`; "
        "Poetry's `[tool.poetry]` layout is detected and noted, not parsed.",
        "- Only exact-pin conflicts (`==x` vs `==y`) are detected; overlapping version "
        "ranges are not evaluated.",
        "- Import name and distribution name are not always identical, so "
        "declaration/import mismatches are conservative observations, not confident "
        "unused/missing claims.",
        "",
    ]
