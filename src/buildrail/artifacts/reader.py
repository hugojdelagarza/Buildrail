"""ArtifactReader: read-only browsing of runs and artifacts written by ArtifactStore.

Reuses the same flat-file layout ArtifactStore writes (docs/artifacts.md):
`<root>/<run-id>/run.json` as the run index, plus one `<slug>.meta.json` and
one payload file per artifact. Listing runs reads only each run's
`run.json` — never artifact payloads — per the browsing contract. Every
run/artifact id is treated as untrusted input: ids are validated against a
strict charset (no path separators, no ".." as a whole segment) and the
resolved path is confirmed to stay under `root` before anything is read.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from buildrail.artifacts.errors import (
    ArtifactAccessError,
    ArtifactNotFoundError,
    ChecksumMismatchError,
    InvalidIdentifierError,
    InvalidLimitError,
    MalformedMetadataError,
    RunNotFoundError,
)

_RUN_MANIFEST_FILENAME = "run.json"
_MAX_LIMIT = 1000
_DEFAULT_LIMIT = 20
_ID_PATTERN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_RUN_ID_TIMESTAMP = re.compile(r"^(\d{8})-(\d{6})-")


@dataclass(frozen=True)
class PipelineStepSummary:
    """One step's recorded outcome within a named pipeline run (docs/artifacts.md)."""

    name: str
    status: str
    reason: str | None
    artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class RunSummary:
    """One run's index-level info, built only from its run.json."""

    run_id: str
    status: str
    created_at: str | None
    artifact_count: int
    artifact_types: tuple[str, ...]
    pipeline: str | None = None


@dataclass(frozen=True)
class ArtifactDetail:
    """One artifact's full metadata (no payload)."""

    id: str
    run_id: str
    type: str
    content_path: Path
    status: str
    produced_by_skill: str | None
    produced_by_version: str | None
    provider_usage: dict[str, object] | None
    created_at: str | None
    checksum: str | None
    content_type: str | None
    pipeline: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class RunDetail:
    """Full detail for one run: its manifest plus each artifact's own metadata."""

    run_id: str
    status: str
    created_at: str | None
    artifacts: tuple[ArtifactDetail, ...]
    pipeline: str | None = None
    pipeline_steps: tuple[PipelineStepSummary, ...] = ()
    duration_seconds: float | None = None


@dataclass(frozen=True)
class ArtifactPayload:
    """One artifact's full metadata plus its checksum-verified content."""

    detail: ArtifactDetail
    content: str


