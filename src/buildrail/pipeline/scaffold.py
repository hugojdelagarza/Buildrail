"""Scaffolds a new project-local pipeline manifest under `.buildrail/pipelines/<name>.yaml`.

Generates a deterministic, valid manifest matching `buildrail.pipeline.manifest`'s
format exactly — no separate template language. The CLI's `buildrail pipeline
create <name>` uses the single-step default; the HTTP service's `POST
/pipelines` (a narrowly-scoped structured endpoint, never an arbitrary YAML
upload) passes its own validated `name`/`description`/ordered `(skill,
condition)` steps through the same function and the same validation. Writes
are atomic and refuse to overwrite an existing manifest; this module never
deletes anything.
"""

import tempfile
from collections.abc import Sequence
from pathlib import Path

import yaml

from buildrail.extensions import (
    InvalidExtensionNameError,
    project_pipelines_dir,
    validate_extension_name,
)
from buildrail.pipeline.errors import PipelineError
from buildrail.pipeline.manifest import SUPPORTED_CONDITIONS

_DEFAULT_VERSION = "0.1.0"
_DEFAULT_DESCRIPTION = "Project-local Buildrail pipeline"
_DEFAULT_STEPS: tuple[tuple[str, str], ...] = (("verify-project", "always"),)


class PipelineScaffoldError(PipelineError):
    """Raised when a project-local pipeline manifest cannot be scaffolded."""


def create_pipeline(
    project_root: Path,
    name: str,
    *,
    description: str = _DEFAULT_DESCRIPTION,
    steps: Sequence[tuple[str, str]] = _DEFAULT_STEPS,
) -> Path:
    """Scaffold `.buildrail/pipelines/<name>.yaml` and return its path.

    `steps` is an ordered sequence of `(skill_name, condition)` pairs — the
    same shape `buildrail.pipeline.manifest.SUPPORTED_CONDITIONS` validates
    at load time, checked again here so a bad request fails before any
    file is written. Raises `PipelineScaffoldError` (wrapping name and
    step validation failures too) if `name` is unsafe, a step is invalid,
    or a manifest already exists at that path — this never overwrites
    existing project-local content.
    """
    try:
        validate_extension_name(name, label="pipeline name")
    except InvalidExtensionNameError as exc:
        raise PipelineScaffoldError(str(exc)) from exc

    if not isinstance(description, str) or not description:
        raise PipelineScaffoldError("Pipeline description must be a non-empty string.")
    if not steps:
        raise PipelineScaffoldError("A pipeline needs at least one step.")

    step_docs: list[dict[str, str]] = []
    for skill, condition in steps:
        if not isinstance(skill, str) or not skill:
            raise PipelineScaffoldError("Each step needs a non-empty skill name.")
        if condition not in SUPPORTED_CONDITIONS:
            supported = ", ".join(sorted(SUPPORTED_CONDITIONS))
            raise PipelineScaffoldError(
                f"Unsupported condition '{condition}'. Supported: {supported}."
            )
        step_doc: dict[str, str] = {"skill": skill}
        if condition != "always":
            step_doc["condition"] = condition
        step_docs.append(step_doc)

    pipelines_dir = project_pipelines_dir(project_root)
    manifest_path = pipelines_dir / f"{name}.yaml"
    if manifest_path.exists():
        raise PipelineScaffoldError(f"A project-local pipeline already exists at {manifest_path}.")

    document = {
        "name": name,
        "version": _DEFAULT_VERSION,
        "description": description,
        "steps": step_docs,
    }
    rendered = yaml.safe_dump(document, sort_keys=False, default_flow_style=False)

    pipelines_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".buildrail-scaffold-", dir=pipelines_dir)
    tmp_path = Path(tmp_name)
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(rendered)
        tmp_path.replace(manifest_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return manifest_path
