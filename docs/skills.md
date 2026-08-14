# Buildrail Skill Specification

A skill is Buildrail's unit of reusable capability: "review a diff,"
"generate docs for a module," "summarize test failures." This document
is the complete contract a skill must satisfy — the interface the Core
Engine builds against, and the interface community-authored skills must
target.

`docs/milestone-1.md` left the manifest shape, execution model, and
provider-access mechanism as open questions to resolve during
implementation. This document resolves them before implementation
starts, per the working agreement in `CLAUDE.md` that structural
decisions go through docs first.

## 1. Execution Model — the Central Design Decision

This is the one place in this document where multiple real options
exist and the choice matters, so it's worth stating explicitly.

**Option A — in-process Python modules.** A skill is a Python module the
Skill Registry imports directly and calls (`run(input) -> output`).

- *Pros:* simplest possible implementation, no serialization overhead,
  trivial debugging (one stack, one process).
- *Cons:* a skill runs with the full privileges of the host process —
  filesystem, network, environment (including provider credentials) are
  all directly reachable. Only works for Python skills. Not a viable
  foundation for third-party/community skills, which the user's goals
  explicitly name as a target.

**Option B — subprocess skills with a JSON protocol over stdin/stdout.**
A skill declares an `entrypoint` command; Buildrail invokes it as a
subprocess, writes a JSON `SkillRequest` to its stdin, and reads a JSON
`SkillResponse` from its stdout.

- *Pros:* language-agnostic (a skill can be written in anything that can
  read stdin and write stdout), process-boundary crash containment, and
  — critically — the subprocess never needs direct access to provider
  credentials or Buildrail's internals (see §5). This is the only option
  that scales to untrusted, third-party skills.
- *Cons:* serialization overhead, more moving parts, requires a stable
  wire protocol that must stay backwards compatible as Buildrail evolves.

**Decision: Option B.** Community-developed skills are an explicit
requirement for this design (not a hypothetical future one), and Option
A cannot support that safely or across languages. Designing the
protocol now costs nothing extra — it's a JSON schema — while designing
for Option A first and migrating later would be a breaking change to
every skill ever written against it.

**Phasing note, so this doesn't read as overengineering for Milestone
1:** Milestone 1 has exactly one built-in, trusted, first-party skill.
Its *implementation* may run as an in-process function call for
simplicity, as long as it is built and tested against the exact same
`SkillRequest` / `SkillResponse` JSON contract defined here. Swapping
the transport from "in-process call" to "real subprocess" later is then
a Core Engine change with zero impact on the skill or the protocol —
the contract, not the transport, is the thing being designed today.

## 2. Directory Structure

```
skills/<skill-name>/
  skill.yaml           # required — manifest (§3)
  <entrypoint file>     # required — whatever `entrypoint` in skill.yaml names
  README.md             # optional — human-facing docs for the skill
  CHANGELOG.md          # optional
  tests/                # optional — the skill's own tests
  examples/             # optional — sample inputs/outputs for manual testing
```

Skill names are unique within a given search path (built-in `skills/`
vs. a project-local skill directory, once that exists in a later
phase). A project-local skill with the same name as a built-in one
overrides it, and the Core Engine logs that override explicitly — it
never silently shadows a skill.

## 3. Manifest (`skill.yaml`)

YAML, for the same reason project config is a plain file
(`docs/architecture.md` §3.5): human-writable, human-diffable, no tooling
required to inspect it.

```yaml
name: review-diff
version: 0.1.0                 # skill's own semver
protocol_version: "1.0"        # SkillRequest/SkillResponse contract version this skill targets
description: Reviews a code diff and produces a structured review artifact.
entrypoint: "python skill.py"  # any executable command; language-agnostic

inputs:
  - name: diff
    type: file                 # string | file | artifact-ref
    required: true
    description: Path to a unified diff.

outputs:
  - name: review
    artifact_type: review      # must match a type from docs/artifacts.md, or a declared custom type

requires_provider: true
provider_capabilities_required:
  - text-completion

requires_binaries: []          # external tools this skill assumes are on PATH; Buildrail checks, never installs

config:                        # optional skill-specific config schema
  - name: max_findings
    type: integer
    required: false
    default: 20

license: MIT
author: Buildrail core team
```

Required fields: `name`, `version`, `protocol_version`, `entrypoint`,
`inputs`, `outputs`. Everything else is optional with the defaults shown
above (`requires_provider: false`, empty lists) when omitted.

## 4. Inputs and Outputs

- **Inputs** are declared with `name`, `type`, `required`, and a
  description. `type` is one of `string`, `file`, or `artifact-ref` (a
  reference to a prior artifact by id, per `docs/artifacts.md`), so
  skills can compose in future pipelines without redefining what a
  "reference to a prior output" means.
