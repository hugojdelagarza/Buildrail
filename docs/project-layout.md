# Buildrail Project Layout

This is the long-term repository layout, including directories owned by
phases later than Milestone 1. Each is included only because a roadmap
phase already names it — nothing here is speculative beyond what
`docs/roadmap.md` commits to. Directories are created empty (with a
`.gitkeep` or similar) as their owning phase begins, not all at once.

```
buildrail/
├── src/
│   └── buildrail/       # the installable package (src-layout; see pyproject.toml)
│       ├── cli/            # command parsing, output formatting
│       ├── core/           # Pipeline Runner, Skill Registry, Run State
│       ├── artifacts/       # Artifact Store: writer, reader, metadata schema
│       ├── providers/
│       │   ├── gateway/      # Provider Gateway: interface, retry policy, usage accounting
│       │   └── adapters/     # one module per concrete provider
│       └── config/          # config loading and validation
├── skills/              # built-in, first-party skills
├── plugins/             # optional cloud/integration plugins (Phase 8)
├── docs/                # design and specification documents
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   ├── fakes/
│   └── golden/
└── artifacts/           # local run output — git-ignored
```

`examples/` is deliberately **not** included. No roadmap phase owns it,
and adding it now would be exactly the kind of directory that exists
"because we might want it" rather than because something needs it —
add it when a phase actually produces example projects worth shipping.

**Current state (Milestone 1, in progress):**
`src/buildrail/cli.py` is a single flat module with real `argparse`
subcommand parsing (`buildrail`, `buildrail config validate`) — not yet
a `cli/` package, since there's still only a handful of commands to
dispatch, not enough to warrant subdividing.
`src/buildrail/core/` holds `engine.py` (`CoreEngine`, `Result`); it has
no Pipeline Runner or Skill Registry yet — those land when a real skill
exists to run.
`src/buildrail/config/` holds `loader.py`: `load_config()`, the
`BuildrailConfig` dataclass, and the `ConfigError` exception hierarchy —
loads and validates `buildrail.toml` (`docs/architecture.md` §3.5)
against exactly what Milestone 1 needs (`provider`, `artifact_root`),
stdlib-only, no secrets.
`artifacts/` and `providers/` are not created yet. Each subdivision
above is created (as a real package, not a stub) only when the phase
that needs it actually lands, per the ownership rules below — not all
at once.

## Ownership and Dependency Rules

The point of stating these explicitly is that they're enforceable —
either by code review or, later, by an import-linter rule — not just
aspirational. "Allowed" means "may import from"; "forbidden" is called
out where it's easy to get wrong by accident.

### `src/buildrail/cli/`
- **Owns:** argument parsing, output formatting, exit codes.
- **Allowed deps:** `src/buildrail/core`, `src/buildrail/config`.
- **Forbidden:** business logic of any kind. `src/buildrail/cli` must not
  talk to `src/buildrail/artifacts` or `src/buildrail/providers` directly
  — if the CLI needs artifact data, it goes through `src/buildrail/core`,
  so a future UI/API consumes the exact same path (`docs/artifacts.md` §8).

### `src/buildrail/core/`
- **Owns:** Pipeline Runner, Skill Registry, Run State, orchestration of
  a skill's execution lifecycle (`docs/skills.md` §6).
- **Allowed deps:** `src/buildrail/artifacts` (to persist output),
  `src/buildrail/providers/gateway` (interface only),
  `src/buildrail/config`.
- **Forbidden:** importing anything from `src/buildrail/cli`,
  `src/buildrail/providers/adapters` (must go through the gateway), or
  any specific skill's internals. The Core Engine knows skills only
  through the manifest + subprocess protocol, never by importing skill
  code.

### `src/buildrail/artifacts/`
- **Owns:** artifact id/path generation, atomic write, metadata schema
  and validation, the read interface (`list_runs`, `get_artifact`, etc.).
- **Allowed deps:** `src/buildrail/config` (storage root path), standard
  library.
- **Forbidden:** depending on `src/buildrail/providers` or
  `src/buildrail/cli` or any skill — artifacts are a data layer,
  agnostic to what produced them.

### `src/buildrail/providers/gateway/`
- **Owns:** the `ProviderRequest`/`ProviderResponse` contract, retry
  policy, usage/cost aggregation, capability checks
  (`docs/provider-interface.md`).
- **Allowed deps:** `src/buildrail/providers/adapters` — but only through
  a registry/factory keyed by config, never a direct import of a
  specific adapter's class from outside that registry.
- **Forbidden:** any vendor SDK import directly in this module — that
  belongs one level down, in an adapter.

### `src/buildrail/providers/adapters/*`
- **Owns:** one module per provider, translating between that vendor's
  SDK and the Gateway's contract, including mapping vendor errors into
  the shared error taxonomy.
- **Allowed deps:** its own vendor SDK, nothing else in `src/` besides
  the Gateway's interface types.
- **Forbidden:** being imported from anywhere except the gateway's
  adapter registry — not from `src/buildrail/core`, not from a skill,
  not from another adapter.

### `src/buildrail/config/`
- **Owns:** loading and validating project-local config (active
  provider, capability-tier mapping, pipeline definitions once Phase 3
  exists).
- **Allowed deps:** standard library only.
- **Forbidden:** reading secrets from the config file itself — secrets
  come from the environment only (`docs/engineering-principles.md`,
  security by default).

### `skills/*`
- **Owns:** the actual skill implementations, one directory each
  (`docs/skills.md` §2).
- **Allowed deps:** whatever a skill's own language/runtime needs,
  entirely isolated per skill; communicates with Buildrail only through
  the `SkillRequest`/`SkillResponse` protocol.
- **Forbidden:** importing Buildrail's `src/` modules directly, even for
  built-in, first-party, Python-implemented skills. Built-in skills stay
  honest examples of what a community skill can actually do — if a
  built-in skill reached into `src/core` internals, the protocol
  boundary in `docs/skills.md` would be fiction.

### `plugins/*` (Phase 8, not yet created)
- **Owns:** optional integrations that reach outside the local machine
  (posting a report to GitHub/Slack, etc.).
- **Allowed deps:** the Core Engine's public artifact read interface
  (`docs/artifacts.md` §8) only.
- **Forbidden:** being depended upon by `src/buildrail/core`,
  `src/buildrail/cli`, or any skill — the dependency arrow points one
  direction. Core must be buildable and runnable with the entire
  `plugins/` directory deleted.

### `tests/*`
- **Owns:** verification, mirroring `src/`'s structure by test level
  (`docs/testing.md`).
- **Allowed deps:** everything in `src/`, plus `tests/fakes`.
- **Forbidden:** any real network call or real credential — enforced as
  a hard rule in `docs/testing.md` §8, not a convention.

### `docs/*`
- **Owns:** no code, but each doc has an implicit owning module (this
  doc ↔ the whole tree; `docs/skills.md` ↔ `src/buildrail/core` +
  `skills/`, etc.).
  A structural change to a module's contract updates its doc in the same
  change, per `CLAUDE.md`'s working agreements — docs and code are
  expected to match continuously, not eventually.

### `artifacts/`
- **Owns:** nothing but generated output. Git-ignored. No module may
  treat this directory's *layout* as an API — all reads go through
  `src/buildrail/artifacts`'s read interface, never a raw path join, so
  the on-disk layout can change without breaking every caller.
