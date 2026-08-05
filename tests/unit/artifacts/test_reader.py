import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.fakes.clock import FixedClock, FixedIdGenerator

from buildrail.artifacts import (
    ArtifactAccessError,
    ArtifactNotFoundError,
    ArtifactReader,
    ArtifactReference,
    ArtifactStore,
    ChecksumMismatchError,
    InvalidIdentifierError,
    InvalidLimitError,
    MalformedMetadataError,
    RunNotFoundError,
)


def _store(tmp_path: Path, *, timestamp: datetime, suffix: str) -> ArtifactStore:
    return ArtifactStore(
        tmp_path, clock=FixedClock(timestamp), id_generator=FixedIdGenerator(suffix)
    )


def _write_review(
    tmp_path: Path, *, timestamp: datetime, suffix: str, content: str = "hello"
) -> tuple[str, ArtifactReference]:
    store = _store(tmp_path, timestamp=timestamp, suffix=suffix)
    run_id = store.generate_run_id()
    reference = store.write_artifact(
        run_id,
        artifact_type="review",
        content=content,
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
    return run_id, reference


def test_list_runs_returns_empty_tuple_when_no_runs_exist(tmp_path: Path) -> None:
    reader = ArtifactReader(tmp_path)

    assert reader.list_runs() == ()


def test_list_runs_returns_empty_tuple_when_root_does_not_exist(tmp_path: Path) -> None:
    reader = ArtifactReader(tmp_path / "does-not-exist")

    assert reader.list_runs() == ()


def test_list_runs_orders_newest_first(tmp_path: Path) -> None:
    _write_review(tmp_path, timestamp=datetime(2026, 1, 1, tzinfo=UTC), suffix="aaaaaa")
    _write_review(tmp_path, timestamp=datetime(2026, 6, 1, tzinfo=UTC), suffix="bbbbbb")
    _write_review(tmp_path, timestamp=datetime(2026, 3, 1, tzinfo=UTC), suffix="cccccc")
    reader = ArtifactReader(tmp_path)

    runs = reader.list_runs()

    assert [r.run_id for r in runs] == [
        "20260601-000000-bbbbbb",
        "20260301-000000-cccccc",
        "20260101-000000-aaaaaa",
    ]


def test_list_runs_respects_limit(tmp_path: Path) -> None:
    for i in range(5):
        _write_review(tmp_path, timestamp=datetime(2026, 1, i + 1, tzinfo=UTC), suffix=f"{i:06d}")
    reader = ArtifactReader(tmp_path)

    runs = reader.list_runs(limit=2)

    assert len(runs) == 2
    assert runs[0].run_id == "20260105-000000-000004"


def test_list_runs_reports_summary_fields(tmp_path: Path) -> None:
    _write_review(tmp_path, timestamp=datetime(2026, 8, 3, 12, 0, 0, tzinfo=UTC), suffix="abc123")
    reader = ArtifactReader(tmp_path)

    (summary,) = reader.list_runs()

    assert summary.run_id == "20260803-120000-abc123"
    assert summary.status == "success"
    assert summary.created_at == "2026-08-03T12:00:00+00:00"
    assert summary.artifact_count == 1
    assert summary.artifact_types == ("review",)


@pytest.mark.parametrize("limit", [0, -1, 1001])
def test_list_runs_rejects_invalid_limits(tmp_path: Path, limit: int) -> None:
    reader = ArtifactReader(tmp_path)

    with pytest.raises(InvalidLimitError):
        reader.list_runs(limit=limit)


def test_get_run_returns_full_detail(tmp_path: Path) -> None:
    run_id, reference = _write_review(
        tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123"
    )
    reader = ArtifactReader(tmp_path)

    run = reader.get_run(run_id)

    assert run.run_id == run_id
    assert run.status == "success"
    assert len(run.artifacts) == 1
    artifact = run.artifacts[0]
    assert artifact.id == reference.id
    assert artifact.type == "review"
    assert artifact.content_path == reference.content_path
    assert artifact.status == "success"
    assert artifact.produced_by_skill == "review-diff"
    assert artifact.produced_by_version == "0.1.0"
    assert artifact.provider_usage == {
        "provider": "fake",
        "model": "fake-model",
        "input_tokens": 1,
        "output_tokens": 2,
    }


def test_get_run_raises_for_unknown_run(tmp_path: Path) -> None:
    reader = ArtifactReader(tmp_path)

    with pytest.raises(RunNotFoundError):
        reader.get_run("20260101-000000-000000")


def test_get_run_raises_for_malformed_run_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "20260101-000000-000000"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text("not json", encoding="utf-8")
    reader = ArtifactReader(tmp_path)

    with pytest.raises(MalformedMetadataError):
        reader.get_run("20260101-000000-000000")


def test_get_run_surfaces_pipeline_level_fields(tmp_path: Path) -> None:
    run_id, _ = _write_review(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    store = _store(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    store.write_run_summary(
        run_id,
        pipeline="pre-commit",
        status="success",
        steps=[
            {
                "name": "verify-project",
                "status": "passed",
                "reason": None,
                "artifact_ids": ["ignored"],
            },
            {
                "name": "review-diff",
                "status": "skipped",
                "reason": "no changes",
                "artifact_ids": [],
            },
        ],
        duration_seconds=2.5,
    )
    reader = ArtifactReader(tmp_path)

    run = reader.get_run(run_id)

    assert run.pipeline == "pre-commit"
    assert run.duration_seconds == 2.5
    assert len(run.pipeline_steps) == 2
    assert run.pipeline_steps[0].name == "verify-project"
    assert run.pipeline_steps[0].status == "passed"
    assert run.pipeline_steps[1].status == "skipped"
    assert run.pipeline_steps[1].reason == "no changes"


def test_get_run_surfaces_provider_usage_totals_when_present(tmp_path: Path) -> None:
    run_id, _ = _write_review(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    store = _store(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    store.write_run_summary(
        run_id,
        pipeline="project-intelligence",
        status="success",
        steps=[],
        duration_seconds=1.0,
        provider_usage={"provider": "fake", "model": "fake-model", "input_tokens": 10},
    )
    reader = ArtifactReader(tmp_path)

    run = reader.get_run(run_id)

    assert run.provider_usage_totals == {
        "provider": "fake",
        "model": "fake-model",
        "input_tokens": 10,
    }


def test_get_run_provider_usage_totals_is_none_when_absent(tmp_path: Path) -> None:
    run_id, _ = _write_review(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    reader = ArtifactReader(tmp_path)

    run = reader.get_run(run_id)

    assert run.provider_usage_totals is None


def test_list_runs_prefers_explicit_status_over_derived_status(tmp_path: Path) -> None:
    run_id, _ = _write_review(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    store = _store(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    store.write_run_summary(
        run_id, pipeline="pre-commit", status="failure", steps=[], duration_seconds=1.0
    )
    reader = ArtifactReader(tmp_path)

    (summary,) = reader.list_runs()

    assert summary.status == "failure"
    assert summary.pipeline == "pre-commit"


def test_get_artifact_returns_metadata_and_verified_content(tmp_path: Path) -> None:
    run_id, reference = _write_review(
        tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123", content="hello"
    )
    reader = ArtifactReader(tmp_path)

    payload = reader.get_artifact(reference.id)

    assert payload.content == "hello"
    assert payload.detail.id == reference.id
    assert payload.detail.run_id == run_id
    assert payload.detail.checksum is not None
    assert payload.detail.checksum.startswith("sha256:")


def test_get_artifact_raises_for_unknown_artifact(tmp_path: Path) -> None:
    run_id, _ = _write_review(tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123")
    reader = ArtifactReader(tmp_path)

    with pytest.raises(ArtifactNotFoundError):
        reader.get_artifact(f"{run_id}/999-nope-nope")


def test_get_artifact_raises_when_payload_file_is_missing(tmp_path: Path) -> None:
    run_id, reference = _write_review(
        tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123"
    )
    reference.content_path.unlink()
    reader = ArtifactReader(tmp_path)

    with pytest.raises(ArtifactAccessError):
        reader.get_artifact(reference.id)


def test_get_artifact_raises_for_malformed_metadata(tmp_path: Path) -> None:
    run_id, reference = _write_review(
        tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123"
    )
    reference.metadata_path.write_text("not json", encoding="utf-8")
    reader = ArtifactReader(tmp_path)

    with pytest.raises(MalformedMetadataError):
        reader.get_artifact(reference.id)


def test_get_artifact_raises_on_checksum_mismatch(tmp_path: Path) -> None:
    run_id, reference = _write_review(
        tmp_path, timestamp=datetime(2026, 8, 3, tzinfo=UTC), suffix="abc123"
    )
    reference.content_path.write_text("tampered content", encoding="utf-8")
    reader = ArtifactReader(tmp_path)

    with pytest.raises(ChecksumMismatchError):
        reader.get_artifact(reference.id)


@pytest.mark.parametrize(
    "run_id",
    ["../etc", "..", "a/b", "/etc/passwd", "C:\\Windows", "with\x00null", ""],
)
def test_get_run_rejects_path_traversal_run_ids(tmp_path: Path, run_id: str) -> None:
    reader = ArtifactReader(tmp_path)

    with pytest.raises(InvalidIdentifierError):
        reader.get_run(run_id)


@pytest.mark.parametrize(
    "artifact_id",
    [
        "../secret/x",
        "run/../../etc/passwd",
        "run/a/b",
        "no-slash-at-all",
        "/abs/path",
        "run/with\x00null",
        "",
    ],
)
def test_get_artifact_rejects_path_traversal_artifact_ids(tmp_path: Path, artifact_id: str) -> None:
    reader = ArtifactReader(tmp_path)

    with pytest.raises(InvalidIdentifierError):
        reader.get_artifact(artifact_id)


def test_get_run_confirms_resolved_path_stays_within_root_via_symlink(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret"
    outside.mkdir(exist_ok=True)
    (outside / "run.json").write_text(
        json.dumps({"run_id": "outside-secret", "artifacts": []}), encoding="utf-8"
    )
    root = tmp_path / "artifacts"
    root.mkdir()
    link = root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not permitted in this environment.")
    reader = ArtifactReader(root)

    with pytest.raises(InvalidIdentifierError):
        reader.get_run("escape")
