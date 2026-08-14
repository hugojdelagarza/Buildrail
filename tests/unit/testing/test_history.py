import json
from pathlib import Path

from buildrail.artifacts import ArtifactReader, ArtifactStore
from buildrail.testing import (
    HistoryEntry,
    flaky_signals_from_history,
    gather_recent_failure_history,
    history_from_dict,
    history_to_dict,
)


def _write_test_report_run(store: ArtifactStore, *, failing_node_ids: list[str], total: int) -> str:
    run_id = store.generate_run_id()
    payload = json.dumps(
        {"counts": {"total": total}, "failures": [{"node_id": n} for n in failing_node_ids]}
    )
    store.write_artifact(
        run_id,
        artifact_type="test-report",
        content=payload,
        content_type="application/json",
        slug="report_json",
        produced_by={"skill": "test-report", "version": "0.1.0"},
    )
    return run_id


def test_gather_recent_failure_history_reads_failing_node_ids(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    _write_test_report_run(store, failing_node_ids=["test_a.py::test_x"], total=3)
    reader = ArtifactReader(tmp_path)

    history = gather_recent_failure_history(reader)

    assert len(history) == 1
    assert history[0].failing_node_ids == ("test_a.py::test_x",)


def test_gather_recent_failure_history_ignores_runs_with_no_tests(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    _write_test_report_run(store, failing_node_ids=[], total=0)
    reader = ArtifactReader(tmp_path)

    history = gather_recent_failure_history(reader)

    assert history == ()


def test_gather_recent_failure_history_ignores_unrelated_runs(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    run_id = store.generate_run_id()
    store.write_artifact(
        run_id,
        artifact_type="verification-report",
        content="# report",
        content_type="text/markdown",
        slug="report",
        produced_by={"skill": "verify-project", "version": "0.1.0"},
    )
    reader = ArtifactReader(tmp_path)

    history = gather_recent_failure_history(reader)

    assert history == ()


def test_gather_recent_failure_history_degrades_on_missing_root(tmp_path: Path) -> None:
    reader = ArtifactReader(tmp_path / "does-not-exist")

    assert gather_recent_failure_history(reader) == ()


def test_flaky_signal_fires_when_test_absent_from_a_recent_failure_list() -> None:
    history = (HistoryEntry(run_id="run-1", failing_node_ids=("test_a.py::test_x",)),)

    signals = flaky_signals_from_history(("test_a.py::test_y",), history)

    assert len(signals) == 1
    assert signals[0].node_id == "test_a.py::test_y"
    assert "possible flaky signal" in signals[0].note.lower()


def test_no_signal_when_test_also_failed_recently() -> None:
    history = (HistoryEntry(run_id="run-1", failing_node_ids=("test_a.py::test_x",)),)

    signals = flaky_signals_from_history(("test_a.py::test_x",), history)

    assert signals == ()


def test_no_signal_without_current_failures() -> None:
    history = (HistoryEntry(run_id="run-1", failing_node_ids=()),)

    assert flaky_signals_from_history((), history) == ()


def test_no_signal_without_history() -> None:
    assert flaky_signals_from_history(("test_a.py::test_x",), ()) == ()


def test_each_node_id_flagged_at_most_once() -> None:
    history = (
        HistoryEntry(run_id="run-1", failing_node_ids=()),
        HistoryEntry(run_id="run-2", failing_node_ids=()),
    )

    signals = flaky_signals_from_history(("test_a.py::test_x",), history)

    assert len(signals) == 1


def test_history_dict_round_trip() -> None:
    original = (HistoryEntry(run_id="run-1", failing_node_ids=("a", "b")),)

    round_tripped = history_from_dict(history_to_dict(original))

    assert round_tripped == original
