"""Conservative flaky-test signals derived from recent `test-report` artifacts.

Split into two pure pieces so the `test-report` skill (which has no
`ArtifactReader` access, by design — it only ever sees `SkillRequest`/a
provider, like every other skill) can still use them: `CoreEngine` gathers
recent history *before* running the skill (reading only prior runs, so
there's no chicken-and-egg dependency on the current run's own result) and
passes it in as a small JSON file, the same way `analysis_json` is passed to
`explain-project`. The skill then compares its own just-computed failing
test ids against that history and folds the signals into the report it
returns — no artifact is ever mutated after being written.

No reruns, no certainty claims — a signal only ever means "this test is
failing now and its outcome looks inconsistent with a recent run," worded as
a "possible flaky signal," never a confident "this test is flaky."
"""

import json
from dataclasses import dataclass

from buildrail.artifacts import ArtifactReader, ArtifactReadError
from buildrail.testing.models import FlakySignal

_DEFAULT_HISTORY_LIMIT = 10


@dataclass(frozen=True)
class HistoryEntry:
    """One prior run's failing test node ids, per its test-report JSON artifact."""

    run_id: str
    failing_node_ids: tuple[str, ...]


def gather_recent_failure_history(
    reader: ArtifactReader, *, limit: int = _DEFAULT_HISTORY_LIMIT
) -> tuple[HistoryEntry, ...]:
    """Read the failing node ids from up to `limit` recent test-report runs.

    Degrades to no history (never raises) if it can't be read — history is
    an advisory addition to a test report, not something that should ever
    block or fail a test run.
    """
    try:
        runs = reader.list_runs(limit)
    except ArtifactReadError:
        return ()

    entries: list[HistoryEntry] = []
    for run in runs:
        if "test-report" not in run.artifact_types:
            continue
        try:
            detail = reader.get_run(run.run_id)
        except ArtifactReadError:
            continue

        json_artifact = next(
            (
                a
                for a in detail.artifacts
                if a.type == "test-report" and a.content_type == "application/json"
            ),
            None,
        )
        if json_artifact is None:
            continue

        try:
            payload = reader.get_artifact(json_artifact.id)
            data = json.loads(payload.content)
        except (ArtifactReadError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue

        counts = data.get("counts")
        if not isinstance(counts, dict) or not counts.get("total"):
            continue

        raw_failures = data.get("failures", [])
        if not isinstance(raw_failures, list):
            continue
        failing_node_ids = tuple(
            entry["node_id"]
            for entry in raw_failures
            if isinstance(entry, dict) and isinstance(entry.get("node_id"), str)
        )
        entries.append(HistoryEntry(run_id=run.run_id, failing_node_ids=failing_node_ids))

    return tuple(entries)


def flaky_signals_from_history(
    current_failing_node_ids: tuple[str, ...], history: tuple[HistoryEntry, ...]
) -> tuple[FlakySignal, ...]:
    """Flag currently-failing tests absent from a recent run's own failures."""
    if not current_failing_node_ids or not history:
        return ()

    signals: list[FlakySignal] = []
    flagged: set[str] = set()
    for entry in history:
        for node_id in current_failing_node_ids:
            if node_id in flagged or node_id in entry.failing_node_ids:
                continue
            signals.append(
                FlakySignal(
                    node_id=node_id,
                    note=(
                        f"Failing now; did not appear in the failures of recent run "
                        f"{entry.run_id} (possible flaky signal)."
                    ),
                )
            )
            flagged.add(node_id)
    return tuple(signals)


def history_to_dict(history: tuple[HistoryEntry, ...]) -> list[dict[str, object]]:
    """Serialize history entries for the temp file passed to the skill as an input."""
    return [{"run_id": e.run_id, "failing_node_ids": list(e.failing_node_ids)} for e in history]


def history_from_dict(data: list[dict[str, object]]) -> tuple[HistoryEntry, ...]:
    """Deserialize history entries read back from the temp file by the skill."""
    entries = []
    for item in data:
        run_id = item["run_id"]
        failing_node_ids = item["failing_node_ids"]
        if not isinstance(run_id, str) or not isinstance(failing_node_ids, list):
            continue
        entries.append(
            HistoryEntry(run_id=run_id, failing_node_ids=tuple(str(n) for n in failing_node_ids))
        )
    return tuple(entries)
