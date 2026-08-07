import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MarkdownView } from './MarkdownView'

describe('MarkdownView', () => {
  it('renders headings and text as elements', () => {
    render(<MarkdownView content={'# Title\n\nSome **bold** text.'} />)

    expect(screen.getByRole('heading', { level: 1, name: 'Title' })).toBeInTheDocument()
    expect(screen.getByText('bold')).toBeInTheDocument()
  })

  it('does not execute raw embedded HTML/script tags', () => {
    const { container } = render(
      <MarkdownView content={'<script>window.__pwned = true</script>\n\nHello'} />,
    )

    expect(container.querySelector('script')).not.toBeInTheDocument()
    expect((window as unknown as { __pwned?: boolean }).__pwned).toBeUndefined()
  })

  it('does not render a table of contents for a single heading', () => {
    render(<MarkdownView content={'# Only One\n\nBody text.'} />)

    expect(screen.queryByRole('navigation', { name: 'Table of contents' })).not.toBeInTheDocument()
  })

  it('generates a table of contents with stable heading ids and scrolls on click', async () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const user = userEvent.setup()
    const content = '# Title\n\n## First Section\n\nText.\n\n## Second Section\n\nMore text.'

    render(<MarkdownView content={content} />)

    const toc = screen.getByRole('navigation', { name: 'Table of contents' })
    expect(toc).toBeInTheDocument()

    const firstLink = screen.getByRole('link', { name: 'First Section' })
    expect(firstLink).toHaveAttribute('href', '#first-section')
    expect(screen.getByRole('heading', { level: 2, name: 'First Section' })).toHaveAttribute(
      'id',
      'first-section',
    )

    await user.click(firstLink)
    expect(scrollIntoView).toHaveBeenCalled()
  })

  it('de-duplicates slugs for repeated heading text', () => {
    const content = '# Notes\n\n## Overview\n\nA.\n\n## Overview\n\nB.'
    render(<MarkdownView content={content} />)

    const headings = screen.getAllByRole('heading', { level: 2, name: 'Overview' })
    expect(headings[0]).toHaveAttribute('id', 'overview')
    expect(headings[1]).toHaveAttribute('id', 'overview-1')
  })
})
