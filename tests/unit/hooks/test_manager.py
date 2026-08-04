import subprocess
from pathlib import Path

import pytest

from buildrail.hooks import (
    HooksDirectoryError,
    MalformedManagedBlockError,
    NotAGitRepositoryError,
)
from buildrail.hooks import manager as hooks


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "-q")


def _hook_path(repo: Path) -> Path:
    return repo / ".git" / "hooks" / "pre-commit"


def test_install_in_a_repository_with_no_existing_hook(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    result = hooks.install(tmp_path)

    assert result.action == "installed"
    content = _hook_path(tmp_path).read_text(encoding="utf-8")
    assert content.startswith("#!/bin/sh\n")
    assert "# BEGIN BUILDRAIL MANAGED BLOCK" in content
    assert "buildrail verify" in content
    assert "# END BUILDRAIL MANAGED BLOCK" in content


def test_install_preserves_an_existing_user_hook(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    hook_path = _hook_path(tmp_path)
    hook_path.write_text('#!/bin/sh\necho "custom hook"\n', encoding="utf-8")

    result = hooks.install(tmp_path)

    assert result.action == "installed"
    content = hook_path.read_text(encoding="utf-8")
    assert content.startswith('#!/bin/sh\necho "custom hook"\n')
    assert "# BEGIN BUILDRAIL MANAGED BLOCK" in content
    assert "buildrail verify" in content


def test_repeated_install_is_idempotent(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    first = hooks.install(tmp_path)
    content_after_first = _hook_path(tmp_path).read_text(encoding="utf-8")
    second = hooks.install(tmp_path)
    content_after_second = _hook_path(tmp_path).read_text(encoding="utf-8")

    assert first.action == "installed"
    assert second.action == "already_installed"
    assert content_after_first == content_after_second
    assert content_after_second.count("# BEGIN BUILDRAIL MANAGED BLOCK") == 1


def test_uninstall_removes_only_the_managed_block(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    hook_path = _hook_path(tmp_path)
    hook_path.write_text('#!/bin/sh\necho "custom hook"\n', encoding="utf-8")
    hooks.install(tmp_path)

    result = hooks.uninstall(tmp_path)

    assert result.action == "removed_block"
    content = hook_path.read_text(encoding="utf-8")
    assert content == '#!/bin/sh\necho "custom hook"\n'
    assert "BUILDRAIL" not in content


def test_repeated_uninstall_is_idempotent(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    hooks.install(tmp_path)

    first = hooks.uninstall(tmp_path)
    second = hooks.uninstall(tmp_path)

    assert first.action in ("removed_file", "removed_block")
    assert second.action == "not_installed"


def test_uninstall_deletes_a_hook_created_solely_by_buildrail(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    hooks.install(tmp_path)

    result = hooks.uninstall(tmp_path)

    assert result.action == "removed_file"
    assert not _hook_path(tmp_path).exists()


def test_status_reports_installed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    hooks.install(tmp_path)

    result = hooks.status(tmp_path)

    assert result.state == "installed"


def test_status_reports_not_installed(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    result = hooks.status(tmp_path)

    assert result.state == "not_installed"


def test_status_raises_for_duplicate_markers(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    hook_path = _hook_path(tmp_path)
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text(
        "#!/bin/sh\n"
        "# BEGIN BUILDRAIL MANAGED BLOCK\n"
        "echo one\n"
        "# BEGIN BUILDRAIL MANAGED BLOCK\n"
        "echo two\n"
        "# END BUILDRAIL MANAGED BLOCK\n",
        encoding="utf-8",
    )

    with pytest.raises(MalformedManagedBlockError, match="Duplicate"):
        hooks.status(tmp_path)


def test_install_raises_for_unterminated_block(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    hook_path = _hook_path(tmp_path)
    hook_path.parent.mkdir(parents=True, exist_ok=True)
    hook_path.write_text("#!/bin/sh\n# BEGIN BUILDRAIL MANAGED BLOCK\necho one\n", encoding="utf-8")

    with pytest.raises(MalformedManagedBlockError, match="Unterminated"):
        hooks.install(tmp_path)


def test_install_respects_a_custom_relative_hooks_path(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "custom-hooks").mkdir()
    _git(tmp_path, "config", "core.hooksPath", "custom-hooks")

    result = hooks.install(tmp_path)

    assert result.hook_path == tmp_path / "custom-hooks" / "pre-commit"
    assert result.hook_path.is_file()
    assert not _hook_path(tmp_path).is_file()


def test_install_works_in_a_path_containing_spaces(tmp_path: Path) -> None:
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    _init_repo(repo)

    result = hooks.install(repo)

    assert result.action == "installed"
    assert result.hook_path.is_file()


def test_install_raises_when_not_a_git_repository(tmp_path: Path) -> None:
    with pytest.raises(NotAGitRepositoryError):
        hooks.install(tmp_path)


def test_install_raises_when_hooks_path_is_blocked_by_a_file(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "custom-hooks").write_text("not a directory", encoding="utf-8")
    _git(tmp_path, "config", "core.hooksPath", "custom-hooks")

    with pytest.raises(HooksDirectoryError):
        hooks.install(tmp_path)


def test_atomic_write_failure_is_mapped_to_a_typed_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _init_repo(tmp_path)

    def _raise(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", _raise)

    with pytest.raises(HooksDirectoryError, match="disk full"):
        hooks.install(tmp_path)
