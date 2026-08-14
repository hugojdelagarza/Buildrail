# Buildrail Roadmap

This roadmap sequences work as complete vertical slices. Each phase
should leave Buildrail in a working, demonstrable state — no phase ends
with partial, unusable layers. See `docs/architecture.md` for the
modules referenced below, and `docs/milestone-1.md` for the detailed
breakdown of the phase we start with. The skill, provider, artifact, and
testing contracts referenced throughout are fully specified in
`docs/skills.md`, `docs/provider-interface.md`, `docs/artifacts.md`, and
`docs/testing.md` — phases below implement against those, they don't
redesign them.

## Phase 0 — Design — **Complete**

- Define architecture, module boundaries, and constraints.
- No implementation.
- Output: `CLAUDE.md`, `README.md`, `docs/architecture.md`,
  `docs/roadmap.md`, `docs/milestone-1.md`, and the engineering
  specification set (`docs/artifacts.md`, `docs/skills.md`,
  `docs/provider-interface.md`, `docs/testing.md`,
  `docs/project-layout.md`, `docs/engineering-principles.md`).

## Phase 1 — Single Skill, End to End — **Complete**

Prove the full vertical slice works with the smallest possible surface:
one CLI command, running one real skill, through the Core Engine, with
one AI provider adapter wired through the Provider Gateway, writing one
artifact.

- Repository scaffolding, the Core Engine, configuration
  loading/validation (`buildrail config validate`), the `review-diff`
  skill, the Provider Gateway, and the Fake and Anthropic adapters are
  all implemented.
- Detailed in `docs/milestone-1.md`.

## Phase 2 — Skill Registry — **Complete**

- Two built-in skills (`review-diff`, `test-summary`), discovered and
  listed by the CLI (`buildrail skill list`, `buildrail skill inspect
  <name>`) via a manifest-driven `SkillRegistry`, replacing Milestone
  1's hardcoded skill loading.
- Validates the minimal manifest subset both skills actually use;
  rejects duplicate names, missing/malformed manifests, unsupported
  protocol versions, and missing entrypoints.
