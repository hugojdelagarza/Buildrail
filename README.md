# Buildrail

Buildrail is a local-first software engineering platform for orchestrating
pipelines, reusable AI skills, code reviews, documentation generation,
testing, and developer workflows.

It is designed around a simple idea: the developer's machine is the source
of truth. Pipelines, skills, and workflows run locally by default; AI
providers and cloud services are optional, swappable backends rather than
hard requirements.

> **Status:** Milestone 1 in progress. Repository scaffolding and the
> Core Engine skeleton (CLI → CoreEngine → Result → CLI output) are
> complete; Milestone 1's business logic (the review skill, Provider
> Gateway, Anthropic adapter) has not been implemented yet. See
> [docs/roadmap.md](docs/roadmap.md) for what's planned and
> [docs/milestone-1.md](docs/milestone-1.md) for the current unit of work.

## Why Buildrail

Most AI-assisted dev tooling today either:

- locks you into a single cloud AI provider, or
- locks you into a single hosted pipeline/CI product, or
- treats "AI skills" as one-off scripts that aren't reusable across projects.

Buildrail is built the other way around: a small, modular core that runs
pipelines and skills locally, with AI providers and cloud integrations
plugged in — never baked in.

## Core Principles

- **Local-first core** — no cloud provider dependency required to run.
- **Interchangeable AI providers** — swap providers without touching core logic.
- **Reusable skills** — a skill written for one pipeline works in another.
- **CLI-first** — every capability is reachable from the command line.
- **One complete feature at a time** — vertical slices, not partial layers.
- **Minimal abstraction** — concrete solutions over speculative flexibility.

## Documentation

- [docs/architecture.md](docs/architecture.md) — system design and module boundaries.
- [docs/roadmap.md](docs/roadmap.md) — phased plan from design to working CLI.
- [docs/milestone-1.md](docs/milestone-1.md) — the current milestone's scope.
- [docs/artifacts.md](docs/artifacts.md) — the artifact model: lifecycle, storage, versioning.
- [docs/skills.md](docs/skills.md) — the skill specification: manifest, execution model, protocol.
- [docs/provider-interface.md](docs/provider-interface.md) — the Provider Gateway contract.
- [docs/testing.md](docs/testing.md) — testing strategy and offline-by-default rule.
- [docs/project-layout.md](docs/project-layout.md) — full directory ownership and dependency rules.
- [docs/engineering-principles.md](docs/engineering-principles.md) — the engineering constitution.
- [docs/git-workflow.md](docs/git-workflow.md) — commit cadence, branch strategy, release philosophy.
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to develop, test, and submit changes.
- [CLAUDE.md](CLAUDE.md) — working agreements for AI agents contributing here.

## Project Layout (planned)

```
buildrail/
├── src/        # CLI + Core Engine skeleton implemented; Provider Gateway not yet built
├── skills/     # reusable skill definitions (none yet — first one lands in Milestone 1)
├── plugins/    # optional cloud/integration plugins (later phase)
├── tests/      # test suite
├── artifacts/  # generated output (reviews, docs, test reports, etc.) — git-ignored
└── docs/       # design and planning documents
```

See [docs/project-layout.md](docs/project-layout.md) for full directory
ownership and dependency rules, and
[docs/artifacts.md](docs/artifacts.md) for what "generated output" means
in Buildrail.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow,
coding standards, and commit/PR expectations. Read `docs/architecture.md`
and `CLAUDE.md` first — implementation work follows milestone docs, not
ad hoc additions.

## License

MIT — see [LICENSE](LICENSE).
