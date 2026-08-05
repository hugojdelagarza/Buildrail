import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AppShell } from './AppShell'

describe('AppShell', () => {
  it('does not render any persistent service-status indicator', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<div>Page content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Page content')).toBeInTheDocument()
    expect(screen.queryByText('Connected')).not.toBeInTheDocument()
    expect(screen.queryByText('Offline')).not.toBeInTheDocument()
    expect(screen.queryByText('Checking')).not.toBeInTheDocument()
  })
})
