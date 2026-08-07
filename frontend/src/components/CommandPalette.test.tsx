import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { CommandPalette } from './CommandPalette'

afterEach(() => {
  vi.unstubAllGlobals()
})

function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

function TestHarness({ initialOpen }: { initialOpen: boolean }) {
  const [open, setOpen] = useState(initialOpen)
  return (
    <MemoryRouter initialEntries={['/']}>
      <LocationDisplay />
      <CommandPalette open={open} onClose={() => setOpen(false)} />
    </MemoryRouter>
  )
}

describe('CommandPalette', () => {
  it('renders nothing when closed', () => {
    mockApi({ 'GET /commands': { body: { commands: [] } } })
    render(<TestHarness initialOpen={false} />)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('lists navigation entries and filters by search', async () => {
    mockApi({ 'GET /commands': { body: { commands: [] } } })
    const user = userEvent.setup()
    render(<TestHarness initialOpen={true} />)

    expect(screen.getByRole('dialog', { name: 'Command palette' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Overview/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Runs/ })).toBeInTheDocument()

    await user.type(screen.getByRole('combobox'), 'settings')

    expect(screen.getByRole('option', { name: /Settings/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /^Runs/ })).not.toBeInTheDocument()
  })

  it('navigates with the keyboard: ArrowDown then Enter', async () => {
    mockApi({ 'GET /commands': { body: { commands: [] } } })
    const user = userEvent.setup()
    render(<TestHarness initialOpen={true} />)

    const input = screen.getByRole('combobox')
    await user.click(input)
    await user.keyboard('{ArrowDown}{Enter}')

    expect(await screen.findByTestId('location')).toHaveTextContent('/runs')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes on Escape and returns focus to the previously focused element', async () => {
    mockApi({ 'GET /commands': { body: { commands: [] } } })
    const user = userEvent.setup()

    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <MemoryRouter initialEntries={['/']}>
          <button type="button" onClick={() => setOpen(true)}>
            Open palette
          </button>
          <CommandPalette open={open} onClose={() => setOpen(false)} />
        </MemoryRouter>
      )
    }
    render(<Harness />)

    const opener = screen.getByRole('button', { name: 'Open palette' })
    opener.focus()
    await user.click(opener)

    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    await user.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(opener).toHaveFocus()
  })

  it('executes a discovered command action and navigates to Runs', async () => {
    mockApi({
      'GET /commands': {
        body: {
          commands: [
            {
              id: 'verify',
              display_name: 'Verify',
              description: 'Run the local quality gate.',
              endpoint: '/commands/verify',
              method: 'POST',
              requires_provider: false,
              accepts_arguments: false,
              arguments: [],
              artifact_types: ['verification-report'],
              category: 'quality',
            },
          ],
        },
      },
      'POST /commands/verify': { body: { success: true, message: 'ok' } },
    })
    const user = userEvent.setup()
    render(<TestHarness initialOpen={true} />)

    const action = await screen.findByRole('option', { name: /Verify/ })
    await user.click(action)

    expect(await screen.findByTestId('location')).toHaveTextContent('/runs')
  })
})
