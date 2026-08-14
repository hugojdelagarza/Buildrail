# Buildrail Frontend

A browser-based local dashboard for Buildrail, under `frontend/`. It is a
plain client-side React app — no server-side rendering, no bundled backend —
that talks to a locally running `buildrail serve` over HTTP.

## Architecture Boundary

```
frontend/ (React + Vite, runs in a browser)
        │  HTTP (JSON, localhost only)
        ▼
buildrail serve (src/buildrail/service/)
        │  in-process calls
        ▼
CoreEngine, ArtifactReader, SkillRegistry, PipelineRunner
```

The frontend **never** talks to `CoreEngine`, `ArtifactReader`, or the
filesystem directly — it only calls the HTTP endpoints `buildrail serve`
exposes, through the single typed client in `frontend/src/api/client.ts`. No
component performs a raw `fetch`. No frontend code parses CLI output; every
view is built from structured JSON responses (see
`src/buildrail/service/routes.py`).

The service itself never wraps responses in a `{ data: ... }` envelope —
introducing one now would have meant rewriting every existing, already-tested
endpoint response shape for no functional gain. Instead, response-shape
normalization (and the one `ApiError` type every failure surfaces as) lives
entirely in the frontend's API client, so the rest of the app only ever
depends on one consistent contract regardless of what the wire shape looked
like.

## Development

```
# terminal 1 — from the repository root, with a configured buildrail.toml
buildrail serve

# terminal 2
cd frontend
npm install
npm run dev
```

The dev server prints a local URL (typically `http://localhost:5173`). The
Buildrail service must already be running — the Overview page's "Service
unavailable" state explains how to start it if it isn't.

Other scripts: `npm run format` / `format:check` (Prettier), `npm run lint`
(oxlint), `npm run typecheck` (`tsc -b`), `npm test` (Vitest), `npm run
build` (production build to `frontend/dist/`, git-ignored).

### Desktop Shell (Tauri)

`frontend/src-tauri/` is a minimal Tauri 2 shell that hosts this same React
app in a native window — it is a **display host only**: no Buildrail
business logic lives in Rust, `CoreEngine`/providers/skills/pipelines/the
HTTP service are not reimplemented or ported, and **Python remains
Buildrail's runtime**. The desktop shell is optional; the frontend works
identically in a plain browser with or without it.

```
# terminal 1 — same as browser development
buildrail serve

# terminal 2
cd frontend
npm run tauri:dev
```

