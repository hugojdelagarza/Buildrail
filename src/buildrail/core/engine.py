"""The Core Engine: Buildrail's single orchestration entry point."""

import json
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from buildrail import vcs
from buildrail.analysis import AnalysisError, ProjectAnalysis, analyze_project, to_dict
from buildrail.artifacts import ArtifactReader, ArtifactReadError, ArtifactStore
from buildrail.config import (
    CONFIG_FILENAME,
    DEFAULT_ARTIFACT_ROOT,
    BuildrailConfig,
    ConfigError,
    ensure_artifact_root_within_project,
    load_config,
    write_config,
)
from buildrail.config import validate as validate_config_fields
from buildrail.extensions import (
    PROJECT_EXTENSIONS_DIRNAME,
    project_pipelines_dir,
    project_skills_dir,
)
from buildrail.hooks import HookError
from buildrail.hooks import install as install_hook_file
from buildrail.hooks import status as hook_status_file
from buildrail.hooks import uninstall as uninstall_hook_file
from buildrail.pipeline import (
    NamedPipelineResult,
    NamedStepOutcome,
    PipelineContext,
    PipelineDefinition,
    PipelineError,
    PipelineRegistry,
    PipelineRunner,
    PipelineScaffoldError,
)
from buildrail.pipeline import (
    create_pipeline as scaffold_pipeline,
)
from buildrail.pipeline.types import PipelineResult, PipelineStepResult
from buildrail.providers import (
    Message,
    ProviderError,
    ProviderGateway,
    ProviderRequest,
    TextPart,
    create_provider,
)
from buildrail.skill_protocol import SkillOutput, SkillResponse
from buildrail.skills import (
    SkillError,
    SkillManifest,
    SkillNotFoundError,
    SkillRegistry,
    SkillScaffoldError,
)
from buildrail.skills import (
    create_skill as scaffold_skill,
)
from buildrail.testing import HistoryEntry, gather_recent_failure_history, history_to_dict

_DOC_FILENAMES = ("project-overview.md", "module-reference.md", "development-guide.md")

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


def _outcome_from_step(result: PipelineResult, name: str) -> NamedStepOutcome:
    """Convert a single-step PipelineResult into a NamedStepOutcome for pre-commit reporting."""
    step = result.steps[-1] if result.steps else None
    return NamedStepOutcome(
        name=name,
        status="passed" if result.success else "failed",
        reason=None if result.success else result.error,
        artifacts=step.artifacts if step else (),
    )


def _verify_outcome(result: PipelineResult) -> NamedStepOutcome:
    """Convert verify-project's PipelineResult into a NamedStepOutcome.

    verify-project's SkillResponse always reports "success" (per its own
    contract: failing local checks is a normal outcome, not a skill
    execution failure) — actual pass/fail lives in its output metadata,
    exactly as the standalone `buildrail verify` command already reads it.
    """
    if not result.success or not result.steps:
        return _outcome_from_step(result, "verify-project")

    step = result.steps[-1]
    output = step.response.outputs.get("report")
    metadata = output.metadata if output is not None and output.metadata else {}
    passed = bool(metadata.get("passed", False))
    failed_check = metadata.get("failed_check")
    reason = (
        None if passed else f"failed check: {failed_check}" if failed_check else "checks failed"
    )
    return NamedStepOutcome(
        name="verify-project",
        status="passed" if passed else "failed",
        reason=reason,
        artifacts=step.artifacts,
    )


def _test_report_outcome(result: PipelineResult) -> NamedStepOutcome:
    """Convert test-report's PipelineResult into a NamedStepOutcome.

    Like verify-project, test-report's SkillResponse always reports
    "success" for a completed run — a failing test suite is a normal
    outcome recorded in output metadata, not a skill execution failure.
    """
    if not result.success or not result.steps:
        return _outcome_from_step(result, "test-report")

    step = result.steps[-1]
    output = step.response.outputs.get("report")
    metadata = output.metadata if output is not None and output.metadata else {}
    passed = bool(metadata.get("passed", False))
    status = metadata.get("status")
    reason = None if passed else f"status: {status}" if status else "tests did not pass"
    return NamedStepOutcome(
        name="test-report",
        status="passed" if passed else "failed",
        reason=reason,
        artifacts=step.artifacts,
    )


def _test_report_passed(output: SkillOutput) -> bool:
    metadata = output.metadata or {}
    return bool(metadata.get("passed", False))


