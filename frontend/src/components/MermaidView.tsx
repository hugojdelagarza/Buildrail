import { useMemo, useState } from 'react'
import { MermaidBlock } from './MermaidBlock'
import styles from './MermaidView.module.css'

function extractMermaidBlocks(markdown: string): string[] {
  const blocks: string[] = []
  const pattern = /```mermaid\n([\s\S]*?)```/g
  let match = pattern.exec(markdown)
  while (match !== null) {
    blocks.push(match[1].trim())
    match = pattern.exec(markdown)
  }
  return blocks
}

/** Diagram artifacts are Markdown containing one or more fenced ```mermaid
 * blocks — this extracts and renders each one, with a source-code fallback. */
export function MermaidView({ content }: { content: string }) {
  const [mode, setMode] = useState<'rendered' | 'source'>('rendered')
  const blocks = useMemo(() => extractMermaidBlocks(content), [content])

  return (
    <div>
      <div className={styles.toggle} role="group" aria-label="Diagram view">
        <button
          type="button"
          className={mode === 'rendered' ? styles.active : ''}
          aria-pressed={mode === 'rendered'}
          onClick={() => setMode('rendered')}
        >
          Rendered
        </button>
        <button
          type="button"
          className={mode === 'source' ? styles.active : ''}
          aria-pressed={mode === 'source'}
          onClick={() => setMode('source')}
        >
          Source
        </button>
      </div>
      {mode === 'source' ? (
        <pre className={styles.source}>{content}</pre>
      ) : blocks.length === 0 ? (
        <p className={styles.empty}>No Mermaid diagrams found in this artifact.</p>
      ) : (
        <div className={styles.diagramList}>
          {blocks.map((block, index) => (
            <MermaidBlock key={index} code={block} />
          ))}
        </div>
      )}
    </div>
  )
}
