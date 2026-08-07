# Claude Code status line example

A compact, one-line Claude Code status line showing the project name, git
branch (with a dirty-tree marker), model, and context-window usage:

```
Buildrail  main*  Sonnet 5  Context [████░░░░░░] 38% used · ~124k free
```

This is a **Claude Code developer-experience setup**, not part of the
Buildrail application. It's included here only as a repository-safe,
reusable template — Claude Code status lines are configured per-machine in
your user-level `~/.claude/settings.json`, never inside a project repo, so
nothing here is loaded or run automatically.

## What data it uses

`statusline.mjs` reads only the fields Claude Code's status-line feature
[officially documents on stdin](https://code.claude.com/docs/en/statusline):
`workspace.current_dir`, `workspace.repo.name`, `model.display_name`, and
`context_window.{used_percentage,remaining_percentage,context_window_size}`.
It does not scrape `/context` output, read Claude Code's session transcript,
or invent numbers that aren't supplied. If `context_window` data isn't
present yet (e.g. before the first message in a session), that segment is
simply omitted rather than shown as zero or guessed.

**Known limitation:** Claude Code does not expose an exact "remaining
tokens" field. The "~124k free" figure above is computed from two fields it
*does* expose (`context_window_size × remaining_percentage`), so it's an
approximation, not a value read directly off the wire — shown with a `~` to
say so.

The only subprocess calls are read-only `git branch --show-current` and
`git status --porcelain`, scoped to the directory Claude Code reports, each
with a 200ms timeout and no shell string interpolation. No network requests
are made.

## Setup

1. Copy the script to your user-level Claude Code directory:

   ```
   cp statusline.mjs ~/.claude/statusline.mjs
   ```

2. Add a `statusLine` entry to your user-level `~/.claude/settings.json`
   (create the file if it doesn't exist yet):

   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "node ~/.claude/statusline.mjs"
     }
   }
   ```

   On Windows, Claude Code runs status-line commands through Git Bash (if
   installed) or PowerShell otherwise; `~` is expanded to your home
   directory either way, so this same command works unmodified on
   Windows, macOS, and Linux as long as `node` and `git` are on `PATH`.

3. Start a new Claude Code session (or resume one) — the status line
   appears automatically.

Alternatively, run `/statusline show project, branch, model, and context
usage` inside Claude Code and let it generate and wire up an equivalent
script for you, then compare against this one.

## Testing it standalone

Before wiring it into `settings.json`, you can feed it mock input directly:

```
echo '{"model":{"display_name":"Sonnet 5"},"workspace":{"current_dir":"."},"context_window":{"used_percentage":38,"remaining_percentage":62,"context_window_size":200000}}' | node statusline.mjs
```

## Disabling or removing it

- Run `/statusline remove it` in any Claude Code session, or
- Delete the `"statusLine"` key from `~/.claude/settings.json`, or
- Delete `~/.claude/statusline.mjs` entirely.

None of these affect the Buildrail repository or any other project.
