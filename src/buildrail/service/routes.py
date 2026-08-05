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
from buildrail.config import ConfigError, load_config
from buildrail.core import CoreEngine, Result

JsonObject = dict[str, Any]
JsonBody = JsonObject | None
Response = tuple[int, JsonObject]

_COMMANDS = frozenset(
    {"explain", "docs", "diagram", "verify", "pre-commit", "project-intelligence"}
)


def dispatch(method: str, raw_path: str, body: JsonBody, project_root: Path) -> Response:
    """Route one HTTP request to a handler and return (status_code, json_body)."""
    split = urlsplit(raw_path)
    parts = [segment for segment in split.path.split("/") if segment != ""]
    query = parse_qs(split.query)

    if method == "GET" and parts == ["health"]:
        return _health()

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
    if name not in _COMMANDS:
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
