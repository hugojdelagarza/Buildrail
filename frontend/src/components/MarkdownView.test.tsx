import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
})