def _test_report_message(step: PipelineStepResult) -> str:
    output = step.response.outputs["report"]
    metadata = output.metadata or {}
    status = str(metadata.get("status", "unknown")).replace("_", " ").upper()
    counts_line = (
        f"{metadata.get('passed_count', 0)} passed, {metadata.get('failed_count', 0)} failed, "
        f"{metadata.get('skipped_count', 0)} skipped, {metadata.get('xfailed_count', 0)} xfailed, "
        f"{metadata.get('xpassed_count', 0)} xpassed, {metadata.get('errors_count', 0)} errors"
    )
    duration = metadata.get("duration_seconds", 0.0)
    message = f"Tests {status}: {counts_line}. Duration: {duration:.2f}s."

    analysis_mode = metadata.get("analysis_mode")
    if analysis_mode == "unavailable_no_provider":
        message += (
            " Analysis was requested but no provider is configured; "
            "deterministic results are unaffected."
        )
    elif analysis_mode == "completed":
        message += " AI failure analysis included."

    message += f" Report written to {step.artifacts[0].content_path}."
    return message


def _write_temp_diff(diff_text: str) -> Path:
    """Write a collected diff to a private temp file for review-diff's file-path input."""
    fd, path_str = tempfile.mkstemp(prefix="buildrail-precommit-", suffix=".patch")
    path = Path(path_str)
    with open(fd, "w", encoding="utf-8") as handle:
        handle.write(diff_text)
    return path


def _write_temp_analysis(analysis: ProjectAnalysis) -> Path:
    """Write a ProjectAnalysis to a private temp JSON file so pipeline steps can share it
    without each one reanalyzing the repository."""
    fd, path_str = tempfile.mkstemp(prefix="buildrail-analysis-", suffix=".json")
    path = Path(path_str)
    with open(fd, "w", encoding="utf-8") as handle:
        json.dump(to_dict(analysis), handle)
    return path


def _write_temp_history(entries: tuple[HistoryEntry, ...]) -> Path:
    """Write gathered test-report history to a private temp JSON file so the test-report
    skill can compare its own failures against it without needing ArtifactReader access."""
    fd, path_str = tempfile.mkstemp(prefix="buildrail-test-history-", suffix=".json")
    path = Path(path_str)
    with open(fd, "w", encoding="utf-8") as handle:
        json.dump(history_to_dict(entries), handle)
    return path


def _resolve_repository_path(project_root: Path, path: str | None) -> Path:
    """Resolve the repository to analyze: `path` if given, else `project_root`."""
    if path is None:
        return project_root
    if "\x00" in path:
        raise ValueError("Repository path contains a null byte.")
    return Path(path)


def _resolve_output_path(repo_root: Path, output: str) -> Path:
    """Resolve a project-relative `--output` directory, refusing to escape `repo_root`."""
    if "\x00" in output:
        raise ValueError("Output path contains a null byte.")
    resolved_root = repo_root.resolve()
    candidate = (resolved_root / output).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError(f"Output path '{output}' escapes the repository root.")
    return candidate


_EXTENSIONS_README = """\
# Project-Local Buildrail Extensions

This directory holds project-local skills and pipelines that Buildrail
discovers automatically alongside its built-in ones.

    .buildrail/
    ├── skills/       # `buildrail skill create <name>` scaffolds here
    └── pipelines/    # `buildrail pipeline create <name>` scaffolds here

**Project-local skills execute code from this repository.** Only use
project-local skills from repositories you trust — Buildrail does not
sandbox them.

See `buildrail skill list`, `buildrail skill create <name>`,
`buildrail pipeline list`, `buildrail pipeline create <name>`, and
`buildrail run <pipeline>`.
"""


def _scaffold_project_extensions(project_root: Path) -> bool:
    """Idempotently create `.buildrail/skills/`, `.buildrail/pipelines/`, and a short
    README explaining them. Never overwrites or deletes existing content.

    Returns True if anything was actually created, False if everything
    already existed.
    """
    created_any = False
    for subdir in (project_skills_dir(project_root), project_pipelines_dir(project_root)):
        if subdir.is_dir():
            continue
        subdir.mkdir(parents=True, exist_ok=True)
        gitkeep = subdir / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")
        created_any = True

    readme_path = project_root / PROJECT_EXTENSIONS_DIRNAME / "README.md"
    if not readme_path.exists():
        readme_path.write_text(_EXTENSIONS_README, encoding="utf-8")
        created_any = True
    return created_any


def _relative_to_project(project_root: Path, path: Path) -> str:
    """Return `path` relative to `project_root` as a POSIX string, for safe display.

    Falls back to the absolute path only if `path` genuinely isn't under
    `project_root` (shouldn't happen for project-local extensions, but
    this must never raise on a caller's behalf).
    """
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _skill_source_label(manifest: SkillManifest, project_root: Path) -> str:
    if manifest.source == "built-in":
        return "built-in"
    return f"project-local ({_relative_to_project(project_root, manifest.path)})"


def _pipeline_source_label(definition: PipelineDefinition, project_root: Path) -> str:
    if definition.source == "built-in" or definition.path is None:
        return "built-in"
    return f"project-local ({_relative_to_project(project_root, definition.path)})"


def _first_existing_doc_path(output_dir: Path) -> Path | None:
    """Return the first of the three generated doc filenames that already exists, if any."""
    for filename in _DOC_FILENAMES:
        candidate = output_dir / filename
        if candidate.exists():
            return candidate
    return None


