#!/usr/bin/env node
// Claude Code status line — reads the officially documented stdin JSON
// (https://code.claude.com/docs/en/statusline) and prints one compact line:
// project name, git branch (with a dirty marker), model, and context-window
// usage. Only fields Claude Code actually supplies are used; nothing here
// invents token counts. No network access. The only subprocess calls are
// read-only `git` lookups scoped to the directory Claude Code reports,
// invoked via structured options (no shell string interpolation).
//
// Disable/remove: run `/statusline remove it` in Claude Code, or delete the
// "statusLine" key from this machine's ~/.claude/settings.json.

import { execFileSync } from 'node:child_process'

const GIT_TIMEOUT_MS = 200
const BAR_WIDTH = 10

let input = ''
process.stdin.setEncoding('utf8')
process.stdin.on('data', (chunk) => {
  input += chunk
})
process.stdin.on('end', () => {
  process.stdout.write(render(input))
})

function render(raw) {
  let data
  try {
    data = JSON.parse(raw)
  } catch {
    return ''
  }

  const cwd = data.workspace?.current_dir ?? data.cwd ?? process.cwd()
  const repoName = data.workspace?.repo?.name ?? baseName(cwd)
  const model = data.model?.display_name ?? data.model?.id ?? 'Claude'
  const branch = gitBranchWithDirtyMarker(cwd)

  const parts = [repoName]
  if (branch) parts.push(branch)
  parts.push(model)

  const context = contextSegment(data.context_window)
  if (context) parts.push(context)

  return parts.join('  ')
}

function baseName(path) {
  const trimmed = String(path).replace(/[\\/]+$/, '')
  const segments = trimmed.split(/[\\/]/)
  return segments[segments.length - 1] || trimmed
}

function gitBranchWithDirtyMarker(cwd) {
  const branch = runGit(cwd, ['branch', '--show-current'])
  if (!branch) return null
  const dirty = runGit(cwd, ['status', '--porcelain'])
  return dirty ? `${branch}*` : branch
}

function runGit(cwd, args) {
  try {
    return execFileSync('git', args, {
      cwd,
      stdio: ['ignore', 'pipe', 'ignore'],
      timeout: GIT_TIMEOUT_MS,
      encoding: 'utf8',
    }).trim()
  } catch {
    return null
  }
}

function contextSegment(contextWindow) {
  if (!contextWindow || typeof contextWindow.used_percentage !== 'number') return null

  const used = contextWindow.used_percentage
  const remaining = contextWindow.remaining_percentage
  const size = contextWindow.context_window_size

  let label = `Context ${renderBar(used)} ${used}% used`
  if (typeof remaining === 'number' && typeof size === 'number') {
    label += ` · ~${formatTokenCount(Math.round((size * remaining) / 100))} free`
  } else if (typeof remaining === 'number') {
    label += ` · ${remaining}% free`
  }
  return label
}

function renderBar(usedPercentage) {
  const filled = Math.max(0, Math.min(BAR_WIDTH, Math.round((usedPercentage / 100) * BAR_WIDTH)))
  return `[${'█'.repeat(filled)}${'░'.repeat(BAR_WIDTH - filled)}]`
}

function formatTokenCount(tokens) {
  return tokens >= 1000 ? `${Math.round(tokens / 1000)}k` : String(tokens)
}
