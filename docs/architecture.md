# Buildrail Architecture

> **Revision note:** this document originally described a `reports/`
> directory for generated run output and left the Skill manifest and
> Provider Gateway shapes to be decided during Milestone 1. Those are
> now fully specified in `docs/artifacts.md`, `docs/skills.md`, and
> `docs/provider-interface.md`; this document is updated to point to
> them rather than duplicate them, and `reports/` is renamed to
> `artifacts/` throughout (see `docs/artifacts.md` §9 for why).

## 1. Goals and Constraints

Buildrail orchestrates pipelines, reusable AI skills, code reviews,
documentation generation, testing, and developer workflows, from the
developer's machine.

Design constraints (see `CLAUDE.md` for the enforced version of these rules):

- The **core** must run with no cloud provider and no network access.
- **AI providers** are interchangeable — the core never depends on a
  specific vendor SDK.
- **Skills** are reusable, composable units, portable across pipelines
  and projects.
- The **CLI** is the primary interface; everything else consumes the
  same core.
- Built **one complete vertical feature at a time**.
- **No speculative abstraction** — interfaces exist only where a second
  real implementation already exists or is imminent.

## 2. System Overview

```
                     ┌─────────────────────┐
                     │         CLI          │   primary interface
                     └──────────┬───────────┘
                                │  commands
                     ┌──────────▼───────────┐
                     │      Core Engine      │   local-first, no network
                     │  ─────────────────── │
                     │  Pipeline Runner      │
                     │  Skill Registry/Loader│
                     │  Run State / Reports  │
                     └───┬───────────────┬───┘
                         │               │
              ┌──────────▼───┐     ┌─────▼───────────┐
              │    Skills     │     │  Provider Gateway │  optional, pluggable
              │ (reusable)    │     │  (AI abstraction)  │
              └───────────────┘     └─────┬─────────────┘
                                           │
                                ┌──────────▼──────────┐
                                │  Provider Adapters    │  Anthropic, OpenAI,
                                │  (plugins)            │  local model, etc.
                                └───────────────────────┘
```

Everything below the CLI line runs locally. The Provider Gateway is the
only component permitted to reach a network, and only when a skill
actually needs AI assistance — many skills (lint, static checks,
templated doc scaffolds) need no provider at all.

## 3. Modules

### 3.1 CLI

- Thin layer: parses commands/flags, loads config, calls into the Core
  Engine, formats output.
- Contains no business logic. If logic can't be reused by a future
  non-CLI consumer, it doesn't belong here.
- One subcommand per capability (e.g. `buildrail run <pipeline>`,
  `buildrail skill list`), consistent with "CLI is the primary interface."

### 3.2 Core Engine

The only part of the system every feature depends on. Split into three
responsibilities, kept separate because they change for different reasons:

- **Pipeline Runner** — executes a pipeline: an ordered (initially
  linear; graph support only if/when a real use case needs it) sequence
  of skill invocations. Owns retries, step ordering, and passing output
  from one step to the next.
- **Skill Registry/Loader** — discovers skills (from `skills/` and any
  project-local skill directory), validates their manifest, and exposes
  them to the Pipeline Runner by name. Does not know what a skill does
  internally.
- **Run State / Artifacts** — records what ran, its inputs/outputs, and
  writes every output as a typed artifact to `artifacts/`. Local
  filesystem only; no database requirement. Full spec:
  `docs/artifacts.md`.

The Core Engine depends on nothing outside the standard library plus
the Skill and Provider *interfaces* — never on a specific skill's
internals or a specific provider's SDK.

### 3.3 Skills

