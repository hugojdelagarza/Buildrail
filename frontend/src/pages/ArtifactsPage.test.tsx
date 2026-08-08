import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { ArtifactsPage } from './ArtifactsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

function artifact(overrides: Record<string, unknown>) {
  return {
    id: 'run-1/001-x',
    run_id: 'run-1',
    type: 'review',
    content_path: '/x',
    status: 'success',
    produced_by_skill: 'review-diff',
    produced_by_version: '0.1.0',
    provider_usage: null,
    pipeline: null,
    display_name: null,
    created_at: '2026-01-01T00:00:00Z',
    checksum: null,
    content_type: 'text/markdown',
    ...overrides,
  }
}

describe('ArtifactsPage', () => {
  it('shows an empty state with no artifacts', async () => {
    mockApi({ 'GET /runs': { body: { runs: [] } } })

    render(<ArtifactsPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/No artifacts yet/)).toBeInTheDocument()
  })

  it('lists artifacts from recent runs', async () => {
    mockApi({
      'GET /runs': {
        body: {
          runs: [
            {
              run_id: 'run-1',
              status: 'success',
              created_at: null,
              artifact_count: 1,
              artifact_types: ['review'],
              pipeline: null,
            },
          ],
        },
      },
      'GET /runs/run-1': {
        body: {
          run_id: 'run-1',
          status: 'success',
          created_at: null,
          pipeline: null,
          duration_seconds: null,
          pipeline_steps: [],
          artifacts: [artifact({ id: 'run-1/001-review', display_name: 'review-artifact-1' })],
          provider_usage_totals: null,
        },
      },
    })

    render(<ArtifactsPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('review-artifact-1')).toBeInTheDocument()
  })

  const RUNS_LIST = {
    runs: [
      {
        run_id: 'run-1',
        status: 'success',
        created_at: null,
        artifact_count: 2,
        artifact_types: [],
        pipeline: null,
      },
    ],
  }
  const MIXED_ARTIFACTS = {
    run_id: 'run-1',
    status: 'success',
    created_at: null,
    pipeline: null,
    duration_seconds: null,
    pipeline_steps: [],
    artifacts: [
      artifact({
        id: 'run-1/001-review',
        display_name: 'review-artifact',
        type: 'review',
        produced_by_skill: 'review-diff',
        content_type: 'text/markdown',
      }),
      artifact({
        id: 'run-1/002-verify',
        display_name: 'verify-artifact',
        type: 'verification-report',
        produced_by_skill: 'verify-project',
        content_type: 'application/json',
      }),
    ],
    provider_usage_totals: null,
  }

  it('filters artifacts by producing skill', async () => {
    mockApi({ 'GET /runs': { body: RUNS_LIST }, 'GET /runs/run-1': { body: MIXED_ARTIFACTS } })
    const user = userEvent.setup()
    render(<ArtifactsPage />, { wrapper: MemoryRouter })
    await screen.findByText('review-artifact')

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Filter by producing skill' }),
      'verify-project',
    )

    expect(screen.queryByText('review-artifact')).not.toBeInTheDocument()
    expect(screen.getByText('verify-artifact')).toBeInTheDocument()
  })

  it('sorts artifacts by name', async () => {
    mockApi({ 'GET /runs': { body: RUNS_LIST }, 'GET /runs/run-1': { body: MIXED_ARTIFACTS } })
    const user = userEvent.setup()
    render(<ArtifactsPage />, { wrapper: MemoryRouter })
    await screen.findByText('review-artifact')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort artifacts' }), 'name')

    const rows = screen.getAllByRole('row').slice(1)
    expect(rows[0]).toHaveTextContent('review-artifact')
    expect(rows[1]).toHaveTextContent('verify-artifact')
  })

  it('shows a distinct empty state when filters match nothing, with a reset action', async () => {
    mockApi({ 'GET /runs': { body: RUNS_LIST }, 'GET /runs/run-1': { body: MIXED_ARTIFACTS } })
    const user = userEvent.setup()
    render(<ArtifactsPage />, { wrapper: MemoryRouter })
    await screen.findByText('review-artifact')

    await user.type(screen.getByRole('textbox', { name: 'Search artifacts' }), 'no-such-artifact')

    expect(screen.getByText('No artifacts match the current filters.')).toBeInTheDocument()

    await user.click(screen.getAllByRole('button', { name: 'Reset filters' })[0])

    expect(screen.getByText('review-artifact')).toBeInTheDocument()
  })
})
