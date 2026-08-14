# Buildrail

Buildrail is a local-first software engineering platform for orchestrating
pipelines, reusable AI skills, code reviews, documentation generation,
testing, and developer workflows.

It is designed around a simple idea: the developer's machine is the source
of truth. Pipelines, skills, and workflows run locally by default; AI
providers and cloud services are optional, swappable backends rather than
hard requirements.

> **Status:** Phases 0–3, 6, 7, and 9 are complete: CLI, Core Engine,
> configuration, Provider Gateway (Fake + Anthropic adapters), a
> manifest-driven Skill Registry, the Artifact Store/Reader, Git hook
> management, named pipelines (`buildrail run pre-commit`,
> `buildrail run project-intelligence`, `buildrail run quality-gate`),
> project-local skills/pipelines (`buildrail skill create`,
> `buildrail pipeline create`), and a first-class testing workflow
> (`buildrail test`, `buildrail test --analyze`) are all implemented —
> plus a local HTTP service and dashboard (`buildrail serve`) and a
> dependency audit (`buildrail dependency-audit`) that go beyond the
> original roadmap. See [docs/roadmap.md](docs/roadmap.md) for phase status
> and what's next.

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

### Testing

`buildrail test` is Buildrail's primary testing workflow: it runs the
project's pytest suite deterministically and writes a `test-report`
artifact (Markdown plus a machine-readable JSON sidecar) with pass/fail
counts, individual failures, collection errors, and — only when a
`coverage.xml` already exists — a coverage summary. It never invokes
coverage tooling itself and has no hard dependency on it.

```
buildrail test
buildrail test --analyze
buildrail test --history
```

`--analyze` sends failing-test context to the configured provider for a
short root-cause summary — only when the run actually has failures,
never on a clean pass, and it never blocks the deterministic result if
no provider is configured. `--history` compares this run's failures
against recent `test-report` runs and notes tests that failed now but
not in the immediately preceding run as a possible flaky signal — a
conservative note, never an automatic rerun or a "confirmed flaky"
verdict. `buildrail test-summary` — the older, narrower AI-summary-only
command — still works exactly as before and now shares this same
pytest executor internally instead of a second implementation.

`buildrail run quality-gate` composes `verify-project`, `test-report`,
and `dependency-audit` into one run: Buildrail's broadest local quality
check, still fully offline by default.

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

### Dependency Audit

```
buildrail dependency-audit
buildrail dependency-audit --path <repository>
```

A fully local, offline audit of a Python repository's declared
dependencies (`pyproject.toml`, `requirements*.txt`) against the imports
Buildrail's deterministic analyzer observes in the code — declared
runtime/dev/optional dependencies, version constraints, duplicate and
conflicting declarations, unpinned packages, and VCS/URL/local-path/editable
dependencies. It never runs `pip`/`poetry`/`uv`, never imports the analyzed
project, and never contacts a package registry.

**This is not a vulnerability or CVE scanner.** It reports deterministic
facts about declarations and local imports only; it does not check any
package against a security database. Because Python import names and
distribution names don't always match (`pyyaml` vs. `yaml`), mismatches
between declared dependencies and observed imports are reported as
conservative, uncertain observations — never as confident "unused" or
"missing" claims.

### Project-Local Skills and Pipelines

Every project gets its own extension points — `buildrail init` scaffolds
empty `.buildrail/skills/` and `.buildrail/pipelines/` directories (an
already-configured project can add them with `buildrail init --extensions`).
Scaffold a new skill or pipeline, then discover and run it exactly like
a built-in:

```
buildrail skill create my-skill
buildrail pipeline create quality
buildrail run quality
```

A project-local skill (`.buildrail/skills/<name>/skill.yaml` + `skill.py`)
uses the exact same manifest and `SkillRequest`/`SkillResponse` protocol
as a built-in skill — there is no second format. A project-local pipeline
(`.buildrail/pipelines/<name>.yaml`) is a small declarative YAML file: an
ordered list of existing skill names, each with an optional `condition`
(`always` or `changes_exist`) and `inputs`:

```yaml
name: quality
version: 0.1.0
description: Verify and review the current project

steps:
  - skill: verify-project
  - skill: review-diff
    condition: changes_exist
```

