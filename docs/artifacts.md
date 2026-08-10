# Buildrail Artifacts

Artifacts are Buildrail's core unit of output. Every execution — a single
skill or a full pipeline — produces zero or more artifacts. This document
defines what an artifact is, how it's stored, and how it's identified,
versioned, and consumed.

This supersedes the earlier, narrower idea of a `reports/` directory
described in the first draft of `docs/architecture.md`. "Report" named
one artifact *type* (human-readable text); it was the wrong word for the
general concept. See the note at the end of this document and the
corresponding update to `docs/architecture.md`.

## 1. What an Artifact Is

An artifact is any **typed, immutable, versioned output** produced by a
single skill execution, accompanied by structured metadata that records
what produced it, from what inputs, and how it relates to other
artifacts.

An artifact always has two parts:

- **Payload** — the actual content (markdown text, JSON, a diagram
  source file, a generated source file, etc.). Format is type-specific.
- **Metadata** — a sidecar JSON document describing the payload
  (§4), so tooling can reason about an artifact without parsing its
  payload.

Known artifact types (open set — see §7):

| Type            | Payload example                              |
|-----------------|-----------------------------------------------|
| `review`        | Markdown/JSON findings from a code review      |
| `documentation` | Markdown/HTML docs for a module or project     |
| `diagram`       | Diagram *source* (Mermaid, DOT) — not a rendered image; see §7 |
| `test-report`   | Structured pass/fail/coverage summary          |
| `pipeline-log`  | Ordered record of a pipeline run's steps       |
| `metrics`       | Structured numeric measurements (JSON)         |
| `generated-file`| Any file a skill produces for the project itself (e.g. a scaffolded config) |

## 2. Lifecycle

1. **Produced** — a skill's execution completes and returns one or more
   declared outputs (per its manifest, see `docs/skills.md` §Outputs).
2. **Written** — the Core Engine's Artifact Store assigns an id, computes
   the storage path, and writes payload + metadata **atomically**: write
   to a temp file in the same run directory, then rename. A crash mid-run
   must never leave a half-written artifact that looks valid.
3. **Immutable** — once written, an artifact's payload and metadata are
   never edited in place. Re-running the same skill produces a *new*
   artifact. This is what makes reproducibility (see
   `docs/engineering-principles.md`) and safe concurrent reads possible —
   nothing else needs to worry about an artifact changing under it.
4. **Referenced** — later skills, pipeline steps, or a future UI/API can
   read a prior artifact by id (§4 `inputs`, §6 relationships).
5. **Superseded (optional)** — a later artifact can declare it supersedes
   an earlier one (§5 versioning). The earlier artifact is not deleted or
   mutated; supersession is a link, not a destructive operation.

Retention/pruning of old artifacts is **explicitly out of scope** for
now — filesystem cleanup is the developer's call until real usage shows
it's needed. Do not build a garbage collector speculatively.

## 3. Naming and Storage Layout

Artifacts are grouped by **run**, because the most common question
("what did this run produce?") should be answerable by looking at one
directory, and because pipelines (Phase 3) need to pass one step's
artifacts to the next within a run's scope.

```
artifacts/
  <run-id>/
    run.json                        # run-level manifest (see below)
    001-review-<slug>.md
    001-review-<slug>.meta.json
    002-test-report-<slug>.json
    002-test-report-<slug>.meta.json
```

- `<run-id>` — `<UTC timestamp>-<short random suffix>`, e.g.
  `20260802-143201-a1b2c3`. Timestamp gives chronological sort order for
  free in a plain directory listing; the suffix avoids collisions for
  two runs started in the same second.
- `<sequence>` — zero-padded step order within the run (`001`, `002`,
  ...), so artifacts sort in execution order alongside the timestamp.
