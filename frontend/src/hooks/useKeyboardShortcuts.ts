import { useEffect } from 'react'

// "G" chord targets — press G, then one of these within GO_CHORD_TIMEOUT_MS.
const GO_TARGETS: Record<string, string> = {
  o: '/',
  r: '/runs',
  a: '/artifacts',
  s: '/skills',
  p: '/pipelines',
  t: '/testing',
  i: '/project-intelligence',
  ',': '/settings',
}

const GO_CHORD_TIMEOUT_MS = 900

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || target.isContentEditable
}

export interface KeyboardShortcutsOptions {
  onOpenPalette: () => void
  onNavigate: (path: string) => void
  onRefresh: () => void
  /** While an overlay like the command palette is open, it owns key handling. */
  suspended: boolean
}

/**
 * Restrained, developer-tool-style global shortcuts: Ctrl+K / Ctrl+Shift+P
 * opens the command palette, "G" then a letter navigates, plain "R" refreshes
 * the current page. Every shortcut is a no-op while focus is inside a text
 * input, textarea, select, or contenteditable element.
 */
export function useKeyboardShortcuts({
  onOpenPalette,
  onNavigate,
  onRefresh,
  suspended,
}: KeyboardShortcutsOptions) {
  useEffect(() => {
    let pendingG = false
    let timer: ReturnType<typeof setTimeout> | null = null

    function clearPending() {
      pendingG = false
      if (timer !== null) {
        clearTimeout(timer)
        timer = null
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (suspended || isTypingTarget(event.target)) return

      const key = event.key
      const lower = key.toLowerCase()
      const isPaletteChord =
        (event.ctrlKey || event.metaKey) &&
        !event.altKey &&
        (lower === 'k' || (event.shiftKey && lower === 'p'))

      if (isPaletteChord) {
        event.preventDefault()
        clearPending()
        onOpenPalette()
        return
      }

      if (event.ctrlKey || event.metaKey || event.altKey) {
        clearPending()
        return
      }

      if (pendingG) {
        clearPending()
        const target = GO_TARGETS[lower]
        if (target) {
          event.preventDefault()
          onNavigate(target)
        }
        return
      }

      if (lower === 'g') {
        pendingG = true
        timer = setTimeout(clearPending, GO_CHORD_TIMEOUT_MS)
        return
      }

      if (lower === 'r') {
        event.preventDefault()
        onRefresh()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      clearPending()
    }
  }, [onOpenPalette, onNavigate, onRefresh, suspended])
}
