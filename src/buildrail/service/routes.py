"""Routes Buildrail's local HTTP service to CoreEngine and ArtifactReader.

The HTTP layer owns only routing, JSON serialization, request validation,
and status codes — every read goes through `ArtifactReader`, every write
goes through `CoreEngine`, exactly as the CLI already does. No business
logic is reimplemented here, and no command's result is ever derived by
parsing CLI text output — a command endpoint's JSON response wraps the
same `Result` the CLI prints; the browsing endpoints (`/runs`,
`/artifacts`) return the same typed data the CLI's `runs`/`artifacts`
commands already read via `ArtifactReader`.
"""

import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from buildrail.artifacts import (
    ArtifactDetail,
    ArtifactNotFoundError,
    ArtifactPayload,
    ArtifactReader,
    ArtifactReadError,
    InvalidIdentifierError,
    InvalidLimitError,
    RunDetail,
    RunNotFoundError,
    RunSummary,
)
from buildrail.config import BuildrailConfig, ConfigError, ConfigNotFoundError, load_config
from buildrail.core import CoreEngine, Result
from buildrail.pipeline import (
    PipelineArgument,
    PipelineDefinition,
    PipelineError,
    PipelineNotFoundError,
    PipelineRegistry,
    PipelineScaffoldError,
)
from buildrail.pipeline import create_pipeline as scaffold_pipeline
from buildrail.providers import ProviderError, create_provider
from buildrail.service.descriptors import COMMANDS, CommandArgument, CommandDescriptor
from buildrail.skills import SkillError, SkillManifest, SkillRegistry, SkillScaffoldError
from buildrail.skills import create_skill as scaffold_skill

JsonObject = dict[str, Any]
JsonBody = JsonObject | None
Response = tuple[int, JsonObject]

_API_VERSION = "1"
_COMMAND_NAMES = frozenset(command.id for command in COMMANDS)

# Discovery routes below never require a loaded buildrail.toml — they describe
# Buildrail itself (built-in skills, built-in pipelines, the service's own
# version) or degrade gracefully when the project isn't configured yet, so a
# frontend can still render a helpful screen instead of an opaque 500.
_CONFIG_FREE_GET_ROUTES = frozenset(
    {
        ("health",),
        ("version",),
        ("commands",),
        ("skills",),
        ("pipelines",),
        ("project",),
        ("config",),
    }
)


def dispatch(method: str, raw_path: str, body: JsonBody, project_root: Path) -> Response:
    """Route one HTTP request to a handler and return (status_code, json_body)."""
    split = urlsplit(raw_path)
    parts = [segment for segment in split.path.split("/") if segment != ""]
    query = parse_qs(split.query)

    if method == "GET" and tuple(parts) in _CONFIG_FREE_GET_ROUTES:
        return _dispatch_config_free_get(tuple(parts), project_root)

    # Config writes are handled before the load_config gate below, since the
    # whole point of this route is to create a configuration that doesn't
    # exist yet (project onboarding) — it must work on an unconfigured project.
    if method == "PUT" and parts == ["config"]:
        if body is None:
            return 400, {"error": "Request body must be a JSON object."}
        return _update_config(project_root, body)

    # Scaffolding project-local skills/pipelines never requires a loaded
    # buildrail.toml either — a fresh project may want to create one before
    # its first `buildrail init` config write, same reasoning as above.
    if method == "POST" and parts == ["skills"]:
        if body is None:
            return 400, {"error": "Request body must be a JSON object."}
        return _create_skill(project_root, body)
    if method == "POST" and parts == ["pipelines"]:
        if body is None:
            return 400, {"error": "Request body must be a JSON object."}
        return _create_pipeline(project_root, body)

    try:
        config = load_config(project_root)
    except ConfigError as exc:
        return 500, {"error": str(exc)}
    reader = ArtifactReader(project_root / config.artifact_root)

    if method == "GET" and parts == ["runs"]:
        return _list_runs(reader, query)

    if method == "GET" and len(parts) == 2 and parts[0] == "runs":
        return _get_run(reader, parts[1])

    if method == "GET" and len(parts) >= 2 and parts[0] == "artifacts":
        artifact_id = "/".join(parts[1:])
        return _get_artifact(reader, artifact_id)

    if method == "POST" and len(parts) == 2 and parts[0] == "commands":
        if body is None:
            return 400, {"error": "Request body must be a JSON object."}
        return _run_command(project_root, parts[1], body)

    return 404, {"error": f"No route for {method} {split.path}."}


