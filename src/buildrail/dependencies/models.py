"""DependencyAudit: the typed, serializable output of the deterministic
dependency auditor. Mirrors `buildrail.analysis.models`' round-trip pattern —
plain dataclasses of strings/bools/tuples so the whole model round-trips
through `to_dict`/`audit_from_dict` and `json.dumps` without a custom encoder.
"""

from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class DeclaredDependency:
    """One dependency declaration, from one source file."""

    name: str
    raw: str
    group: str  # "runtime", "dev", or an extras/requirements-derived group name
    source: str  # relative path of the file this was declared in
    version_constraint: str | None
    is_pinned: bool
    is_vcs: bool
    is_url: bool
    is_editable: bool
    is_local_path: bool


@dataclass(frozen=True)
class DuplicateDeclaration:
    """The same dependency name declared more than once."""

    name: str
    occurrences: tuple[str, ...]


@dataclass(frozen=True)
class ConstraintConflict:
    """Two or more declarations of the same dependency with disagreeing exact pins."""

    name: str
    constraints: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class ImportMismatch:
    """A conservative observation comparing declared dependencies to local imports.

    Python import names and distribution names are not always identical, so
    this is never a confident "unused" or "missing" claim — see `note`.
    """

    name: str
    kind: str  # "declared_not_observed" | "imported_not_declared"
    note: str


@dataclass(frozen=True)
class DependencyAuditWarning:
    """One non-fatal issue encountered while auditing (parse error, unsupported format, ...)."""

    kind: str
    path: str
    message: str


@dataclass(frozen=True)
class DependencyAudit:
    """The normalized, deterministic dependency audit of one Python repository."""

    schema_version: str
    repository_name: str
    repository_root: str
    build_backend: str | None
    sources: tuple[str, ...]
    dependencies: tuple[DeclaredDependency, ...]
    duplicates: tuple[DuplicateDeclaration, ...]
    conflicts: tuple[ConstraintConflict, ...]
    mismatches: tuple[ImportMismatch, ...]
    observed_third_party_imports: tuple[str, ...]
    warnings: tuple[DependencyAuditWarning, ...]


def to_dict(audit: DependencyAudit) -> dict[str, Any]:
    """Convert a DependencyAudit into a plain, JSON-serializable dict."""

    def _seq(items: tuple[Any, ...]) -> list[Any]:
        return [_value(item) for item in items]

    def _value(item: Any) -> Any:
        if hasattr(item, "__dataclass_fields__"):
            return {field: _value(getattr(item, field)) for field in item.__dataclass_fields__}
        if isinstance(item, tuple):
            return _seq(item)
        return item

    return _value(audit)  # type: ignore[no-any-return]


def audit_from_dict(data: dict[str, Any]) -> DependencyAudit:
    """Reconstruct a DependencyAudit from the dict produced by `to_dict`."""
    return DependencyAudit(
        schema_version=data["schema_version"],
        repository_name=data["repository_name"],
        repository_root=data["repository_root"],
        build_backend=data["build_backend"],
        sources=tuple(data["sources"]),
        dependencies=tuple(DeclaredDependency(**item) for item in data["dependencies"]),
        duplicates=tuple(
            DuplicateDeclaration(name=item["name"], occurrences=tuple(item["occurrences"]))
            for item in data["duplicates"]
        ),
        conflicts=tuple(
            ConstraintConflict(
                name=item["name"], constraints=tuple(item["constraints"]), note=item["note"]
            )
            for item in data["conflicts"]
        ),
        mismatches=tuple(ImportMismatch(**item) for item in data["mismatches"]),
        observed_third_party_imports=tuple(data["observed_third_party_imports"]),
        warnings=tuple(DependencyAuditWarning(**item) for item in data["warnings"]),
    )
