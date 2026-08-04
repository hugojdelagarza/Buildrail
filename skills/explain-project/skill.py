"""The explain-project skill: deterministically summarizes a Python repository's architecture.

Provider-free — never imports or references buildrail.providers, and never
receives a real ProviderGateway. Runs the shared, offline `buildrail.analysis`
analyzer and renders its ProjectAnalysis as one Markdown summary plus one
machine-readable JSON sidecar. Makes no architectural judgments ("bad
design", "dead code") beyond what the analyzer can prove deterministically.
"""

import json
from pathlib import Path

from buildrail.analysis import (
    AnalysisError,
    ProjectAnalysis,
    analysis_from_dict,
    analyze_project,
    suggested_reading_order,
    to_dict,
)
from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse


def run(request: SkillRequest, provider: object | None) -> SkillResponse:
    """Analyze the requested repository and produce an architecture-summary artifact."""
    repository_path = request.inputs.get("repository_path")
    if not repository_path:
        return SkillResponse(status="failure", outputs={}, error="No repository_path provided.")

    analysis_json_path = request.inputs.get("analysis_json")
    try:
        if analysis_json_path:
            data = json.loads(Path(analysis_json_path).read_text(encoding="utf-8"))
            analysis = analysis_from_dict(data)
        else:
            analysis = analyze_project(Path(repository_path))
    except (AnalysisError, OSError, json.JSONDecodeError, KeyError) as exc:
        return SkillResponse(
            status="failure", outputs={}, error=f"Could not analyze project: {exc}"
        )

    summary_output = SkillOutput(
        content=_build_summary(analysis),
        artifact_type="architecture-summary",
        display_name="architecture-summary",
    )
    analysis_output = SkillOutput(
        content=json.dumps(to_dict(analysis), indent=2, sort_keys=True) + "\n",
        artifact_type="architecture-summary",
        content_type="application/json",
        display_name="project-analysis",
    )
    return SkillResponse(
        status="success", outputs={"summary": summary_output, "analysis": analysis_output}
    )


def _build_summary(analysis: ProjectAnalysis) -> str:
    lines: list[str] = [f"# Architecture Summary: {analysis.repository_name}", ""]
    lines.extend(_overview_section(analysis))
    lines.extend(_entry_points_section(analysis))
    lines.extend(_package_map_section(analysis))
    lines.extend(_cli_commands_section(analysis))
    lines.extend(_definitions_section(analysis))
    lines.extend(_skills_section(analysis))
    lines.extend(_pipelines_section(analysis))
    lines.extend(_artifact_types_section(analysis))
    lines.extend(_test_organization_section(analysis))
    lines.extend(_statistics_section(analysis))
    lines.extend(_warnings_section(analysis))
    lines.extend(_reading_order_section(analysis))
    return "\n".join(lines).rstrip() + "\n"


def _overview_section(analysis: ProjectAnalysis) -> list[str]:
    lines = ["## Overview", "", f"- Root: `{analysis.repository_root}`"]
    if analysis.python_requires:
        lines.append(f"- Python requires: `{analysis.python_requires}`")
    if analysis.build_system:
        lines.append(f"- Build backend: `{analysis.build_system}`")
    lines.append("")
    return lines


def _entry_points_section(analysis: ProjectAnalysis) -> list[str]:
    if not analysis.entry_points:
        return []
    lines = ["## Entry Points", ""]
    for entry in analysis.entry_points:
        lines.append(f"- `{entry.name}` -> `{entry.target}` ({entry.kind})")
    lines.append("")
    return lines


def _package_map_section(analysis: ProjectAnalysis) -> list[str]:
    lines = ["## Package / Module Map", ""]
    if not analysis.packages and not analysis.modules:
        lines.append("_No Python packages or modules discovered._")
        lines.append("")
        return lines
    for package in analysis.packages:
        lines.append(f"- `{package.dotted_name}/`")
        for module in package.modules:
            lines.append(f"  - `{module}`")
    top_level_modules = sorted(m.dotted_name for m in analysis.modules if "." not in m.dotted_name)
    for module in top_level_modules:
        lines.append(f"- `{module}`")
    lines.append("")
    return lines


