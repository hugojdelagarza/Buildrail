"""SkillRegistry: discovers built-in skills, validates their manifests, and resolves them by name.

Replaces Milestone 1's hardcoded `buildrail.skill_loader` path
(docs/skills.md §6's Execution Lifecycle, step 1). Only the minimal
manifest subset actually used by review-diff and test-summary is
validated here — not a generalized schema engine for fields no skill
uses yet. Skills still execute in-process (docs/skills.md's phasing
note); `entrypoint` is parsed only to locate the Python file to import,
not to spawn a subprocess.
"""

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from buildrail.providers import ProviderGateway
from buildrail.skill_protocol import SkillRequest, SkillResponse
from buildrail.skills.errors import (
    DuplicateSkillError,
    ManifestNotFoundError,
    ManifestParseError,
    ManifestValidationError,
    SkillNotFoundError,
)

SkillRunner = Callable[[SkillRequest, ProviderGateway], SkillResponse]

_MANIFEST_FILENAME = "skill.yaml"
_SUPPORTED_PROTOCOL_VERSIONS = frozenset({"1.0"})
_REQUIRED_FIELDS = ("name", "version", "protocol_version", "entrypoint", "inputs", "outputs")

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SKILLS_DIR = _REPO_ROOT / "skills"


@dataclass(frozen=True)
class SkillManifest:
    """The minimal validated subset of a skill.yaml manifest."""

    name: str
    version: str
    protocol_version: str
    description: str
    entrypoint: str
    requires_provider: bool
    path: Path


class SkillRegistry:
    """Discovers skill.yaml manifests under a directory and resolves skills by name."""

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir if skills_dir is not None else DEFAULT_SKILLS_DIR

    def list_skills(self) -> tuple[SkillManifest, ...]:
        """Return every discovered skill's manifest, sorted by name."""
        manifests = _discover_manifests(self._skills_dir)
        return tuple(manifests[name] for name in sorted(manifests))

    def get_manifest(self, name: str) -> SkillManifest:
        """Return the validated manifest for one skill, by name."""
        manifests = _discover_manifests(self._skills_dir)
        try:
            return manifests[name]
        except KeyError:
            raise SkillNotFoundError(f"No skill named '{name}' is registered.") from None

    def resolve(self, name: str) -> SkillRunner:
        """Return the callable run() function for one skill, by name."""
        manifest = self.get_manifest(name)
        entrypoint_path = _resolve_entrypoint_path(manifest)

        spec = importlib.util.spec_from_file_location(
            f"buildrail_skill_{manifest.name}", entrypoint_path
        )
        if spec is None or spec.loader is None:
            raise ManifestValidationError(
                f"Could not load skill '{manifest.name}' from {entrypoint_path}."
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return cast(SkillRunner, module.run)


def _discover_manifests(skills_dir: Path) -> dict[str, SkillManifest]:
    manifests: dict[str, SkillManifest] = {}
    if not skills_dir.is_dir():
        return manifests

    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        manifest_path = skill_dir / _MANIFEST_FILENAME
        if not manifest_path.is_file():
            continue

        manifest = _load_manifest(manifest_path)
        if manifest.name in manifests:
            raise DuplicateSkillError(
                f"Duplicate skill name '{manifest.name}': already registered from "
                f"{manifests[manifest.name].path}, also found at {manifest.path}."
            )
        manifests[manifest.name] = manifest
    return manifests


def _load_manifest(manifest_path: Path) -> SkillManifest:
    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestNotFoundError(f"Could not read {manifest_path}: {exc}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ManifestParseError(f"{manifest_path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestValidationError(f"{manifest_path} must contain a YAML mapping.")

    return _validate(raw, manifest_path)


def _validate(raw: dict[str, Any], manifest_path: Path) -> SkillManifest:
    for field in _REQUIRED_FIELDS:
        if field not in raw:
            raise ManifestValidationError(f"{manifest_path} is missing required field '{field}'.")

    name = raw["name"]
    if not isinstance(name, str) or not name:
        raise ManifestValidationError(f"{manifest_path}: 'name' must be a non-empty string.")

    version = raw["version"]
    if not isinstance(version, str) or not version:
        raise ManifestValidationError(f"{manifest_path}: 'version' must be a non-empty string.")

    protocol_version = raw["protocol_version"]
    if (
        not isinstance(protocol_version, str)
        or protocol_version not in _SUPPORTED_PROTOCOL_VERSIONS
    ):
        supported = ", ".join(sorted(_SUPPORTED_PROTOCOL_VERSIONS))
        raise ManifestValidationError(
            f"{manifest_path}: unsupported protocol_version '{protocol_version}'. "
            f"Supported: {supported}."
        )

    entrypoint = raw["entrypoint"]
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        raise ManifestValidationError(f"{manifest_path}: 'entrypoint' must be a non-empty string.")

    inputs = raw["inputs"]
    if not isinstance(inputs, list):
        raise ManifestValidationError(f"{manifest_path}: 'inputs' must be a list.")

    outputs = raw["outputs"]
    if not isinstance(outputs, list) or not outputs:
        raise ManifestValidationError(f"{manifest_path}: 'outputs' must be a non-empty list.")

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise ManifestValidationError(f"{manifest_path}: 'description' must be a string.")

    requires_provider = raw.get("requires_provider", False)
    if not isinstance(requires_provider, bool):
        raise ManifestValidationError(f"{manifest_path}: 'requires_provider' must be a boolean.")

    return SkillManifest(
        name=name,
        version=version,
        protocol_version=protocol_version,
        description=description,
        entrypoint=entrypoint,
        requires_provider=requires_provider,
        path=manifest_path.parent,
    )


def _resolve_entrypoint_path(manifest: SkillManifest) -> Path:
    tokens = manifest.entrypoint.split()
    script_name = tokens[-1] if tokens else ""
    entrypoint_path = manifest.path / script_name
    if not script_name or not entrypoint_path.is_file():
        raise ManifestValidationError(
            f"Skill '{manifest.name}' declares entrypoint '{manifest.entrypoint}', "
            f"but no file was found at {entrypoint_path}."
        )
    return entrypoint_path
