---
name: finish-feature
description: This skill should be used when the user asks to "finish this feature", "wrap up this feature", "is this done", "run the completion checklist", "verify and dogfood this change", or when Claude believes an implementation is complete and ready for final verification before a commit is proposed. Runs Buildrail's backend/frontend verification, targeted dogfooding, and cleanup, then reports remaining work and a recommended commit boundary. It never commits or pushes.
---

# Finish Feature

Run Buildrail's standard feature-completion workflow: verify a change is
actually done, dogfood it, clean up, and report a commit boundary. Stop
at the boundary and wait for explicit approval before handing off to
`commit-feature` — this skill never commits or pushes.

## 1. Determine scope

Run `git status` and `git diff --stat` (and `git diff --cached --stat`
if anything is staged) to see exactly which files changed. Classify the
change: backend (`src/`, `skills/`, `tests/`), frontend (`frontend/`),
Rust/Tauri (`frontend/src-tauri/`), or docs-only — more than one
category can apply. Use the working tree as the source of truth, not
conversation memory.

## 2. Backend verification (when `src/`, `skills/`, or `tests/` changed)

Run from the repository root, using the project virtualenv
(`.venv/Scripts/python.exe` on Windows if present):

```
ruff format --check .
ruff check .
mypy
pytest
```

Run `mypy` with no path argument — `pyproject.toml`'s
`[tool.mypy] files = ["src", "tests"]` already scopes it correctly;
passing `.` explicitly widens the scope to `examples/` and produces
false "duplicate module" errors.

## 3. Frontend verification (when `frontend/` changed, excluding `src-tauri/`)

From `frontend/`:

```
npm run format:check
npm run lint
npm run typecheck
npm run test -- --run
npm run build
```

## 4. Rust/Tauri verification (only when `src-tauri/` changed AND cargo is available)

Check with `where cargo` first. If unavailable, skip it and say so
explicitly — never claim a check ran when it did not.

## 5. Dogfooding

- **CLI dogfooding** — exercise the actual `buildrail` command(s) the
  feature adds or changes, against a real or temporary project. Use
  `provider = "fake"` in a temporary `buildrail.toml`; never a real API
  key or a live Anthropic call for verification purposes.
- **Browser dogfooding** — only when frontend UI behavior changed.
  Start `buildrail serve` and `npm run dev`, then exercise the
  new/changed UI paths with the Chrome browser tools (light/dark mode,
  the empty state, the primary action, an error/service-unavailable
  state). Load the `claude-in-chrome` skill first if those tools are
  deferred.
- Prefer the Fake provider path by default in both cases. If a change
  specifically needs to prove analysis/failure behavior, use a Fake
  provider that deterministically succeeds/fails rather than a real
  request.

## 6. Cleanup

Remove every temporary artifact created for verification/dogfooding:

- Any temporary `buildrail.toml` created for dogfooding.
- Generated content under `artifacts/` beyond `.gitkeep`.
- `frontend/dist/`, stray `node_modules/`, Rust `target/`, or any other
  build output not already gitignored.
- Any background `buildrail serve` / `npm run dev` process started for
  browser dogfooding.

## 7. Final safety pass

```
git status
git diff --check
```

Scan the diff and any new files for secrets, API keys, credentials,
absolute local paths, or accidentally-tracked generated output. If
anything looks unsafe, stop and explain instead of recommending a
commit that includes it.

## 8. Report

Summarize, concisely:

- What was actually implemented — no changelog prose.
- Verification results per category actually run. State plainly when a
  category was skipped and why (e.g. "no cargo toolchain available").
- Concrete remaining limitations, if any.
- A recommended commit boundary — one coherent slice, or several if the
  diff bundles unrelated concerns (`docs/git-workflow.md` §2).
- Exact Windows CMD-compatible `git add` / `git commit` commands for the
  recommended boundary (Conventional Commits, `docs/git-workflow.md` §5).

Then say **"This is a good place to commit."** and stop. Do not run
`git add`, `git commit`, or `git push` — that is `commit-feature`'s job,
only after the user explicitly approves.
