import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { resetLayout, useResizableWidth } from './useResizableWidth'

const STORAGE_KEY = 'buildrail:test-panel-width'

afterEach(() => {
  localStorage.removeItem(STORAGE_KEY)
})

describe('useResizableWidth', () => {
  it('starts at the default width when nothing is stored', () => {
    const { result } = renderHook(() =>
      useResizableWidth({ storageKey: STORAGE_KEY, defaultWidth: 200, min: 100, max: 400 }),
    )

    expect(result.current.width).toBe(200)
  })

  it('reads a previously persisted width, clamped to bounds', () => {
    localStorage.setItem(STORAGE_KEY, '999')

    const { result } = renderHook(() =>
      useResizableWidth({ storageKey: STORAGE_KEY, defaultWidth: 200, min: 100, max: 400 }),
    )

    expect(result.current.width).toBe(400)
  })

  it('persists width changes made via stepBy', () => {
    const { result } = renderHook(() =>
      useResizableWidth({ storageKey: STORAGE_KEY, defaultWidth: 200, min: 100, max: 400 }),
    )

    act(() => result.current.stepBy(50))

    expect(result.current.width).toBe(250)
    expect(localStorage.getItem(STORAGE_KEY)).toBe('250')
  })

  it('clamps stepBy changes to the configured bounds', () => {
    const { result } = renderHook(() =>
      useResizableWidth({ storageKey: STORAGE_KEY, defaultWidth: 200, min: 100, max: 220 }),
    )

    act(() => result.current.stepBy(100))

    expect(result.current.width).toBe(220)
  })

  it('resets to the default width and clears storage on the reset event', () => {
    const { result } = renderHook(() =>
      useResizableWidth({ storageKey: STORAGE_KEY, defaultWidth: 200, min: 100, max: 400 }),
    )
    act(() => result.current.stepBy(50))
    expect(localStorage.getItem(STORAGE_KEY)).toBe('250')

    act(() => resetLayout())

    expect(result.current.width).toBe(200)
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull()
  })
})
