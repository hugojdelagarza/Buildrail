"""PipelineRunner: executes a fixed sequence of skills, writing each output as an artifact.

Milestone-1 scope (docs/roadmap.md): exactly one built-in pipeline
(review-diff alone). No pipeline discovery, no YAML-defined pipelines, no
parallel execution, no branching, no retries, no scheduling — those are
later-phase concerns. A skill never knows whether it's running alone or as
one step of several; it only ever sees a SkillRequest and a ProviderGateway
(or None, for provider-free skills like verify-project, which never
construct or call one).
"""

from buildrail.artifacts import ArtifactReference, ArtifactStore
from buildrail.pipeline.types import PipelineContext, PipelineResult, PipelineStepResult
from buildrail.providers import ProviderError, ProviderGateway
from buildrail.skill_protocol import RunContext, SkillRequest, SkillResponse
from buildrail.skills import SkillRegistry

_DEFAULT_STEPS: tuple[str, ...] = ("review-diff",)


class PipelineRunner:
    """Runs a fixed sequence of skills in order, stopping at the first failure."""

    def __init__(
        self,
        gateway: ProviderGateway | None,
        store: ArtifactStore,
        *,
        steps: tuple[str, ...] = _DEFAULT_STEPS,
        registry: SkillRegistry | None = None,
    ) -> None:
        self._gateway = gateway
        self._store = store
        self._steps = steps
        self._registry = registry if registry is not None else SkillRegistry()

    def run(self, context: PipelineContext) -> PipelineResult:
        """Run each configured skill in order, persisting its outputs as artifacts."""
        step_results: list[PipelineStepResult] = []

        for index, skill_name in enumerate(self._steps, start=1):
            run_skill = self._registry.resolve(skill_name)
            request = SkillRequest(
                protocol_version="1.0",
                run_context=RunContext(
                    run_id=context.run_id, step_index=index, workdir=context.workdir
                ),
                inputs=context.inputs,
                config={},
            )

            try:
                response = run_skill(request, self._gateway)
            except ProviderError as exc:
                return PipelineResult(success=False, steps=tuple(step_results), error=str(exc))

            if response.status == "failure":
                step_results.append(
                    PipelineStepResult(skill=skill_name, response=response, artifacts=())
                )
                return PipelineResult(
                    success=False,
                    steps=tuple(step_results),
                    error=response.error or f"The {skill_name} skill failed.",
                )

            artifacts = self._write_artifacts(context, skill_name, response)
            step_results.append(
                PipelineStepResult(skill=skill_name, response=response, artifacts=artifacts)
            )

        return PipelineResult(success=True, steps=tuple(step_results))

    def _write_artifacts(
        self, context: PipelineContext, skill_name: str, response: SkillResponse
    ) -> tuple[ArtifactReference, ...]:
        references: list[ArtifactReference] = []
        for output_name, output in response.outputs.items():
            provider_usage: dict[str, object] | None = None
            if output.usage is not None and output.model_used is not None:
                provider_usage = {
                    "provider": context.provider_name,
                    "model": output.model_used,
                    "input_tokens": output.usage.input_tokens,
                    "output_tokens": output.usage.output_tokens,
                }
            reference = self._store.write_artifact(
                context.run_id,
                artifact_type=output.artifact_type,
                content=output.content,
                content_type="text/markdown",
                slug=output_name,
                produced_by={"skill": skill_name, "version": "0.1.0"},
                provider_usage=provider_usage,
            )
            references.append(reference)
        return tuple(references)
