# Buildrail Git Workflow

This is the Git workflow Buildrail follows: when to commit, when to
push, how commits are written, how branches and tags are used, and what
a "release" means for a local-first CLI tool. `CLAUDE.md`'s "Commit
Boundaries" section is the operational summary of this document for any
AI agent working in the repository; this doc is the full policy both
humans and agents follow.

## 1. The Core Statement

**Commits are save points. Tags represent releases.**

Those are two different things with two different bars to clear. A
commit only needs to be a clean, working, self-contained step — it
doesn't need to be "done" in any larger sense. A tag means "this is a
point someone could reasonably build on or depend on." Conflating the
two — treating every commit as a mini-release, or hoarding changes
until something release-worthy accumulates — causes the two failure
modes this workflow is designed to avoid: history that's too coarse to
bisect or review, and releases that don't mean anything because
everything gets tagged.

## 2. When to Commit

Commit at every natural boundary: a self-contained, working slice of
change that leaves the repository in a clean, demonstrable state. This
mirrors `docs/engineering-principles.md` §3 (one complete vertical slice
at a time) applied to version control specifically, and it's the same
test `CLAUDE.md`'s Commit Boundaries section uses to decide when to
recommend a commit.

Concretely, a commit boundary looks like:

- A scaffolding step is done and verified (formatting, linting, type
  checking, and tests all pass).
- A documentation revision pass is complete and internally consistent.
- A bug is fixed and covered by a test that would have caught it.
- A milestone's acceptance criterion (or a clearly separable piece of
  one) is met end to end.

**Recommended frequency:** commit *often* — in practice, this usually
means several commits over the course of a single work session, one per
coherent step, not one giant commit at the end of the session and not
one commit per individual file edit. If you can't summarize a commit in
one imperative sentence without using "and" to join two unrelated
things, it's probably two commits.

Do **not** commit:

- A change that fails formatting, linting, type checking, or the test
  suite — a commit is a save point, but not a save point for broken
  state.
- Two unrelated concerns bundled together (e.g. a doc consistency pass
  and an unrelated dependency bump) — split them, even if it means two
  commits instead of one.
- Anything that hasn't been checked against the security checklist in
  §7.

## 3. When to Push

Buildrail is currently solo-developed directly on `main` while the
foundational scaffolding is being built (see §4 for when that changes).
In this phase:

- Push whenever a commit represents a complete, clean boundary (§2) —
  there's no reason to let verified, working commits sit unpushed.
  Since there's only one branch and one contributor right now, `main`
  is both the working branch and the record of progress; pushing is
  cheap and low-risk.
- Push before ending a session, so work isn't stranded on one machine.
- Never push a commit that fails the checks in §2's "do not commit"
  list — pushing doesn't get a lower bar than committing.

Once branching (§4) is in use, pushing a feature branch is unrestricted
(it's not `main`), but merging into `main` follows the same "clean,
verified state" rule, via review rather than direct push.

## 4. Branch Strategy

**Now (solo, foundational scaffolding):** commit directly to `main`.
Introducing branches and PRs for a single contributor building
sequential, approved milestone steps would be process for its own sake
— exactly what `docs/engineering-principles.md` §2 (simplicity over
cleverness) and CLAUDE.md's "no unnecessary abstraction" argue against.

**When this changes:** the moment either becomes true —

- A second contributor (human or agent working concurrently) is active, or
- A change is risky enough to want review/CI before it lands on `main`
  (e.g. anything touching the Provider Gateway or Skill Protocol
  contracts once they're implemented).

At that point, use short-lived feature branches merged via pull request:

- Naming: `<type>/<short-description>`, e.g. `feat/review-skill`,
  `fix/artifact-path-escaping`, `docs/provider-interface-clarify`.
  `<type>` matches the commit-message prefix conventions in §5.
- Keep branches short-lived — days, not weeks. A branch that's stayed
  open long enough to need repeated rebasing is a sign the underlying
  slice was too big (back to "one complete vertical slice at a time").
- Delete branches after merge. A stale branch is a save point nobody
  needs once its content is on `main`.
- `main` is always the deployable/demonstrable branch — the same
  standard §2 already holds it to.

## 5. Commit Message Style

Imperative mood, matching the two commits already on `main`
("Complete Buildrail architecture and engineering specification", "Add
initial Python project scaffolding"):

- First line: imperative, concise (aim for under ~72 characters),
  states *what* changed.
- Body (when the *why* isn't obvious from the diff or the first line):
  a sentence or two on the reasoning — a past incident, a doc this
  responds to, a tradeoff. Skip the body when the first line already
  says everything worth saying.
- Reference the relevant doc or milestone when it adds real context
  (e.g. "per docs/milestone-1.md acceptance criterion 4"), not as
  ritual on every commit.

```
Add initial Python project scaffolding

Add review skill: parse unified diff and call Provider Gateway

Fix artifact id collision when two runs start in the same second
```

Avoid: past tense ("Added...", "Fixed..."), vague summaries ("Update
files", "Fix stuff"), and commits that describe the session instead of
the change ("More work on milestone 1").

## 6. Semantic Version Tags

Buildrail is pre-1.0: version `0.MINOR.PATCH`. Tags are created only for
real, intentional release points — not every commit, not every merged
branch.

- **Tag format:** `vX.Y.Z` (e.g. `v0.1.0`).
- **Pre-1.0 convention:** SemVer formally allows anything to change at
  `0.y.z`, but Buildrail follows a tighter internal rule so version
  numbers stay meaningful: a `0.MINOR` bump marks a breaking change to
  a durable contract (Skill Protocol `protocol_version`, Provider
  Gateway request/response shape, artifact `schema_version`); a
  `PATCH` bump is everything else — fixes, additive non-breaking
  changes, docs.
- **1.0.0 is reserved:** it marks the point where the Skill Protocol and
  Artifact schema are considered stable compatibility surfaces per
  `docs/engineering-principles.md` §14 — not a calendar date, and not
  "feels done." Don't tag `1.0.0` speculatively.
- A tag is pushed explicitly (`git push origin vX.Y.Z`) — tagging
  locally and forgetting to push it defeats the point of a tag as a
  shared reference point.

## 7. Release Philosophy

A "release" for a local-first CLI tool is a tagged commit on `main`
that represents a coherent, working milestone or feature — not a
build artifact, not a hosted deployment. Releases are **milestone-driven,
not calendar-driven**: tag when a roadmap phase (`docs/roadmap.md`) or a
milestone's Definition of Done is actually met, never on a schedule
that might catch a half-finished slice mid-flight.

No automated release pipeline exists or is designed yet — that's
downstream of Phase 8 (optional cloud/integration layer) at the
earliest, and would need its own doc before implementation, per
`CLAUDE.md`'s documentation-first working agreement. For now, a release
is manual: verify the checks in §2, tag, push the tag.

## 8. Security Checklist (Applies to Every Commit)

Before any commit — not just tagged releases — check for:

- Secrets, API keys, tokens, credentials.
- Absolute local paths or machine-specific configuration.
- Virtual environments or other generated/build output.
- Anything `.gitignore` is supposed to catch but that got force-added.

This is the same checklist `CLAUDE.md`'s Commit Boundaries section
requires an AI agent to run before recommending a commit, and it holds
for human commits too.