No DAGs, loops, variables, templating, or parallel steps — see
[docs/pipelines.md](docs/pipelines.md) for the full manifest format and
what's intentionally not supported yet. A project-local skill or pipeline
sharing a built-in's name is a discovery error, never a silent override.

**Project-local skills execute code from the repository they're found
in.** Buildrail does not sandbox them — only use project-local skills
from repositories you trust. See
[docs/skills.md](docs/skills.md) §10 for the full trust model.

`examples/project-local/` has a minimal example skill and pipeline to
copy in and try (never auto-discovered on its own).

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

### Discovering Skills and Pipelines

Built-in and project-local skills are discovered by the Skill Registry
together, not hardcoded. List what's available (each shown with its
source), or inspect one skill's manifest:

```
buildrail skill list
buildrail skill inspect review-diff
```

Pipelines work the same way, through the Pipeline Registry — built-in
(`pre-commit`, `project-intelligence`, `quality-gate`) and project-local
pipelines listed and inspected together:

```
buildrail pipeline list
buildrail pipeline inspect quality
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

### Local Dashboard (Frontend)

`buildrail serve` starts a lightweight, localhost-only HTTP service
(`http://127.0.0.1:8787` by default; no TLS, no authentication) that
exposes the same `CoreEngine`/`ArtifactReader` functionality above as
JSON endpoints, for the local React dashboard under `frontend/`:

```
buildrail serve

cd frontend
npm install
npm run dev
```

The service must be running before the frontend can connect — it never
starts one on your behalf. No data leaves the machine except an explicit
provider call your own commands make (`FakeProvider` supports the whole
dashboard fully offline, with no API key). The frontend is read-only for
configuration and artifacts in this release — it can execute commands
and pipelines, but it cannot edit `buildrail.toml` or modify any
artifact. Press `Ctrl+K` (or `Ctrl+Shift+P`) for a searchable command
palette covering every page and action, or `G` then a letter to jump
directly to a page — see [docs/frontend.md](docs/frontend.md) for the
full shortcut list, layout customization, architecture boundary, API URL
configuration, and current limitations.

### Desktop Shell (Optional)

The same frontend can also run as a native desktop window via a minimal
Tauri 2 shell under `frontend/src-tauri/` — a display host only, with no
Buildrail logic in Rust. Python is still Buildrail's runtime; Rust exists
here solely to host the existing web UI natively. Requires a Rust toolchain
([rustup](https://rustup.rs/)):

```
buildrail serve

cd frontend
npm run tauri:dev
```

See [docs/frontend.md](docs/frontend.md) for setup requirements and current
desktop-specific limitations.

## Documentation

- [docs/architecture.md](docs/architecture.md) — system design and module boundaries.
- [docs/roadmap.md](docs/roadmap.md) — phased plan from design to working CLI.
- [docs/frontend.md](docs/frontend.md) — the local dashboard: architecture boundary, dev setup, limitations.
- [docs/milestone-1.md](docs/milestone-1.md) — the current milestone's scope.
- [docs/artifacts.md](docs/artifacts.md) — the artifact model: lifecycle, storage, versioning.
- [docs/skills.md](docs/skills.md) — the skill specification: manifest, execution model, protocol, project-local skills.
- [docs/pipelines.md](docs/pipelines.md) — built-in vs. project-local pipelines, manifest format, conditions.
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
├── skills/     # reusable skill definitions (review-diff, test-summary, test-report,
│               #   verify-project, release-notes, explain-project, generate-docs,
│               #   generate-diagram, dependency-audit)
├── plugins/    # optional cloud/integration plugins (later phase)
├── frontend/   # local React/Vite dashboard — talks to `buildrail serve` over HTTP only
│   └── src-tauri/  # optional minimal Tauri shell that hosts the same frontend natively
├── tests/      # test suite
├── artifacts/  # generated output (reviews, docs, test reports, etc.) — git-ignored
├── examples/   # standalone reference material not part of the app, including
│               #   project-local/ (example project-local skill + pipeline)
└── docs/       # design and planning documents
```

A project you run Buildrail *against* gets its own `.buildrail/skills/`
and `.buildrail/pipelines/` (created by `buildrail init`) — that
directory belongs to the project, not to this repository.

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
