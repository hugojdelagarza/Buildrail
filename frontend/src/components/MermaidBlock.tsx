import { useEffect, useId, useState } from 'react'
import mermaid from 'mermaid'
import styles from './MermaidView.module.css'

let initialized = false
function ensureInitialized() {
  if (!initialized) {
    mermaid.initialize({ startOnLoad: false, securityLevel: 'strict' })
    initialized = true
  }
}

/** Renders one Mermaid diagram client-side, falling back to its source on parse failure. */
export function MermaidBlock({ code }: { code: string }) {
  const rawId = useId().replace(/:/g, '-')
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setSvg(null)
    setError(null)
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
    // Mermaid's own generated SVG (securityLevel: 'strict' escapes label text) —
    // this is the standard way to mount mermaid's output into a React tree.
    // eslint-disable-next-line react/no-danger
    <div className={styles.diagram} dangerouslySetInnerHTML={{ __html: svg }} />
  )
}
