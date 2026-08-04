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

## Phase 1 — Single Skill, End to End — **In progress (current)**

Prove the full vertical slice works with the smallest possible surface:
one CLI command, running one real skill, through the Core Engine, with
one AI provider adapter wired through the Provider Gateway, writing one
artifact.

- Repository scaffolding, the Core Engine skeleton, and configuration
  loading/validation (`buildrail config validate`) are complete. The
  skill, Provider Gateway, and adapter have not been implemented yet.
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

## Phase 3 — Pipelines — **Not started**

- Introduce the Pipeline Runner: a named, linear sequence of skills
  with output from one step available to the next.
- CLI gains `buildrail run <pipeline>`.
- Still single AI provider; still local-first.

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

## Phase 6 — Documentation Generation Feature — **Not started**

- A pipeline that generates or updates docs for a module/project,
  reusing the skill and provider infrastructure built for code review.

## Phase 7 — Testing Workflows — **Not started**

- A pipeline that runs a project's tests and produces a `test-report`
  artifact (failures, flaky signals, coverage deltas where available)
  — no new orchestration concepts, just new skills.

## Phase 8 — Optional Cloud/Integration Layer — **Not started**

- Only after the local-first core is proven across multiple features:
  optional integrations (e.g. posting a report to GitHub/Slack) as
  plugins outside the core, never required to run Buildrail locally.

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
