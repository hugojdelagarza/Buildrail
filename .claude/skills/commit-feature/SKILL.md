---
name: commit-feature
description: This skill should be used only when the user has explicitly approved committing (and, separately, pushing) a reviewed change — for example after saying "approved, commit this" or "commit and push". It performs the final safety check, stages exactly the reviewed files, commits with a Conventional Commit message, and pushes only if push was explicitly approved. It must never be invoked by Claude on its own initiative.
disable-model-invocation: true
---

# Commit Feature

Stage, commit, and — only if separately approved — push a change that
has already been reviewed and explicitly approved by the user. This
skill performs Git mutations: never run it speculatively, and never
treat its own invocation as blanket approval beyond what was actually
granted.

## 0. Confirm approval before doing anything

Before running any command, confirm from the actual conversation what
was approved:

- Was a **commit** approved? (Required to proceed at all.)
- Was a **push** separately approved? Commit approval does not imply
  push approval — check for both explicitly.
- What is the **exact intended file scope**? Use the most recently
  reviewed/recommended set (e.g. from `finish-feature`'s report), not a
  blind `git add -A` / `git add .`.

If any of this is ambiguous, stop and ask rather than guessing — this
skill exists specifically because commit/push are hard-to-reverse,
visible actions.

## 1. Pre-stage safety check

```
git status
git diff --check
```

Confirm the working tree matches the state that was actually reviewed.
If it doesn't — unexpected new changes, missing expected changes — stop
and explain what's different before proceeding.

Confirm there are no:

- Temporary config files created for dogfooding/verification (e.g. a
  scratch `buildrail.toml`).
- Generated artifacts (`artifacts/*` beyond `.gitkeep`), `dist/`,
  `node_modules/`, Rust `target/`, virtualenvs, or caches.
- `.env` files, secrets, API keys, credentials.
- Personal or machine-specific absolute paths.
- Any `~/.claude/` user-global file — only repository-local `.claude/`
  paths belong in this repo.

## 2. Stage exactly the intended files

Stage each intended file/path individually by name — never `git add -A`
or `git add .` without having just enumerated and justified every file
it would include. List the exact paths in the staging command itself so
the scope is auditable.

## 3. Review staged scope

```
git status
git diff --cached --check
git diff --cached
```

Confirm the staged diff contains only the approved change — nothing
unexpected staged, nothing expected missing. If anything unexpected is
staged, unstage it and explain rather than committing it.

## 4. Commit

Use the approved or previously-recommended Conventional Commit message
(`docs/git-workflow.md` §5: `type(scope): concise imperative
description`). On Windows CMD, use one `-m` per line — no heredocs, no
`$(...)`:

```
git commit -m "type(scope): subject" -m "Optional body sentence on why."
```

## 5. Push — only if explicitly approved

If push was **not** explicitly approved, stop after the commit and say
so plainly — do not push "since it seemed implied."

If push **was** approved:

```
git push
```

Never `--force`, never force-push to `main`, never push to a branch
other than the one actually intended.

## 6. Verify and report

```
git status
git log --oneline -10
git rev-parse HEAD
git rev-parse origin/main
```

Report: the new commit hash, whether push succeeded (or was skipped and
why), confirmation the working tree is clean, and whether HEAD matches
`origin/main`.

## Hard safety rules

- Never `git add -A` / `git add .` blindly.
- Never commit unexpected untracked files.
- Never commit secrets, credentials, or `~/.claude/` user-global files.
- Never rewrite history (`rebase`, `commit --amend`) unless explicitly
  requested.
- Never force-push.
- Never delete branches.
- Never bypass hooks (`--no-verify`) unless explicitly requested.
- Never push if approval only covered a local commit.
