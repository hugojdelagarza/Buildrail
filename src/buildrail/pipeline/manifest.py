"""PipelineManifest: parses and structurally validates a project-local pipeline YAML file.

Deliberately small: ordered sequential steps, existing skill names, and a
handful of supported `condition` values — no DAGs, loops, variables,
templating, or expression language. This module validates shape only
(types, required fields, supported condition values); whether a step's
`skill` actually exists is validated by `buildrail.pipeline.registry`,
which is the layer that has a SkillRegistry to check against.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from buildrail.pipeline.errors import (
    PipelineManifestNotFoundError,
    PipelineManifestParseError,
    PipelineManifestValidationError,
)

SUPPORTED_CONDITIONS = frozenset({"always", "changes_exist"})
_DEFAULT_CONDITION = "always"
_SCALAR_INPUT_TYPES = (str, bool, int, float)


@dataclass(frozen=True)
class PipelineStepManifest:
    """One step in a project-local pipeline: which skill, when to run it, what to pass it."""

    skill: str
    condition: str = _DEFAULT_CONDITION
    inputs: dict[str, str | bool | int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineManifest:
    """A validated project-local pipeline definition, loaded from one YAML file."""

    name: str
    version: str
    description: str
    steps: tuple[PipelineStepManifest, ...]
    path: Path


def load_pipeline_manifest(manifest_path: Path) -> PipelineManifest:
    """Load and validate one `.buildrail/pipelines/<name>.yaml` file."""
    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PipelineManifestNotFoundError(f"Could not read {manifest_path}: {exc}") from exc

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise PipelineManifestParseError(f"{manifest_path} is not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise PipelineManifestValidationError(f"{manifest_path} must contain a YAML mapping.")

    return _validate(raw, manifest_path)


def _validate(raw: dict[str, Any], manifest_path: Path) -> PipelineManifest:
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise PipelineManifestValidationError(
            f"{manifest_path}: 'name' must be a non-empty string."
        )

    version = raw.get("version")
    if not isinstance(version, str) or not version:
        raise PipelineManifestValidationError(
            f"{manifest_path}: 'version' must be a non-empty string."
        )

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise PipelineManifestValidationError(f"{manifest_path}: 'description' must be a string.")

    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PipelineManifestValidationError(f"{manifest_path}: 'steps' must be a non-empty list.")

    return PipelineManifest(
        name=name,
        version=version,
        description=description,
        steps=tuple(_parse_step(entry, manifest_path) for entry in steps),
        path=manifest_path,
    )


def _parse_step(entry: Any, manifest_path: Path) -> PipelineStepManifest:
    if not isinstance(entry, dict):
        raise PipelineManifestValidationError(f"{manifest_path}: each step must be a mapping.")

    skill = entry.get("skill")
    if not isinstance(skill, str) or not skill:
        raise PipelineManifestValidationError(
            f"{manifest_path}: a step is missing a non-empty 'skill'."
        )

    condition = entry.get("condition", _DEFAULT_CONDITION)
    if not isinstance(condition, str) or condition not in SUPPORTED_CONDITIONS:
        supported = ", ".join(sorted(SUPPORTED_CONDITIONS))
        raise PipelineManifestValidationError(
            f"{manifest_path}: step '{skill}' has unsupported condition {condition!r}. "
            f"Supported: {supported}."
        )

    raw_inputs = entry.get("inputs", {})
    if not isinstance(raw_inputs, dict):
        raise PipelineManifestValidationError(
            f"{manifest_path}: step '{skill}' inputs must be a mapping."
        )
    inputs: dict[str, str | bool | int | float] = {}
    for key, value in raw_inputs.items():
        if not isinstance(key, str) or not key:
            raise PipelineManifestValidationError(
                f"{manifest_path}: step '{skill}' has a non-string input name."
            )
        # bool is an int subclass in Python, so this also accepts booleans —
        # deliberately: no lists, mappings, or null values (no templating,
        # no structured data — see this module's docstring).
        if not isinstance(value, _SCALAR_INPUT_TYPES):
            raise PipelineManifestValidationError(
                f"{manifest_path}: step '{skill}' input '{key}' must be a string, "
                "boolean, or number."
            )
        inputs[key] = value

    return PipelineStepManifest(skill=skill, condition=condition, inputs=inputs)
