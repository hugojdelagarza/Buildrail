import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MermaidView } from './MermaidView'

const renderMock = vi.fn()

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: (...args: unknown[]) => renderMock(...args),
  },
}))

afterEach(() => {
  renderMock.mockReset()
})

const CONTENT = '# Diagrams\n\n```mermaid\ngraph TD\n  a --> b\n```\n'

describe('MermaidView', () => {
  it('renders a diagram block as SVG on success', async () => {
    renderMock.mockResolvedValue({ svg: '<svg data-testid="rendered-svg"></svg>' })

    const { container } = render(<MermaidView content={CONTENT} />)

    await waitFor(() => expect(container.querySelector('svg')).toBeInTheDocument())
  })

  it('falls back to the diagram source when rendering fails', async () => {
    renderMock.mockRejectedValue(new Error('Parse error on line 1'))

    render(<MermaidView content={CONTENT} />)

    expect(await screen.findByText(/Could not render this diagram/)).toBeInTheDocument()
    expect(screen.getByText(/graph TD/)).toBeInTheDocument()
  })

  it('shows the raw source when the Source toggle is selected', async () => {
    renderMock.mockResolvedValue({ svg: '<svg></svg>' })
    const user = userEvent.setup()
    render(<MermaidView content={CONTENT} />)

    await user.click(screen.getByRole('button', { name: 'Source' }))

    expect(screen.getByText(/```mermaid/)).toBeInTheDocument()
  })

  it('shows an empty message when no mermaid blocks are found', () => {
    render(<MermaidView content="# No diagrams here" />)

    expect(screen.getByText(/No Mermaid diagrams found/)).toBeInTheDocument()
  })
})
