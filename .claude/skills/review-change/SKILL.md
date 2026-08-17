---
name: review-change
description: This skill should be used when the user asks to "review this change", "do a final review", "review-change", "check this diff before committing", or before finish-feature/commit-feature on a nontrivial change. Performs Buildrail's final engineering review of the current diff — architecture, correctness, duplication, regressions, tests, error handling, determinism, and scope creep — and reports blockers versus optional improvements without inventing nitpicks. Read-only unless explicitly asked to apply fixes.
allowed-tools: Read, Grep, Glob, Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git show*)
context: fork
agent: general-purpose
---

# Review Change

Perform Buildrail's final engineering review of the current diff (or
the scope named in `$ARGUMENTS`) before it moves to `finish-feature` /
`commit-feature`. This is a judgment pass, not a checklist to exhaust —
only report what's genuinely worth a reader's attention.

## Scope

Use `git status` / `git diff` (or the branch/scope in `$ARGUMENTS`) to
see the actual change. Review only what changed, in the context of the
surrounding code it touches — not the whole repository.

## What to evaluate

- **Architecture** — does the change respect Buildrail's layering
  (`docs/architecture.md`, `docs/project-layout.md`)? Local-first core,
  provider-agnostic, skills reusable, CLI-first.
- **Correctness** — does the logic do what it claims? Walk through the
  actual failure/edge cases, not just the happy path.
- **Unnecessary abstraction / duplication** — new interfaces, config
  flags, or generalized code introduced for a hypothetical second use
  case that doesn't exist yet (`CLAUDE.md`'s "no unnecessary
  abstraction" rule). Logic that duplicates something already in the
  codebase.
- **Compatibility/regressions** — does this change alter the public
  behavior of an existing skill/command/pipeline that's supposed to
  stay stable (e.g. `test-summary`'s output shape)?
- **Tests** — do the new/changed tests actually exercise the new
  behavior, including failure paths, not just the happy path? Is there
  a regression test for any bug fixed?
- **Error handling** — errors handled at the right boundary, not
  swallowed silently, not over-defended against scenarios that can't
  happen.
- **Determinism** — anything that should be deterministic (artifact
  content, IDs, ordering) actually is, per `docs/testing.md` §3.
- **Performance**, where relevant to the change — only flag it if the
  change plausibly affects a real workload, not speculatively.
- **Security** — flag anything security-relevant in passing, but defer
  the full audit to `buildrail-security-review` rather than duplicating
  it here.
- **Documentation** — does this change require a doc update that hasn't
  happened yet? (Defer the actual sync to `sync-docs`.)
- **Scope creep** — does the diff do more than the task actually
  required?

## Reporting

Distinguish clearly:

- **Blocker** — must be fixed before this ships.
- **Worth fixing** — a real improvement, not required.
- **Non-issue** — considered and rejected as a concern (say why,
  briefly, so it's clear it wasn't missed).

If the implementation is already good, say so plainly and stop — do not
manufacture stylistic nitpicks to seem thorough. Do not refactor for
preference alone (`CLAUDE.md` / `docs/engineering-principles.md`).

Stay read-only: report findings, don't edit code. If the invoking
request explicitly asks for fixes to be applied, apply only the
specific fixes requested, minimally, and say what changed.
