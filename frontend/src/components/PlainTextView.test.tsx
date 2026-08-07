import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PlainTextView } from './PlainTextView'

describe('PlainTextView', () => {
  it('renders each line with a line number', () => {
    render(<PlainTextView content={'first\nsecond\nthird'} />)

    expect(screen.getByText('first')).toBeInTheDocument()
    expect(screen.getByText('second')).toBeInTheDocument()
    expect(screen.getByText('third')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('toggles line wrapping', async () => {
    const user = userEvent.setup()
    const { container } = render(<PlainTextView content="one line" />)

    const checkbox = screen.getByRole('checkbox', { name: 'Wrap lines' })
    expect(checkbox).not.toBeChecked()

    await user.click(checkbox)

    expect(checkbox).toBeChecked()
    expect(container.querySelector('pre')?.className).toMatch(/wrapped/)
  })

  it('copies the raw content without line numbers', async () => {
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    render(<PlainTextView content={'line one\nline two'} />)
    await user.click(screen.getByRole('button', { name: 'Copy' }))

    expect(writeText).toHaveBeenCalledWith('line one\nline two')
  })
})
