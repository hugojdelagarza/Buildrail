import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { RunsPage } from './RunsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('RunsPage', () => {
  it('shows an empty state with no runs', async () => {
    mockApi({ 'GET /runs': { body: { runs: [] } } })

    render(<RunsPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/No runs yet/)).toBeInTheDocument()
  })

  it('lists runs with status and pipeline', async () => {
    mockApi({
      'GET /runs': {
        body: {
          runs: [
            {
              run_id: '20260101-000000-abc',
              status: 'success',
              created_at: '2026-01-01T00:00:00Z',
              artifact_count: 2,
              artifact_types: ['review'],
              pipeline: 'pre-commit',
            },
          ],
        },
      },
    })

    render(<RunsPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('20260101-000000-abc')).toBeInTheDocument()
    expect(screen.getByText('pre-commit')).toBeInTheDocument()
    expect(screen.getByText('success')).toBeInTheDocument()
  })
})
