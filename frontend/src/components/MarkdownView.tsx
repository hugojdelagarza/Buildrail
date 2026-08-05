import ReactMarkdown from 'react-markdown'
import styles from './MarkdownView.module.css'

/**
 * Renders Markdown safely: react-markdown parses to a React element tree and
 * never injects raw HTML unless a rehype-raw-style plugin is added — none is
 * used here, so embedded `<script>`/`<img onerror>` etc. render as inert text.
 */
export function MarkdownView({ content }: { content: string }) {
  return (
    <div className={styles.markdown}>
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}
