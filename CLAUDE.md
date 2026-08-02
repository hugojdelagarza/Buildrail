# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repository.

## What Buildrail Is

Buildrail is a local-first software engineering platform for orchestrating
pipelines, reusable AI skills, code reviews, documentation generation,
testing, and developer workflows. It runs on the developer's machine by
default and treats cloud services as optional, swappable backends — never
as a requirement.

See `docs/architecture.md` for the full design and `docs/roadmap.md` for
sequencing. `docs/milestone-1.md` is the current unit of work. The full
engineering specification — `docs/artifacts.md`, `docs/skills.md`,
`docs/provider-interface.md`, `docs/testing.md`, `docs/project-layout.md`,
`docs/engineering-principles.md` — is binding wherever it's more specific
than this file. `docs/git-workflow.md` covers commit/branch/release
conventions, and `CONTRIBUTING.md` covers the day-to-day dev workflow.

## Project Status

**Milestone 1 (in progress).** Repository scaffolding is complete and
committed: project structure, `pyproject.toml`, Ruff/mypy/pytest config.
The Core Engine skeleton exists (`src/buildrail/core`: a `CoreEngine`
class returning a placeholder `Result`), and the CLI (`src/buildrail/cli.py`)
delegates to it rather than hardcoding output. Milestone 1's actual
business logic — the review skill, the Provider Gateway, the Anthropic
adapter, artifact writing — has **not** been implemented yet. Do not
implement it, add dependencies beyond what a given approved step
requires, or scaffold further ahead of the current step without the
user's approval. See `docs/milestone-1.md` for exact scope and
acceptance criteria, and `docs/roadmap.md` for phase-by-phase status.

## Core Design Rules

These constraints are non-negotiable and should shape every future change:

1. **Local-first core.** The core engine (pipeline runner, skill loader,
   workflow state) must run fully offline with no cloud provider
   dependency. Cloud/network features are optional plugins layered on top.
2. **AI providers are interchangeable.** Nothing in the core may hardcode
   a specific AI vendor or SDK. Provider access goes through a single
   abstraction; adding a new provider must never require touching core
   logic.
3. **Skills are reusable units.** A skill is a self-contained, composable
   piece of capability (e.g., "review a diff," "generate docs for a
   module"). Skills must not assume a specific pipeline, provider, or
   project layout.
4. **CLI is the primary interface.** Every capability must be reachable
   from the CLI first. Any future UI (TUI, web dashboard, IDE plugin) is
   a consumer of the same core, not a parallel implementation.
5. **One complete feature at a time.** Build vertically — a full,
   working slice (CLI command → core logic → output) — rather than
   broad partial layers across the system.
6. **No unnecessary abstraction.** Prefer concrete, direct implementations.
   Introduce an interface or plugin point only when a second real
   implementation is imminent, not speculatively.

## Working Agreements

- Do not add implementation code without an approved milestone doc.
- Keep documentation in sync with structural decisions — if a change to
  `docs/architecture.md` is implied, propose it explicitly rather than
  drifting.
- Ask before introducing a new external dependency, especially anything
  cloud-hosted.
- Favor small, complete, reviewable increments over large speculative
  changes.

## Commit Boundaries

Recommending commits is a proactive, default part of working in this
repository — the user shouldn't have to ask. Full policy (cadence,
message style, branching, tags, releases) lives in
`docs/git-workflow.md`; this section is the operational rule for any AI
agent acting in this repo.

- **Recognize natural commit boundaries.** A boundary is reached whenever
  a self-contained, working slice is done: a scaffolding step, a doc
  revision pass, a passing test suite after a change, a bug fix —
  anything that leaves the repository clean and demonstrable, per the
  "one complete vertical slice at a time" principle
  (`docs/engineering-principles.md` §3).
- **Recommend commits automatically, without being asked.** When a
  boundary is reached, say so plainly: **"This is a good place to
  commit."** Don't wait to be prompted.
- **Never execute git commands that change repository or remote state.**
  No `git add`, `commit`, `push`, `reset`, `checkout`, branch deletion,
  or tagging — ever, regardless of how routine it seems. Read-only
  commands (`git status`, `git diff`, `git log`, `git ls-files`) are
  fine to run freely to inform a recommendation.
- **Inspect for secrets before recommending a commit.** Check
  changed/staged/untracked files against `docs/git-workflow.md`'s
  security checklist (secrets, keys, tokens, credentials, absolute local
  paths, machine-specific config, virtual environments, generated
  artifacts). If anything looks unsafe, stop and explain why instead of
  recommending the commit.
- **At every commit boundary, provide:**
  1. A recommended commit message (imperative mood).
  2. A summary of `git status` — what changed, what's untracked.
  3. The exact `git add` / `git commit` commands to run. Only include a
     `git push` recommendation when a push is actually appropriate
     (see `docs/git-workflow.md`) — never suggest it reflexively.
- **Stop after each clean implementation milestone.** Land one coherent
  slice, recommend the commit, and wait for approval before starting the
  next one — don't chain unrelated changes into a single unreviewed pass.
