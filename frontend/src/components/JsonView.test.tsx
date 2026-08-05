import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { JsonView } from './JsonView'

describe('JsonView', () => {
  it('shows a formatted view by default', () => {
    render(<JsonView raw='{"a":1}' parsed={{ a: 1 }} />)

    expect(screen.getByText(/"a": 1/)).toBeInTheDocument()
  })

  it('switches to the raw view on toggle', async () => {
    const user = userEvent.setup()
    render(<JsonView raw='{"a":1}' parsed={{ a: 1 }} />)

    await user.click(screen.getByRole('button', { name: 'Raw' }))

    expect(screen.getByText('{"a":1}')).toBeInTheDocument()
  })
})
