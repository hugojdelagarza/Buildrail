# Contributing to Buildrail

This document is written for both human contributors and AI agents
(Claude Code or otherwise) working in this repository. Where this file
and `CLAUDE.md` overlap, `CLAUDE.md` is the binding, enforced version
for AI agents; this file is the shared explanation of *why*, aimed at
anyone picking up the project.

## Project Philosophy

Buildrail is local-first: the core runs fully offline, AI providers are
interchangeable, skills are reusable and portable, and the CLI is the
primary interface every other consumer builds on. The full reasoning is
in `docs/engineering-principles.md` — read it before making a structural
decision that isn't obviously covered by an existing doc. In short:

- Prefer the boring, obvious implementation over a clever one.
- Build one complete, working vertical slice at a time — never a
  partial layer across the whole system.
- Don't introduce an abstraction, dependency, or directory ahead of a
  real, current need.
- Specify a contract (manifest, interface, schema) in docs before
  building against it.

## Development Workflow

1. **Read before you build.** `docs/architecture.md`, `docs/roadmap.md`,
   and the current milestone doc (`docs/milestone-1.md` right now) are
   the source of truth for what's in scope. Implementation work follows
   an approved milestone doc — it doesn't get ahead of one.
2. **Set up the environment** (Windows CMD; macOS/Linux equivalent noted):
   ```
   python -m venv .venv
   .venv\Scripts\activate.bat
   pip install -e ".[dev]"
   ```
   macOS/Linux: `source .venv/bin/activate` instead of the `.bat` line.
3. **Know where code goes.** `docs/project-layout.md` defines what each
   directory owns and, critically, what it's *forbidden* to depend on
   (e.g. only a provider adapter may import a vendor SDK). Check it
   before adding a new module, not after.
4. **Work in small, complete steps.** Finish and verify one slice (a
   scaffolding step, one skill, one bug fix) before starting the next —
   see `docs/git-workflow.md` for how this maps to commits.

## Coding Standards

- Python 3.12+, matching `pyproject.toml`'s `requires-python`.
- Formatting and linting: `ruff format .` and `ruff check .` — both must
  be clean before a commit.
- Type checking: `mypy` runs in `strict` mode; new code must satisfy it,
  not add `# type: ignore` to work around a real typing gap.
- No comments explaining *what* code does — names should already do
  that. A comment is only justified for a non-obvious *why* (a hidden
  constraint, a workaround, a subtle invariant).
- No speculative abstraction: don't add an interface, config option, or
  extension point for a second use case that doesn't exist yet.
- Follow the dependency boundaries in `docs/project-layout.md` exactly —
  they're written to be enforceable, not aspirational.

## Testing Workflow

Full philosophy in `docs/testing.md`; the short version:

- The entire test suite runs locally, offline, with no credentials.
  Nothing in `tests/unit`, `tests/integration`, `tests/e2e`, or
  `tests/golden` may instantiate a real provider adapter.
- Use the **Fake Provider** (once it exists) for integration/e2e tests
  that need provider-shaped behavior — not a mocking library standing
  in for a full implementation, and never a real API call.
- Run `pytest` before every commit. A commit that fails tests isn't a
  valid save point (`docs/git-workflow.md` §2).
- New behavior gets a test in the same commit that introduces it — not
  as a follow-up.

## Documentation Workflow

- A structural change to a contract — skill manifest, Provider Gateway
  interface, artifact schema, directory ownership — is proposed in the
  relevant doc *before* the code that implements it. This isn't
  bureaucracy for its own sake: `docs/skills.md`, `docs/artifacts.md`,
  and `docs/provider-interface.md` all exist because milestone-1 needed
  those decisions resolved before implementation could start cleanly.
- If implementation reveals a doc is wrong or incomplete, fix the doc in
  the same piece of work — don't let code and docs quietly diverge.
- Cross-reference rather than duplicate: if two docs would otherwise
  repeat the same explanation, one should own it and the other should
  link to it.

## Commit Philosophy

Full policy in `docs/git-workflow.md`. The core rule, stated there
explicitly: **commits are save points, tags represent releases.**
Commit at every clean, working boundary — don't hoard changes into one
large commit, and don't commit broken or half-finished state. Messages
follow **Conventional Commits** (`type(scope): description`) — see
`docs/git-workflow.md` §5 for the full type list, scope rules, and
examples.

## Pull Request Expectations

Buildrail is currently developed solo, directly on `main`
(`docs/git-workflow.md` §4), so this section is what applies once
branching starts — a second contributor, or a change risky enough to
want review first:

- One PR per vertical slice — the same boundary that defines a good
  commit (§ above) defines a good PR; don't bundle unrelated changes.
- A PR description states *why*, not just *what* — link the milestone
  or doc section it implements.
- Formatting, linting, type checking, and tests must all pass before
  requesting review — a PR is not a place to get CI to do that checking
  for you.
- If the change touches a documented contract, the doc update is part
  of the same PR, not a promised follow-up.

## Security Expectations

- Never commit secrets, API keys, tokens, or credentials. Configuration
  that needs a real value comes from the environment (`.env`, which is
  git-ignored) — `.env.example` documents the shape with no real
  values, and is the only one of the two ever tracked in Git.
- Never commit absolute local paths, machine-specific configuration,
  virtual environments, or generated output (`artifacts/` contents,
  caches, build directories) — `.gitignore` is authoritative on what
  stays untracked.
- Before recommending or making a commit, check the actual diff and
  file list against `docs/git-workflow.md` §8's security checklist —
  not just trust that `.gitignore` caught everything.
- If anything looks unsafe to commit, stop and say so rather than
  committing and fixing it in a follow-up — a secret in history isn't
  undone by a later commit that removes it.
