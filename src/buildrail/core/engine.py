"""The Core Engine: Buildrail's single orchestration entry point."""

from dataclasses import dataclass
from pathlib import Path

from buildrail.artifacts import ArtifactStore
from buildrail.config import ConfigError, load_config
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


@dataclass(frozen=True)
class Result:
    """The outcome of a single Core Engine invocation."""

    success: bool
    message: str


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
            provider = create_provider(config.provider, model=config.anthropic_model)
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
            provider = create_provider(config.provider, model=config.anthropic_model)
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
            provider = create_provider(config.provider, model=config.anthropic_model)
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
            provider = create_provider(config.provider, model=config.anthropic_model)
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