def _cli_commands_section(analysis: ProjectAnalysis) -> list[str]:
    if not analysis.cli_commands:
        return []
    lines = ["## CLI Commands", ""]
    for command in analysis.cli_commands:
        suffix = f" — {command.description}" if command.description else ""
        lines.append(f"- `{command.command}`{suffix}")
    lines.append("")
    return lines


def _definitions_section(analysis: ProjectAnalysis) -> list[str]:
    modules_with_definitions = [m for m in analysis.modules if m.classes or m.functions]
    if not modules_with_definitions:
        return []
    lines = ["## Major Classes and Functions", ""]
    for module in modules_with_definitions:
        lines.append(f"### `{module.dotted_name}`")
        if module.docstring:
            lines.append(f"_{module.docstring}_")
        for cls in module.classes:
            suffix = f" — {cls.docstring}" if cls.docstring else ""
            lines.append(f"- class `{cls.name}`{suffix}")
        for func in module.functions:
            suffix = f" — {func.docstring}" if func.docstring else ""
            lines.append(f"- function `{func.name}`{suffix}")
        lines.append("")
    return lines


def _skills_section(analysis: ProjectAnalysis) -> list[str]:
    if not analysis.skills:
        return []
    lines = ["## Buildrail Skills", ""]
    for skill in analysis.skills:
        provider_note = "requires a provider" if skill.requires_provider else "provider-free"
        types = ", ".join(skill.artifact_types) or "none"
        lines.append(f"- `{skill.name}` ({skill.version}, {provider_note}) — artifacts: {types}")
    lines.append("")
    return lines


def _pipelines_section(analysis: ProjectAnalysis) -> list[str]:
    if not analysis.pipelines:
        return []
    lines = ["## Buildrail Pipelines", ""]
    for pipeline in analysis.pipelines:
        steps = " -> ".join(pipeline.steps) or "(no steps detected)"
        lines.append(f"- `{pipeline.name}`: {steps}")
    lines.append("")
    return lines


def _artifact_types_section(analysis: ProjectAnalysis) -> list[str]:
    if not analysis.artifact_types:
        return []
    lines = ["## Artifact Types", ""]
    for artifact_type in analysis.artifact_types:
        lines.append(f"- `{artifact_type}`")
    lines.append("")
    return lines


def _test_organization_section(analysis: ProjectAnalysis) -> list[str]:
    lines = ["## Test Organization", ""]
    if not analysis.test_layout.test_directories and not analysis.test_layout.test_files:
        lines.append("_No test files discovered._")
        lines.append("")
        return lines
    for directory in analysis.test_layout.test_directories:
        lines.append(f"- `{directory}/`")
    lines.append(f"- {len(analysis.test_layout.test_files)} test file(s) total")
    lines.append("")
    return lines


def _statistics_section(analysis: ProjectAnalysis) -> list[str]:
    stats = analysis.statistics
    return [
        "## Project Statistics",
        "",
        f"- Python files: {stats.python_files}",
        f"- Modules: {stats.modules}",
        f"- Classes: {stats.classes}",
        f"- Functions: {stats.functions}",
        f"- Test files: {stats.test_files}",
        f"- Lines of Python: {stats.lines_of_python}",
        "",
    ]


def _warnings_section(analysis: ProjectAnalysis) -> list[str]:
    lines = ["## Analysis Warnings", ""]
    if not analysis.warnings:
        lines.append("_No warnings._")
        lines.append("")
        return lines
    for warning in analysis.warnings:
        lines.append(f"- [{warning.kind}] `{warning.path}`: {warning.message}")
    lines.append("")
    return lines


def _reading_order_section(analysis: ProjectAnalysis) -> list[str]:
    order = suggested_reading_order(analysis)
    if not order:
        return []
    lines = [
        "## Suggested Reading Order",
        "",
        "_Derived from entry points and import relationships._",
        "",
    ]
    for i, dotted in enumerate(order, start=1):
        lines.append(f"{i}. `{dotted}`")
    lines.append("")
    return lines