class ArtifactReader:
    """Read-only access to runs and artifacts under one artifact_root."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def list_runs(self, limit: int = _DEFAULT_LIMIT) -> tuple[RunSummary, ...]:
        """Return up to `limit` most recent runs, newest first, from run.json alone."""
        if limit <= 0 or limit > _MAX_LIMIT:
            raise InvalidLimitError(f"'limit' must be between 1 and {_MAX_LIMIT}, got {limit}.")

        if not self._root.is_dir():
            return ()

        run_dirs = sorted(
            (p for p in self._root.iterdir() if p.is_dir()), key=lambda p: p.name, reverse=True
        )

        summaries: list[RunSummary] = []
        for run_dir in run_dirs:
            manifest_path = run_dir / _RUN_MANIFEST_FILENAME
            if not manifest_path.is_file():
                continue
            manifest = _load_json(manifest_path)
            summaries.append(_summarize_run(run_dir.name, manifest, manifest_path))
            if len(summaries) >= limit:
                break
        return tuple(summaries)

    def get_run(self, run_id: str) -> RunDetail:
        """Return full detail for one run: its manifest plus each artifact's metadata."""
        run_dir = self._resolve_run_dir(run_id)
        manifest_path = run_dir / _RUN_MANIFEST_FILENAME
        if not manifest_path.is_file():
            raise RunNotFoundError(f"No run named '{run_id}' was found.")

        manifest = _load_json(manifest_path)
        summary = _summarize_run(run_id, manifest, manifest_path)

        details = []
        for entry in _manifest_artifacts(manifest, manifest_path):
            entry_id = _require_str(entry, "id", manifest_path)
            entry_status = _require_str(entry, "status", manifest_path)
            _, base_name = _split_artifact_id(entry_id)
            details.append(
                self._load_artifact_detail(
                    run_dir, entry_id, base_name=base_name, status=entry_status
                )
            )

        return RunDetail(
            run_id=summary.run_id,
            status=summary.status,
            created_at=summary.created_at,
            artifacts=tuple(details),
            pipeline=summary.pipeline,
            pipeline_steps=_pipeline_steps(manifest, manifest_path),
            duration_seconds=_optional_float(manifest, "duration_seconds", manifest_path),
        )

    def get_artifact(self, artifact_id: str) -> ArtifactPayload:
        """Return one artifact's metadata and checksum-verified payload content."""
        run_id, base_name = _split_artifact_id(artifact_id)
        run_dir = self._resolve_run_dir(run_id)
        status = _lookup_status(run_dir, artifact_id)
        detail = self._load_artifact_detail(
            run_dir, artifact_id, base_name=base_name, status=status
        )

        content_path = detail.content_path
        if not content_path.is_file():
            raise ArtifactAccessError(f"Artifact payload not found at {content_path}.")
        try:
            content = content_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ArtifactAccessError(f"Could not read artifact payload: {exc}") from exc

        if detail.checksum is not None:
            actual = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
            if actual != detail.checksum:
                raise ChecksumMismatchError(
                    f"Checksum mismatch for '{artifact_id}': "
                    f"expected {detail.checksum}, got {actual}."
                )

        return ArtifactPayload(detail=detail, content=content)

    def _resolve_run_dir(self, run_id: str) -> Path:
        _validate_id(run_id, label="run id")
        run_dir = (self._root / run_id).resolve()
        _confirm_within_root(run_dir, self._root)
        return run_dir

    def _load_artifact_detail(
        self, run_dir: Path, artifact_id: str, *, base_name: str, status: str
    ) -> ArtifactDetail:
        metadata_path = run_dir / f"{base_name}.meta.json"
        if not metadata_path.is_file():
            raise ArtifactNotFoundError(f"No artifact named '{artifact_id}' was found.")

        metadata = _load_json(metadata_path)
        produced_by = metadata.get("produced_by")
        if produced_by is not None and not isinstance(produced_by, dict):
            raise MalformedMetadataError(f"{metadata_path}: 'produced_by' must be an object.")
        provider_usage = metadata.get("provider_usage")
        if provider_usage is not None and not isinstance(provider_usage, dict):
            raise MalformedMetadataError(f"{metadata_path}: 'provider_usage' must be an object.")
        pipeline = metadata.get("pipeline")
        if pipeline is not None and not isinstance(pipeline, str):
            raise MalformedMetadataError(f"{metadata_path}: 'pipeline' must be a string.")

        display_name = metadata.get("display_name")
        if display_name is not None and not isinstance(display_name, str):
            raise MalformedMetadataError(f"{metadata_path}: 'display_name' must be a string.")

        content_ref = _require_str(metadata, "content_ref", metadata_path)

        return ArtifactDetail(
            id=_require_str(metadata, "id", metadata_path),
            run_id=_require_str(metadata, "run_id", metadata_path),
            type=_require_str(metadata, "type", metadata_path),
            content_path=run_dir / content_ref,
            status=status,
            produced_by_skill=(produced_by or {}).get("skill"),
            produced_by_version=(produced_by or {}).get("version"),
            provider_usage=provider_usage,
            pipeline=pipeline,
            display_name=display_name,
            created_at=metadata.get("created_at"),
            checksum=metadata.get("checksum"),
            content_type=metadata.get("content_type"),
        )


def _lookup_status(run_dir: Path, artifact_id: str) -> str:
    manifest_path = run_dir / _RUN_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return "unknown"
    try:
        manifest = _load_json(manifest_path)
        entries = _manifest_artifacts(manifest, manifest_path)
    except MalformedMetadataError:
        return "unknown"
    for entry in entries:
        if entry.get("id") == artifact_id:
            status = entry.get("status")
            return status if isinstance(status, str) else "unknown"
    return "unknown"