- Skills still run in-process (docs/skills.md's phasing note) and
  pipelines are still fixed step lists — subprocess transport and a
  project-local skill override path remain for later phases.

## Phase 3 — Pipelines — **Complete**

- The CLI gained `buildrail run <pipeline>`, with the first named
  pipeline, `pre-commit` (`verify-project`, then `review-diff` only
  when there's a Git diff to review), registered in code — not yet
  user-authored YAML/TOML pipeline files.
- All of a named pipeline's steps share one run id and one `run.json`,
  which now also records the pipeline name, overall status, ordered
  step results (including steps skipped by pipeline-level logic, e.g.
  no diff), and aggregate provider usage.
- Still a linear sequence (no DAG, no parallelism, no retries); still
  single AI provider; still local-first.

## Phase 4 — Second AI Provider — **Not started**

- Add a second provider adapter behind the existing Provider Gateway
  interface, proving the abstraction holds without modifying the Core
  Engine or any existing skill.
- Provider selection becomes a config value, not a code change.

## Phase 5 — Code Review Feature, Fully Built Out — **Not started**

- Build out the code review capability as a first-class pipeline:
  diff intake → review skill(s) → `review` artifact
  (`docs/artifacts.md` §1).
- This is the first feature area called out in the project's original
  goals; treat it as the reference example for what a fully-built
  feature looks like end to end (as opposed to Milestone 1's minimal
  single-skill slice).

## Phase 6 — Documentation Generation Feature — **Complete**

- Three built-in skills (`explain-project`, `generate-docs`,
  `generate-diagram`) share one deterministic, offline analyzer
  (`buildrail.analysis`) that inspects a Python repository via `ast` —
  no regex parsing, no execution of analyzed code.
- `buildrail explain`, `buildrail docs generate`, and `buildrail diagram
  generate` all work fully offline; `buildrail docs generate --enhance`
  is the only one that optionally reuses the existing Provider Gateway,
  making at most one bounded request per generated document and never
  replacing a deterministic fact with model output.
- The named pipeline `buildrail run project-intelligence` composes all
  three, analyzing the repository once and sharing that analysis, one
  run id, and one `run.json` across every step — no re-analysis per step.

## Phase 7 — Testing Workflows — **Not started**

- A pipeline that runs a project's tests and produces a `test-report`
  artifact (failures, flaky signals, coverage deltas where available)
  — no new orchestration concepts, just new skills.

## Phase 8 — Optional Cloud/Integration Layer — **Not started**

- Only after the local-first core is proven across multiple features:
  optional integrations (e.g. posting a report to GitHub/Slack) as
  plugins outside the core, never required to run Buildrail locally.

## Phase 9 — Project-Local Extensibility — **Complete**

- Every project gets its own extension points: `buildrail init` (and
  `buildrail init --extensions` for an already-configured project)
  scaffolds `.buildrail/skills/` and `.buildrail/pipelines/`.
- Project-local skills (`.buildrail/skills/<name>/`) use the exact same
  manifest and `SkillRequest`/`SkillResponse` protocol as built-in
  skills — `SkillRegistry` discovers both together, with a project-local
  skill sharing a built-in's name failing discovery clearly rather than
  silently overriding it. `buildrail skill create <name>` scaffolds one;
  the same function backs the local HTTP service's `POST /skills`.
- Project-local pipelines (`.buildrail/pipelines/<name>.yaml`) are a
  small declarative YAML format — an ordered list of existing skills,
  each with an optional `condition` (`always`/`changes_exist`) and
  `inputs` — executed generically by `CoreEngine.run_named_pipeline`,
  sharing Buildrail's existing run/artifact model exactly as `pre-commit`
  and `project-intelligence` already do. `buildrail pipeline create` and
  `POST /pipelines` scaffold one from structured input, never raw YAML.
- A single `PipelineRegistry` (`docs/pipelines.md`) is now the shared
  source of truth for built-in *and* project-local pipelines that the
  CLI (`buildrail run <name>`, `buildrail pipeline list`/`inspect`), the
  local HTTP service, and the frontend all read — built-in pipelines
  (`pre-commit`, `project-intelligence`) keep their bespoke orchestration
  and CLI flags; only their *description* moved into the shared registry.
- The frontend's Skills and Pipelines pages show built-in vs.
  project-local source, filter by source, and can create either through
  narrowly-scoped forms — no arbitrary code or YAML upload. See
  `docs/frontend.md`.
- Project-local skills are trusted repository code, documented as such
  everywhere they're surfaced — Buildrail does not sandbox them. This is
  explicitly not a community/third-party skill distribution mechanism;
  that remains gated on solving sandboxing separately (`docs/skills.md`
  §9).

## Current Implementation Beyond the Original Roadmap

A few complete, working slices exist that don't map cleanly onto Phases
4–8 above, because they solve problems the original phase list didn't
anticipate rather than advancing toward one of its named features:

- **Project init and configuration** — `buildrail init` and
  `buildrail config validate`, plus a first-run onboarding flow in the
  frontend, for creating and checking `buildrail.toml`.
- **Local HTTP service and dashboard** — `buildrail serve` exposes
  `CoreEngine`/`ArtifactReader` functionality over a localhost-only HTTP
  API; a React/Vite dashboard under `frontend/` (and an optional minimal
  Tauri desktop shell) consumes it. See `docs/frontend.md`.
- **Dependency audit** — `buildrail dependency-audit`, a deterministic,
  offline audit of a repository's declared dependencies against local
  imports (explicitly not a vulnerability/CVE scanner). Kept standalone
  rather than folded into the `project-intelligence` pipeline, to avoid
  disturbing that pipeline's fixed three-step contract.

These are verified the same way every phase above is (`docs/testing.md`,
offline by default); they're recorded here rather than forcing a new
numbered phase onto each one.

## Sequencing Principles

- A phase does not start until the previous phase's vertical slice
  actually works end to end.
- Abstractions introduced in an earlier phase (Skill interface,
  Provider Gateway) are only generalized when a later phase's real
  requirement forces it — not preemptively.
- If a phase reveals that a design doc (architecture, skills, provider
  interface, artifacts, testing, or project layout) is wrong or
  incomplete, fix the doc as part of that phase's work rather than
  carrying the drift forward.
