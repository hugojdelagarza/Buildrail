import subprocess
from pathlib import Path

import pytest

from buildrail import vcs


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")


def _commit(repo: Path, filename: str, content: str, message: str) -> None:
    (repo / filename).write_text(content, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-q", "-m", message)


def test_repository_root_returns_top_level_directory(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    root = vcs.repository_root(tmp_path)

    assert root.resolve() == tmp_path.resolve()


def test_repository_root_raises_when_not_a_git_repository(tmp_path: Path) -> None:
    with pytest.raises(vcs.NotAGitRepositoryError):
        vcs.repository_root(tmp_path)


def test_resolve_base_ref_uses_explicit_ref(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "a\n", "chore: first")

    resolved = vcs.resolve_base_ref(tmp_path, "HEAD")

    assert resolved == "HEAD"


def test_resolve_base_ref_raises_for_invalid_explicit_ref(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "a\n", "chore: first")

    with pytest.raises(vcs.InvalidBaseRefError):
        vcs.resolve_base_ref(tmp_path, "does-not-exist")


def test_resolve_base_ref_falls_back_to_head_parent(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "a\n", "chore: first")
    _commit(tmp_path, "b.txt", "b\n", "feat: second")

    resolved = vcs.resolve_base_ref(tmp_path, None)

    assert resolved == "HEAD~1"


def test_resolve_base_ref_raises_when_no_base_is_usable(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "a\n", "chore: only commit")

    with pytest.raises(vcs.InvalidBaseRefError):
        vcs.resolve_base_ref(tmp_path, None)


def test_resolve_base_ref_prefers_upstream_branch(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    _git(tmp_path, "init", "-q", "--bare", str(remote))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _commit(repo, "a.txt", "a\n", "chore: first")
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "-u", "origin", "HEAD:main")

    resolved = vcs.resolve_base_ref(repo, None)

    assert resolved == "origin/main"


def test_collect_diff_reports_empty_diff_for_a_clean_tree(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "a\n", "chore: first")

    result = vcs.collect_diff(tmp_path, "HEAD")

    assert result.is_empty


def test_collect_diff_reports_a_real_diff(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "a\n", "chore: first")
    (tmp_path / "a.txt").write_text("a\nb\n", encoding="utf-8")

    result = vcs.collect_diff(tmp_path, "HEAD")

    assert not result.is_empty
    assert "a.txt" in result.diff_text


def test_collect_diff_raises_for_a_command_failure(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _commit(tmp_path, "a.txt", "a\n", "chore: first")

    with pytest.raises(vcs.GitCommandError):
        vcs.collect_diff(tmp_path, "not-a-real-ref-at-all")


def test_diff_collection_works_in_a_path_containing_spaces(tmp_path: Path) -> None:
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    _init_repo(repo)
    _commit(repo, "a.txt", "a\n", "chore: first")
    (repo / "a.txt").write_text("a\nb\n", encoding="utf-8")

    resolved = vcs.resolve_base_ref(repo, "HEAD")
    result = vcs.collect_diff(repo, resolved)

    assert not result.is_empty
