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

## API URL Configuration

Set `VITE_BUILDRAIL_API_URL` (see `frontend/.env.example`) if the service
isn't on the default `http://127.0.0.1:8787` — e.g. you started it with
`buildrail serve --port 9000`. Copy `.env.example` to `.env` and edit it;
`.env` is git-ignored. Never put a real credential in either file — the
local service has no authentication and never accepts one from the
frontend.

## Supported Views

Overview, Runs (list + detail), Artifacts (Markdown/Mermaid/JSON/plain-text
viewer with a metadata panel), Skills, Pipelines (with execution forms for
`pre-commit` and `project-intelligence`), Project Intelligence (renders the
latest `architecture-summary` JSON artifact), and a read-only Settings page.
See `README.md` for the command-by-command summary.

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

## Tauri Readiness

The frontend is a static, browser-only SPA today by design: no `window.*`
Tauri APIs, no filesystem access, no assumption about how it's hosted — it
only needs a URL to reach `buildrail serve`. That means it can later be
loaded into a Tauri WebView with no rewrite: the CORS allowlist in
`src/buildrail/service/transport.py` already includes `tauri://localhost`
and `http://tauri.localhost`. Packaging a Tauri shell — and deciding whether
the shell launches `buildrail serve` itself or expects it already running —
is deliberately out of scope for this milestone; see `docs/roadmap.md`.

## Current Limitations

- Read-only: no artifact editing/deletion, no writing `buildrail.toml` from
  the UI.
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
  but is not a paginated, indefinitely-scaling view.
