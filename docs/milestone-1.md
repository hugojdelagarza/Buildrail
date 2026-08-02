# Milestone 1 — Single Skill, End to End

> **Status: In progress.** Repository scaffolding and the Core Engine
> skeleton are complete and committed: the CLI delegates to a
> `CoreEngine` (`src/buildrail/core`) that returns a placeholder
> `Result`. None of the business logic below — the review skill, the
> Provider Gateway, the Anthropic adapter, artifact writing — has been
> implemented yet.

> **Revision note:** this milestone was approved before
> `docs/artifacts.md`, `docs/skills.md`, `docs/provider-interface.md`,
> and `docs/testing.md` existed. It's updated here to use their
> terminology (`artifacts/`, not `reports/`) and to point at those docs
> instead of leaving their contents as open questions — the scope and
> acceptance criteria below are unchanged in substance.

## Goal

Prove the full vertical slice — CLI → Core Engine → Skill → Provider
Gateway → Artifact — with the smallest possible real feature. This is
the skeleton every later feature will reuse, so it must be built
correctly, not quickly.

No later phase (Skill Registry, Pipelines, Second AI Provider — see
`docs/roadmap.md`) starts until this milestone runs end to end and is
approved.

## Scope

**In scope:**

- A CLI entrypoint with exactly one working command, e.g.:
  `buildrail run review --diff <path>`
- One real skill: **review a diff**. Given a diff (a file path or
  stdin), produce a structured review (issues found, summary) as text.
- The Core Engine pieces needed to run *one* skill: a minimal Skill
  Registry (can hardcode the one skill for now — do not build dynamic
  discovery yet), and Run State that writes one `review` artifact per
  `docs/artifacts.md`.
- The Provider Gateway interface (`docs/provider-interface.md`), plus
  exactly **one** adapter (the Anthropic API), used by the review skill
  to produce the actual review content.
- The skill runs against the manifest and request/response contract
  defined in `docs/skills.md`. Per that doc's phasing note, the
  transport may be an in-process call for this milestone as long as it
  honors the same `SkillRequest`/`SkillResponse` JSON shapes — a real
  subprocess is not required yet.
- Config: a way to supply the API key via environment variable, and a
  minimal project config file naming which provider is active.
- Output: a `review` artifact written to `artifacts/`, plus a summary
  printed to the CLI.

**Out of scope (deliberately deferred):**

- More than one skill.
- Pipelines (multi-skill sequences).
- A second AI provider.
- Dynamic skill discovery from a `skills/` directory — Milestone 1 may
  hardcode the one skill; generalize in Phase 2 once there's a second
  real skill to design the manifest against.
- Any cloud/integration plugin (posting results anywhere).
- Non-CLI interfaces.

## Why This Slice

"Review a diff" is chosen as the first skill because:

- It's genuinely useful standalone (not a toy "hello world").
- It exercises every module in the architecture: it needs input
  handling (CLI), orchestration (Core Engine), a real skill contract
  (Skills), and an actual AI call (Provider Gateway) — nothing is
  faked or stubbed to make the slice look complete.
- It's the first capability named in the project's goals (code
  reviews), so Milestone 1's output is real progress, not throwaway
  scaffolding.

## Acceptance Criteria

1. Running the CLI command against a real diff produces a `review`
   artifact in `artifacts/` and a summary on stdout.
2. The review skill contains no reference to a specific provider SDK —
   it calls the Provider Gateway interface only.
3. The Core Engine contains no reference to the review skill's
   internals, and no reference to the Anthropic SDK.
4. With no `ANTHROPIC_API_KEY` (or equivalent) set, the CLI fails with
   a clear, specific error — it does not silently no-op or crash with
   a stack trace.
5. No network call occurs anywhere except the single call the review
   skill makes through the Provider Gateway.
6. A second engineer (or a future session) can read `src/` and
   determine the boundary between Core Engine, Skill, and Provider
   Gateway without reading this doc.

## Design Questions (Resolved Before Implementation)

The original version of this milestone left these open to be answered
during implementation. They're resolved in doc form first instead,
per `CLAUDE.md`'s documentation-first working agreement:

- Skill manifest/definition shape → `docs/skills.md` §3.
- Provider Gateway request/response shape → `docs/provider-interface.md` §2, §4.
- Artifact/report format and storage → `docs/artifacts.md` §3–4.

Implementation may still surface a real gap in one of these — if it
does, fix the doc as part of this milestone's work (per
`docs/roadmap.md`'s sequencing principles), rather than quietly
diverging from it.

## Definition of Done

- Code merged, tests covering the review skill and the Provider
  Gateway interface using the Fake Provider defined in
  `docs/testing.md` §2 — no live network calls in the default test
  suite.
- `docs/architecture.md` (and, if reality diverges from them,
  `docs/skills.md`, `docs/provider-interface.md`, or
  `docs/artifacts.md`) updated to match what was actually built.
- Demo: a real diff reviewed end to end, shown to the user.
