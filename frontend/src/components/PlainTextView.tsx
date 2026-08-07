import { useState } from 'react'
import shared from '../styles/shared.module.css'
import styles from './PlainTextView.module.css'

/** Plain-text/code artifact viewer: line numbers, a wrap toggle, and a copy button. */
export function PlainTextView({ content }: { content: string }) {
  const [wrap, setWrap] = useState(false)
  const lines = content.split('\n')

  async function copyContent() {
    try {
      await navigator.clipboard.writeText(content)
    } catch {
      // Clipboard access can be denied by the browser; the button simply no-ops.
    }
  }

  return (
    <div>
      <div className={styles.toolbar}>
        <label className={styles.wrapLabel}>
          <input
            type="checkbox"
            checked={wrap}
            onChange={(event) => setWrap(event.target.checked)}
          />
          Wrap lines
        </label>
        <button type="button" className={shared.button} onClick={() => void copyContent()}>
          Copy
        </button>
      </div>
      <pre className={wrap ? `${styles.code} ${styles.wrapped}` : styles.code}>
        <code>
          {lines.map((line, index) => (
            // Line order is stable for a given artifact payload; index is a safe key.
            // eslint-disable-next-line react/no-array-index-key
            <div key={index} className={styles.line}>
              <span className={styles.lineNumber}>{index + 1}</span>
              <span className={styles.lineContent}>{line}</span>
            </div>
          ))}
        </code>
      </pre>
    </div>
  )
}
