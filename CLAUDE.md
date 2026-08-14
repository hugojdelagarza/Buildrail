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
`docs/pipelines.md`, `docs/provider-interface.md`, `docs/testing.md`,
`docs/project-layout.md`, `docs/engineering-principles.md` — is binding
wherever it's more specific than this file. `docs/git-workflow.md` covers
commit/branch/release conventions, and `CONTRIBUTING.md` covers the
day-to-day dev workflow.

## Project Status

Milestone 1 and roadmap Phases 0–3, 6, and 9 are complete; see
`docs/roadmap.md` for full phase-by-phase status (including what's
`Not started`/`Deferred`) and `docs/milestone-1.md` for Milestone 1's
original scope and acceptance criteria. Do not add dependencies beyond
what an approved step requires, or scaffold ahead of a real, current
need without the user's approval.

## Current Project Context

Durable decisions that should carry between sessions — update this list
when one changes or a milestone completes; it's a snapshot, not a log:

- Buildrail is local-first.
- Buildrail is open source.
- Python 3.12 is the current implementation language.
- The CLI delegates to the Core Engine.
- Providers are interchangeable — Fake and Anthropic adapters exist
  behind the Provider Gateway (`src/buildrail/providers`).
- Skills are reusable and provider-neutral; built-in skills currently
  run in-process against the same request/response contract a real
  subprocess transport would use later (`docs/skills.md` §1).
- Built-in skills: `review-diff`, `test-summary`, `release-notes`,
  `verify-project`, `explain-project`, `generate-docs`,
  `generate-diagram`, `dependency-audit`.
- Named pipelines: `pre-commit`, `project-intelligence` (built-in,
  code-backed).
- Every project also gets `.buildrail/skills/` and `.buildrail/pipelines/`
  (scaffolded by `buildrail init`) for project-local skills and
  declarative pipelines, discovered alongside built-ins by one shared
  `SkillRegistry`/`PipelineRegistry` — a project-local name colliding
  with a built-in fails discovery, it never silently overrides. Trusted
  repository code, not a sandboxed or community plugin mechanism
  (`docs/skills.md` §10, `docs/pipelines.md`).
- Generated outputs are typed artifacts, written under `artifact_root`
  and browsable via `buildrail runs`/`buildrail artifacts`.
- A local HTTP service (`buildrail serve`) and a React/Vite dashboard
  under `frontend/` exist, plus an optional minimal Tauri desktop shell
  — see `docs/frontend.md`.
- Tests run offline by default.
- Buildrail is implemented one complete vertical slice at a time.
- Do not implement cloud infrastructure or community skill distribution
  before their roadmap phase (`docs/roadmap.md` Phase 8).

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

Recommending commits is proactive — the user shouldn't have to ask. Full
policy (cadence, branching, tags, releases) lives in
`docs/git-workflow.md`; commit messages follow **Conventional Commits**,
`type(scope): concise imperative description` — full type list, scope
rules, and examples in `docs/git-workflow.md` §5. This section is the
operational rule for any AI agent acting in this repo.

- **Recognize the boundary and say so.** When a self-contained, working
  slice is done (per `docs/engineering-principles.md` §3), say plainly:
  **"This is a good place to commit."** Don't wait to be asked.
- **Never run a repository-changing Git command without explicit
  approval.** No `add`, `commit`, `push`, `reset`, `checkout`, `clean`,
  branch deletion, or tagging. Read-only commands (`status`, `diff`,
  `log`, `ls-files`) are always fine to run to inform a recommendation.
- **Before recommending, always run/inspect:** `git status`, `git diff
  --check`, `git diff`, `git diff --cached` (if anything is staged), and
  the changed/untracked files for secrets, credentials, API keys, local
  paths, or other unsafe content (`docs/git-workflow.md` §8). If
  anything looks unsafe, stop and explain why instead of recommending
  the commit.
- **This project is developed from Windows Command Prompt.** Every
  command given must work in CMD — no `$(...)`, heredocs, or `export`.
  Use multiple `-m` flags for a multi-line commit message, and `set` for
  environment variables (`docs/git-workflow.md` §5).
- **At the boundary, respond using the Completion Summary Format
  below.**
- **Stop after each clean slice.** Land one coherent change, recommend
  the commit, and wait for approval before starting the next one.

## Completion Summary Format

Keep completion summaries concise by default:

```
Summary
- 2-5 bullets on the meaningful changes

Verification
- format / lint / mypy / tests / relevant runtime check

Git
- safety status
- recommended commit message
- exact commands
```

Don't repeat every file's purpose when it's obvious from the diff,
restate the whole architecture, or add celebratory commentary. Expand
beyond this structure only when a decision is risky, surprising, or
architectural — a tradeoff worth flagging, not a status update.