- A skill is a self-contained unit with a declared input, a declared
  output, and a single responsibility (e.g. "review a diff," "generate
  docs for a module," "run project tests and summarize failures").
- A skill declares whether it needs the Provider Gateway. Skills that
  don't need AI (formatting, static analysis wrappers) must not depend
  on it.
- Skills are portable: the same skill definition must work from any
  pipeline and, so far as its declared inputs allow, any project.
- Skills live in `skills/`, one directory per skill, with a manifest
  plus its logic, executed as a subprocess against a versioned
  request/response protocol so skills can be written in any language
  and never hold provider credentials directly. Full spec, including
  the manifest format and the execution model tradeoffs considered:
  `docs/skills.md`.

### 3.4 Provider Gateway (AI abstraction)

- A single, narrow interface the Core Engine and Skills use to ask for
  AI assistance (e.g. "complete this prompt," "review this text").
- Concrete providers (Anthropic, OpenAI, a local model runner, etc.)
  implement that interface as adapters and are selected via config —
  never imported directly by core or skill code.
- Adding a provider means adding one adapter. It must never require
  changing the Core Engine, the Skill interface, or existing skills.
- If no AI-dependent skill is in use, the Provider Gateway is never
  invoked and no network call is made — this is what keeps the core
  local-first rather than merely "local-capable."
- Because skills run as subprocesses (§3.3), the Gateway is reachable
  from a skill only through a short-lived, run-scoped local loopback
  endpoint — a skill never receives a raw API key. Full request/response
  contract, capability model, error taxonomy, and retry policy:
  `docs/provider-interface.md`.

### 3.5 Config

- Project-local configuration (which provider is active, pipeline
  definitions, skill parameters) lives in a plain file at the project
  root, checked into version control like any other project setting.
- Secrets (API keys) are never stored in that file — they come from
  the environment. Buildrail must run with zero configured secrets for
  any pipeline that uses no AI-dependent skill.

### 3.6 Artifacts

- Every output of a run (a code review, generated docs, a diagram, a
  test summary) is written as a typed, immutable, versioned artifact to
  `artifacts/`, with structured metadata recording provenance and
  relationships to other artifacts.
- Artifacts are a Core Engine responsibility (Run State), not something
  each skill reinvents. Full spec: `docs/artifacts.md`.

## 4. Data Flow (typical run)

1. Developer runs a CLI command naming a pipeline or a single skill.
2. CLI loads config, resolves the pipeline via the Core Engine.
3. Pipeline Runner executes each step by invoking the named skill
   through the Skill Registry.
4. If a skill needs AI assistance, it calls the Provider Gateway, which
   dispatches to whichever adapter is configured — the skill never
   knows which one.
5. Run State persists each declared output as an artifact under
   `artifacts/`; a run-level manifest indexes what the run produced.
6. CLI prints a summary and exits.

## 5. Directory Layout

```
buildrail/
├── src/            # CLI + Core Engine + Provider Gateway + adapters
├── skills/         # reusable skill definitions, one directory each
├── plugins/        # optional cloud/integration plugins (Phase 8)
├── tests/          # test suite, mirrors src/ structure
├── artifacts/      # generated run output (git-ignored)
└── docs/           # design and planning documents
```

Full ownership and dependency rules for each directory (allowed/forbidden
imports between modules): `docs/project-layout.md`.

## 6. What Is Explicitly Deferred

To honor "no unnecessary abstractions" and "one feature at a time,"
the following are **not** designed yet, on purpose:

- Graph-shaped (non-linear) pipelines — start linear, generalize only
  when a real pipeline needs branching.
- A plugin marketplace or dynamic plugin discovery — start with
  adapters registered in code/config.
- Multi-user, remote, or hosted execution — Buildrail is single-developer,
  local-first; anything multi-user is a future, separate concern.
- A database or persistent service — filesystem-based state is
  sufficient until a concrete need proves otherwise (see
  `docs/artifacts.md` §3 for why artifacts are files, not a DB).
- Streaming provider responses through the subprocess skill protocol —
  the interface allows for it, nothing consumes it yet
  (`docs/provider-interface.md` §5).
- Sandboxing of subprocess skills beyond the provider-credential
  boundary — a named, open risk, not a solved problem
  (`docs/skills.md` §9).

## 7. See Also

The following documents are part of the architecture and take
precedence over this one wherever they're more specific:

- `docs/artifacts.md` — artifact lifecycle, storage, versioning.
- `docs/skills.md` — skill manifest, execution model, protocol.
- `docs/provider-interface.md` — Provider Gateway contract.
- `docs/testing.md` — testing strategy and offline-by-default rule.
- `docs/project-layout.md` — full directory ownership and dependency rules.
- `docs/engineering-principles.md` — the principles all of the above answer to.