`npm run tauri:dev` starts the Vite dev server itself (via `beforeDevCommand`
in `tauri.conf.json`) and opens it in a native window. `npm run tauri:build`
compiles a release binary. Both require a Rust toolchain (`rustc`/`cargo`,
installed via [rustup](https://rustup.rs/)) plus, on Windows, the Visual
Studio Build Tools "Desktop development with C++" workload and the WebView2
Runtime (usually already present on Windows 10/11) — none of this is
required for ordinary browser development.

The desktop shell **does not start, stop, or manage `buildrail serve`** —
you run it exactly as you would for browser development, in a separate
terminal. If it isn't running, the desktop window shows the same
"Service unavailable" state as the browser (see Current Limitations below).

Capabilities are intentionally minimal: no filesystem, shell, or dialog
plugins are enabled, and the window's Content-Security-Policy only permits
connecting to `localhost`/`127.0.0.1` (any port, so `VITE_BUILDRAIL_API_URL`
still works) plus the app's own bundled assets. The WebView's native `fetch`
reaches the Buildrail service directly — no Tauri HTTP plugin is needed.

## API URL Configuration

Set `VITE_BUILDRAIL_API_URL` (see `frontend/.env.example`) if the service
isn't on the default `http://127.0.0.1:8787` — e.g. you started it with
`buildrail serve --port 9000`. Copy `.env.example` to `.env` and edit it;
`.env` is git-ignored. Never put a real credential in either file — the
local service has no authentication and never accepts one from the
frontend.

## Supported Views

Overview, Runs (list + detail, with client-side search/filter/sort), Artifacts
(list with client-side search/filter/sort; a Markdown/Mermaid/JSON/plain-text
viewer with a resizable metadata panel), Skills (built-in and project-local,
with a source filter and a "New Skill" form), Pipelines (built-in and
project-local, with a source filter, execution forms for `pre-commit` and
`project-intelligence`, a generic "Run" for any project-local pipeline, and a
"New Pipeline" form with an ordered, reorderable skill/condition step list),
Project Intelligence (renders the latest `architecture-summary` JSON artifact,
plus an independent Dependency Audit section rendering the latest
`dependency-audit` JSON artifact — dependency counts, possible
declaration/import mismatches, local/VCS/URL dependencies, and warnings, with
no security-alert styling since it is a declaration audit, not a
vulnerability scanner), and a Settings page (read-only project/config info, a
"Project Extensions" built-in-vs-project-local skill/pipeline count, a
keyboard-shortcuts reference, and a reset-layout action). See `README.md` for
the command-by-command summary and `docs/skills.md`/`docs/pipelines.md` for
what a project-local skill/pipeline actually is.

### Creating Project-Local Skills and Pipelines

The "New Skill" and "New Pipeline" forms on the Skills and Pipelines pages
call `POST /skills` and `POST /pipelines` — the exact same narrowly-scoped
scaffolding functions `buildrail skill create`/`buildrail pipeline create`
use (`buildrail.skills.scaffold`/`buildrail.pipeline.scaffold`). Neither
endpoint accepts source code, a file path, or raw YAML: a skill request is
just `name`/`description`/`requires_provider`; a pipeline request is
`name`/`description`/an ordered list of `{skill, condition}` steps, rendered
into YAML server-side with `yaml.safe_dump`. There is no code editor and no
YAML editor in the frontend — creation is scaffold-only, matching the CLI.

## Keyboard Shortcuts & Command Palette

`Ctrl+K` or `Ctrl+Shift+P` opens a command palette (searchable, arrow keys to
move, Enter to run, Escape to close, focus returns to whatever triggered it)
listing every page plus every action `GET /commands` describes — the palette
never hardcodes a command's behavior separately from that endpoint, it just
calls `POST /commands/{id}` the same way the Overview and Pipelines pages do.
Page navigation entries are the one thing kept local to the frontend, since
routes aren't part of the backend's contract.

`G` then a letter navigates (`O` Overview, `R` Runs, `A` Artifacts, `S`
Skills, `P` Pipelines, `I` Project Intelligence, `,` Settings); plain `R`
refreshes whatever the current page last loaded. Every shortcut is a no-op
while focus is inside a text input, textarea, select, or contenteditable
element, so they never interfere with typing. The full list is also always
visible on the Settings page.

Refreshing "the current page" works without a global data-fetching layer:
each page registers its own `useAsync` `reload` with a small context
(`useRegisterRefresh`/`useTriggerRefresh` in
`src/hooks/useRefreshRegistry.tsx`), and the shortcut/palette action just
calls whatever the mounted page most recently registered.

## Layout

The sidebar and the artifact-view metadata panel are resizable by dragging
their edge, or via the keyboard when the divider is focused (arrow keys).
Both widths persist to `localStorage` per browser profile
(`src/hooks/useResizableWidth.ts`) and collapse to a stacked, full-width
layout under the existing 720px narrow-window breakpoint, where they aren't
resizable. Settings has a "Reset layout" action that broadcasts one event;
every mounted resizable panel listens for it and reverts to its default width
and clears its own stored value — there's no central layout registry to keep
in sync.

## Data Reuse, Not Reimplementation

- Diagram artifacts are Markdown containing fenced ` ```mermaid ` blocks;
  the frontend extracts and renders them client-side (with a raw-source
  fallback on parse failure) rather than asking the backend for a second,
  diagram-only format.
- JSON artifacts (e.g. explain-project's `ProjectAnalysis` sidecar) are
  returned pre-parsed as `content_json` alongside the raw `content` string,
  so the Project Intelligence page never parses Markdown to recover
  structured data.
- The "suggested reading order" section only exists in the generated
  Markdown summary (it's a rendering choice of the `explain-project` skill,
  not a `ProjectAnalysis` field) — the Project Intelligence page embeds that
  Markdown directly for this section instead of inventing a JSON-only
  substitute.
- The Dependency Audit section looks up its own latest run by
  `dependency-audit` artifact type, independently of the `architecture-summary`
  lookup above — `dependency-audit` is a standalone command, not a
  project-intelligence pipeline step, so the section renders whether or not a
  project-intelligence run exists.

## Tauri Shell Internals

The frontend itself stays a static, browser-only SPA: no `window.*` Tauri
APIs are used in ordinary rendering paths, and it only needs a URL to reach
`buildrail serve`. The one exception is `SettingsPage`, which calls
`@tauri-apps/api/core`'s `isTauri()` to show one static, non-badge sentence
explaining the desktop shell's connection model (see Current Limitations) —
`isTauri()` returns `false` harmlessly in a plain browser, so this is the
only frontend code that's aware the desktop shell exists at all.

The CORS allowlist in `src/buildrail/service/transport.py` already includes
`tauri://localhost` and `http://tauri.localhost`, which is what let this
shell be added without any backend change. Packaging Python as a Tauri
sidecar, auto-starting `buildrail serve`, and producing signed installers
are all deliberately out of scope for this slice; see `docs/roadmap.md`.

## Current Limitations

- Read-only: no artifact editing/deletion, no writing `buildrail.toml` from
  the UI.
- Project-local skills and pipelines can only be created from the frontend,
  not deleted, updated, or edited — matching the CLI and service, which have
  no delete/update endpoints yet either (`docs/pipelines.md`, `docs/skills.md`
  §10). Remove or edit them directly under `.buildrail/` in the meantime.
- No live updates — every view fetches on load/navigation; there is no
  polling, WebSocket, or background refresh. Use a page's own re-run/reload
  action to see new data.
- No advisory cost estimate is shown in the artifact metadata panel yet —
  `provider_usage` records tokens and model, but per-artifact cost
  estimation was intentionally not threaded through `SkillOutput` in this
  milestone to avoid an unnecessary protocol change; the UI omits that row
  when it's absent rather than fabricating a value.
- The Artifacts page scans the 20 most recent runs to build its list (no
  dedicated "all artifacts" backend endpoint exists); this is fine locally
  but is not a paginated, indefinitely-scaling view. Search/filter/sort on
  both the Runs and Artifacts pages operate entirely on that already-fetched
  page of data — there's no backend search or indexing, so filters only see
  what's already loaded.
- The Runs page has no provider/model filter: `RunSummary` doesn't carry
  that field (only per-artifact `provider_usage` does), and fetching every
  run's detail just to populate a filter would defeat the point of the
  lightweight `/runs` list.
- Desktop shell: `buildrail serve` must be started independently — the
  window does not launch, monitor, or stop it, and there is no persistent
  connection-status indicator in either the browser or the desktop shell.
  When the service is unreachable, the desktop window shows the same
  Overview "Service unavailable" message as the browser. Python packaging
  (bundling the service as a Tauri sidecar) and installers/auto-update are
  not implemented — see `docs/roadmap.md`.
- The Tauri shell was scaffolded and its config validated with the Tauri
  CLI, but this development environment has no Rust toolchain installed, so
  `cargo check`/`cargo fmt`/`cargo clippy`/`npm run tauri:dev`/`npm run
  tauri:build` have not actually been run. `frontend/src-tauri/Cargo.lock`
  does not exist yet — it needs to be generated by running `cargo build`
  once on a machine with Rust installed, then committed.
