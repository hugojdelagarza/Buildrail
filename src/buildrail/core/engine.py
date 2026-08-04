"""The Core Engine: Buildrail's single orchestration entry point."""

from dataclasses import dataclass
from pathlib import Path

from buildrail.artifacts import ArtifactReader, ArtifactReadError, ArtifactStore
from buildrail.config import BuildrailConfig, ConfigError, load_config
from buildrail.hooks import HookError
from buildrail.hooks import install as install_hook_file
from buildrail.hooks import status as hook_status_file
from buildrail.hooks import uninstall as uninstall_hook_file
from buildrail.pipeline import PipelineContext, PipelineRunner
from buildrail.providers import (
    Message,
    ProviderError,
    ProviderGateway,
    ProviderRequest,
    TextPart,
    create_provider,
)
from buildrail.skills import SkillError, SkillRegistry

_MAX_PAYLOAD_DISPLAY_CHARS = 4000


@dataclass(frozen=True)
class Result:
    """The outcome of a single Core Engine invocation."""

    success: bool
    message: str


def _require_provider(config: BuildrailConfig) -> str:
    """Return the configured provider name, or raise ConfigError if none is set."""
    if config.provider is None:
        raise ConfigError(
            'No provider configured. Add provider = "fake" or provider = "anthropic" '
            "to buildrail.toml."
        )
    return config.provider


