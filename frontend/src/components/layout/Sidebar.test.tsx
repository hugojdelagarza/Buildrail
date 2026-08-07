import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import { resetLayout, useResizableWidth } from '../../hooks/useResizableWidth'
import { Sidebar } from './Sidebar'

const STORAGE_KEY = 'buildrail:sidebar-width'

afterEach(() => {
  localStorage.removeItem(STORAGE_KEY)
})

function Harness() {
  const resizable = useResizableWidth({
    storageKey: STORAGE_KEY,
    defaultWidth: 200,
    min: 160,
    max: 360,
  })
  return <Sidebar resizable={resizable} />
}

describe('Sidebar', () => {
  it('resizes via the keyboard-accessible handle and persists the width', async () => {
    const user = userEvent.setup()
    render(<Harness />, { wrapper: MemoryRouter })

    const handle = screen.getByRole('slider', { name: 'Resize sidebar' })
    expect(handle).toHaveAttribute('aria-valuenow', '200')

    handle.focus()
    await user.keyboard('{ArrowRight}')

    expect(handle).toHaveAttribute('aria-valuenow', '216')
    expect(localStorage.getItem(STORAGE_KEY)).toBe('216')
  })

  it('reverts to the default width when layout is reset', async () => {
    const user = userEvent.setup()
    render(<Harness />, { wrapper: MemoryRouter })

    const handle = screen.getByRole('slider', { name: 'Resize sidebar' })
    handle.focus()
    await user.keyboard('{ArrowRight}')
    expect(handle).toHaveAttribute('aria-valuenow', '216')

    act(() => resetLayout())

    expect(handle).toHaveAttribute('aria-valuenow', '200')
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
