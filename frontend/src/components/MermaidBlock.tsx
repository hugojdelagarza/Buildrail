import { useEffect, useId, useRef, useState } from 'react'
import mermaid from 'mermaid'
import styles from './MermaidView.module.css'

let initialized = false
function ensureInitialized() {
  if (!initialized) {
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' })
    initialized = true
  }
}

const MIN_SCALE = 0.25
const MAX_SCALE = 4
const ZOOM_STEP = 1.25
const FIT_PADDING = 0.95

interface DragState {
  startX: number
  startY: number
  originX: number
  originY: number
}

/** Renders one Mermaid diagram client-side, falling back to its source on parse failure. */
export function MermaidBlock({ code }: { code: string }) {
  const rawId = useId().replace(/:/g, '-')
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [scale, setScale] = useState(1)
  const [translate, setTranslate] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const dragState = useRef<DragState | null>(null)
  const viewportRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    setSvg(null)
    setError(null)
    setScale(1)
    setTranslate({ x: 0, y: 0 })
    ensureInitialized()
    mermaid
      .render(`mermaid-${rawId}`, code)
      .then((result) => {
        if (!cancelled) setSvg(result.svg)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Could not render this diagram.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [code, rawId])

  function zoomIn() {
    setScale((current) => Math.min(MAX_SCALE, current * ZOOM_STEP))
  }

  function zoomOut() {
    setScale((current) => Math.max(MIN_SCALE, current / ZOOM_STEP))
  }

  function resetView() {
    setScale(1)
    setTranslate({ x: 0, y: 0 })
  }

  function fitToView() {
    const viewport = viewportRef.current
    const svgEl = viewport?.querySelector('svg')
    if (!viewport || !svgEl) return

    let intrinsicWidth = 0
    let intrinsicHeight = 0
    const viewBox = svgEl.getAttribute('viewBox')
    if (viewBox) {
      const parts = viewBox.trim().split(/\s+/).map(Number)
      intrinsicWidth = parts[2] ?? 0
      intrinsicHeight = parts[3] ?? 0
    }
    if (!intrinsicWidth || !intrinsicHeight) {
      const rect = svgEl.getBoundingClientRect()
      intrinsicWidth = rect.width / scale
      intrinsicHeight = rect.height / scale
    }
    if (!intrinsicWidth || !intrinsicHeight) return

    const containerRect = viewport.getBoundingClientRect()
    const nextScale =
      Math.min(containerRect.width / intrinsicWidth, containerRect.height / intrinsicHeight) *
      FIT_PADDING
    setScale(Math.min(MAX_SCALE, Math.max(MIN_SCALE, nextScale)))
    setTranslate({ x: 0, y: 0 })
  }

  function onPointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (scale <= 1) return
    event.currentTarget.setPointerCapture?.(event.pointerId)
    dragState.current = {
      startX: event.clientX,
      startY: event.clientY,
      originX: translate.x,
      originY: translate.y,
    }
    setDragging(true)
  }

  function onPointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!dragState.current) return
    setTranslate({
      x: dragState.current.originX + (event.clientX - dragState.current.startX),
      y: dragState.current.originY + (event.clientY - dragState.current.startY),
    })
  }

  function onPointerUp(event: React.PointerEvent<HTMLDivElement>) {
    dragState.current = null
    setDragging(false)
    if (event.currentTarget.hasPointerCapture?.(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  if (error) {
    return (
      <div className={styles.error} role="alert">
        <p>Could not render this diagram: {error}</p>
        <pre className={styles.source}>{code}</pre>
      </div>
    )
  }
  if (!svg) {
    return <p className={styles.loading}>Rendering diagram…</p>
  }

  return (
    <div>
      <div className={styles.zoomToolbar} role="group" aria-label="Diagram zoom controls">
        <button type="button" onClick={zoomOut} aria-label="Zoom out">
          −
        </button>
        <span className={styles.zoomLevel}>{Math.round(scale * 100)}%</span>
        <button type="button" onClick={zoomIn} aria-label="Zoom in">
          +
        </button>
        <button type="button" onClick={fitToView}>
          Fit to view
        </button>
        <button type="button" onClick={resetView}>
          Reset zoom
        </button>
      </div>
      <div
        ref={viewportRef}
        className={styles.viewport}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <div
          className={styles.diagram}
          style={{
            transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
            cursor: scale > 1 ? (dragging ? 'grabbing' : 'grab') : 'default',
          }}
          // Mermaid's own generated SVG (securityLevel: 'strict' escapes label text) —
          // this is the standard way to mount mermaid's output into a React tree.
          // eslint-disable-next-line react/no-danger
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </div>
    </div>
  )
}
