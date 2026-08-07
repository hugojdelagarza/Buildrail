import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { JsonView } from './JsonView'

describe('JsonView', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows a formatted, expanded tree by default', () => {
    render(<JsonView raw='{"a":1}' parsed={{ a: 1 }} />)

    expect(screen.getByText('"a"')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('collapses and re-expands the root node on click', async () => {
    const user = userEvent.setup()
    render(<JsonView raw='{"a":1}' parsed={{ a: 1 }} />)

    const toggle = screen.getByRole('button', { expanded: true })
    await user.click(toggle)
    expect(screen.queryByText('"a"')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { expanded: false }))
    expect(screen.getByText('"a"')).toBeInTheDocument()
  })

  it('renders nested containers collapsed by default, expandable on click', async () => {
    const user = userEvent.setup()
    render(<JsonView raw='{"a":{"b":1}}' parsed={{ a: { b: 1 } }} />)

    expect(screen.queryByText('"b"')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { expanded: false }))
    expect(screen.getByText('"b"')).toBeInTheDocument()
  })

  it('collapse all and expand all toggle every node', async () => {
    const user = userEvent.setup()
    render(<JsonView raw='{"a":{"b":1}}' parsed={{ a: { b: 1 } }} />)

    await user.click(screen.getByRole('button', { name: 'Collapse all' }))
    expect(screen.queryByText('"a"')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Expand all' }))
    expect(screen.getByText('"b"')).toBeInTheDocument()
  })

  it('switches to the raw view on toggle', async () => {
    const user = userEvent.setup()
    render(<JsonView raw='{"a":1}' parsed={{ a: 1 }} />)

    await user.click(screen.getByRole('button', { name: 'Raw' }))

    expect(screen.getByText('{"a":1}')).toBeInTheDocument()
  })

  it('copies the formatted JSON to the clipboard', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    // user-event installs its own navigator.clipboard stub during setup(), so
    // ours must be defined afterward to take effect.
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    render(<JsonView raw='{"a":1}' parsed={{ a: 1 }} />)

    await user.click(screen.getByRole('button', { name: 'Copy JSON' }))

    expect(writeText).toHaveBeenCalledWith(JSON.stringify({ a: 1 }, null, 2))
  })
})
