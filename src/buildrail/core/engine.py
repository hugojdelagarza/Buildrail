"""The Core Engine: Buildrail's single orchestration entry point."""

from dataclasses import dataclass
from pathlib import Path

from buildrail.artifacts import ArtifactStore
from buildrail.config import ConfigError, load_config
from buildrail.core.skill_loader import load_skill
from buildrail.providers import (
    Message,
    ProviderError,
    ProviderGateway,
    ProviderRequest,
    TextPart,
    create_provider,
)
from buildrail.skill_protocol import RunContext, SkillRequest


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
            provider = create_provider(config.provider)
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
        """Review a diff with the review-diff skill and write the result as an artifact."""
        if not diff_path.is_file():
            return Result(success=False, message=f"No diff file found at {diff_path}.")

        try:
            config = load_config(project_root)
            provider = create_provider(config.provider)
        except (ConfigError, ProviderError) as exc:
            return Result(success=False, message=str(exc))

        gateway = ProviderGateway(provider)
        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        request = SkillRequest(
            protocol_version="1.0",
            run_context=RunContext(run_id=run_id, step_index=1, workdir=str(project_root)),
            inputs={"diff": str(diff_path.resolve())},
            config={},
        )

        run_review = load_skill("review-diff")
        try:
            response = run_review(request, gateway)
        except ProviderError as exc:
            return Result(success=False, message=str(exc))

        if response.status == "failure":
            return Result(success=False, message=response.error or "The review-diff skill failed.")

        output = response.outputs.get("review")
        if output is None:
            return Result(success=False, message="The review-diff skill did not produce a review.")

        provider_usage: dict[str, object] | None = None
        usage_note = ""
        if output.usage is not None and output.model_used is not None:
            provider_usage = {
                "provider": config.provider,
                "model": output.model_used,
                "input_tokens": output.usage.input_tokens,
                "output_tokens": output.usage.output_tokens,
            }
            usage_note = (
                f" Provider: {config.provider}/{output.model_used}, "
                f"tokens: {output.usage.input_tokens} in / {output.usage.output_tokens} out."
            )

        reference = store.write_artifact(
            run_id,
            artifact_type=output.artifact_type,
            content=output.content,
            content_type="text/markdown",
            slug="diff",
            produced_by={"skill": "review-diff", "version": "0.1.0"},
            provider_usage=provider_usage,
        )

        return Result(
            success=True,
            message=f"Review written to {reference.content_path}.{usage_note}",
        )
