import { useCallback, useEffect, useRef, useState } from 'react'

// Fired by Settings' "Reset layout" action; every panel using this hook
// resets to its own default and forgets its stored width.
export const LAYOUT_RESET_EVENT = 'buildrail:layout-reset'

export function resetLayout() {
  window.dispatchEvent(new Event(LAYOUT_RESET_EVENT))
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function readStored(storageKey: string, fallback: number, min: number, max: number): number {
  const raw = localStorage.getItem(storageKey)
  if (raw === null) return fallback
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? clamp(parsed, min, max) : fallback
}

export interface ResizableWidthOptions {
  /** localStorage key this panel's width is persisted under. */
  storageKey: string
  defaultWidth: number
  min: number
  max: number
  /** 1 if dragging right grows the panel (handle on its right edge), -1 if
   * dragging left grows it (handle on its left edge). Defaults to 1. */
  direction?: 1 | -1
}

export interface ResizableWidth {
  width: number
  min: number
  max: number
  /** Attach to a drag handle's onPointerDown. */
  startDrag: (event: React.PointerEvent) => void
  /** Attach to a drag handle's onKeyDown for arrow-key resizing. */
  stepBy: (delta: number) => void
}

/**
 * A panel width that's draggable, keyboard-resizable, clamped to [min, max],
 * and persisted to localStorage — the one reusable primitive behind every
 * resizable panel in the app (Sidebar, artifact metadata panel).
 */
export function useResizableWidth({
  storageKey,
  defaultWidth,
  min,
  max,
  direction = 1,
}: ResizableWidthOptions): ResizableWidth {
  const [width, setWidth] = useState(() => readStored(storageKey, defaultWidth, min, max))
  const widthRef = useRef(width)
  widthRef.current = width

  useEffect(() => {
    function onReset() {
      localStorage.removeItem(storageKey)
      setWidth(defaultWidth)
    }
    window.addEventListener(LAYOUT_RESET_EVENT, onReset)
    return () => window.removeEventListener(LAYOUT_RESET_EVENT, onReset)
  }, [storageKey, defaultWidth])

  const commit = useCallback(
    (next: number) => {
      const clamped = clamp(next, min, max)
      setWidth(clamped)
      localStorage.setItem(storageKey, String(clamped))
    },
    [storageKey, min, max],
  )

  const startDrag = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      const startX = event.clientX
      const startWidth = widthRef.current

      function onMove(moveEvent: PointerEvent) {
        commit(startWidth + direction * (moveEvent.clientX - startX))
      }
      function onUp() {
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
      }
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
    },
    [commit, direction],
  )

  const stepBy = useCallback((delta: number) => commit(widthRef.current + delta), [commit])

  return { width, min, max, startDrag, stepBy }
}