def _sum_usage(response: SkillResponse, provider_name: str | None) -> dict[str, object] | None:
    """Sum token usage across every output a multi-document skill response produced."""
    total_input = 0
    total_output = 0
    model_used: str | None = None
    found = False
    for output in response.outputs.values():
        if output.usage is not None:
            found = True
            total_input += output.usage.input_tokens
            total_output += output.usage.output_tokens
            model_used = output.model_used or model_used
    if not found:
        return None
    return {
        "provider": provider_name,
        "model": model_used,
        "input_tokens": total_input,
        "output_tokens": total_output,
    }


def _evaluate_step_condition(project_root: Path, condition: str) -> tuple[bool, str | None]:
    """Evaluate a declarative pipeline step's `condition`. Returns (should_run, skip_reason).

    `changes_exist` reuses the exact same Git helpers `run_pre_commit`
    uses for its own diff-based skip logic. Any Git resolution failure
    (not a repository, no usable base ref) skips the step rather than
    failing the whole pipeline — a project-local pipeline may combine
    Git-gated and unconditional steps, and one ungated step shouldn't be
    able to break the other kind.
    """
    if condition == "always":
        return True, None
    if condition == "changes_exist":
        try:
            resolved_base = vcs.resolve_base_ref(project_root, None)
            diff_result = vcs.collect_diff(project_root, resolved_base)
        except vcs.GitError as exc:
            return False, str(exc)
        if diff_result.is_empty:
            return False, f"no changes against {resolved_base}"
        return True, None
    raise AssertionError(f"Unreachable: unsupported condition {condition!r} passed validation.")