def _summarize_run(run_id: str, manifest: dict[str, Any], source: Path) -> RunSummary:
    artifacts = _manifest_artifacts(manifest, source)
    types = tuple(_require_str(entry, "type", source) for entry in artifacts)

    explicit_status = manifest.get("status")
    if explicit_status is not None:
        status = _require_str(manifest, "status", source)
    else:
        statuses = [_require_str(entry, "status", source) for entry in artifacts]
        if not statuses:
            status = "empty"
        elif all(s == "success" for s in statuses):
            status = "success"
        else:
            status = "failure"

    pipeline = manifest.get("pipeline")
    if pipeline is not None and not isinstance(pipeline, str):
        raise MalformedMetadataError(f"{source}: 'pipeline' must be a string.")

    return RunSummary(
        run_id=run_id,
        status=status,
        created_at=_created_at_from_run_id(run_id),
        artifact_count=len(artifacts),
        artifact_types=types,
        pipeline=pipeline,
    )


def _pipeline_steps(manifest: dict[str, Any], source: Path) -> tuple[PipelineStepSummary, ...]:
    raw_steps = manifest.get("pipeline_steps")
    if raw_steps is None:
        return ()
    if not isinstance(raw_steps, list):
        raise MalformedMetadataError(f"{source}: 'pipeline_steps' must be a list.")

    steps = []
    for entry in raw_steps:
        if not isinstance(entry, dict):
            raise MalformedMetadataError(f"{source}: each pipeline step must be an object.")
        artifact_ids = entry.get("artifact_ids", [])
        if not isinstance(artifact_ids, list) or not all(
            isinstance(item, str) for item in artifact_ids
        ):
            raise MalformedMetadataError(f"{source}: 'artifact_ids' must be a list of strings.")
        reason = entry.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise MalformedMetadataError(f"{source}: a pipeline step's 'reason' must be a string.")
        steps.append(
            PipelineStepSummary(
                name=_require_str(entry, "name", source),
                status=_require_str(entry, "status", source),
                reason=reason,
                artifact_ids=tuple(artifact_ids),
            )
        )
    return tuple(steps)


def _optional_float(manifest: dict[str, Any], key: str, source: Path) -> float | None:
    value = manifest.get(key)
    if value is None:
        return None
    if not isinstance(value, int | float):
        raise MalformedMetadataError(f"{source}: '{key}' must be a number.")
    return float(value)


def _created_at_from_run_id(run_id: str) -> str | None:
    match = _RUN_ID_TIMESTAMP.match(run_id)
    if not match:
        return None
    try:
        return (
            datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
            .replace(tzinfo=UTC)
            .isoformat()
        )
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ArtifactAccessError(f"Could not read {path}: {exc}") from exc
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise MalformedMetadataError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise MalformedMetadataError(f"{path} must contain a JSON object.")
    return data


def _require_str(data: dict[str, Any], key: str, source: Path) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise MalformedMetadataError(f"{source} is missing required field '{key}'.")
    return value


def _manifest_artifacts(manifest: dict[str, Any], source: Path) -> list[dict[str, Any]]:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise MalformedMetadataError(f"{source}: 'artifacts' must be a list.")
    for entry in artifacts:
        if not isinstance(entry, dict):
            raise MalformedMetadataError(f"{source}: each artifact entry must be an object.")
    return artifacts


def _validate_id(value: str, *, label: str) -> None:
    if not value:
        raise InvalidIdentifierError(f"{label} must not be empty.")
    if "\x00" in value:
        raise InvalidIdentifierError(f"{label} contains a null byte.")
    if not _ID_PATTERN.match(value):
        raise InvalidIdentifierError(f"Invalid {label}: {value!r}.")


def _split_artifact_id(artifact_id: str) -> tuple[str, str]:
    if not artifact_id or "\x00" in artifact_id:
        raise InvalidIdentifierError(f"Invalid artifact id: {artifact_id!r}.")
    parts = artifact_id.split("/")
    if len(parts) != 2:
        raise InvalidIdentifierError(f"Invalid artifact id: {artifact_id!r}.")
    run_id, base_name = parts
    _validate_id(run_id, label="run id")
    _validate_id(base_name, label="artifact id")
    return run_id, base_name


def _confirm_within_root(path: Path, root: Path) -> None:
    try:
        resolved_root = root.resolve()
    except OSError as exc:
        raise ArtifactAccessError(f"Could not resolve artifact root {root}: {exc}") from exc
    if not path.is_relative_to(resolved_root):
        raise InvalidIdentifierError(f"Resolved path {path} escapes the artifact root.")
