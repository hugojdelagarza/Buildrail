import type { ArtifactPayload } from '../api/types'
import { JsonView } from './JsonView'
import { MarkdownView } from './MarkdownView'
import { MermaidView } from './MermaidView'
import styles from './MermaidView.module.css'

/** Picks the right renderer for one artifact's payload: JSON, Mermaid
 * (diagram artifacts embed ```mermaid fences in Markdown), Markdown, or a
 * plain-text fallback for anything else. */
export function ArtifactViewer({ artifact }: { artifact: ArtifactPayload }) {
  if (artifact.content_type === 'application/json') {
    return <JsonView raw={artifact.content} parsed={artifact.content_json} />
  }
  if (artifact.type === 'diagram' || artifact.content.includes('```mermaid')) {
    return <MermaidView content={artifact.content} />
  }
  if (artifact.content_type === 'text/markdown') {
    return <MarkdownView content={artifact.content} />
  }
  return <pre className={styles.source}>{artifact.content}</pre>
}
