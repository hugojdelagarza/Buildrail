"""Deterministic, offline dependency auditing for a Python repository.

Inspects declared dependencies (`pyproject.toml`, `requirements*.txt`) and
cross-references them against locally observed imports. Not a vulnerability
or CVE scanner — see `buildrail.dependencies.auditor` for scope.
"""

from buildrail.analysis import AnalysisError
from buildrail.dependencies.auditor import audit_dependencies
from buildrail.dependencies.models import (
    SCHEMA_VERSION,
    ConstraintConflict,
    DeclaredDependency,
    DependencyAudit,
    DependencyAuditWarning,
    DuplicateDeclaration,
    ImportMismatch,
    audit_from_dict,
    to_dict,
)

__all__ = [
    "SCHEMA_VERSION",
    "AnalysisError",
    "ConstraintConflict",
    "DeclaredDependency",
    "DependencyAudit",
    "DependencyAuditWarning",
    "DuplicateDeclaration",
    "ImportMismatch",
    "audit_dependencies",
    "audit_from_dict",
    "to_dict",
]
