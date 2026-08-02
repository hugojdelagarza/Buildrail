# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repository.

## What Buildrail Is

Buildrail is a local-first software engineering platform for orchestrating
pipelines, reusable AI skills, code reviews, documentation generation,
testing, and developer workflows. It runs on the developer's machine by
default and treats cloud services as optional, swappable backends — never
as a requirement.

See `docs/architecture.md` for the full design and `docs/roadmap.md` for
sequencing. `docs/milestone-1.md` is the current unit of work.

## Project Status

Design phase. No implementation exists yet. Do not scaffold source code,
add dependencies, or generate implementation until a milestone doc has
been approved by the user.

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