class CoreEngine:
    """Owns orchestration; the CLI's only entry point into Buildrail's core logic."""

    def run(self) -> Result:
        """Execute the current orchestration step and return its outcome."""
        return Result(success=True, message="Buildrail initialized.")

    def validate_config(self, project_root: Path) -> Result:
        """Load and validate the project's configuration and return the outcome."""
        try:
            load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))
        return Result(success=True, message="Configuration is valid.")

    def check_provider(self, project_root: Path) -> Result:
        """Resolve the configured provider through the gateway and confirm it responds."""
        try:
            config = load_config(project_root)
            provider = create_provider(_require_provider(config), model=config.anthropic_model)
            gateway = ProviderGateway(provider)
            request = ProviderRequest(
                messages=(Message(role="user", content=(TextPart(text="ping"),)),)
            )
            response = gateway.complete(request)
        except (ConfigError, ProviderError) as exc:
            return Result(success=False, message=str(exc))
        return Result(
            success=True,
            message=f"Provider '{config.provider}' is ready. Response: {response.content}",
        )

    def review(self, project_root: Path, diff_path: Path) -> Result:
        """Run the review pipeline on a diff and write its output as an artifact."""
        if not diff_path.is_file():
            return Result(success=False, message=f"No diff file found at {diff_path}.")

        try:
            config = load_config(project_root)
            provider = create_provider(_require_provider(config), model=config.anthropic_model)
        except (ConfigError, ProviderError) as exc:
            return Result(success=False, message=str(exc))

        gateway = ProviderGateway(provider)
        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        context = PipelineContext(
            run_id=run_id,
            workdir=str(project_root),
            inputs={"diff": str(diff_path.resolve())},
            provider_name=config.provider,
        )

        result = PipelineRunner(gateway, store).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        output = step.response.outputs.get("review")
        if output is None or not step.artifacts:
            return Result(success=False, message="The review-diff skill did not produce a review.")

        usage_note = ""
        if output.usage is not None and output.model_used is not None:
            usage_note = (
                f" Provider: {config.provider}/{output.model_used}, "
                f"tokens: {output.usage.input_tokens} in / {output.usage.output_tokens} out."
            )

        return Result(
            success=True,
            message=f"Review written to {step.artifacts[0].content_path}.{usage_note}",
        )

    def test_summary(self, project_root: Path) -> Result:
        """Run the test-summary pipeline and write its output as an artifact."""
        try:
            config = load_config(project_root)
            provider = create_provider(_require_provider(config), model=config.anthropic_model)
        except (ConfigError, ProviderError) as exc:
            return Result(success=False, message=str(exc))

        gateway = ProviderGateway(provider)
        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        context = PipelineContext(
            run_id=run_id,
            workdir=str(project_root),
            inputs={},
            provider_name=config.provider,
        )

        result = PipelineRunner(gateway, store, steps=("test-summary",)).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        output = step.response.outputs.get("summary")
        if output is None or not step.artifacts:
            return Result(
                success=False, message="The test-summary skill did not produce a summary."
            )

        usage_note = ""
        if output.usage is not None and output.model_used is not None:
            usage_note = (
                f" Provider: {config.provider}/{output.model_used}, "
                f"tokens: {output.usage.input_tokens} in / {output.usage.output_tokens} out."
            )

        return Result(
            success=True,
            message=f"Test summary written to {step.artifacts[0].content_path}.{usage_note}",
        )

    def release_notes(
        self, project_root: Path, *, from_ref: str | None = None, to_ref: str | None = None
    ) -> Result:
        """Run the release-notes pipeline on the project's Git history and write an artifact."""
        try:
            config = load_config(project_root)
            provider = create_provider(_require_provider(config), model=config.anthropic_model)
        except (ConfigError, ProviderError) as exc:
            return Result(success=False, message=str(exc))

        gateway = ProviderGateway(provider)
        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        inputs: dict[str, str] = {}
        if from_ref:
            inputs["from"] = from_ref
        if to_ref:
            inputs["to"] = to_ref

        context = PipelineContext(
            run_id=run_id,
            workdir=str(project_root),
            inputs=inputs,
            provider_name=config.provider,
        )

        result = PipelineRunner(gateway, store, steps=("release-notes",)).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        output = step.response.outputs.get("notes")
        if output is None or not step.artifacts:
            return Result(success=False, message="The release-notes skill did not produce notes.")

        usage_note = ""
        if output.usage is not None and output.model_used is not None:
            usage_note = (
                f" Provider: {config.provider}/{output.model_used}, "
                f"tokens: {output.usage.input_tokens} in / {output.usage.output_tokens} out."
            )

        return Result(
            success=True,
            message=f"Release notes written to {step.artifacts[0].content_path}.{usage_note}",
        )

    def verify_project(self, project_root: Path) -> Result:
        """Run the provider-free verify-project pipeline and write a verification artifact.

        Never constructs or calls a provider — success/failure here reflects
        whether the local checks (format, lint, types, tests) passed, not
        whether the artifact was written.
        """
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        context = PipelineContext(
            run_id=run_id,
            workdir=str(project_root),
            inputs={},
        )

        result = PipelineRunner(None, store, steps=("verify-project",)).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        output = step.response.outputs.get("report")
        if output is None or not step.artifacts:
            return Result(
                success=False, message="The verify-project skill did not produce a report."
            )

        metadata = output.metadata or {}
        passed = bool(metadata.get("passed", False))
        checks_passed = metadata.get("checks_passed", 0)
        checks_total = metadata.get("checks_total", 0)
        failed_check = metadata.get("failed_check")
        duration = metadata.get("duration_seconds", 0.0)

        status_word = "PASSED" if passed else "FAILED"
        message = f"Verification {status_word}: {checks_passed}/{checks_total} checks passed."
        if failed_check:
            message += f" Failed check: {failed_check}."
        message += (
            f" Duration: {duration:.2f}s. Report written to {step.artifacts[0].content_path}."
        )

        return Result(success=passed, message=message)

    def list_skills(self) -> Result:
        """List every discovered built-in skill's name, version, and description."""
        try:
            manifests = SkillRegistry().list_skills()
        except SkillError as exc:
            return Result(success=False, message=str(exc))

        if not manifests:
            return Result(success=True, message="No skills found.")

        lines = [f"{m.name} ({m.version}): {m.description}" for m in manifests]
        return Result(success=True, message="\n".join(lines))

    def inspect_skill(self, name: str) -> Result:
        """Show the validated manifest details for one built-in skill."""
        try:
            manifest = SkillRegistry().get_manifest(name)
        except SkillError as exc:
            return Result(success=False, message=str(exc))

        lines = [
            f"name: {manifest.name}",
            f"version: {manifest.version}",
            f"protocol_version: {manifest.protocol_version}",
            f"description: {manifest.description}",
            f"entrypoint: {manifest.entrypoint}",
            f"requires_provider: {manifest.requires_provider}",
            f"path: {manifest.path}",
        ]
        return Result(success=True, message="\n".join(lines))

    def install_hook(self, project_root: Path) -> Result:
        """Install or update the Buildrail-managed Git pre-commit hook."""
        try:
            result = install_hook_file(project_root)
        except HookError as exc:
            return Result(success=False, message=str(exc))

        messages = {
            "installed": f"Installed pre-commit hook at {result.hook_path}.",
            "updated": f"Updated pre-commit hook at {result.hook_path}.",
            "already_installed": f"Pre-commit hook already installed at {result.hook_path}.",
        }
        return Result(success=True, message=messages[result.action])

    def uninstall_hook(self, project_root: Path) -> Result:
        """Remove the Buildrail-managed block from the Git pre-commit hook."""
        try:
            result = uninstall_hook_file(project_root)
        except HookError as exc:
            return Result(success=False, message=str(exc))

        messages = {
            "removed_file": f"Removed pre-commit hook at {result.hook_path}.",
            "removed_block": (
                f"Removed Buildrail's block from {result.hook_path}; "
                "existing hook content preserved."
            ),
            "not_installed": f"Buildrail is not installed at {result.hook_path}.",
        }
        return Result(success=True, message=messages[result.action])

    def hook_status(self, project_root: Path) -> Result:
        """Report whether the Buildrail-managed Git pre-commit hook is installed."""
        try:
            result = hook_status_file(project_root)
        except HookError as exc:
            return Result(success=False, message=str(exc))

        if result.state == "installed":
            return Result(success=True, message=f"Installed at {result.hook_path}.")
        return Result(success=True, message=f"Not installed. Hook path: {result.hook_path}.")

    def list_runs(self, project_root: Path, *, limit: int = 20) -> Result:
        """List recent runs from the configured artifact_root, newest first."""
        try:
            config = load_config(project_root)
            reader = ArtifactReader(project_root / config.artifact_root)
            runs = reader.list_runs(limit)
        except (ConfigError, ArtifactReadError) as exc:
            return Result(success=False, message=str(exc))

        if not runs:
            return Result(success=True, message="No runs found.")

        lines = []
        for run in runs:
            created = run.created_at or "unknown"
            types = ", ".join(run.artifact_types) or "none"
            lines.append(
                f"{run.run_id}  status={run.status}  created={created}  "
                f"artifacts={run.artifact_count}  types={types}"
            )
        return Result(success=True, message="\n".join(lines))

    def inspect_run(self, project_root: Path, run_id: str) -> Result:
        """Show one run's status and each of its artifacts' metadata."""
        try:
            config = load_config(project_root)
            reader = ArtifactReader(project_root / config.artifact_root)
            run = reader.get_run(run_id)
        except (ConfigError, ArtifactReadError) as exc:
            return Result(success=False, message=str(exc))

        lines = [
            f"run_id: {run.run_id}",
            f"status: {run.status}",
            f"created_at: {run.created_at or 'unknown'}",
            f"artifact_count: {len(run.artifacts)}",
        ]
        for artifact in run.artifacts:
            produced_by = artifact.produced_by_skill or "unknown"
            if artifact.produced_by_version:
                produced_by += f" ({artifact.produced_by_version})"
            lines.append("")
            lines.append(f"- id: {artifact.id}")
            lines.append(f"  type: {artifact.type}")
            lines.append(f"  content_path: {artifact.content_path}")
            lines.append(f"  status: {artifact.status}")
            lines.append(f"  produced_by: {produced_by}")
            lines.append(f"  provider_usage: {artifact.provider_usage or 'none'}")
        return Result(success=True, message="\n".join(lines))

    def inspect_artifact(self, project_root: Path, artifact_id: str) -> Result:
        """Show one artifact's metadata and checksum-verified payload content."""
        try:
            config = load_config(project_root)
            reader = ArtifactReader(project_root / config.artifact_root)
            payload = reader.get_artifact(artifact_id)
        except (ConfigError, ArtifactReadError) as exc:
            return Result(success=False, message=str(exc))

        detail = payload.detail
        produced_by = detail.produced_by_skill or "unknown"
        if detail.produced_by_version:
            produced_by += f" ({detail.produced_by_version})"

        content = payload.content
        truncated = len(content) > _MAX_PAYLOAD_DISPLAY_CHARS
        displayed = content[:_MAX_PAYLOAD_DISPLAY_CHARS]

        lines = [
            f"id: {detail.id}",
            f"type: {detail.type}",
            f"content_type: {detail.content_type or 'unknown'}",
            f"produced_by: {produced_by}",
            f"run_id: {detail.run_id}",
            f"created_at: {detail.created_at or 'unknown'}",
            f"checksum: {detail.checksum or 'unknown'}",
            f"provider_usage: {detail.provider_usage or 'none'}",
            "",
            "--- payload ---",
            displayed,
        ]
        if truncated:
            lines.append(
                f"... [truncated, showing {_MAX_PAYLOAD_DISPLAY_CHARS} of "
                f"{len(content)} characters]"
            )
        return Result(success=True, message="\n".join(lines))
