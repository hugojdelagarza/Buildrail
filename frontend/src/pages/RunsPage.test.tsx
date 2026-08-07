import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    expect(screen.getByRole('table')).toHaveTextContent('success')
  })

  const MIXED_RUNS = {
    runs: [
      {
        run_id: 'run-success-pre-commit',
        status: 'success',
        created_at: '2026-01-01T00:00:00Z',
        artifact_count: 3,
        artifact_types: ['review'],
        pipeline: 'pre-commit',
      },
      {
        run_id: 'run-failed-verify',
        status: 'failure',
        created_at: '2026-02-01T00:00:00Z',
        artifact_count: 1,
        artifact_types: ['verification-report'],
        pipeline: null,
      },
    ],
  }

  it('filters runs by search text', async () => {
    mockApi({ 'GET /runs': { body: MIXED_RUNS } })
    const user = userEvent.setup()
    render(<RunsPage />, { wrapper: MemoryRouter })
    await screen.findByText('run-success-pre-commit')

    await user.type(screen.getByRole('textbox', { name: 'Search runs' }), 'verify')

    expect(screen.queryByText('run-success-pre-commit')).not.toBeInTheDocument()
    expect(screen.getByText('run-failed-verify')).toBeInTheDocument()
  })

  it('filters runs by status', async () => {
    mockApi({ 'GET /runs': { body: MIXED_RUNS } })
    const user = userEvent.setup()
    render(<RunsPage />, { wrapper: MemoryRouter })
    await screen.findByText('run-success-pre-commit')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by status' }), 'failure')

    expect(screen.queryByText('run-success-pre-commit')).not.toBeInTheDocument()
    expect(screen.getByText('run-failed-verify')).toBeInTheDocument()
  })

  it('sorts runs by artifact count', async () => {
    mockApi({ 'GET /runs': { body: MIXED_RUNS } })
    const user = userEvent.setup()
    render(<RunsPage />, { wrapper: MemoryRouter })
    await screen.findByText('run-success-pre-commit')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort runs' }), 'artifacts')

    const rows = within(screen.getByRole('table')).getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('run-success-pre-commit')
    expect(rows[1]).toHaveTextContent('run-failed-verify')
  })

  it('shows a distinct empty state when filters match nothing, with a reset action', async () => {
    mockApi({ 'GET /runs': { body: MIXED_RUNS } })
    const user = userEvent.setup()
    render(<RunsPage />, { wrapper: MemoryRouter })
    await screen.findByText('run-success-pre-commit')

    await user.type(screen.getByRole('textbox', { name: 'Search runs' }), 'no-such-run')

    expect(screen.getByText('No runs match the current filters.')).toBeInTheDocument()
    expect(screen.queryByText('run-success-pre-commit')).not.toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Reset filters' })[0])

    expect(screen.getByText('run-success-pre-commit')).toBeInTheDocument()
    expect(screen.getByText('run-failed-verify')).toBeInTheDocument()
  })
})
