# Buildrail Pipelines

A pipeline is an ordered sequence of skill invocations that share one run
id, one `ArtifactStore`, and one `run.json`. This document specifies the
two ways a pipeline exists in Buildrail today: **built-in** (code-backed,
bespoke orchestration) and **project-local** (declarative YAML,
discovered under `.buildrail/pipelines/`). Both are described by one
shared `PipelineRegistry` (`src/buildrail/pipeline/registry.py`), so the
CLI, the local HTTP service, and the frontend all read one source of
truth instead of independently hand-maintained copies.

## 1. Built-In Pipelines

`pre-commit` and `project-intelligence` are implemented as dedicated
`CoreEngine` methods (`run_pre_commit`, `run_project_intelligence`) —
their orchestration is bespoke enough (Git-diff-gated steps, a shared
`ProjectAnalysis` computed once up front) that forcing them through the
declarative manifest executor would either lose that behavior or bloat
the manifest format to accommodate one-off cases. `PipelineRegistry`
still *describes* them (name, version, steps, arguments) for discovery,
but does not execute them — `buildrail run pre-commit` and
`buildrail run project-intelligence` keep their own dedicated code paths
and their own CLI flags (`--base`/`--skip-review`,
`--path`/`--enhance`).

`quality-gate` (`verify-project` → `test-report` → `dependency-audit`)
is also a built-in, code-registered `PipelineDefinition`, but its steps
need none of `pre-commit`/`project-intelligence`'s bespoke behavior — no
Git-diff gating, no shared up-front analysis — so it's registered with
`execution_kind="declarative"` and runs through the exact same generic
`CoreEngine.run_named_pipeline` executor as a project-local pipeline
(§2.4), rather than getting its own `CoreEngine` method. A built-in
pipeline being "declarative" is an implementation detail, not a
user-visible distinction: `buildrail run quality-gate` works like any
other named pipeline. It's named `quality-gate`, not `quality`, to
avoid colliding with `examples/project-local/pipelines/quality.yaml`,
the documented project-local pipeline example.

## 2. Project-Local Pipelines

A project-local pipeline is one YAML file under
`.buildrail/pipelines/<name>.yaml`, created by `buildrail init` (empty
directory, scaffolded automatically) and populated by
`buildrail pipeline create <name>` or by hand. Unlike built-ins, a
project-local pipeline's steps are executed generically — an ordered
list of existing skill names, run sequentially, sharing one run id.

### 2.1 Manifest Format

```yaml
name: quality
version: 0.1.0
description: Verify and review the current project

steps:
  - skill: verify-project

  - skill: review-diff
    condition: changes_exist
    inputs:
      diff: changes.patch
```

- **`name`** — required, non-empty string; the pipeline's identifier for
  `buildrail run <name>`, `buildrail pipeline inspect <name>`, and
  `POST /commands/<name>`.
- **`version`** — required, non-empty string (the pipeline's own
  version, independent of Buildrail's).
- **`description`** — optional string, defaults to `""`.
- **`steps`** — required, non-empty list. Each step:
  - **`skill`** — required; must name a skill the same `SkillRegistry`
    resolves (built-in or project-local). An unknown skill name is a
    validation error at discovery time, not a runtime surprise.
  - **`condition`** — optional, defaults to `always`. See §2.2.
  - **`inputs`** — optional mapping of plain strings/booleans/numbers,
    passed to the skill as `SkillRequest.inputs` (coerced to strings).
    No lists, no nested mappings, no `null` values.

### 2.2 Supported Conditions

Deliberately small — this is not an expression language:

| Condition | Meaning |
|---|---|
| `always` (default) | The step always runs. |
| `changes_exist` | Skip the step if there are no Git changes against the resolved base ref (the same upstream-then-`HEAD~1` resolution `pre-commit` uses). Any Git resolution failure (not a repository, no usable base) also skips the step, with the failure recorded as the skip reason — one ungated step in a pipeline should never be able to break another. |

### 2.3 What Is Intentionally Not Supported

No DAGs, loops, variables, templating (`${...}`), environment
interpolation, command substitution, secret interpolation, parallel
steps, retries, or remote pipelines. A step's `inputs` values are
treated as inert data, never evaluated or substituted. These are later,
separate milestones — see `docs/roadmap.md` — not omissions to work
around.

### 2.4 Execution Model

`CoreEngine.run_named_pipeline` (used for any pipeline name that isn't
one of the built-ins) runs each step in order:

1. Evaluate the step's `condition`; skip with a recorded reason if it
   doesn't hold.
2. If a previous step in this run failed, every remaining step is
   recorded `skipped` (reason: "a previous step failed") — Buildrail
   never runs a step after a failure, matching `pre-commit`'s
   stop-on-failure model.
3. Resolve the skill through `SkillRegistry` (built-in or project-local,
   same precedence rules as §3 below); construct a `ProviderGateway`
   only if the skill's manifest declares `requires_provider: true`.
4. `verify-project` is special-cased the same way `pre-commit` special-
   cases it: its `SkillResponse.status` is always `"success"` by its own
   contract (a failing local check is a normal outcome, not a skill
   execution failure) — actual pass/fail is read from its output
   metadata, not the response status.
5. Provider usage (tokens, model) is summed across every step that used
   a provider into one run-level total, the same as `pre-commit` and
   `project-intelligence` already do.

The result is one `NamedPipelineResult`, written to `run.json` exactly
like a built-in pipeline's, with `pipeline_source: "project-local"`
(`docs/artifacts.md` §4) — `buildrail runs list`/`runs inspect`/
`artifacts inspect` need no special handling for either source.

## 3. Precedence

Mirrors `buildrail.skills.SkillRegistry`'s rule exactly: a project-local
pipeline sharing a built-in's name (or another project-local pipeline's
name) is a discovery error — `buildrail pipeline list` and
`buildrail run <name>` fail clearly, naming both locations. There is no
override/replace semantics in this version of Buildrail.

## 4. Trust

**Project-local pipelines only ever reference skills — they do not
themselves contain executable code.** The actual trust boundary is at
the skill level: see `docs/skills.md`'s project-local skills section.
A pipeline referencing a project-local skill inherits that skill's
trust requirement.

## 5. See Also

- `docs/skills.md` — the skill manifest, protocol, and project-local
  skill discovery/precedence this document's steps build on.
- `docs/artifacts.md` §3–4 — run/artifact storage, including the
  `pipeline`/`pipeline_source` run.json fields.
- `README.md` — user-facing quick start (`buildrail pipeline create`,
  `buildrail run <pipeline>`).
