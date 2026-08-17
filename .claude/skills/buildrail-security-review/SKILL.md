---
name: buildrail-security-review
description: This skill should be used when the user asks to "run a security review", "check this diff for security issues", "security-review this change", "check for leaked secrets", or before recommending a commit that touches subprocess, file, provider, or HTTP code. Performs a Buildrail-specific, read-only security audit of the current diff against the project's actual risk surface — subprocess execution, provider calls, artifact writes, the project-local skill trust boundary, HTTP input handling — and reports blockers versus non-issues. Named "buildrail-security-review" rather than "security-review" to avoid colliding with Claude Code's own bundled security-review skill.
allowed-tools: Read, Grep, Glob, Bash(git status*), Bash(git diff*), Bash(git log*), Bash(git show*)
context: fork
agent: general-purpose
---

# Buildrail Security Review

Perform a Buildrail-specific security review of the current diff (or
the path/scope named in `$ARGUMENTS`). Stay read-only: report findings,
do not edit files. If the invoking request explicitly asks for fixes to
be applied, say that is out of scope for this skill rather than
starting to edit.

## Scope

Determine what changed with `git status` and `git diff` (or
`git diff <base>...HEAD` if a base/branch is named in `$ARGUMENTS`).
Review only what actually changed — do not audit the whole repository
unless explicitly asked to.

## What to check

Only report on items genuinely relevant to what changed. This is
Buildrail's actual risk surface — do not turn this into generic
security theater beyond it:

**Subprocess and command execution**
- `shell=True` anywhere.
- Subprocess calls built from string concatenation/interpolation
  instead of a fixed argument list.
- Any path where user-controlled or frontend-controlled input could
  reach a shell command.

**File and path safety**
- Path traversal in artifact IDs, run IDs, or any user-supplied path
  segment.
- Symlink/path-escape behavior in the Artifact Store/Reader.
- Non-atomic writes where a partial write would corrupt an artifact or
  config file.

**Secrets and credentials**
- API keys, tokens, or credentials hardcoded, logged, or persisted into
  an artifact.
- `.env` values leaking into git-tracked files or artifacts.
- Absolute local/machine-specific paths in tracked files.
- Environment-variable dumps captured into output.

**Provider Gateway boundary**
- Unbounded context sent to a provider (compare against `test-report`'s
  failure cap as the existing pattern).
- Any code path that could make a live provider call as a side effect
  of verification/testing rather than a genuine user action.
- `analyze`/`--enhance`-style flags actually gating the provider call,
  not merely labeling output.

**Frontend → backend surface**
- Any new HTTP endpoint or command descriptor accepting a raw command
  string, arbitrary file path, or unvalidated shell-adjacent input from
  the frontend.
- Missing input validation on new `/commands/*` or REST routes.

**Project-local skill/pipeline trust boundary**
- New code that blurs the documented trust boundary (`docs/skills.md`
  §10) — project-local skills are trusted repository code, not
  sandboxed; don't introduce anything implying otherwise.
- Built-in vs. project-local name collisions silently allowed instead
  of failing discovery.

**Repository hygiene**
- Generated artifacts, `node_modules/`, `dist/`, Rust `target/`,
  virtualenvs, or caches accidentally staged/tracked.
- Any `~/.claude/` user-global file (settings, statusline, credentials)
  appearing in a repo-local diff — this must never happen; repository
  skills belong under `.claude/skills/` only.

## Reporting

For each finding, state:

- **Severity** — blocker / worth fixing / known limitation / non-issue.
- **Location** — file and line.
- **Why it matters**, concretely — not generic security boilerplate.

If nothing genuinely relevant was found, say so plainly rather than
manufacturing findings. A clean review is a valid, useful result.