- **Outputs** declare the `artifact_type` they produce. The Core Engine
  validates after execution that the skill's `SkillResponse` actually
  produced an artifact of the declared type — a mismatch is a skill
  failure (contract violation), not a warning.

## 5. The Wire Protocol and Provider Access

### 5.1 `SkillRequest` (Buildrail → skill, via stdin)

```json
{
  "protocol_version": "1.0",
  "run_context": { "run_id": "20260802-143201-a1b2c3", "step_index": 1, "workdir": "/abs/path" },
  "inputs": { "diff": "/abs/path/to/diff.patch" },
  "config": { "max_findings": 20 },
  "provider_endpoint": { "url": "http://127.0.0.1:53211", "token": "run-scoped-opaque-token" }
}
```

### 5.2 `SkillResponse` (skill → Buildrail, via stdout)

```json
{
  "status": "success",
  "outputs": { "review": { "content_ref": "review.md", "artifact_type": "review" } },
  "logs": ["fetched diff", "sent 1 request to provider"],
  "error": null
}
```

Exit code must agree with `status` (`0` for `success`, non-zero for
`failure`). Stderr is treated as diagnostic log output, not parsed for
structured data. A `SkillResponse` that fails schema validation is
treated as a skill failure — Buildrail never guesses at malformed
output.

### 5.3 Why Provider Access Is a Loopback Endpoint, Not a Credential

A skill that `requires_provider` does **not** receive an API key. It
receives a `provider_endpoint`: a URL and a short-lived, run-scoped
token for a local loopback server the Core Engine starts for the
duration of that skill's execution. The skill calls this endpoint using
the request/response shapes defined in `docs/provider-interface.md`;
the Core Engine proxies the call to whichever real provider adapter is
configured, and does token/cost accounting centrally.

This matters for two of the stated design goals at once:

- **Provider neutrality** — a skill written against this endpoint never
  imports a vendor SDK, so it works unmodified regardless of which
  provider a user has configured.
- **Security by default** — a third-party skill, which may be arbitrary
  code in an arbitrary language, never holds a real API key. The blast
  radius of a malicious or buggy community skill is bounded by what the
  loopback endpoint allows, not by what the configured provider's key
  allows.

The endpoint is loopback-only (bound to `127.0.0.1`/a local Unix socket
or named pipe) and torn down when the skill process exits — it never
becomes a standing local service. This is still "local-first": no
external network access is granted that the skill couldn't otherwise
reach anyway if the provider call is actually needed.

**What this does not solve:** a subprocess skill can still make its own
arbitrary filesystem or network calls unrelated to the provider endpoint
— true sandboxing (OS-level process restrictions) is not designed here.
This is an explicit open risk (§9), not a solved problem; it should be
addressed before community skills are distributed for wide use, not
before Milestone 1.

**Implementation note:** all built-in skills (`review-diff`,
`test-summary`, `release-notes`, `verify-project`, `explain-project`,
`generate-docs`, `generate-diagram`, `dependency-audit`) still run
in-process (§1's phasing note), so there is no subprocess boundary yet
for a loopback
endpoint to cross. `SkillRequest`/`SkillResponse` live in
`src/buildrail/skill_protocol.py`; the Provider Gateway is passed to the
skill's `run()` function as a direct second argument instead of via
`provider_endpoint`, and `SkillOutput.content` holds the produced text
directly rather than a `content_ref` file pointer, since nothing is
written to disk until the Core Engine persists it as an artifact. A
skill declaring `requires_provider: false` (e.g. `verify-project`)
receives `None` in that argument instead — the Pipeline Runner never
constructs a provider for it, so such skills genuinely never touch
`buildrail.providers`. The Skill Registry (`src/buildrail/skills`)
parses `entrypoint` only to locate the Python file to import in-process
(the last whitespace-separated token, e.g. `skill.py` from `"python
skill.py"`) — it does not yet spawn the command as a subprocess. All of
this is additive to replace, not breaking, once a real subprocess
transport is built.

## 6. Execution Lifecycle

1. Skill Registry loads `skill.yaml`, validates it against the manifest
   schema (§3), and checks `protocol_version` compatibility.
2. Caller (CLI or, later, Pipeline Runner) resolves declared inputs from
   CLI args, prior artifacts, or config.
3. Core Engine builds the `SkillRequest`; if `requires_provider`, starts
   the run-scoped loopback endpoint first.
4. Core Engine also validates, before running, that if
   `provider_capabilities_required` is set, the *configured* provider
   actually supports those capabilities (`docs/provider-interface.md`
   §Capabilities) — failing fast with a specific error rather than
   letting the skill fail deep inside a provider call.
5. Executes the skill under a timeout (config-controlled, sane default).
6. Captures stdout (`SkillResponse`), stderr (logs), and exit code.
7. Validates `SkillResponse` against schema. On failure, the skill run
   is marked failed with the validation error attached — never silently
   accepted.
8. Declared outputs are persisted via the Artifact Store
   (`docs/artifacts.md`).
9. Run State records the skill's result (status, duration, provider
   usage if any) for the run manifest.

