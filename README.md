# Buildrail

Buildrail is a local-first software engineering platform for orchestrating
pipelines, reusable AI skills, code reviews, documentation generation,
testing, and developer workflows.

It is designed around a simple idea: the developer's machine is the source
of truth. Pipelines, skills, and workflows run locally by default; AI
providers and cloud services are optional, swappable backends rather than
hard requirements.

> **Status:** Phases 0–3 are complete: CLI, Core Engine, configuration,
> Provider Gateway (Fake + Anthropic adapters), a manifest-driven Skill
> Registry (four built-in skills), the Artifact Store/Reader, Git hook
> management, and the first named pipeline (`buildrail run pre-commit`)
> are all implemented. See [docs/roadmap.md](docs/roadmap.md) for phase
> status and what's next.

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

## Usage Example

`buildrail review --diff <path>` reviews a unified diff using whichever
provider `buildrail.toml` names.

**Offline, no API key (default for development and tests):**

```toml
provider = "fake"
artifact_root = "artifacts"
```

**Real reviews via Claude:**

```toml
provider = "anthropic"
artifact_root = "artifacts"
anthropic_model = "claude-haiku-4-5-20251001"  # optional; this is the default
```

Set your API key for the current terminal session (Windows CMD):

```
set ANTHROPIC_API_KEY=your_key_here
```

Then run:

```
buildrail review --diff path\to\changes.patch
```

**Never commit a real API key.** `ANTHROPIC_API_KEY` must only ever come
from the environment — never write it into `buildrail.toml` or any
other tracked file. `.env` is git-ignored for this reason;
`.env.example` documents the variable name only.

### Local Verification (No Provider Needed)

`buildrail verify` runs Buildrail's local Python quality gate — `ruff
format --check`, `ruff check`, `mypy`, then `pytest -v`, stopping at the
first failed check — and writes a `verification-report` artifact. It
works in any valid Buildrail project with no provider configured, no
`ANTHROPIC_API_KEY`, and no network access:

```toml
artifact_root = "artifacts"
```

```
buildrail verify
```

Exits `0` when every check passes, nonzero otherwise — safe to use as a
pre-commit or CI gate.

### The Pre-Commit Pipeline

`buildrail run pre-commit` is Buildrail's daily workflow: it runs
`verify-project` first, then `review-diff` — but only when there's a
Git diff to review — sharing one run and one artifact history:

```
buildrail run pre-commit
buildrail run pre-commit --base main
buildrail run pre-commit --skip-review
```

Failed verification blocks the pipeline before any provider is
constructed. With no `--base`, the diff is collected against the
branch's upstream if one is configured, otherwise `HEAD~1`. If there
are no changes against the resolved base, review is skipped (no
provider call) and the pipeline still reports success.

### Project Intelligence

Three commands share one deterministic, offline analyzer that inspects a
Python repository with `ast` — no AI required to use any of them:

```
buildrail explain
buildrail docs generate
buildrail diagram generate
```

`explain` writes a Markdown architecture summary plus a machine-readable
JSON sidecar (entry points, package/module map, CLI commands, classes,
functions, imports, statistics, and warnings). `docs generate` writes
`project-overview.md`, `module-reference.md`, and `development-guide.md`;
add `--output <path>` to also write them into the project itself (it
refuses to overwrite existing files) and `--enhance` to have the
configured provider draft a short prose introduction for each document —
every fact still comes from the deterministic analysis, never the model.
`diagram generate` writes Mermaid diagram source only (no SVG/PNG
rendering yet). All three accept `--path <repository>` (default: the
current directory) and never make a network call unless `--enhance` is
used.

`buildrail run project-intelligence` runs all three together, analyzing
the repository once and sharing that analysis, one run id, and one
`run.json` across every step:

```
buildrail run project-intelligence
buildrail run project-intelligence --enhance
```

Every artifact from any of these commands is browsable with the same
`buildrail runs`/`buildrail artifacts` commands as the rest of Buildrail.

### Git Pre-Commit Hook

`buildrail hooks install` adds a local Git pre-commit hook that runs
`buildrail verify` before each commit — a failed verification blocks the
commit. It only ever touches the current repository (never global Git
config), and preserves any pre-existing pre-commit hook content instead
of overwriting it:

```
buildrail hooks install
buildrail hooks status
buildrail hooks uninstall
```

`uninstall` removes only Buildrail's managed block, leaving any
unrelated hook content exactly as it was. This is a local pre-commit
hook only — it does not add a pre-push hook or any CI workflow. The
installed hook still runs `buildrail verify` for now, not the
pre-commit pipeline above.

### Discovering Skills

Built-in skills are discovered by the Skill Registry, not hardcoded.
List what's available, or inspect one skill's manifest:

```
buildrail skill list
buildrail skill inspect review-diff
```

### Browsing Runs and Artifacts

Every command above writes its output under `artifact_root` as a typed
artifact. These commands browse that local history read-only — nothing
is mutated, moved, or deleted:

```
buildrail runs list
buildrail runs inspect <run-id>
buildrail artifacts inspect <artifact-id>
```

`runs list` shows the most recent runs (newest first, 20 by default;
use `--limit <n>` to change that). `runs inspect` shows one run's
artifacts; `artifacts inspect` shows one artifact's full metadata and
payload, checksum-verified before it's displayed.

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

## Project Layout

```
buildrail/
├── src/        # CLI, Core Engine, Provider Gateway, Skill Registry, Pipeline Runner, Artifact Store/Reader
├── skills/     # reusable skill definitions (review-diff, test-summary, verify-project,
│               #   release-notes, explain-project, generate-docs, generate-diagram)
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
