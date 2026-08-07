import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { ArtifactViewPage } from './ArtifactViewPage'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

function renderAt(artifactId: string) {
  return render(
    <MemoryRouter initialEntries={[`/artifacts/${artifactId}`]}>
      <Routes>
        <Route path="/artifacts/*" element={<ArtifactViewPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ArtifactViewPage', () => {
  it('renders a Markdown artifact', async () => {
    mockApi({
      'GET /artifacts/run-1/001-review-diff': {
        body: {
          id: 'run-1/001-review-diff',
          run_id: 'run-1',
          type: 'review',
          content_path: '/x',
          status: 'success',
          produced_by_skill: 'review-diff',
          produced_by_version: '0.1.0',
          provider_usage: null,
          pipeline: null,
          display_name: 'review',
          created_at: null,
          checksum: 'sha256:abc',
          content_type: 'text/markdown',
          content: '# Diff Review\n\nLooks good.',
          content_json: null,
        },
      },
    })

    renderAt('run-1/001-review-diff')

    expect(await screen.findByRole('heading', { name: 'Diff Review' })).toBeInTheDocument()
    expect(screen.getByText('sha256:abc')).toBeInTheDocument()
  })

  it('renders a JSON artifact using content_json', async () => {
    mockApi({
      'GET /artifacts/run-1/001-architecture-summary-analysis': {
        body: {
          id: 'run-1/001-architecture-summary-analysis',
          run_id: 'run-1',
          type: 'architecture-summary',
          content_path: '/x',
          status: 'success',
          produced_by_skill: 'explain-project',
          produced_by_version: '0.1.0',
          provider_usage: null,
          pipeline: null,
          display_name: 'project-analysis',
          created_at: null,
          checksum: null,
          content_type: 'application/json',
          content: '{"repository_name":"demo"}',
          content_json: { repository_name: 'demo' },
        },
      },
    })

    renderAt('run-1/001-architecture-summary-analysis')

    expect(await screen.findByText('"repository_name"')).toBeInTheDocument()
    expect(screen.getByText('"demo"')).toBeInTheDocument()
  })

  it('copies the artifact id and payload to the clipboard', async () => {
    mockApi({
      'GET /artifacts/run-1/001-review-diff': {
        body: {
          id: 'run-1/001-review-diff',
          run_id: 'run-1',
          type: 'review',
          content_path: '/x',
          status: 'success',
          produced_by_skill: 'review-diff',
          produced_by_version: '0.1.0',
          provider_usage: null,
          pipeline: null,
          display_name: 'review',
          created_at: null,
          checksum: 'sha256:abc',
          content_type: 'text/markdown',
          content: '# Diff Review\n\nLooks good.',
          content_json: null,
        },
      },
    })
    const user = userEvent.setup()
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })

    renderAt('run-1/001-review-diff')
    await screen.findByRole('heading', { name: 'Diff Review' })

    await user.click(screen.getByRole('button', { name: 'Copy artifact ID' }))
    expect(writeText).toHaveBeenCalledWith('run-1/001-review-diff')

    await user.click(screen.getByRole('button', { name: 'Copy payload' }))
    expect(writeText).toHaveBeenCalledWith('# Diff Review\n\nLooks good.')
  })
})
