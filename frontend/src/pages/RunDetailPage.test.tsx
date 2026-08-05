import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { RunDetailPage } from './RunDetailPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderAt(runId: string) {
  return render(
    <MemoryRouter initialEntries={[`/runs/${runId}`]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RunDetailPage', () => {
  it('renders steps, statuses, and artifacts', async () => {
    mockApi({
      'GET /runs/20260101-000000-abc': {
        body: {
          run_id: '20260101-000000-abc',
          status: 'failure',
          created_at: '2026-01-01T00:00:00Z',
          pipeline: 'pre-commit',
          duration_seconds: 1.23,
          pipeline_steps: [
            {
              name: 'verify-project',
              status: 'failed',
              reason: 'ruff failed',
              artifact_ids: ['a'],
            },
            { name: 'review-diff', status: 'skipped', reason: null, artifact_ids: [] },
          ],
          artifacts: [
            {
              id: '20260101-000000-abc/001-verification-report-report',
              run_id: '20260101-000000-abc',
              type: 'verification-report',
              content_path: '/x',
              status: 'success',
              produced_by_skill: 'verify-project',
              produced_by_version: '0.1.0',
              provider_usage: null,
              pipeline: 'pre-commit',
              display_name: 'verification-report',
              created_at: null,
              checksum: null,
              content_type: 'text/markdown',
            },
          ],
          provider_usage_totals: null,
        },
      },
    })

    renderAt('20260101-000000-abc')

    expect(await screen.findByText('Run 20260101-000000-abc')).toBeInTheDocument()
    expect(screen.getByText('verify-project')).toBeInTheDocument()
    expect(screen.getByText('ruff failed')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'verification-report' })).toBeInTheDocument()
  })

  it('shows an error state for an unknown run', async () => {
    mockApi({
      'GET /runs/does-not-exist': { status: 404, body: { error: 'No run found.' } },
    })

    renderAt('does-not-exist')

    expect(await screen.findByText('No run found.')).toBeInTheDocument()
  })
})
