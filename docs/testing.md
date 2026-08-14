# Buildrail Testing Philosophy

Buildrail's entire test suite must run locally, offline, with no
credentials, by default. This is not just a testing preference — it's
the same local-first constraint the core architecture must satisfy
(`docs/architecture.md`), applied to how the project verifies itself. A
test suite that needs network access to pass would be lying about what
"local-first" means.

## 1. Test Levels

**Unit tests** — a single function or module in isolation: manifest
schema validation, artifact id/path generation, retry backoff
calculation, error-taxonomy mapping. No filesystem, no subprocess, no
network.

**Integration tests** — real collaboration across a module boundary,
still fully local: the Skill Registry loading an actual `skill.yaml`
from a temp directory and executing it (via the Fake Provider, §2, when
`requires_provider` is set); the Artifact Store writing to a temp
`artifacts/` directory and reading it back; the Provider Gateway's retry
logic against an adapter that deterministically fails N times.

**End-to-end tests** — drive the real CLI entrypoint as a subprocess
against a temp project directory, asserting on exit code, stdout, and
the actual artifact files written. This is the test level that answers
"does `buildrail run review --diff x` actually work" — with the real
provider swapped for the Fake Provider via a test-only config/env value,
never a real API call.

## 2. Fake Provider vs. Mocked Provider

These are two different tools for two different jobs — conflating them
leads to either brittle unit tests or under-specified integration
tests.

- **Mocked provider** — a unit-test-level stand-in (a mocking library's
  double) used to assert exact request shape: "did the Gateway send
  `structured_output_schema`? Did retry logic call the adapter exactly
  3 times?" It doesn't need to behave like a real model — it needs to
  record calls and return exactly what the test tells it to.
- **Fake Provider** — a full implementation of the `docs/provider-interface.md`
  contract that behaves plausibly: deterministic canned or rule-based
  responses, realistic-shaped `usage`/`cost_estimate` fields, and the
  ability to simulate any error in §8 of that doc on demand. It does no
  network I/O, ever.

The Fake Provider does double duty, and that's a deliberate design
point, not an accident: it's both test infrastructure (used in
integration/e2e tests) **and** a documented offline developer mode
(`provider = "fake"` in `buildrail.toml`, the default `buildrail init`
writes) a contributor can run the whole system against with zero API
key. This directly reinforces the local-first principle — the "does
this run at all" question never depends on having a funded API account.

## 3. Determinism

The Fake Provider must be deterministic: the same request produces the
same response, unless a test explicitly configures it to vary (e.g.
"fail twice, then succeed," for retry tests). This matters because
artifact and pipeline tests assert on exact output — non-determinism
anywhere in that path makes tests flaky by construction, and flaky
tests get ignored, which defeats the point of having them.

Two other things in the Core Engine are non-deterministic by nature and
must be made injectable specifically *because* tests need it — not
speculatively:

- **Clock** — run ids embed a timestamp (`docs/artifacts.md` §3); tests
  need a fixed clock to assert on exact ids/paths.
- **ID generation** — the random suffix in a run id; tests need a seeded
  or fixed generator for the same reason.

This is the one place this design pass introduces an abstraction
(`Clock`, `IdGenerator`) purely for testability — justified because the
concrete need exists today, in this same document, not hypothetically.

## 4. Regression Tests

Golden-file (snapshot) tests: a fixed input (a specific diff) run
through a skill with the Fake Provider must always produce an artifact
matching a checked-in expected structure. This catches unintentional
drift in artifact shape, manifest fields, or report formatting that
unit tests focused on individual functions wouldn't catch. Golden files
live under `tests/golden/` and are updated deliberately (a reviewed
diff), never regenerated blindly.

## 5. Performance Tests

Explicitly **not** designed yet. A local CLI running one skill at a
time has no load profile worth benchmarking today — writing performance
tests now would be testing against a workload that doesn't exist. Once
Phase 3 (pipelines) introduces multi-step runs, add a lightweight
benchmark for Core Engine dispatch overhead specifically (not provider
latency, which Buildrail doesn't control and shouldn't be graded on).
This is deferred deliberately, not forgotten.

