import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../../test/mockApi'
import { AppShell } from './AppShell'

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderShell(initialPath = '/') {
  mockApi({ 'GET /commands': { body: { commands: [] } } })
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<div>Overview page content</div>} />
          <Route path="runs" element={<div>Runs page content</div>} />
          <Route
            path="settings"
            element={
              <div>
                Settings page content
                <input aria-label="Free text field" />
              </div>
            }
          />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('AppShell', () => {
  it('does not render any persistent service-status indicator', () => {
    renderShell()

    expect(screen.getByText('Overview page content')).toBeInTheDocument()
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
    expect(screen.queryByText('Offline')).not.toBeInTheDocument()
    expect(screen.queryByText('Checking')).not.toBeInTheDocument()
  })

  it('opens the command palette with Ctrl+K', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.keyboard('{Control>}k{/Control}')

    expect(await screen.findByRole('dialog', { name: 'Command palette' })).toBeInTheDocument()
  })

  it('opens the command palette via the search button and closes on Escape', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.click(screen.getByRole('button', { name: /Search pages and actions/ }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('navigates with the "g then r" chord', async () => {
    const user = userEvent.setup()
    renderShell()

    await user.keyboard('gr')

    expect(await screen.findByText('Runs page content')).toBeInTheDocument()
  })

  it('does not trigger shortcuts while typing in an input', async () => {
    const user = userEvent.setup()
    renderShell('/settings')
    await screen.findByText('Settings page content')

    await user.click(screen.getByRole('textbox', { name: 'Free text field' }))
    await user.keyboard('gr')

    expect(screen.getByText('Settings page content')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