def _dispatch_config_free_get(parts: tuple[str, ...], project_root: Path) -> Response:
    if parts == ("health",):
        return _health()
    if parts == ("version",):
        return _version()
    if parts == ("commands",):
        return _list_commands()
    if parts == ("skills",):
        return _list_skills(project_root)
    if parts == ("pipelines",):
        return _list_pipelines(project_root)
    if parts == ("project",):
        return _project_summary(project_root)
    return _config_summary(project_root)


def _health() -> Response:
    try:
        version = importlib.metadata.version("buildrail")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"
    return 200, {"status": "ok", "version": version}


def _list_runs(reader: ArtifactReader, query: dict[str, list[str]]) -> Response:
    limit = 20
    if "limit" in query:
        try:
            limit = int(query["limit"][0])
        except ValueError:
            return 400, {"error": "'limit' must be an integer."}
    try:
        runs = reader.list_runs(limit)
    except ArtifactReadError as exc:
        return _artifact_error(exc)
    return 200, {"runs": [_run_summary_dict(run) for run in runs]}


def _get_run(reader: ArtifactReader, run_id: str) -> Response:
    try:
        run = reader.get_run(run_id)
    except ArtifactReadError as exc:
        return _artifact_error(exc)
    return 200, _run_detail_dict(run)


def _get_artifact(reader: ArtifactReader, artifact_id: str) -> Response:
    try:
        payload = reader.get_artifact(artifact_id)
    except ArtifactReadError as exc:
        return _artifact_error(exc)
    return 200, _artifact_payload_dict(payload)


def _artifact_error(exc: ArtifactReadError) -> Response:
    if isinstance(exc, RunNotFoundError | ArtifactNotFoundError):
        return 404, {"error": str(exc)}
    if isinstance(exc, InvalidIdentifierError | InvalidLimitError):
        return 400, {"error": str(exc)}
    return 500, {"error": str(exc)}


def _run_summary_dict(run: RunSummary) -> JsonObject:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "created_at": run.created_at,
        "artifact_count": run.artifact_count,
        "artifact_types": list(run.artifact_types),
        "pipeline": run.pipeline,
        "pipeline_source": run.pipeline_source,
    }


def _artifact_detail_dict(detail: ArtifactDetail) -> JsonObject:
    return {
        "id": detail.id,
        "run_id": detail.run_id,
        "type": detail.type,
        "content_path": str(detail.content_path),
        "status": detail.status,
        "produced_by_skill": detail.produced_by_skill,
        "produced_by_version": detail.produced_by_version,
        "provider_usage": detail.provider_usage,
        "pipeline": detail.pipeline,
        "display_name": detail.display_name,
        "created_at": detail.created_at,
        "checksum": detail.checksum,
        "content_type": detail.content_type,
    }


def _run_detail_dict(run: RunDetail) -> JsonObject:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "created_at": run.created_at,
        "pipeline": run.pipeline,
        "pipeline_source": run.pipeline_source,
        "duration_seconds": run.duration_seconds,
        "pipeline_steps": [
            {
                "name": step.name,
                "status": step.status,
                "reason": step.reason,
                "artifact_ids": list(step.artifact_ids),
            }
            for step in run.pipeline_steps
        ],
        "artifacts": [_artifact_detail_dict(artifact) for artifact in run.artifacts],
        "provider_usage_totals": run.provider_usage_totals,
    }


def _artifact_payload_dict(payload: ArtifactPayload) -> JsonObject:
    result = _artifact_detail_dict(payload.detail)
    result["content"] = payload.content
    # Reuse structured JSON directly (e.g. explain-project's ProjectAnalysis
    # sidecar) instead of making a frontend parse Markdown or re-decode a
    # JSON string embedded inside this JSON response.
    result["content_json"] = None
    if payload.detail.content_type == "application/json":
        try:
            result["content_json"] = json.loads(payload.content)
        except json.JSONDecodeError:
            result["content_json"] = None
    return result