## 6. Real Adapter Conformance Is a Separate, Opt-In Suite

The real question this raises: if the default suite never calls a real
provider, how does anyone know the real Anthropic adapter actually
works? Answer: a small, separate, manually-triggered conformance suite
(e.g. tagged `@live`, or living outside the default `tests/` discovery
path) that does make real calls, requires a real key, and is never run
in CI by default or as part of `docs/milestone-1.md`'s definition of
done. Keeping this suite structurally separate — not just
"skippable" — makes it obvious to anyone reading the test tree that the
default suite's local-only guarantee isn't conditional on remembering
to pass a flag.

## 7. Directory Layout

```
tests/
  unit/
  integration/
  e2e/
  fakes/        # Fake Provider, fake skills, shared across levels
  golden/       # regression fixtures
```

Mirrors `src/` at the level each test targets (see
`docs/project-layout.md`). `tests/fakes/` is shared infrastructure, not
tied to one test level, because both integration and e2e tests need the
same Fake Provider behavior.

## 8. Rule

No test in `tests/unit`, `tests/integration`, `tests/e2e`, or
`tests/golden` may instantiate a real provider adapter or require an
environment variable holding a real credential. If a test needs that,
it belongs in the separate `@live` conformance suite (§6), full stop.

## 9. `buildrail test` — Testing as a User-Facing Feature

The sections above describe how Buildrail's own suite is tested. This
section describes `buildrail test`, the built-in workflow Buildrail
offers for testing *any* project it runs against — implemented by
`src/buildrail/testing/` and the `test-report` skill.

**Deterministic by default, AI strictly optional.** `buildrail test`
runs `pytest` as a subprocess and parses its JUnit XML output plus its
final summary line into a `TestReport` (counts, individual failures,
collection errors) — no provider call, no network, works with zero
configuration beyond a valid `buildrail.toml`. `--analyze` is additive:
it sends failing-test context to the configured provider for a
root-cause summary, but only when the run actually has failures. A
clean pass never constructs a provider, and a missing/unconfigured
provider never blocks the deterministic report — analysis degrades to
"not available," not a failed command.

**Why hybrid parsing, not a new dependency.** JUnit XML alone can't
distinguish `xfail` from `skipped`, or `xpass` from an ordinary pass, in
pytest's non-strict default mode — the schema wasn't designed for
pytest's outcome vocabulary. Rather than add `pytest-json-report` (a
new hard dependency for something achievable without one), the runner
also parses pytest's own deterministic one-line summary
(`"3 passed, 1 failed in 0.12s"`-style) and reconciles the two. This
keeps `pytest` itself as the only required test tool.

**Coverage is read, never run.** If a `coverage.xml` (Cobertura format)
already exists in the project — because the project's own test setup
produced one — `buildrail test` reads it into the report's coverage
summary. Buildrail never invokes `coverage.py` itself and never treats
its absence as an error; coverage is opportunistic, not a requirement.

**Flaky signals are conservative, not automatic reruns.** `--history`
compares the current run's failing node ids against the immediately
preceding `test-report` run (via the Artifact Store, `docs/artifacts.md`)
and flags a test that failed now but not last time as a "possible flaky
signal." This is a note for a human to investigate, not a verdict —
Buildrail never reruns tests automatically to "confirm" flakiness.

**One executor, two commands.** `test-summary` (the original, narrower
AI-summary-only command from Phase 2) and `test-report`/`buildrail test`
(Phase 7) both call the same `buildrail.testing.run_pytest` executor
rather than maintaining two independent pytest integrations.
`test-summary`'s public behavior is unchanged; only its internals were
refactored to reuse the shared runner.

**Composes into `quality-gate`.** The built-in `quality-gate` pipeline
(`docs/pipelines.md`) runs `verify-project`, then `test-report`, then
`dependency-audit` as one run — the broadest local quality check
Buildrail offers, still fully offline unless `--analyze` is requested
and a provider is configured.
