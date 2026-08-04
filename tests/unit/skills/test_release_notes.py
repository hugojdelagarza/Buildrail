import subprocess
from pathlib import Path

from buildrail.providers import ProviderGateway
from buildrail.providers.adapters.fake import FakeProvider
from buildrail.providers.errors import AuthenticationError
from buildrail.skill_protocol import RunContext, SkillRequest
from buildrail.skills import SkillRegistry

_SKILL_SOURCE = (
    Path(__file__).resolve().parents[3] / "skills" / "release-notes" / "skill.py"
).read_text(encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")


def _commit(repo: Path, filename: str, message: str) -> None:
    (repo / filename).write_text("content\n", encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-q", "-m", message)


def _request(repo: Path, inputs: dict[str, str] | None = None) -> SkillRequest:
    return SkillRequest(
        protocol_version="1.0",
        run_context=RunContext(run_id="20260804-000000-test", step_index=1, workdir=str(repo)),
        inputs=inputs or {},
        config={},
    )


def test_skill_source_never_imports_a_provider_adapter_or_core_internals() -> None:
    assert "FakeProvider" not in _SKILL_SOURCE
    assert "providers.adapters" not in _SKILL_SOURCE
    assert "buildrail.core" not in _SKILL_SOURCE


def test_run_returns_failure_when_not_a_git_repository(tmp_path: Path) -> None:
    run_release_notes = SkillRegistry().resolve("release-notes")
    gateway = ProviderGateway(FakeProvider())

    response = run_release_notes(_request(tmp_path), gateway)

    assert response.status == "failure"
    assert response.error is not None
    assert response.outputs == {}


def test_run_reports_no_commits_without_calling_the_provider(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "feat: initial commit")
    _git(tmp_path, "tag", "v0.1.0")
    run_release_notes = SkillRegistry().resolve("release-notes")
    gateway = ProviderGateway(FakeProvider(error=AuthenticationError("must not be called")))

    response = run_release_notes(_request(tmp_path), gateway)

    assert response.status == "success"
    output = response.outputs["notes"]
    assert "No commits found" in output.content
    assert output.model_used is None


def test_run_generates_notes_from_commits_since_last_tag(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "chore: initial commit")
    _git(tmp_path, "tag", "v0.1.0")
    _commit(tmp_path, "b.txt", "feat: add widgets")
    _commit(tmp_path, "c.txt", "fix: correct widget count")
    _commit(tmp_path, "d.txt", "docs: document widgets")
    run_release_notes = SkillRegistry().resolve("release-notes")
    gateway = ProviderGateway(FakeProvider())

    response = run_release_notes(_request(tmp_path), gateway)

    assert response.status == "success"
    output = response.outputs["notes"]
    assert "_Range: v0.1.0..HEAD_" in output.content
    assert "## Features" in output.content
    assert "add widgets" in output.content
    assert "## Fixes" in output.content
    assert "correct widget count" in output.content
    assert "## Documentation" in output.content
    assert "document widgets" in output.content
    assert "## Contributors" in output.content
    assert "Test User" in output.content
    assert "[fake response]" in output.content
    assert output.model_used == "fake-model"
    assert output.usage is not None


def test_run_detects_breaking_changes_from_bang_and_footer(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "chore: initial commit")
    _git(tmp_path, "tag", "v0.1.0")
    _commit(tmp_path, "b.txt", "feat!: remove legacy API")
    _git(
        tmp_path,
        "commit",
        "--allow-empty",
        "-q",
        "-m",
        "fix: adjust config\n\nBREAKING CHANGE: config format changed",
    )
    run_release_notes = SkillRegistry().resolve("release-notes")
    gateway = ProviderGateway(FakeProvider())

    response = run_release_notes(_request(tmp_path), gateway)

    output = response.outputs["notes"]
    assert "## Breaking Changes" in output.content
    assert "remove legacy API" in output.content
    assert "adjust config" in output.content


def test_run_uses_explicit_from_and_to_inputs(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "chore: first")
    first_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit(tmp_path, "b.txt", "feat: second")
    second_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout.strip()
    _commit(tmp_path, "c.txt", "feat: third")
    run_release_notes = SkillRegistry().resolve("release-notes")
    gateway = ProviderGateway(FakeProvider())

    response = run_release_notes(_request(tmp_path, {"from": first_sha, "to": second_sha}), gateway)

    output = response.outputs["notes"]
    assert "second" in output.content
    assert "third" not in output.content


def test_run_returns_failure_when_provider_errors(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "feat: add thing")
    run_release_notes = SkillRegistry().resolve("release-notes")
    gateway = ProviderGateway(FakeProvider(error=AuthenticationError("no key")))

    response = run_release_notes(_request(tmp_path), gateway)

    assert response.status == "failure"
    assert response.error == "no key"
    assert response.outputs == {}


def test_run_returns_failure_for_invalid_range(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "feat: add thing")
    run_release_notes = SkillRegistry().resolve("release-notes")
    gateway = ProviderGateway(FakeProvider())

    response = run_release_notes(_request(tmp_path, {"from": "does-not-exist"}), gateway)

    assert response.status == "failure"
    assert response.error is not None
