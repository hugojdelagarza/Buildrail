import { useMemo, useState } from 'react'
import { collectContainerPaths, JsonTree } from './JsonTree'
import shared from '../styles/shared.module.css'
import styles from './MermaidView.module.css'

const ROOT_PATH = 'root'
const DEFAULT_EXPAND_DEPTH = 0

/** Structured JSON artifact viewer: a collapsible tree in "Formatted" mode,
 * plus the exact raw text the server sent, unmodified, in "Raw" mode. */
export function JsonView({ raw, parsed }: { raw: string; parsed: unknown }) {
  const [mode, setMode] = useState<'formatted' | 'raw'>('formatted')
  const [expanded, setExpanded] = useState<Set<string>>(
    () => new Set(collectContainerPaths(parsed, ROOT_PATH, DEFAULT_EXPAND_DEPTH)),
  )

  const formatted = useMemo(() => {
    try {
      return JSON.stringify(parsed, null, 2)
    } catch {
      return raw
    }
  }, [parsed, raw])

  function toggle(path: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  function expandAll() {
    setExpanded(new Set(collectContainerPaths(parsed, ROOT_PATH)))
  }

  function collapseAll() {
    setExpanded(new Set())
  }

  async function copyJson() {
    try {
      await navigator.clipboard.writeText(mode === 'raw' ? raw : formatted)
    } catch {
      // Clipboard access can be denied by the browser; the button simply no-ops.
    }
  }

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

      <div className={shared.buttonRow}>
        {mode === 'formatted' && (
          <>
            <button type="button" className={shared.button} onClick={expandAll}>
              Expand all
            </button>
            <button type="button" className={shared.button} onClick={collapseAll}>
              Collapse all
            </button>
          </>
        )}
        <button type="button" className={shared.button} onClick={() => void copyJson()}>
          Copy JSON
        </button>
      </div>

      {mode === 'formatted' ? (
        <pre className={styles.source}>
          <JsonTree value={parsed} path={ROOT_PATH} expanded={expanded} onToggle={toggle} />
        </pre>
      ) : (
        <pre className={styles.source}>{raw}</pre>
      )}
    </div>
  )
}