## 7. Validation Rules

- `name`, `version` (semver), `protocol_version`, `entrypoint`, `inputs`,
  `outputs` are required; missing any of them fails registry load, not
  execution — bad skills are caught before a run starts.
- A skill declaring `requires_provider: true` is never invoked when no
  provider is configured; the Core Engine fails with a specific,
  actionable error (this is Milestone 1 acceptance criterion 4,
  generalized to all skills).
- A skill declaring `provider_capabilities_required` that the configured
  provider doesn't support fails the same way, before execution.
- Declared `outputs` must match the artifact type(s) actually produced.
- `requires_binaries` are checked on PATH before execution; a missing
  binary is reported by name, not surfaced as a generic execution
  failure.

## 8. Versioning

- `version` — the skill's own semver, independent of Buildrail's
  version. Two versions of the same skill can coexist in principle;
  only one is registered under a given name at a time in the current
  design (no side-by-side version resolution — flagged as deferred,
  not needed until a real multi-version use case exists).
- `protocol_version` — the `SkillRequest`/`SkillResponse` contract
  version the skill was built against. The Core Engine maintains
  compatibility across minor protocol revisions and refuses to run a
  skill targeting an incompatible major version, with a clear error
  naming both versions. This is the mechanism that lets community
  skills exist without upgrading in lockstep with Buildrail — an
  imminent concern the moment a skill isn't maintained by this project.
- No skill-to-skill dependency resolution (a skill declaring "requires
  skill X at version Y") exists in this design. Composite/meta-skills
  are a real future idea but not one any current roadmap phase needs;
  designing dependency resolution now would be exactly the kind of
  speculative abstraction `CLAUDE.md` rules out.

## 9. What This Enables (and Doesn't Yet) for Community Skills

The subprocess model, declarative manifest, versioned protocol, and
credential-free provider access together make it *reasonable* to accept
a third-party skill without auditing its source line by line for
credential theft. They do **not** provide full sandboxing — filesystem
and outbound-network access beyond the provider loopback are
unrestricted in this design. Treat community-skill distribution as
gated on solving that separately, not as already solved by this
document.

## 10. Project-Local Skills

A project-local skill lives at `.buildrail/skills/<name>/` — the exact
same directory structure, `skill.yaml` manifest, and
`SkillRequest`/`SkillResponse` protocol as a built-in skill (§2–§5).
**There is no second skill format.** `SkillRegistry` discovers built-in
skills (`skills/`) and, when constructed with a `project_root`,
project-local skills (`<project_root>/.buildrail/skills/`) together —
built-in directories are always searched first.

`buildrail init` scaffolds an empty `.buildrail/skills/` (and
`.buildrail/pipelines/`, see `docs/pipelines.md`) for every new project;
`buildrail init --extensions` adds it to a project that was configured
before this capability existed. `buildrail skill create <name>`
generates a minimal, valid, immediately-discoverable manifest plus a
runnable `skill.py` stub — the same scaffolding function backs both the
CLI command and the local HTTP service's `POST /skills` endpoint (which
only ever accepts structured `name`/`description`/`requires_provider`
fields, never source code, and renders the manifest with `yaml.safe_dump`
rather than string interpolation).

### 10.1 Precedence

A project-local skill sharing a built-in skill's name is a **discovery
error**, not a silent override: `SkillRegistry` raises
`DuplicateSkillError` naming both locations, and `buildrail skill list`/
`buildrail run <pipeline>` fail clearly rather than picking one
silently. Two project-local skills sharing a name are rejected the same
way. There is no override/replace semantics in this version of Buildrail
— that keeps discovery behavior safe and predictable rather than
depending on search-path ordering a reader can't see at a glance.

### 10.2 Trust

**Project-local skills execute code from the repository they're found
in.** Buildrail does not sandbox them — they run in-process with the
same privileges as any other skill (§1's phasing note still applies:
no subprocess boundary exists yet for any skill, built-in or
project-local). This is not a third-party plugin mechanism and must
never be presented as one: only use project-local skills from
repositories you trust, exactly as you would trust any other code
checked into that repository. §9's "not yet sandboxed" caveat applies
here with equal force, not less.