def _run_command(project_root: Path, name: str, body: JsonObject) -> Response:
    engine = CoreEngine()
    if name not in _COMMAND_NAMES:
        # Not a single-skill command or a built-in pipeline — the only other
        # runnable thing behind this endpoint is a project-local pipeline
        # (`PipelineRegistry`'s declarative kind); anything else is a 404.
        try:
            definition = PipelineRegistry(project_root=project_root).get_pipeline(name)
        except PipelineNotFoundError:
            return 404, {"error": f"No command named '{name}'."}
        except PipelineError as exc:
            return 500, {"error": str(exc)}
        if definition.execution_kind != "declarative":
            return 404, {"error": f"No command named '{name}'."}
        result = engine.run_named_pipeline(project_root, name)
        return 200, {"success": result.success, "message": result.message}

    try:
        result = _dispatch_command(engine, project_root, name, body)
    except TypeError as exc:
        return 400, {"error": str(exc)}
    return 200, {"success": result.success, "message": result.message}


def _dispatch_command(
    engine: CoreEngine, project_root: Path, name: str, body: JsonObject
) -> Result:
    path = _optional_str(body, "path")
    if name == "explain":
        return engine.explain_project(project_root, path=path)
    if name == "dependency-audit":
        return engine.dependency_audit(project_root, path=path)
    if name == "docs":
        output = _optional_str(body, "output")
        enhance = _optional_bool(body, "enhance")
        return engine.docs_generate(project_root, path=path, output=output, enhance=enhance)
    if name == "diagram":
        diagram_format = body.get("format", "mermaid")
        if not isinstance(diagram_format, str):
            raise TypeError("'format' must be a string.")
        return engine.diagram_generate(project_root, path=path, format=diagram_format)
    if name == "verify":
        return engine.verify_project(project_root)
    if name == "pre-commit":
        base_ref = _optional_str(body, "base")
        skip_review = _optional_bool(body, "skip_review")
        return engine.run_pre_commit(project_root, base_ref=base_ref, skip_review=skip_review)
    if name == "project-intelligence":
        enhance = _optional_bool(body, "enhance")
        return engine.run_project_intelligence(project_root, path=path, enhance=enhance)
    raise AssertionError(f"Unreachable: command '{name}' passed validation but has no handler.")


def _optional_str(body: JsonObject, key: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"'{key}' must be a string.")
    return value


def _optional_bool(body: JsonObject, key: str) -> bool:
    value = body.get(key, False)
    if not isinstance(value, bool):
        raise TypeError(f"'{key}' must be a boolean.")
    return value


