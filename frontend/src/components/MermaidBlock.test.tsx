import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MermaidBlock } from './MermaidBlock'

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

async function renderBlock() {
  renderMock.mockResolvedValue({ svg: '<svg viewBox="0 0 100 100"></svg>' })
  const view = render(<MermaidBlock code="graph TD\n  a --> b" />)
  await waitFor(() => expect(view.container.querySelector('svg')).toBeInTheDocument())
  return view
}

describe('MermaidBlock', () => {
  it('shows zoom controls at 100% once rendered', async () => {
    await renderBlock()

    expect(screen.getByLabelText('Zoom in')).toBeInTheDocument()
    expect(screen.getByLabelText('Zoom out')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('zooms in and out', async () => {
    await renderBlock()

    fireEvent.click(screen.getByLabelText('Zoom in'))
    expect(screen.getByText('125%')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Zoom out'))
    fireEvent.click(screen.getByLabelText('Zoom out'))
    expect(screen.getByText('80%')).toBeInTheDocument()
  })

  it('resets zoom back to 100%', async () => {
    await renderBlock()

    fireEvent.click(screen.getByLabelText('Zoom in'))
    fireEvent.click(screen.getByRole('button', { name: 'Reset zoom' }))

    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('fits to view within the min/max zoom bounds', async () => {
    await renderBlock()

    fireEvent.click(screen.getByRole('button', { name: 'Fit to view' }))

    // jsdom reports zero-size layout boxes, so fit-to-view clamps to the minimum.
    expect(screen.getByText('25%')).toBeInTheDocument()
  })

  it('pans the diagram via pointer drag once zoomed in', async () => {
    const { container } = await renderBlock()
    fireEvent.click(screen.getByLabelText('Zoom in'))

    const viewport = container.querySelector('[class*="viewport"]') as HTMLElement
    const diagramEl = viewport.firstElementChild as HTMLElement

    fireEvent.pointerDown(viewport, { clientX: 100, clientY: 100, pointerId: 1 })
    fireEvent.pointerMove(viewport, { clientX: 130, clientY: 140, pointerId: 1 })
    fireEvent.pointerUp(viewport, { clientX: 130, clientY: 140, pointerId: 1 })

    expect(diagramEl.style.transform).toContain('translate(30px, 40px)')
  })

  it('does not pan while at the default 100% zoom', async () => {
    const { container } = await renderBlock()

    const viewport = container.querySelector('[class*="viewport"]') as HTMLElement
    const diagramEl = viewport.firstElementChild as HTMLElement

    fireEvent.pointerDown(viewport, { clientX: 100, clientY: 100, pointerId: 1 })
    fireEvent.pointerMove(viewport, { clientX: 130, clientY: 140, pointerId: 1 })
    fireEvent.pointerUp(viewport, { clientX: 130, clientY: 140, pointerId: 1 })

    expect(diagramEl.style.transform).toContain('translate(0px, 0px)')
  })
})