- `<slug>` — a short, filesystem-safe label derived from the skill name
  or a skill-provided hint (e.g. the reviewed file's basename).
- `run.json` — indexes every artifact produced in the run (id, type,
  path, status) so a reader (CLI, and later a UI/API) doesn't need to
  scan the directory or parse every sidecar file just to list what a run
  produced.

**Why files-plus-JSON instead of a database:** a SQLite (or similar)
index would make cross-run queries ("find all reviews for file X across
every run") easier, but it adds a schema-migration surface, a binary
artifact that doesn't diff or grep, and a dependency Buildrail doesn't
yet need — no roadmap phase requires cross-run querying. Flat files
keep every artifact human-readable and greppable, which matches the
local-first, filesystem-is-the-database posture already established in
`docs/architecture.md` §6. If a real cross-run query need shows up
later (e.g. Phase 8 tooling), an index can be *derived* from the
existing files without changing the storage format — the files remain
the source of truth.

## 4. Metadata (Manifest) Fields

Every artifact's `.meta.json` sidecar:

```json
{
  "id": "20260802-143201-a1b2c3/001-review-diff",
  "schema_version": "1.0",
  "type": "review",
  "produced_by": { "skill": "review-diff", "version": "0.1.0" },
  "run_id": "20260802-143201-a1b2c3",
  "pipeline": null,
  "step_index": 1,
  "created_at": "2026-08-02T14:32:05Z",
  "inputs": [
    { "kind": "file", "ref": "path/to/diff.patch", "checksum": "sha256:..." }
  ],
  "content_ref": "001-review-diff.md",
  "content_type": "text/markdown",
  "checksum": "sha256:...",
  "provider_usage": {
    "provider": "anthropic",
    "model": "claude-sonnet-5",
    "input_tokens": 1820,
    "output_tokens": 640,
    "cost_estimate": { "amount": 0.014, "currency": "USD" }
  },
  "supersedes": null,
  "superseded_by": null,
  "related_artifacts": []
}
```

Field notes:

- `schema_version` — the shape of *this metadata document*. Bumped only
  when the metadata contract changes, so old artifacts stay readable by
  new tooling without a migration step.
- `inputs` — provenance: what fed this artifact, by reference and
  checksum, not by copy. Enables answering "why does this artifact look
  the way it does?" without re-running anything.
- `provider_usage` — present only if the producing skill made an AI
  call; mirrors the accounting fields defined in
  `docs/provider-interface.md`. This is how a pipeline's total token
  spend gets computed without every skill reimplementing accounting.
- `checksum` — content hash of the payload, for integrity checks and
  cheap equality comparisons (e.g. "did this re-run actually change
  anything?").
- `supersedes` / `superseded_by` — versioning links (§5).
- `related_artifacts` — any relationship that isn't provenance or
  supersession (§6).

**Implementation note:** the Artifact Store implementation
(`src/buildrail/artifacts`) writes `id`, `schema_version`, `type`,
`produced_by`, `run_id`, `pipeline`, `step_index`, `created_at`,
`content_ref`, `content_type`, `checksum`, and `provider_usage` —
`pipeline` is `null` for a single-skill run and the pipeline's name for
a named-pipeline run (`docs/roadmap.md` Phase 3). `inputs`, `supersedes`,
`superseded_by`, and `related_artifacts` are still omitted rather than
written as `null` — there is no re-run or provenance tracking yet to
populate them honestly. They're added when a concrete need exists
(re-running the same skill, cross-run references).

## 5. Versioning

Two independent versioning concepts, kept separate because they change
for different reasons:

1. **Schema version** (`schema_version` in the metadata) — versions the
   *shape* of the metadata document itself.
2. **Logical version** — Buildrail never overwrites an artifact. Running
   "generate docs for module X" twice produces two artifacts; the second
   sets `supersedes` to the first's id, and the first gets
   `superseded_by` set retroactively (the Artifact Store updates that
   one field on the prior artifact's metadata — the only metadata
   mutation permitted, and only for this pointer, never for content or
   any other field).

This append-only approach is simple, not clever: no version-numbering
scheme to design, no diffing logic to write, and it gives reproducibility
for free (every artifact a run ever produced still exists exactly as it
was produced).

## 6. Relationships Between Artifacts

Three relationship kinds, all expressed as explicit metadata fields
rather than a separate graph store:

- **Provenance** (`inputs`) — what data produced this artifact.
- **Supersession** (`supersedes` / `superseded_by`) — same logical
  artifact, later version.
- **Reference** (`related_artifacts`) — a looser link where one
  artifact's content depends on another's *meaning*, not just its raw
  bytes (e.g. a documentation artifact that discusses findings from a
  specific review artifact).

No relationship type requires a database join to resolve — every link
is a direct id reference resolvable by looking up one more `.meta.json`
file.

## 7. Open Artifact Types and Community Skills

The type list in §1 is not closed. A skill's manifest declares the
artifact type(s) it produces (`docs/skills.md`); a skill may declare a
custom type not in the core list. Consumers that don't recognize a type
must still be able to render it generically: show `content_type`,
`created_by`, and the raw payload. Buildrail must never hard-fail on an
unrecognized artifact type — only on *malformed* metadata.

`diagram` artifacts store **source**, not rendered images (e.g. Mermaid
or DOT text, not a PNG). Rendering requires an external tool
(a browser engine, Graphviz, etc.), which would violate the local-first,
zero-required-dependency core. Rendering is a future, optional concern
for a UI/API layer or an explicit "export" step — not the artifact
store's job.

## 8. How Future UI/API Layers Consume Artifacts

`docs/architecture.md` and `CLAUDE.md` both establish that any future
UI is a consumer of the same core, not a parallel implementation. For
artifacts specifically, that means the Core Engine exposes a narrow
**read** interface now, even though only the CLI calls it today:

- `list_runs(limit)` → newest-first run summaries, built from each
  run's `run.json` alone (never artifact payloads)
- `get_run(run_id)` → one run's status, created time, and every
  artifact's metadata (supersedes this section's original
  `list_artifacts(run_id)` sketch — one run's full detail is a superset
  of just its artifact list)
- `get_artifact(artifact_id)` → metadata + checksum-verified payload
- `get_relationships(artifact_id)` → provenance/supersession/related
  (not yet implemented)

This is not speculative abstraction: CLAUDE.md already commits to a
future UI/API existing, and defining this boundary now means the CLI
itself is implemented *against* this interface (`ArtifactReader`,
`src/buildrail/artifacts/reader.py`) rather than reading `artifacts/`
off disk directly — so the day a UI or API shows up, it reuses the same
functions instead of reverse-engineering the file layout. The CLI
remains the only *caller* until a second consumer is real; the
interface is just not CLI-shaped. Run and artifact ids are treated as
untrusted input: they're validated against a strict charset and the
resolved path is confirmed to stay under `artifact_root` before
anything is read.

## 9. Note on the `reports/` → `artifacts/` Rename

The original `docs/architecture.md` described a `reports/` directory
for "generated run output." That was a reasonable placeholder before
artifacts were designed in full, but it undersells the concept: a
diagram or a generated file isn't naturally a "report." `reports/` is
renamed to `artifacts/` throughout the documentation set as of this
revision; see the changelog note at the top of `docs/architecture.md`.
`docs/milestone-1.md` is updated to match so the approved milestone
doesn't reference a directory name the rest of the docs no longer use.
