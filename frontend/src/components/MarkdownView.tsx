import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import { extractHeadings, type HeadingEntry } from '../lib/markdownHeadings'
import styles from './MarkdownView.module.css'

type HeadingTag = 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6'
type HeadingProps = React.ComponentPropsWithoutRef<'h1'> & { node?: unknown }

function createHeadingComponent(Tag: HeadingTag, getId: () => string | undefined) {
  return function HeadingComponent({ node: _node, ...rest }: HeadingProps) {
    return <Tag id={getId()} {...rest} />
  }
}

function scrollToHeading(slug: string) {
  const target = document.getElementById(slug)
  if (target && typeof target.scrollIntoView === 'function') {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function TableOfContents({ headings }: { headings: HeadingEntry[] }) {
  return (
    <nav className={styles.toc} aria-label="Table of contents">
      <p className={styles.tocTitle}>Contents</p>
      <ul className={styles.tocList}>
        {headings.map((heading) => (
          <li
            key={heading.slug}
            className={styles.tocItem}
            style={{ paddingLeft: `${(heading.level - 1) * 12}px` }}
          >
            <a
              href={`#${heading.slug}`}
              onClick={(event) => {
                event.preventDefault()
                scrollToHeading(heading.slug)
                window.history.replaceState(null, '', `#${heading.slug}`)
              }}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/**
 * Renders Markdown safely: react-markdown parses to a React element tree and
 * never injects raw HTML unless a rehype-raw-style plugin is added — none is
 * used here, so embedded `<script>`/`<img onerror>` etc. render as inert text.
 * Headings get stable slug ids and a generated table of contents links to them.
 */
export function MarkdownView({ content }: { content: string }) {
  const headings = useMemo(() => extractHeadings(content), [content])

  let headingIndex = 0
  const nextId = () => headings[headingIndex++]?.slug

  const components: Components = {
    h1: createHeadingComponent('h1', nextId),
    h2: createHeadingComponent('h2', nextId),
    h3: createHeadingComponent('h3', nextId),
    h4: createHeadingComponent('h4', nextId),
    h5: createHeadingComponent('h5', nextId),
    h6: createHeadingComponent('h6', nextId),
  }

  return (
    <div className={styles.wrapper}>
      {headings.length > 1 && <TableOfContents headings={headings} />}
      <div className={styles.markdown}>
        <ReactMarkdown components={components}>{content}</ReactMarkdown>
      </div>
    </div>
  )
}