def _buildrail_version() -> str:
    try:
        return importlib.metadata.version("buildrail")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _version() -> Response:
    return 200, {
        "buildrail_version": _buildrail_version(),
        "api_version": _API_VERSION,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def _relative_to_project(project_root: Path, path: Path) -> str:
    """Return `path` relative to `project_root` as a POSIX string — never a full local path."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name


def _argument_dict(argument: CommandArgument | PipelineArgument) -> JsonObject:
    return {
        "name": argument.name,
        "type": argument.type,
        "required": argument.required,
        "description": argument.description,
    }


def _command_dict(command: CommandDescriptor) -> JsonObject:
    return {
        "id": command.id,
        "display_name": command.display_name,
        "description": command.description,
        "endpoint": command.endpoint,
        "method": "POST",
        "requires_provider": command.requires_provider,
        "accepts_arguments": command.accepts_arguments,
        "arguments": [_argument_dict(a) for a in command.arguments],
        "artifact_types": list(command.artifact_types),
        "category": command.category,
    }


def _list_commands() -> Response:
    return 200, {"commands": [_command_dict(c) for c in COMMANDS]}


def _pipeline_dict(pipeline: PipelineDefinition, project_root: Path) -> JsonObject:
    return {
        "name": pipeline.name,
        "version": pipeline.version,
        "display_name": pipeline.display_name,
        "description": pipeline.description,
        "source": pipeline.source,
        "execution_kind": pipeline.execution_kind,
        "project_relative_path": (
            _relative_to_project(project_root, pipeline.path) if pipeline.path is not None else None
        ),
        "steps": [
            {
                "name": step.name,
                "skippable": step.skippable,
                "skip_condition": step.skip_condition,
                "inputs": dict(step.inputs),
            }
            for step in pipeline.steps
        ],
        "requires_provider": pipeline.requires_provider,
        "arguments": [_argument_dict(a) for a in pipeline.arguments],
    }


def _list_pipelines(project_root: Path) -> Response:
    try:
        definitions = PipelineRegistry(project_root=project_root).list_pipelines()
    except PipelineError as exc:
        return 500, {"error": str(exc)}
    return 200, {"pipelines": [_pipeline_dict(p, project_root) for p in definitions]}


def _skill_manifest_dict(manifest: SkillManifest, project_root: Path) -> JsonObject:
    return {
        "name": manifest.name,
        "version": manifest.version,
        "protocol_version": manifest.protocol_version,
        "description": manifest.description,
        "requires_provider": manifest.requires_provider,
        "source": manifest.source,
        "project_relative_path": (
            _relative_to_project(project_root, manifest.path)
            if manifest.source == "project-local"
            else None
        ),
        "inputs": [
            {
                "name": i.name,
                "type": i.type,
                "required": i.required,
                "description": i.description,
            }
            for i in manifest.inputs
        ],
        "outputs": [{"name": o.name, "artifact_type": o.artifact_type} for o in manifest.outputs],
    }


def _list_skills(project_root: Path) -> Response:
    try:
        manifests = SkillRegistry(project_root=project_root).list_skills()
    except SkillError as exc:
        return 500, {"error": str(exc)}
    return 200, {"skills": [_skill_manifest_dict(m, project_root) for m in manifests]}


def _create_skill(project_root: Path, body: JsonObject) -> Response:
    """Scaffold a project-local skill from structured input only.

    Never accepts source code — the server always generates the
    skill.yaml/skill.py template, the exact same function `buildrail
    skill create` uses.
    """
    name = body.get("name")
    if not isinstance(name, str) or not name:
        return 400, {"error": "'name' must be a non-empty string."}
    requires_provider = body.get("requires_provider", False)
    if not isinstance(requires_provider, bool):
        return 400, {"error": "'requires_provider' must be a boolean."}
    description = body.get("description")
    if description is not None and (not isinstance(description, str) or not description):
        return 400, {"error": "'description' must be a non-empty string."}

    try:
        skill_dir = (
            scaffold_skill(
                project_root, name, description=description, requires_provider=requires_provider
            )
            if description is not None
            else scaffold_skill(project_root, name, requires_provider=requires_provider)
        )
    except SkillScaffoldError as exc:
        return 400, {"error": str(exc)}
    return 201, {
        "name": name,
        "project_relative_path": _relative_to_project(project_root, skill_dir),
    }


def _create_pipeline(project_root: Path, body: JsonObject) -> Response:
    """Scaffold a project-local pipeline from structured input only.

    Never accepts raw YAML or a file path — `steps` is a plain list of
    `{skill, condition}` objects, validated and rendered into YAML by
    `buildrail.pipeline.scaffold.create_pipeline`, the exact same function
    `buildrail pipeline create` uses.
    """
    name = body.get("name")
    if not isinstance(name, str) or not name:
        return 400, {"error": "'name' must be a non-empty string."}

    description = body.get("description", "Project-local Buildrail pipeline")
    if not isinstance(description, str) or not description:
        return 400, {"error": "'description' must be a non-empty string."}

    raw_steps = body.get("steps")
    if raw_steps is None:
        steps: list[tuple[str, str]] | None = None
    else:
        if not isinstance(raw_steps, list) or not raw_steps:
            return 400, {"error": "'steps' must be a non-empty list."}
        steps = []
        for entry in raw_steps:
            if not isinstance(entry, dict):
                return 400, {"error": "Each step must be an object."}
            skill = entry.get("skill")
            if not isinstance(skill, str) or not skill:
                return 400, {"error": "Each step needs a non-empty 'skill'."}
            condition = entry.get("condition", "always")
            if not isinstance(condition, str):
                return 400, {"error": "A step's 'condition' must be a string."}
            steps.append((skill, condition))

    try:
        if steps is None:
            manifest_path = scaffold_pipeline(project_root, name, description=description)
        else:
            manifest_path = scaffold_pipeline(
                project_root, name, description=description, steps=steps
            )
    except PipelineScaffoldError as exc:
        return 400, {"error": str(exc)}
    return 201, {
        "name": name,
        "project_relative_path": _relative_to_project(project_root, manifest_path),
    }


def _provider_ready(config: BuildrailConfig) -> bool:
    """Whether the configured provider can be constructed — never makes a network call.

    Reuses the same `create_provider` factory CoreEngine already uses; for
    "anthropic" this only checks that ANTHROPIC_API_KEY is set (the
    adapter's constructor validates presence, it does not call the API).
    """
    if config.provider is None:
        return False
    try:
        create_provider(config.provider, model=config.anthropic_model)
    except ProviderError:
        return False
    return True


def _latest_statistics(reader: ArtifactReader, runs: tuple[RunSummary, ...]) -> JsonObject | None:
    """Return the newest architecture-summary run's `statistics` object, if any exists."""
    for run in runs:
        if "architecture-summary" not in run.artifact_types:
            continue
        try:
            detail = reader.get_run(run.run_id)
        except ArtifactReadError:
            continue
        for artifact in detail.artifacts:
            if (
                artifact.type != "architecture-summary"
                or artifact.content_type != "application/json"
            ):
                continue
            try:
                payload = reader.get_artifact(artifact.id)
                data = json.loads(payload.content)
            except (ArtifactReadError, json.JSONDecodeError):
                continue
            statistics = data.get("statistics")
            return statistics if isinstance(statistics, dict) else None
    return None


def _extension_counts(project_root: Path) -> JsonObject:
    """Built-in vs. project-local skill/pipeline counts, for the frontend's
    "Project Extensions" summary — degrades to all-zero counts rather than
    failing the whole `/project` response if a manifest is malformed."""
    try:
        skills = SkillRegistry(project_root=project_root).list_skills()
    except SkillError:
        skills = ()
    try:
        pipelines = PipelineRegistry(project_root=project_root).list_pipelines()
    except PipelineError:
        pipelines = ()
    return {
        "skill_count": len(skills),
        "skill_count_built_in": sum(1 for s in skills if s.source == "built-in"),
        "skill_count_project_local": sum(1 for s in skills if s.source == "project-local"),
        "pipeline_count": len(pipelines),
        "pipeline_count_built_in": sum(1 for p in pipelines if p.source == "built-in"),
        "pipeline_count_project_local": sum(1 for p in pipelines if p.source == "project-local"),
    }


def _project_summary(project_root: Path) -> Response:
    try:
        config = load_config(project_root)
    except ConfigError:
        return 200, {
            "service_version": _buildrail_version(),
            "project_root": str(project_root),
            "config_status": "missing",
            "artifact_root": None,
            "provider": None,
            "provider_ready": False,
            "recent_run_count": 0,
            "latest_run": None,
            "statistics": None,
            **_extension_counts(project_root),
        }

    reader = ArtifactReader(project_root / config.artifact_root)
    try:
        runs = reader.list_runs(50)
    except ArtifactReadError:
        runs = ()

    return 200, {
        "service_version": _buildrail_version(),
        "project_root": str(project_root),
        "config_status": "ok",
        "artifact_root": config.artifact_root,
        "provider": config.provider,
        "provider_ready": _provider_ready(config),
        "recent_run_count": len(runs),
        "latest_run": _run_summary_dict(runs[0]) if runs else None,
        "statistics": _latest_statistics(reader, runs),
        **_extension_counts(project_root),
    }


def _config_summary(project_root: Path) -> Response:
    try:
        config = load_config(project_root)
    except ConfigNotFoundError:
        return 200, {
            "status": "missing",
            "configured": False,
            "provider": None,
            "anthropic_model": None,
            "artifact_root": None,
            "credential_available": False,
            "error": None,
        }
    except ConfigError as exc:
        return 200, {
            "status": "invalid",
            "configured": False,
            "provider": None,
            "anthropic_model": None,
            "artifact_root": None,
            "credential_available": False,
            "error": str(exc),
        }
    return 200, {
        "status": "ok",
        "configured": True,
        "provider": config.provider,
        "anthropic_model": config.anthropic_model,
        "artifact_root": config.artifact_root,
        "credential_available": _provider_ready(config),
        "error": None,
    }


def _update_config(project_root: Path, body: JsonObject) -> Response:
    """Create or update this project's `buildrail.toml` from a restricted field set.

    Delegates all validation and the atomic write to `CoreEngine.update_config`
    — this handler only maps its `Result` onto an HTTP status: a rejected
    update (unknown field, invalid provider, an escaping artifact root, ...)
    is a client error, so it maps to 400, not the 200-with-success:false shape
    `/commands/{id}` uses for domain-level command outcomes.
    """
    engine = CoreEngine()
    result = engine.update_config(project_root, body)
    if not result.success:
        return 400, {"error": result.message}
    return 200, _config_summary(project_root)[1]
