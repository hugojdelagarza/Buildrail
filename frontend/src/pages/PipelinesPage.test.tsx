import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { PipelinesPage } from './PipelinesPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const PIPELINES_BODY = {
  pipelines: [
    {
      name: 'pre-commit',
      display_name: 'Pre-Commit',
      description: 'Runs verify-project, then review-diff.',
      steps: [
        { name: 'verify-project', skippable: false, skip_condition: null },
        { name: 'review-diff', skippable: true, skip_condition: 'No diff.' },
      ],
      requires_provider: true,
      arguments: [
        { name: 'base', type: 'string', required: false, description: 'Git ref.' },
        { name: 'skip_review', type: 'boolean', required: false, description: 'Skip review.' },
      ],
    },
  ],
}

describe('PipelinesPage', () => {
  it('lists pipelines and their steps', async () => {
    mockApi({ 'GET /pipelines': { body: PIPELINES_BODY } })

    render(<PipelinesPage />, { wrapper: MemoryRouter })

    expect((await screen.findAllByText('Pre-Commit')).length).toBeGreaterThan(0)
    expect(screen.getByText('verify-project')).toBeInTheDocument()
    expect(screen.getByText('review-diff')).toBeInTheDocument()
  })

  it('executes a pipeline and shows the result', async () => {
    mockApi({
      'GET /pipelines': { body: PIPELINES_BODY },
      'POST /commands/pre-commit': {
        body: { success: true, message: 'Pipeline: pre-commit\nStatus: PASSED' },
      },
      'GET /runs': {
        body: {
          runs: [
            {
              run_id: 'r1',
              status: 'success',
              created_at: null,
              artifact_count: 1,
              artifact_types: [],
              pipeline: 'pre-commit',
            },
          ],
        },
      },
    })
    const user = userEvent.setup()

    render(<PipelinesPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('Pre-Commit')

    await user.click(screen.getByRole('button', { name: 'Run Pre-Commit' }))

    expect(await screen.findByText(/Status: PASSED/)).toBeInTheDocument()
    expect(screen.getByText('View run →')).toBeInTheDocument()
  })
})
