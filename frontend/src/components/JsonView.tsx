import { useState } from 'react'
import styles from './MermaidView.module.css'

/** Structured JSON artifact viewer: pretty-printed formatted view, plus the
 * exact raw text the server sent, unmodified. */
export function JsonView({ raw, parsed }: { raw: string; parsed: unknown }) {
  const [mode, setMode] = useState<'formatted' | 'raw'>('formatted')
  const formatted = (() => {
    try {
      return JSON.stringify(parsed, null, 2)
    } catch {
      return raw
    }
  })()

  return (
    <div>
      <div className={styles.toggle} role="group" aria-label="JSON view">
        <button
          type="button"
          className={mode === 'formatted' ? styles.active : ''}
          aria-pressed={mode === 'formatted'}
          onClick={() => setMode('formatted')}
        >
          Formatted
        </button>
        <button
          type="button"
          className={mode === 'raw' ? styles.active : ''}
          aria-pressed={mode === 'raw'}
          onClick={() => setMode('raw')}
        >
          Raw
        </button>
      </div>
      <pre className={styles.source}>{mode === 'formatted' ? formatted : raw}</pre>
    </div>
  )
}
