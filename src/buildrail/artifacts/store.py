"""The Artifact Store: atomic, checksum-verified writes of typed artifacts to disk."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from buildrail.artifacts.ids import Clock, IdGenerator, SystemClock, SystemIdGenerator


@dataclass(frozen=True)
class ArtifactReference:
    """A pointer to one artifact this store just wrote."""

    id: str
    run_id: str
    content_path: Path
    metadata_path: Path


class ArtifactStore:
    """Writes typed artifacts to `<root>/<run-id>/`, per docs/artifacts.md."""

    def __init__(
        self,
        root: Path,
        *,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
    ) -> None:
        self._root = root
        self._clock = clock or SystemClock()
        self._id_generator = id_generator or SystemIdGenerator()

    def generate_run_id(self) -> str:
        """Generate a new, chronologically-sortable, collision-resistant run id."""
        timestamp = self._clock.utcnow().strftime("%Y%m%d-%H%M%S")
        return f"{timestamp}-{self._id_generator.next_id()}"

    def write_artifact(
        self,
        run_id: str,
        *,
        artifact_type: str,
        content: str,
        content_type: str,
        slug: str,
        produced_by: dict[str, str],
        provider_usage: dict[str, object] | None = None,
        pipeline: str | None = None,
        display_name: str | None = None,
    ) -> ArtifactReference:
        """Create the run directory if needed and atomically write one artifact into it."""
        run_dir = self._root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        extension = "md" if content_type == "text/markdown" else "json"
        base_name = f"001-{artifact_type}-{slug}"
        content_path = run_dir / f"{base_name}.{extension}"
        metadata_path = run_dir / f"{base_name}.meta.json"

        _atomic_write(content_path, content)

        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        artifact_id = f"{run_id}/{base_name}"

        metadata: dict[str, object] = {
            "id": artifact_id,
            "schema_version": "1.0",
            "type": artifact_type,
            "produced_by": produced_by,
            "run_id": run_id,
            "pipeline": pipeline,
            "display_name": display_name,
            "step_index": 1,
            "created_at": self._clock.utcnow().isoformat(),
            "content_ref": content_path.name,
            "content_type": content_type,
            "checksum": f"sha256:{checksum}",
        }
        if provider_usage is not None:
            metadata["provider_usage"] = provider_usage

        _atomic_write(metadata_path, json.dumps(metadata, indent=2, sort_keys=True))
        self._append_to_run_manifest(run_dir, run_id, artifact_id, artifact_type, content_path.name)

        return ArtifactReference(
            id=artifact_id, run_id=run_id, content_path=content_path, metadata_path=metadata_path
        )

    def _append_to_run_manifest(
        self, run_dir: Path, run_id: str, artifact_id: str, artifact_type: str, path_name: str
    ) -> None:
        manifest = self._load_or_init_manifest(run_dir, run_id)
        manifest["artifacts"].append(
            {"id": artifact_id, "type": artifact_type, "path": path_name, "status": "success"}
        )
        _atomic_write(run_dir / "run.json", json.dumps(manifest, indent=2, sort_keys=True))

    def write_run_summary(
        self,
        run_id: str,
        *,
        pipeline: str,
        status: str,
        steps: list[dict[str, object]],
        duration_seconds: float,
        provider_usage: dict[str, object] | None = None,
    ) -> None:
        """Record named-pipeline-level metadata (status, ordered steps, duration) in run.json.

        Complements `write_artifact`'s per-artifact entries with the
        aggregate facts a named, multi-step pipeline needs to report —
        e.g. a step that was skipped and so never produced an artifact.
        """
        run_dir = self._root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = self._load_or_init_manifest(run_dir, run_id)
        manifest["pipeline"] = pipeline
        manifest["status"] = status
        manifest["pipeline_steps"] = steps
        manifest["duration_seconds"] = duration_seconds
        if provider_usage is not None:
            manifest["provider_usage_totals"] = provider_usage
        _atomic_write(run_dir / "run.json", json.dumps(manifest, indent=2, sort_keys=True))

    @staticmethod
    def _load_or_init_manifest(run_dir: Path, run_id: str) -> dict[str, Any]:
        manifest_path = run_dir / "run.json"
        if manifest_path.is_file():
            manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
            return manifest
        return {"run_id": run_id, "artifacts": []}


def _atomic_write(path: Path, content: str) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)