def _build_pipeline_message(
    result: NamedPipelineResult, provider_usage: dict[str, object] | None
) -> str:
    status_word = "PASSED" if result.success else "FAILED"
    lines = [
        f"Pipeline: {result.name}",
        f"Status: {status_word}",
        f"Run: {result.run_id}",
    ]
    for outcome in result.steps:
        line = f"- {outcome.name}: {outcome.status}"
        if outcome.reason:
            line += f" ({outcome.reason})"
        lines.append(line)
        for artifact in outcome.artifacts:
            lines.append(f"    artifact: {artifact.id} -> {artifact.content_path}")
    if provider_usage:
        lines.append(
            f"Provider: {provider_usage['provider']}/{provider_usage['model']}, "
            f"tokens: {provider_usage['input_tokens']} in / {provider_usage['output_tokens']} out."
        )
    lines.append(f"Duration: {result.duration_seconds:.2f}s")
    return "\n".join(lines)


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

    def init_config(
        self,
        project_root: Path,
        *,
        provider: str = "fake",
        artifact_root: str = DEFAULT_ARTIFACT_ROOT,
        extensions_only: bool = False,
    ) -> Result:
        """Create a minimal `buildrail.toml` for a new project.

        Also scaffolds `.buildrail/skills/` and `.buildrail/pipelines/`
        (idempotently — never overwrites, never deletes) so the project is
        immediately ready for `buildrail skill create`/`buildrail pipeline
        create`. Refuses to overwrite an existing configuration file —
        re-running `init` on an already-configured project is a no-op
        error, not a silent reset. Use `update_config` to change an
        existing project's configuration instead.

        `extensions_only=True` (`buildrail init --extensions`) skips
        `buildrail.toml` entirely and only scaffolds `.buildrail/` — for a
        project that was configured before this capability existed and
        just needs the extensions directories added.
        """
        if extensions_only:
            created = _scaffold_project_extensions(project_root)
            if created:
                return Result(
                    success=True,
                    message=(
                        f"Created {PROJECT_EXTENSIONS_DIRNAME}/ for project-local "
                        "skills and pipelines."
                    ),
                )
            return Result(
                success=True,
                message=f"{PROJECT_EXTENSIONS_DIRNAME}/ already exists. Nothing to do.",
            )

        config_path = project_root / CONFIG_FILENAME
        if config_path.exists():
            return Result(
                success=False,
                message=f"{CONFIG_FILENAME} already exists at {config_path}. Not overwriting.",
            )

        try:
            candidate = validate_config_fields(
                {"provider": provider, "artifact_root": artifact_root}
            )
            ensure_artifact_root_within_project(project_root, candidate.artifact_root)
        except (ConfigError, ValueError) as exc:
            return Result(success=False, message=str(exc))

        write_config(project_root, candidate)
        _scaffold_project_extensions(project_root)
        return Result(
            success=True,
            message=(
                f"Created {CONFIG_FILENAME} with provider='{candidate.provider}'. "
                f"Created {PROJECT_EXTENSIONS_DIRNAME}/ for project-local skills and pipelines."
            ),
        )

    def update_config(self, project_root: Path, fields: dict[str, object]) -> Result:
        """Create or update `buildrail.toml` from a restricted set of known fields.

        Unknown fields (including anything credential-shaped, e.g. an API
        key) are rejected outright — this endpoint only ever accepts
        `provider`, `artifact_root`, and `anthropic_model`, the same three
        fields `BuildrailConfig` models. Missing fields are filled in from
        the project's existing configuration if one exists, or from
        Buildrail's offline-friendly defaults otherwise, so callers can send
        a partial update (e.g. just `{"provider": "anthropic"}`).
        """
        allowed_fields = {"provider", "artifact_root", "anthropic_model"}
        unexpected = set(fields) - allowed_fields
        if unexpected:
            return Result(
                success=False,
                message=f"Unknown configuration field(s): {', '.join(sorted(unexpected))}.",
            )

        try:
            current = load_config(project_root)
            merged: dict[str, object | None] = {
                "provider": current.provider,
                "artifact_root": current.artifact_root,
                "anthropic_model": current.anthropic_model,
            }
        except ConfigError:
            merged = {
                "provider": None,
                "artifact_root": DEFAULT_ARTIFACT_ROOT,
                "anthropic_model": None,
            }
        merged.update(fields)

        try:
            candidate = validate_config_fields(merged)
            ensure_artifact_root_within_project(project_root, candidate.artifact_root)
        except (ConfigError, ValueError) as exc:
            return Result(success=False, message=str(exc))

        write_config(project_root, candidate)
        return Result(
            success=True,
            message=f"Updated {CONFIG_FILENAME} (provider={candidate.provider}).",
        )

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

    def test_report(
        self, project_root: Path, *, analyze: bool = False, history: bool = False
    ) -> Result:
        """Run the test-report skill: deterministic pytest execution first, writing a
        Markdown + JSON test-report artifact.

        `analyze=True` only ever calls the configured provider when there are
        failures/errors to explain; a missing or misconfigured provider with
        `analyze=True` never blocks the deterministic run — the report is
        still produced, and its `analysis_mode` records that analysis could
        not run. `Result.success` (and so the CLI's exit code) always
        reflects the actual test outcome, never analysis availability — a
        deliberate choice: `--analyze` failing to run is a degraded report,
        not a failed command.
        """
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        inputs: dict[str, str] = {"analyze": "true" if analyze else "false"}
        history_file: Path | None = None
        if history:
            reader = ArtifactReader(project_root / config.artifact_root)
            history_file = _write_temp_history(gather_recent_failure_history(reader))
            inputs["history_json"] = str(history_file)

        gateway: ProviderGateway | None = None
        if analyze:
            try:
                provider = create_provider(_require_provider(config), model=config.anthropic_model)
                gateway = ProviderGateway(provider)
            except (ConfigError, ProviderError):
                gateway = None  # deterministic run still proceeds; skill reports why.

        try:
            context = PipelineContext(
                run_id=run_id,
                workdir=str(project_root),
                inputs=inputs,
                provider_name=config.provider if gateway is not None else None,
            )
            result = PipelineRunner(gateway, store, steps=("test-report",)).run(context)
        finally:
            if history_file is not None:
                history_file.unlink(missing_ok=True)

        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        output = step.response.outputs.get("report")
        if output is None or not step.artifacts:
            return Result(success=False, message="The test-report skill did not produce a report.")

        return Result(success=_test_report_passed(output), message=_test_report_message(step))

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

    def list_skills(self, project_root: Path) -> Result:
        """List every discovered skill's name, version, source, and description."""
        try:
            manifests = SkillRegistry(project_root=project_root).list_skills()
        except SkillError as exc:
            return Result(success=False, message=str(exc))

        if not manifests:
            return Result(success=True, message="No skills found.")

        lines = [f"{m.name} ({m.version}) [{m.source}]: {m.description}" for m in manifests]
        return Result(success=True, message="\n".join(lines))

    def inspect_skill(self, project_root: Path, name: str) -> Result:
        """Show the validated manifest details for one skill."""
        try:
            manifest = SkillRegistry(project_root=project_root).get_manifest(name)
        except SkillError as exc:
            return Result(success=False, message=str(exc))

        lines = [
            f"name: {manifest.name}",
            f"version: {manifest.version}",
            f"protocol_version: {manifest.protocol_version}",
            f"description: {manifest.description}",
            f"entrypoint: {manifest.entrypoint}",
            f"requires_provider: {manifest.requires_provider}",
            f"source: {_skill_source_label(manifest, project_root)}",
        ]
        return Result(success=True, message="\n".join(lines))

    def create_skill(
        self,
        project_root: Path,
        name: str,
        *,
        description: str | None = None,
        requires_provider: bool = False,
    ) -> Result:
        """Scaffold a new project-local skill under `.buildrail/skills/<name>/`."""
        try:
            skill_dir = (
                scaffold_skill(
                    project_root, name, description=description, requires_provider=requires_provider
                )
                if description is not None
                else scaffold_skill(project_root, name, requires_provider=requires_provider)
            )
        except SkillScaffoldError as exc:
            return Result(success=False, message=str(exc))
        relative = _relative_to_project(project_root, skill_dir)
        return Result(success=True, message=f"Created project-local skill at {relative}.")

    def list_pipelines(self, project_root: Path) -> Result:
        """List every discovered pipeline's name, version, source, and description."""
        try:
            definitions = PipelineRegistry(project_root=project_root).list_pipelines()
        except PipelineError as exc:
            return Result(success=False, message=str(exc))

        if not definitions:
            return Result(success=True, message="No pipelines found.")

        lines = [
            f"{d.name} ({d.version}) [{d.source}]: {d.description} ({len(d.steps)} step(s))"
            for d in definitions
        ]
        return Result(success=True, message="\n".join(lines))

    def inspect_pipeline(self, project_root: Path, name: str) -> Result:
        """Show one pipeline's ordered steps, conditions, inputs, and provider requirement."""
        try:
            definition = PipelineRegistry(project_root=project_root).get_pipeline(name)
        except PipelineError as exc:
            return Result(success=False, message=str(exc))

        lines = [
            f"name: {definition.name}",
            f"version: {definition.version}",
            f"source: {_pipeline_source_label(definition, project_root)}",
            f"description: {definition.description}",
            f"requires_provider: {definition.requires_provider}",
            "steps:",
        ]
        for step in definition.steps:
            condition = step.skip_condition or "always"
            line = f"  - {step.name} (condition: {condition})"
            if step.inputs:
                inputs = ", ".join(f"{k}={v}" for k, v in step.inputs.items())
                line += f" inputs: {inputs}"
            lines.append(line)
        return Result(success=True, message="\n".join(lines))

    def create_pipeline(self, project_root: Path, name: str) -> Result:
        """Scaffold a new project-local pipeline manifest under `.buildrail/pipelines/`."""
        try:
            manifest_path = scaffold_pipeline(project_root, name)
        except PipelineScaffoldError as exc:
            return Result(success=False, message=str(exc))
        relative = _relative_to_project(project_root, manifest_path)
        return Result(success=True, message=f"Created project-local pipeline at {relative}.")

    def run_named_pipeline(self, project_root: Path, name: str) -> Result:
        """Resolve `name` through the Pipeline Registry and run it.

        Built-in pipelines (`pre-commit`, `project-intelligence`) are
        rejected here — their real orchestration is bespoke
        (`run_pre_commit`/`run_project_intelligence`) and callers should
        use those directly; this method exists to run project-local,
        declarative pipelines generically.
        """
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        skill_registry = SkillRegistry(project_root=project_root)
        try:
            definition = PipelineRegistry(
                project_root=project_root, skill_registry=skill_registry
            ).get_pipeline(name)
        except PipelineError as exc:
            return Result(success=False, message=str(exc))

        if definition.execution_kind != "declarative":
            return Result(
                success=False,
                message=(
                    f"'{name}' is a built-in pipeline with its own dedicated run command "
                    f"(`buildrail run {name}`)."
                ),
            )

        start = time.perf_counter()
        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        outcomes: list[NamedStepOutcome] = []
        usage_provider: str | None = None
        usage_model: str | None = None
        usage_input_tokens = 0
        usage_output_tokens = 0
        usage_seen = False
        stopped = False
        for step in definition.steps:
            if stopped:
                outcomes.append(
                    NamedStepOutcome(
                        name=step.name,
                        status="skipped",
                        reason="a previous step failed",
                        artifacts=(),
                    )
                )
                continue

            condition = step.skip_condition or "always"
            should_run, skip_reason = _evaluate_step_condition(project_root, condition)
            if not should_run:
                outcomes.append(
                    NamedStepOutcome(
                        name=step.name, status="skipped", reason=skip_reason, artifacts=()
                    )
                )
                continue

            try:
                skill_manifest = skill_registry.get_manifest(step.name)
            except SkillNotFoundError as exc:
                outcomes.append(
                    NamedStepOutcome(name=step.name, status="failed", reason=str(exc), artifacts=())
                )
                stopped = True
                continue

            gateway: ProviderGateway | None = None
            if skill_manifest.requires_provider:
                try:
                    provider = create_provider(
                        _require_provider(config), model=config.anthropic_model
                    )
                except (ConfigError, ProviderError) as exc:
                    outcomes.append(
                        NamedStepOutcome(
                            name=step.name, status="failed", reason=str(exc), artifacts=()
                        )
                    )
                    stopped = True
                    continue
                gateway = ProviderGateway(provider)

            step_context = PipelineContext(
                run_id=run_id,
                workdir=str(project_root),
                # `repository_path` defaults to the project root so declarative steps
                # for skills that take it explicitly (dependency-audit, explain-project,
                # generate-docs, generate-diagram) work without every pipeline author
                # having to repeat it; a step's own `inputs` can still override it.
                inputs={
                    "repository_path": str(project_root),
                    **{key: str(value) for key, value in step.inputs.items()},
                },
                provider_name=config.provider if gateway is not None else None,
                pipeline_name=definition.name,
            )
            step_result = PipelineRunner(
                gateway, store, steps=(step.name,), registry=skill_registry
            ).run(step_context)
            # verify-project's and test-report's SkillResponse always report "success" —
            # a failed check/test suite is a normal outcome recorded in output metadata,
            # not a skill execution failure (see `_verify_outcome`'s docstring). Every
            # other skill's pass/fail is exactly its PipelineResult.success.
            if step.name == "verify-project":
                outcome = _verify_outcome(step_result)
            elif step.name == "test-report":
                outcome = _test_report_outcome(step_result)
            else:
                outcome = _outcome_from_step(step_result, step.name)
            outcomes.append(outcome)
            if outcome.status == "failed":
                stopped = True
            elif step_result.success and step_result.steps:
                for output in step_result.steps[-1].response.outputs.values():
                    if output.usage is None:
                        continue
                    usage_seen = True
                    usage_provider = config.provider
                    usage_model = output.model_used or usage_model
                    usage_input_tokens += output.usage.input_tokens
                    usage_output_tokens += output.usage.output_tokens

        provider_usage_totals: dict[str, object] | None = (
            {
                "provider": usage_provider,
                "model": usage_model,
                "input_tokens": usage_input_tokens,
                "output_tokens": usage_output_tokens,
            }
            if usage_seen
            else None
        )
        return self._finish_named_pipeline(
            definition.name,
            store,
            run_id,
            outcomes,
            start,
            provider_usage_totals,
            source=definition.source,
        )

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
        if run.pipeline:
            lines.append(f"pipeline: {run.pipeline}")
        if run.pipeline_source:
            lines.append(f"pipeline_source: {run.pipeline_source}")
        if run.duration_seconds is not None:
            lines.append(f"duration_seconds: {run.duration_seconds:.2f}")
        for step in run.pipeline_steps:
            lines.append("")
            lines.append(f"step: {step.name}")
            lines.append(f"  status: {step.status}")
            if step.reason:
                lines.append(f"  reason: {step.reason}")
            lines.append(f"  artifact_ids: {list(step.artifact_ids) or 'none'}")
        if run.pipeline_steps:
            lines.append("")
            lines.append("artifacts:")
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
            f"pipeline: {detail.pipeline or 'none'}",
            f"display_name: {detail.display_name or 'none'}",
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

    def run_pre_commit(
        self, project_root: Path, *, base_ref: str | None = None, skip_review: bool = False
    ) -> Result:
        """Run the pre-commit pipeline: verify-project, then review-diff if a diff exists.

        Both steps share one run id and one run.json. No provider is ever
        constructed unless verification passed, a non-empty diff exists
        against the resolved base ref, and --skip-review was not set.
        """
        start = time.perf_counter()
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        try:
            vcs.repository_root(project_root)
        except vcs.GitError as exc:
            return Result(success=False, message=str(exc))

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()

        verify_context = PipelineContext(
            run_id=run_id, workdir=str(project_root), inputs={}, pipeline_name="pre-commit"
        )
        verify_result = PipelineRunner(None, store, steps=("verify-project",)).run(verify_context)
        verify_outcome = _verify_outcome(verify_result)
        outcomes = [verify_outcome]

        provider_usage: dict[str, object] | None = None
        if verify_outcome.status == "passed":
            review_outcome, provider_usage = self._run_pre_commit_review(
                project_root, config, store, run_id, base_ref, skip_review
            )
            outcomes.append(review_outcome)

        return self._finish_named_pipeline(
            "pre-commit", store, run_id, outcomes, start, provider_usage, source="built-in"
        )

    def _run_pre_commit_review(
        self,
        project_root: Path,
        config: BuildrailConfig,
        store: ArtifactStore,
        run_id: str,
        base_ref: str | None,
        skip_review: bool,
    ) -> tuple[NamedStepOutcome, dict[str, object] | None]:
        """Resolve whether review-diff should run, and run it if so. Never raises."""
        if skip_review:
            return (
                NamedStepOutcome(
                    name="review-diff",
                    status="skipped",
                    reason="--skip-review was set",
                    artifacts=(),
                ),
                None,
            )

        try:
            resolved_base = vcs.resolve_base_ref(project_root, base_ref)
            diff_result = vcs.collect_diff(project_root, resolved_base)
        except vcs.GitError as exc:
            return (
                NamedStepOutcome(
                    name="review-diff", status="failed", reason=str(exc), artifacts=()
                ),
                None,
            )

        if diff_result.is_empty:
            return (
                NamedStepOutcome(
                    name="review-diff",
                    status="skipped",
                    reason=f"no changes against {resolved_base}",
                    artifacts=(),
                ),
                None,
            )

        try:
            provider = create_provider(_require_provider(config), model=config.anthropic_model)
        except (ConfigError, ProviderError) as exc:
            return (
                NamedStepOutcome(
                    name="review-diff", status="failed", reason=str(exc), artifacts=()
                ),
                None,
            )

        diff_file = _write_temp_diff(diff_result.diff_text)
        try:
            gateway = ProviderGateway(provider)
            review_context = PipelineContext(
                run_id=run_id,
                workdir=str(project_root),
                inputs={"diff": str(diff_file)},
                provider_name=config.provider,
                pipeline_name="pre-commit",
            )
            review_result = PipelineRunner(gateway, store, steps=("review-diff",)).run(
                review_context
            )
        finally:
            diff_file.unlink(missing_ok=True)

        outcome = _outcome_from_step(review_result, "review-diff")
        usage: dict[str, object] | None = None
        if review_result.success and review_result.steps:
            output = review_result.steps[-1].response.outputs.get("review")
            if output is not None and output.usage is not None and output.model_used is not None:
                usage = {
                    "provider": config.provider,
                    "model": output.model_used,
                    "input_tokens": output.usage.input_tokens,
                    "output_tokens": output.usage.output_tokens,
                }
        return outcome, usage

    def _finish_named_pipeline(
        self,
        name: str,
        store: ArtifactStore,
        run_id: str,
        outcomes: list[NamedStepOutcome],
        start: float,
        provider_usage: dict[str, object] | None,
        *,
        source: str | None = None,
    ) -> Result:
        """Aggregate a named pipeline's step outcomes into one Result and run.json summary."""
        success = all(o.status != "failed" for o in outcomes)
        duration = time.perf_counter() - start
        pipeline_result = NamedPipelineResult(
            name=name,
            run_id=run_id,
            success=success,
            steps=tuple(outcomes),
            duration_seconds=duration,
        )

        store.write_run_summary(
            run_id,
            pipeline=pipeline_result.name,
            status="success" if pipeline_result.success else "failure",
            steps=[
                {
                    "name": o.name,
                    "status": o.status,
                    "reason": o.reason,
                    "artifact_ids": [a.id for a in o.artifacts],
                }
                for o in pipeline_result.steps
            ],
            duration_seconds=pipeline_result.duration_seconds,
            provider_usage=provider_usage,
            pipeline_source=source,
        )

        return Result(
            success=pipeline_result.success,
            message=_build_pipeline_message(pipeline_result, provider_usage),
        )

    def explain_project(self, project_root: Path, *, path: str | None = None) -> Result:
        """Run explain-project: a deterministic architecture summary. No provider, no network."""
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        try:
            repo_root = _resolve_repository_path(project_root, path)
        except ValueError as exc:
            return Result(success=False, message=str(exc))

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()
        context = PipelineContext(
            run_id=run_id, workdir=str(project_root), inputs={"repository_path": str(repo_root)}
        )
        result = PipelineRunner(None, store, steps=("explain-project",)).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        if step.response.outputs.get("summary") is None or not step.artifacts:
            return Result(
                success=False, message="The explain-project skill did not produce a summary."
            )

        artifact_paths = ", ".join(str(a.content_path) for a in step.artifacts)
        return Result(success=True, message=f"Architecture summary written to {artifact_paths}.")

    def dependency_audit(self, project_root: Path, *, path: str | None = None) -> Result:
        """Run dependency-audit: a deterministic audit of declared dependencies vs.
        local imports. No provider, no network, no pip/poetry/uv invocation."""
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        try:
            repo_root = _resolve_repository_path(project_root, path)
        except ValueError as exc:
            return Result(success=False, message=str(exc))

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()
        context = PipelineContext(
            run_id=run_id, workdir=str(project_root), inputs={"repository_path": str(repo_root)}
        )
        result = PipelineRunner(None, store, steps=("dependency-audit",)).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        if step.response.outputs.get("summary") is None or not step.artifacts:
            return Result(
                success=False, message="The dependency-audit skill did not produce a summary."
            )

        artifact_paths = ", ".join(str(a.content_path) for a in step.artifacts)
        return Result(success=True, message=f"Dependency audit written to {artifact_paths}.")

    def docs_generate(
        self,
        project_root: Path,
        *,
        path: str | None = None,
        output: str | None = None,
        enhance: bool = False,
    ) -> Result:
        """Run generate-docs: deterministic Markdown docs, optionally enhanced by a provider.

        Without --enhance, no provider is ever constructed. With --output,
        the same content is also written into the analyzed repository —
        refusing outright if any of the three target files already exist.
        """
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        try:
            repo_root = _resolve_repository_path(project_root, path)
        except ValueError as exc:
            return Result(success=False, message=str(exc))

        output_dir: Path | None = None
        if output is not None:
            try:
                output_dir = _resolve_output_path(repo_root, output)
            except ValueError as exc:
                return Result(success=False, message=str(exc))
            collision = _first_existing_doc_path(output_dir)
            if collision is not None:
                return Result(
                    success=False,
                    message=(
                        f"Refusing to overwrite existing file at {collision}. "
                        "Remove it or choose a different --output."
                    ),
                )

        gateway: ProviderGateway | None = None
        if enhance:
            try:
                provider = create_provider(_require_provider(config), model=config.anthropic_model)
            except (ConfigError, ProviderError) as exc:
                return Result(success=False, message=str(exc))
            gateway = ProviderGateway(provider)

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()
        inputs = {"repository_path": str(repo_root)}
        if enhance:
            inputs["enhance"] = "true"
        context = PipelineContext(
            run_id=run_id,
            workdir=str(project_root),
            inputs=inputs,
            provider_name=config.provider if enhance else None,
        )
        result = PipelineRunner(gateway, store, steps=("generate-docs",)).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        if not step.artifacts:
            return Result(
                success=False, message="The generate-docs skill did not produce any documents."
            )

        message = (
            f"Documentation written to {', '.join(str(a.content_path) for a in step.artifacts)}."
        )
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
            for output_name, skill_output in step.response.outputs.items():
                target = output_dir / f"{output_name.replace('_', '-')}.md"
                target.write_text(skill_output.content, encoding="utf-8")
            message += f" Also written to {output_dir}."

        return Result(success=True, message=message)

    def diagram_generate(
        self, project_root: Path, *, path: str | None = None, format: str = "mermaid"
    ) -> Result:
        """Run generate-diagram: deterministic Mermaid source. No provider, no network."""
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        try:
            repo_root = _resolve_repository_path(project_root, path)
        except ValueError as exc:
            return Result(success=False, message=str(exc))

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()
        context = PipelineContext(
            run_id=run_id,
            workdir=str(project_root),
            inputs={"repository_path": str(repo_root), "format": format},
        )
        result = PipelineRunner(None, store, steps=("generate-diagram",)).run(context)
        if not result.success:
            return Result(success=False, message=result.error or "The pipeline failed.")

        step = result.steps[-1]
        if not step.artifacts:
            return Result(
                success=False, message="The generate-diagram skill did not produce a diagram."
            )

        return Result(success=True, message=f"Diagram written to {step.artifacts[0].content_path}.")

    def run_project_intelligence(
        self, project_root: Path, *, path: str | None = None, enhance: bool = False
    ) -> Result:
        """Run explain-project, generate-docs, and generate-diagram sharing one run and
        one ProjectAnalysis, computed once up front so no step reanalyzes the repository."""
        start = time.perf_counter()
        try:
            config = load_config(project_root)
        except ConfigError as exc:
            return Result(success=False, message=str(exc))

        try:
            repo_root = _resolve_repository_path(project_root, path)
        except ValueError as exc:
            return Result(success=False, message=str(exc))

        try:
            analysis = analyze_project(repo_root)
        except AnalysisError as exc:
            return Result(success=False, message=str(exc))

        gateway: ProviderGateway | None = None
        if enhance:
            try:
                provider = create_provider(_require_provider(config), model=config.anthropic_model)
            except (ConfigError, ProviderError) as exc:
                return Result(success=False, message=str(exc))
            gateway = ProviderGateway(provider)

        store = ArtifactStore(project_root / config.artifact_root)
        run_id = store.generate_run_id()
        analysis_file = _write_temp_analysis(analysis)
        outcomes: list[NamedStepOutcome] = []
        provider_usage: dict[str, object] | None = None
        try:
            base_inputs = {"repository_path": str(repo_root), "analysis_json": str(analysis_file)}

            explain_context = PipelineContext(
                run_id=run_id,
                workdir=str(project_root),
                inputs=base_inputs,
                pipeline_name="project-intelligence",
            )
            explain_result = PipelineRunner(None, store, steps=("explain-project",)).run(
                explain_context
            )
            outcomes.append(_outcome_from_step(explain_result, "explain-project"))

            docs_inputs = dict(base_inputs)
            if enhance:
                docs_inputs["enhance"] = "true"
            docs_context = PipelineContext(
                run_id=run_id,
                workdir=str(project_root),
                inputs=docs_inputs,
                provider_name=config.provider if enhance else None,
                pipeline_name="project-intelligence",
            )
            docs_result = PipelineRunner(gateway, store, steps=("generate-docs",)).run(docs_context)
            outcomes.append(_outcome_from_step(docs_result, "generate-docs"))
            if docs_result.success and docs_result.steps:
                provider_usage = _sum_usage(docs_result.steps[-1].response, config.provider)

            diagram_context = PipelineContext(
                run_id=run_id,
                workdir=str(project_root),
                inputs=base_inputs,
                pipeline_name="project-intelligence",
            )
            diagram_result = PipelineRunner(None, store, steps=("generate-diagram",)).run(
                diagram_context
            )
            outcomes.append(_outcome_from_step(diagram_result, "generate-diagram"))
        finally:
            analysis_file.unlink(missing_ok=True)

        return self._finish_named_pipeline(
            "project-intelligence",
            store,
            run_id,
            outcomes,
            start,
            provider_usage,
            source="built-in",
        )
