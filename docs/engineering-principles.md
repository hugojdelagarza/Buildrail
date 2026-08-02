# Buildrail Engineering Principles

This is Buildrail's constitution: the principles every structural
decision — by a human or an AI agent — should be checked against. Each
principle below is paired with where it's actually enforced elsewhere in
the docs, because a principle nobody can point to a mechanism for is
just a slogan.

## 1. Local-first by default

Every core capability works with zero network access. Enforced by:
`docs/architecture.md`'s core/plugin split, and the Fake Provider
offline mode in `docs/testing.md` §2, which makes "run Buildrail with no
API key" a first-class, tested path rather than an afterthought.

## 2. Simplicity over cleverness

The boring, obvious implementation is preferred to a clever one.
Cleverness is a cost paid by every future reader, not just the author.
Concretely: the Provider Gateway is synchronous, not async
(`docs/provider-interface.md` §1); artifact versioning is append-only
rather than a diffing/merge scheme (`docs/artifacts.md` §5); artifact
storage is flat files, not a database (`docs/artifacts.md` §3).

## 3. One complete vertical slice at a time

No phase merges partial, unusable layers. `docs/roadmap.md` sequences
work this way explicitly; `docs/milestone-1.md` is a full CLI → Core →
Skill → Provider → Artifact slice, not a partial layer of any one of
those.

## 4. Composition over inheritance

Skills, providers, and pipelines compose through data and declared
interfaces (a manifest, a request/response schema), not class
hierarchies. A new provider is a new adapter satisfying an interface
(`docs/provider-interface.md` §11), not a subclass of some base
provider with inherited behavior to reason about.

## 5. Interfaces before implementations

The Skill Protocol (`docs/skills.md` §5) and the Provider Gateway
contract (`docs/provider-interface.md`) are fully specified before a
single concrete skill or adapter beyond Milestone 1 is built, so the
contract is shaped by what the system needs, not by one implementation's
convenience. This document set is that principle applied to itself.

## 6. Provider neutrality

No core or skill code imports a vendor SDK. Enforced structurally: only
`src/buildrail/providers/adapters/*` may import a vendor SDK, and only
the gateway's registry may import an adapter (`docs/project-layout.md`).
Skills reach a provider only through a loopback endpoint
(`docs/skills.md` §5.3) — they cannot import a vendor SDK even if they
wanted to, because they never run in the same process as one.

## 7. Determinism by default

Given the same inputs, a run produces the same artifacts. Enforced by:
immutable artifacts (`docs/artifacts.md` §2), a deterministic Fake
Provider, and injectable clock/id generation specifically because tests
need them (`docs/testing.md` §3) — determinism isn't just claimed, it's
the property the test suite is built to check.

## 8. Testability as a design constraint

If a module can't be exercised without live network access or real
credentials, its boundary is wrong. Every module has a local double: the
Fake Provider for anything provider-shaped, a temp-directory Artifact
Store for anything storage-shaped (`docs/testing.md` §1–2). This is a
constraint on design, not just a testing convenience — it's *why* the
provider loopback and the artifact read interface exist as clean
boundaries at all.

## 9. Observability

Every run produces a legible trail without needing a debugger attached:
the run manifest (`docs/artifacts.md` §3), the `pipeline-log` artifact
type, and per-artifact provenance (`docs/artifacts.md` §4 `inputs`).
Logs and artifacts are the observability surface — not print statements
that disappear when the process exits.

## 10. Reproducibility

Artifacts are immutable and carry enough metadata (skill version,
model used, inputs) to explain why an output looks the way it does,
even though a live AI provider means exact byte-for-byte reproduction
isn't guaranteed. `docs/artifacts.md` §4's `produced_by` and
`provider_usage` fields exist specifically for this — reproducibility
here means "explainable," not "bit-identical on rerun."

## 11. Security by default

Skills never hold real provider credentials — they get a run-scoped
loopback token instead (`docs/skills.md` §5.3). Secrets come only from
the environment, never from a checked-in config file
(`docs/project-layout.md`, `src/buildrail/config` rules). This principle is
explicitly **not** fully satisfied yet: subprocess skills aren't
sandboxed against arbitrary filesystem/network access beyond the
provider loopback. That gap is named, not hidden — see `docs/skills.md`
§9 and `docs/architecture.md` §6.

## 12. Documentation-first architecture

A structural change to a contract — skill manifest, provider interface,
artifact schema — is proposed in docs before code, per `CLAUDE.md`'s
working agreements. This document set is itself an instance of the
principle: every open question `docs/milestone-1.md` deferred to
implementation was resolved here first.

## 13. Minimal dependencies

Every third-party dependency is a liability: supply-chain risk, a
local-first assumption someone else's package might silently break,
upgrade churn. Adding one requires asking "can the standard library do
this" and, per `CLAUDE.md`, explicit sign-off — especially for anything
cloud-hosted. This is why artifact storage is flat files instead of a
database dependency, and why the Fake Provider — not a mocking
framework — is the backbone of `docs/testing.md`'s integration/e2e
layer.

## 14. Backwards compatibility philosophy

Pre-1.0, Buildrail may break its own contracts (manifest schema,
provider interface, artifact schema) when a real design flaw surfaces —
but only explicitly, via a version bump and a migration note in the
relevant doc, never silently. `protocol_version` in `docs/skills.md`
and `schema_version` in `docs/artifacts.md` are the mechanisms that make
"explicit break" possible instead of "quietly stops working." Post-1.0
(not yet reached), the Skill Protocol and Artifact schema become the
primary compatibility surface to protect, since community skills will
depend on them existing.

## How to Use This Document

When a design decision doesn't obviously follow from
`docs/architecture.md`, `docs/skills.md`, or `docs/provider-interface.md`,
check it against this list before improvising. If a principle here
would be violated, that's a signal to write a short doc update
explaining the tradeoff — the same way `docs/provider-interface.md` §3
and `docs/skills.md` §1 walk through the available options and state a
reasoned choice — not to silently pick whichever is more convenient in
the moment.
