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
from buildrail.config import BuildrailConfig, ConfigError, load_config
from buildrail.core import CoreEngine, Result
from buildrail.providers import ProviderError, create_provider
from buildrail.service.descriptors import (
    COMMANDS,
    PIPELINES,
    CommandArgument,
    CommandDescriptor,
    PipelineDescriptor,
)
from buildrail.skills import SkillError, SkillManifest, SkillRegistry

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
        return _list_skills()
    if parts == ("pipelines",):
        return _list_pipelines()
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
    if name not in _COMMAND_NAMES:
        return 404, {"error": f"No command named '{name}'."}
    engine = CoreEngine()
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


def _argument_dict(argument: CommandArgument) -> JsonObject:
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


def _pipeline_dict(pipeline: PipelineDescriptor) -> JsonObject:
    return {
        "name": pipeline.name,
        "display_name": pipeline.display_name,
        "description": pipeline.description,
        "steps": [
            {"name": step.name, "skippable": step.skippable, "skip_condition": step.skip_condition}
            for step in pipeline.steps
        ],
        "requires_provider": pipeline.requires_provider,
        "arguments": [_argument_dict(a) for a in pipeline.arguments],
    }


def _list_pipelines() -> Response:
    return 200, {"pipelines": [_pipeline_dict(p) for p in PIPELINES]}


def _skill_manifest_dict(manifest: SkillManifest) -> JsonObject:
    return {
        "name": manifest.name,
        "version": manifest.version,
        "protocol_version": manifest.protocol_version,
        "description": manifest.description,
        "requires_provider": manifest.requires_provider,
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


def _list_skills() -> Response:
    try:
        manifests = SkillRegistry().list_skills()
    except SkillError as exc:
        return 500, {"error": str(exc)}
    return 200, {"skills": [_skill_manifest_dict(m) for m in manifests]}


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
            "skill_count": len(SkillRegistry().list_skills()),
            "pipeline_count": len(PIPELINES),
            "recent_run_count": 0,
            "latest_run": None,
            "statistics": None,
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
        "skill_count": len(SkillRegistry().list_skills()),
        "pipeline_count": len(PIPELINES),
        "recent_run_count": len(runs),
        "latest_run": _run_summary_dict(runs[0]) if runs else None,
        "statistics": _latest_statistics(reader, runs),
    }


def _config_summary(project_root: Path) -> Response:
    try:
        config = load_config(project_root)
    except ConfigError:
        return 200, {
            "configured": False,
            "provider": None,
            "anthropic_model": None,
            "artifact_root": None,
            "credential_available": False,
        }
    return 200, {
        "configured": True,
        "provider": config.provider,
        "anthropic_model": config.anthropic_model,
        "artifact_root": config.artifact_root,
        "credential_available": _provider_ready(config),
    }
