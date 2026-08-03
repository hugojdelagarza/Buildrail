"""The review-diff skill: reviews a unified diff via the Provider Gateway.

Provider-neutral — only imports buildrail.providers' public Gateway and
request/response types, never a concrete adapter. Executed in-process for
Milestone 1 (docs/skills.md's phasing note); `entrypoint` in skill.yaml
describes the eventual subprocess invocation, not what actually runs today.
"""

from dataclasses import dataclass
from pathlib import Path

from buildrail.providers import Message, ProviderError, ProviderGateway, ProviderRequest, TextPart
from buildrail.skill_protocol import SkillOutput, SkillRequest, SkillResponse


def run(request: SkillRequest, provider: ProviderGateway) -> SkillResponse:
    """Read the requested diff, send it through the Provider Gateway, and review it."""
    diff_path = Path(request.inputs["diff"])
    try:
        diff_text = diff_path.read_text(encoding="utf-8")
    except OSError as exc:
        return SkillResponse(status="failure", outputs={}, error=f"Could not read diff: {exc}")

    provider_request = ProviderRequest(
        messages=(
            Message(role="user", content=(TextPart(text=f"Review this diff:\n\n{diff_text}"),)),
        )
    )

    try:
        provider_response = provider.complete(provider_request)
    except ProviderError as exc:
        return SkillResponse(status="failure", outputs={}, error=str(exc))

    content = _build_review(diff_text, provider_response.content)
    output = SkillOutput(
        content=content,
        artifact_type="review",
        model_used=provider_response.model_used,
        usage=provider_response.usage,
    )
    return SkillResponse(status="success", outputs={"review": output})


@dataclass(frozen=True)
class _DiffStats:
    files: tuple[str, ...]
    additions: int
    deletions: int


def _build_review(diff_text: str, provider_content: str) -> str:
    stats = _diff_stats(diff_text)
    files_list = "\n".join(f"- {name}" for name in stats.files) or "- (no files detected)"
    return (
        "# Diff Review\n\n"
        "## Provider Response\n\n"
        f"{provider_content}\n\n"
        "## Diff Summary\n\n"
        f"- Files changed: {len(stats.files)}\n"
        f"- Lines added: {stats.additions}\n"
        f"- Lines removed: {stats.deletions}\n\n"
        "### Files\n\n"
        f"{files_list}\n"
    )


def _diff_stats(diff_text: str) -> _DiffStats:
    files: list[str] = []
    additions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith(("+++ ", "--- ")):
            normalized = _normalize_diff_path(line[4:].strip())
            if normalized is not None and normalized not in files:
                files.append(normalized)
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return _DiffStats(files=tuple(files), additions=additions, deletions=deletions)


def _normalize_diff_path(path: str) -> str | None:
    """Collapse a unified diff's paired a/... and b/... markers to one filename."""
    if path == "/dev/null":
        return None
    for prefix in ("a/", "b/"):
        if path.startswith(prefix):
            return path[len(prefix) :]
    return path
