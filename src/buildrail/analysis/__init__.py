"""Deterministic, offline analysis of a Python repository — the shared foundation for
`explain-project`, `generate-docs`, and `generate-diagram`."""

from buildrail.analysis.analyzer import analyze_project, suggested_reading_order
from buildrail.analysis.errors import AnalysisError
from buildrail.analysis.models import (
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
    analysis_from_dict,
    to_dict,
)

__all__ = [
    "AnalysisError",
    "AnalysisWarning",
    "ClassInfo",
    "CliCommand",
    "EntryPoint",
    "FunctionInfo",
    "ModuleInfo",
    "PackageNode",
    "PipelineInfo",
    "ProjectAnalysis",
    "ProjectStatistics",
    "ProjectTooling",
    "SkillInfo",
    "TestLayout",
    "analysis_from_dict",
    "analyze_project",
    "suggested_reading_order",
    "to_dict",
]
