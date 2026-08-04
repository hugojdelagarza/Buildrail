"""The release-notes skill: generates Markdown release notes from Git history.

Provider-neutral — only imports buildrail.providers' public Gateway and
request/response types, never a concrete adapter. Executed in-process for
Milestone 1 (docs/skills.md's phasing note); `entrypoint` in skill.yaml
describes the eventual subprocess invocation, not what actually runs today.
All Git access goes through the small `_run_git`/`_collect_commits` helper
layer below — nothing else in this file shells out directly.
"""

import re
import subprocess
from dataclasses import dataclass

from buildrail.providers import Message, ProviderError, ProviderGateway, ProviderRequest, TextPart
from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse

_MAX_COMMITS = 200
_FIELD_SEP = "\x1f"
_RECORD_SEP = "\x1e"
_LOG_FORMAT = f"%H{_FIELD_SEP}%an{_FIELD_SEP}%s{_FIELD_SEP}%b{_RECORD_SEP}"

_COMMIT_PATTERN = re.compile(r"^(?P<type>\w+)(?:\([^)]*\))?(?P<breaking>!)?:\s*(?P<subject>.+)$")

_SECTION_TITLES = {
    "breaking": "Breaking Changes",
    "features": "Features",
    "fixes": "Fixes",
    "documentation": "Documentation",
    "other": "Other Changes",
}
_SECTION_ORDER = ("breaking", "features", "fixes", "documentation", "other")


@dataclass(frozen=True)
class _Commit:
    sha: str
    author: str
    subject: str
    body: str


def run(request: SkillRequest, provider: ProviderGateway) -> SkillResponse:
    """Collect commits since the last tag (or a given range) and summarize them."""
    workdir = request.run_context.workdir
    from_ref = request.inputs.get("from")
    to_ref = request.inputs.get("to")

    check = _run_git(workdir, "rev-parse", "--is-inside-work-tree")
    if check.returncode != 0:
        reason = check.stderr.strip() or f"{workdir} is not a Git repository."
        return SkillResponse(status="failure", outputs={}, error=reason)

    commits, range_label, error = _collect_commits(workdir, from_ref, to_ref)
    if error is not None:
        return SkillResponse(status="failure", outputs={}, error=error)

    if not commits:
        content = f"# Release Notes\n\n_Range: {range_label}_\n\nNo commits found in this range.\n"
        output = SkillOutput(content=content, artifact_type="release-notes")
        return SkillResponse(status="success", outputs={"notes": output})

    grouped = _group_by_category(commits)
    contributors = sorted({commit.author for commit in commits})

    provider_request = ProviderRequest(
        messages=(Message(role="user", content=(TextPart(text=_build_prompt(commits)),)),)
    )
    try:
        provider_response = provider.complete(provider_request)
    except ProviderError as exc:
        return SkillResponse(status="failure", outputs={}, error=str(exc))

    content = _build_report(grouped, contributors, provider_response.content, range_label)
    output = SkillOutput(
        content=content,
        artifact_type="release-notes",
        model_used=provider_response.model_used,
        usage=provider_response.usage,
    )
    return SkillResponse(status="success", outputs={"notes": output})


def _run_git(workdir: str, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args], cwd=workdir, capture_output=True, text=True, timeout=30
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=["git", *args], returncode=1, stdout="", stderr=str(exc)
        )


def _latest_tag(workdir: str) -> str | None:
    result = _run_git(workdir, "describe", "--tags", "--abbrev=0")
    if result.returncode != 0:
        return None
    tag = result.stdout.strip()
    return tag or None


def _resolve_range(workdir: str, from_ref: str | None, to_ref: str | None) -> tuple[str, str]:
    """Return (git range argument, human-readable label)."""
    to_ref = to_ref or "HEAD"
    if from_ref:
        return f"{from_ref}..{to_ref}", f"{from_ref}..{to_ref}"

    tag = _latest_tag(workdir)
    if tag:
        return f"{tag}..{to_ref}", f"{tag}..{to_ref}"
    return to_ref, f"{to_ref} (no previous tag found)"


def _collect_commits(
    workdir: str, from_ref: str | None, to_ref: str | None
) -> tuple[list[_Commit], str, str | None]:
    range_arg, range_label = _resolve_range(workdir, from_ref, to_ref)

    result = _run_git(
        workdir, "log", range_arg, f"-{_MAX_COMMITS}", f"--pretty=format:{_LOG_FORMAT}"
    )
    if result.returncode != 0:
        error = result.stderr.strip() or f"git log failed for range '{range_arg}'."
        return [], range_label, error

    return _parse_log_output(result.stdout), range_label, None


def _parse_log_output(raw: str) -> list[_Commit]:
    commits = []
    for record in raw.split(_RECORD_SEP):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split(_FIELD_SEP)
        if len(parts) < 4:
            continue
        sha, author, subject, body = parts[0], parts[1], parts[2], parts[3]
        commits.append(
            _Commit(
                sha=sha.strip(), author=author.strip(), subject=subject.strip(), body=body.strip()
            )
        )
    return commits


def _categorize(commit: _Commit) -> str:
    is_breaking = "BREAKING CHANGE" in commit.body
    match = _COMMIT_PATTERN.match(commit.subject)
    if match:
        if match.group("breaking") or is_breaking:
            return "breaking"
        commit_type = match.group("type").lower()
        if commit_type == "feat":
            return "features"
        if commit_type == "fix":
            return "fixes"
        if commit_type == "docs":
            return "documentation"
        return "other"
    return "breaking" if is_breaking else "other"


def _group_by_category(commits: list[_Commit]) -> dict[str, list[_Commit]]:
    grouped: dict[str, list[_Commit]] = {key: [] for key in _SECTION_ORDER}
    for commit in commits:
        grouped[_categorize(commit)].append(commit)
    return grouped


def _build_prompt(commits: list[_Commit]) -> str:
    subjects = "\n".join(f"- {commit.subject}" for commit in commits)
    return (
        "Write a concise, 2-4 sentence prose summary of this software release based on "
        f"its commit messages, highlighting the overall theme:\n\n{subjects}"
    )


def _build_report(
    grouped: dict[str, list[_Commit]],
    contributors: list[str],
    ai_summary: str,
    range_label: str,
) -> str:
    lines = ["# Release Notes", "", f"_Range: {range_label}_", "", ai_summary, ""]

    for key in _SECTION_ORDER:
        group = grouped.get(key, [])
        if not group:
            continue
        lines.append(f"## {_SECTION_TITLES[key]}")
        lines.append("")
        for commit in group:
            lines.append(f"- {commit.subject} ({commit.sha[:7]})")
        lines.append("")

    if contributors:
        lines.append("## Contributors")
        lines.append("")
        for name in contributors:
            lines.append(f"- {name}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
