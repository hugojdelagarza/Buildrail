import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from tests.fakes.clock import FixedClock, FixedIdGenerator

from buildrail.artifacts import ArtifactStore


def _store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(
        tmp_path,
        clock=FixedClock(datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC)),
        id_generator=FixedIdGenerator("abc123"),
    )


def test_generate_run_id_is_deterministic_with_fixed_collaborators(tmp_path: Path) -> None:
    store = _store(tmp_path)

    run_id = store.generate_run_id()

    assert run_id == "20260803-120000-abc123"


def test_write_artifact_creates_payload_and_metadata_files(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = store.generate_run_id()

    reference = store.write_artifact(
        run_id,
        artifact_type="review",
        content="# Review\n",
        content_type="text/markdown",
        slug="diff",
        produced_by={"skill": "review-diff", "version": "0.1.0"},
    )

    assert reference.content_path.read_text(encoding="utf-8") == "# Review\n"
    assert reference.content_path.name == "001-review-diff.md"
    assert reference.metadata_path.is_file()


def test_write_artifact_metadata_has_expected_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = store.generate_run_id()

    reference = store.write_artifact(
        run_id,
        artifact_type="review",
        content="hello",
        content_type="text/markdown",
        slug="diff",
        produced_by={"skill": "review-diff", "version": "0.1.0"},
        provider_usage={
            "provider": "fake",
            "model": "fake-model",
            "input_tokens": 1,
            "output_tokens": 2,
        },
    )

    metadata = json.loads(reference.metadata_path.read_text(encoding="utf-8"))
    assert metadata["id"] == reference.id
    assert metadata["type"] == "review"
    assert metadata["run_id"] == run_id
    assert metadata["pipeline"] is None
    assert metadata["content_ref"] == "001-review-diff.md"
    assert metadata["content_type"] == "text/markdown"
    assert metadata["provider_usage"]["model"] == "fake-model"
    assert metadata["checksum"].startswith("sha256:")


def test_write_artifact_records_pipeline_name_when_provided(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = store.generate_run_id()

    reference = store.write_artifact(
        run_id,
        artifact_type="verification-report",
        content="# Report\n",
        content_type="text/markdown",
        slug="report",
        produced_by={"skill": "verify-project", "version": "0.1.0"},
        pipeline="pre-commit",
    )

    metadata = json.loads(reference.metadata_path.read_text(encoding="utf-8"))
    assert metadata["pipeline"] == "pre-commit"


def test_write_artifact_checksum_matches_content(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = store.generate_run_id()
    content = "some review content"

    reference = store.write_artifact(
        run_id,
        artifact_type="review",
        content=content,
        content_type="text/markdown",
        slug="diff",
        produced_by={"skill": "review-diff", "version": "0.1.0"},
    )

    metadata = json.loads(reference.metadata_path.read_text(encoding="utf-8"))
    expected = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
    assert metadata["checksum"] == expected


def test_write_artifact_writes_run_manifest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = store.generate_run_id()

    reference = store.write_artifact(
        run_id,
        artifact_type="review",
        content="hello",
        content_type="text/markdown",
        slug="diff",
        produced_by={"skill": "review-diff", "version": "0.1.0"},
    )

    manifest_path = tmp_path / run_id / "run.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == run_id
    assert manifest["artifacts"] == [
        {"id": reference.id, "type": "review", "path": "001-review-diff.md", "status": "success"}
    ]


def test_write_run_summary_records_pipeline_level_fields(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = store.generate_run_id()
    store.write_artifact(
        run_id,
        artifact_type="verification-report",
        content="# Verification Report\n",
        content_type="text/markdown",
        slug="report",
        produced_by={"skill": "verify-project", "version": "0.1.0"},
    )

    store.write_run_summary(
        run_id,
        pipeline="pre-commit",
        status="success",
        steps=[
            {"name": "verify-project", "status": "passed", "reason": None, "artifact_ids": ["x"]},
            {
                "name": "review-diff",
                "status": "skipped",
                "reason": "no changes",
                "artifact_ids": [],
            },
        ],
        duration_seconds=1.23,
        provider_usage={"provider": "fake", "model": "fake-model", "input_tokens": 1},
    )

    manifest = json.loads((tmp_path / run_id / "run.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == run_id
    assert manifest["pipeline"] == "pre-commit"
    assert manifest["status"] == "success"
    assert manifest["duration_seconds"] == 1.23
    assert manifest["provider_usage_totals"]["model"] == "fake-model"
    assert len(manifest["pipeline_steps"]) == 2
    assert manifest["pipeline_steps"][1]["status"] == "skipped"
    # The artifact written earlier is preserved alongside the new summary fields.
    assert len(manifest["artifacts"]) == 1


def test_write_run_summary_creates_run_directory_if_missing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run_id = store.generate_run_id()

    store.write_run_summary(
        run_id, pipeline="pre-commit", status="failure", steps=[], duration_seconds=0.5
    )

    manifest = json.loads((tmp_path / run_id / "run.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failure"
    assert manifest["artifacts"] == []
