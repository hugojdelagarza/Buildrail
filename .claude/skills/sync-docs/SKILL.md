---
name: sync-docs
description: This skill should be used when the user asks to "sync the docs", "update the documentation for this", "check the docs are still accurate", "sync-docs", or after a feature changes something a doc describes (a command, a skill, a pipeline, a roadmap phase, an architecture boundary). Audits only the documentation plausibly affected by the current diff against the actual implementation, fixes stale claims, and never marks a roadmap phase complete unless the implementation genuinely fulfills it.
context: fork
agent: general-purpose
---

# Sync Docs

Audit and correct Buildrail's documentation against the actual
implementation, scoped to what the current change plausibly affects —
not a full-repository documentation pass on every invocation.

## 1. Determine scope

Look at `git diff --stat` (or the scope named in `$ARGUMENTS`) to see
what changed, then decide which docs are plausibly affected. Do not
read every doc on every invocation — pick from this list based on what
the diff actually touches:

- `CLAUDE.md` — durable project context (skill/pipeline lists, project
  status line).
- `README.md` — Status banner, command examples, Project Layout,
  Documentation links.
- `docs/roadmap.md` — phase status.
- `docs/architecture.md` — module boundaries (only if a boundary
  actually moved).
- `docs/project-layout.md` — directory ownership (only if directories
  changed).
- `docs/provider-interface.md` — only if the Provider Gateway contract
  changed.
- `docs/skills.md` — built-in skill list/behavior.
- `docs/pipelines.md` — built-in/project-local pipeline behavior.
- `docs/artifacts.md` — only if the artifact model changed.
- `docs/testing.md` — only if the testing workflow/philosophy changed.
- `docs/frontend.md` — Supported Views, keyboard shortcuts, limitations.
- `docs/git-workflow.md` — only if the Git workflow itself changed.
- The relevant milestone doc, if one is active.

## 2. Check for staleness

For each doc plausibly affected, check for:

- Stale "not implemented" / "not started" claims for something now
  shipped.
- Stale skill/pipeline/command counts or name lists.
- Stale roadmap phase status — **never mark a phase complete unless the
  implementation genuinely fulfills its stated scope**; when unsure,
  say so instead of guessing.
- Stale architecture text/diagrams that no longer match module
  boundaries.
- Stale provider-behavior, testing-capability, or frontend-capability
  claims.
- Documentation that **overstates** functionality (claims something
  works that doesn't) as well as documentation that **understates** it
  (still says "not yet" for something already shipped) — both are bugs
  worth fixing.

## 3. Fix, don't narrate

Where a doc is genuinely stale, edit it directly and concisely,
matching the existing style and section structure of that doc. Do not
turn any doc into a changelog — state the current fact, not the history
of how it got that way. Keep edits proportional: a one-line count fix
doesn't need a new section; a new capability needs an actual paragraph
in the doc's existing pattern.

## 4. Report

List which docs were checked, which were edited and why, and which were
checked and found already accurate — say so explicitly; a doc needing
no change is a valid, common outcome. Do not commit — that belongs to
`commit-feature`.
