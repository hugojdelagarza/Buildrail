import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { PipelinesPage } from './PipelinesPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const PRE_COMMIT = {
  name: 'pre-commit',
  version: '0.1.0',
  display_name: 'Pre-Commit',
  description: 'Runs verify-project, then review-diff.',
  source: 'built-in',
  execution_kind: 'code',
  project_relative_path: null,
  steps: [
    { name: 'verify-project', skippable: false, skip_condition: null, inputs: {} },
    { name: 'review-diff', skippable: true, skip_condition: 'No diff.', inputs: {} },
  ],
  requires_provider: true,
  arguments: [
    { name: 'base', type: 'string', required: false, description: 'Git ref.' },
    { name: 'skip_review', type: 'boolean', required: false, description: 'Skip review.' },
  ],
}

const QUALITY = {
  name: 'quality',
  version: '0.1.0',
  display_name: 'quality',
  description: 'Project-local Buildrail pipeline',
  source: 'project-local',
  execution_kind: 'declarative',
  project_relative_path: '.buildrail/pipelines/quality.yaml',
  steps: [{ name: 'verify-project', skippable: false, skip_condition: null, inputs: {} }],
  requires_provider: false,
  arguments: [],
}

const PIPELINES_BODY = { pipelines: [PRE_COMMIT, QUALITY] }

describe('PipelinesPage', () => {
  it('lists pipelines and their steps', async () => {
    mockApi({ 'GET /pipelines': { body: PIPELINES_BODY } })

    render(<PipelinesPage />, { wrapper: MemoryRouter })

    expect((await screen.findAllByText('Pre-Commit')).length).toBeGreaterThan(0)
    expect(screen.getByText('verify-project')).toBeInTheDocument()
    expect(screen.getByText('review-diff')).toBeInTheDocument()
    expect(screen.getAllByText('quality').length).toBeGreaterThan(0)
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
              pipeline_source: 'built-in',
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

  it('runs a project-local pipeline through the same generic command endpoint', async () => {
    mockApi({
      'GET /pipelines': { body: PIPELINES_BODY },
      'POST /commands/quality': {
        body: { success: true, message: 'Pipeline: quality\nStatus: PASSED' },
      },
      'GET /runs': {
        body: {
          runs: [
            {
              run_id: 'r2',
              status: 'success',
              created_at: null,
              artifact_count: 1,
              artifact_types: [],
              pipeline: 'quality',
              pipeline_source: 'project-local',
            },
          ],
        },
      },
    })
    const user = userEvent.setup()

    render(<PipelinesPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('Pre-Commit')
    await user.click(screen.getAllByText('quality')[0])

    await user.click(screen.getByRole('button', { name: 'Run quality' }))

    expect(await screen.findByText(/Status: PASSED/)).toBeInTheDocument()
  })

  it('filters pipelines by source', async () => {
    mockApi({ 'GET /pipelines': { body: PIPELINES_BODY } })
    const user = userEvent.setup()

    render(<PipelinesPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('Pre-Commit')

    await user.click(screen.getByRole('button', { name: 'Project' }))

    expect(screen.getAllByText('quality').length).toBeGreaterThan(0)
    expect(screen.queryByText('Pre-Commit')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Built-in' }))

    expect(screen.queryByText('quality')).not.toBeInTheDocument()
    expect(screen.getAllByText('Pre-Commit').length).toBeGreaterThan(0)
  })

  it('shows the project-relative path for a project-local pipeline', async () => {
    mockApi({ 'GET /pipelines': { body: PIPELINES_BODY } })
    const user = userEvent.setup()

    render(<PipelinesPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('Pre-Commit')

    await user.click(screen.getAllByText('quality')[0])

    expect(screen.getByText('.buildrail/pipelines/quality.yaml')).toBeInTheDocument()
  })

  it('creates a project-local pipeline and shows the generated path', async () => {
    mockApi({
      'GET /pipelines': { body: PIPELINES_BODY },
      'GET /skills': {
        body: {
          skills: [
            {
              name: 'verify-project',
              version: '0.1.0',
              protocol_version: '1.0',
              description: 'x',
              requires_provider: false,
              source: 'built-in',
              project_relative_path: null,
              inputs: [],
              outputs: [],
            },
          ],
        },
      },
      'POST /pipelines': {
        body: {
          name: 'review-flow',
          project_relative_path: '.buildrail/pipelines/review-flow.yaml',
        },
      },
    })
    const user = userEvent.setup()

    render(<PipelinesPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('Pre-Commit')

    await user.click(screen.getByRole('button', { name: 'New Pipeline' }))
    await user.type(screen.getByLabelText('Name'), 'review-flow')
    await user.click(screen.getByRole('button', { name: 'Create Pipeline' }))

    await waitFor(() => {
      expect(
        screen.getByText(/Created at \.buildrail\/pipelines\/review-flow\.yaml/),
      ).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
  })

  it('allows adding and removing steps in the New Pipeline form', async () => {
    mockApi({
      'GET /pipelines': { body: PIPELINES_BODY },
      'GET /skills': {
        body: {
          skills: [
            {
              name: 'verify-project',
              version: '0.1.0',
              protocol_version: '1.0',
              description: 'x',
              requires_provider: false,
              source: 'built-in',
              project_relative_path: null,
              inputs: [],
              outputs: [],
            },
            {
              name: 'review-diff',
              version: '0.1.0',
              protocol_version: '1.0',
              description: 'x',
              requires_provider: true,
              source: 'built-in',
              project_relative_path: null,
              inputs: [],
              outputs: [],
            },
          ],
        },
      },
    })
    const user = userEvent.setup()

    render(<PipelinesPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('Pre-Commit')
    await user.click(screen.getByRole('button', { name: 'New Pipeline' }))
    await screen.findByLabelText('Step 1 skill')

    await user.click(screen.getByRole('button', { name: 'Add step' }))

    expect(screen.getByLabelText('Step 2 skill')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove step 2' }))

    expect(screen.queryByLabelText('Step 2 skill')).not.toBeInTheDocument()
  })

  it('closes the New Pipeline modal on cancel without creating anything', async () => {
    mockApi({
      'GET /pipelines': { body: PIPELINES_BODY },
      'GET /skills': { body: { skills: [] } },
    })
    const user = userEvent.setup()

    render(<PipelinesPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('Pre-Commit')
    await user.click(screen.getByRole('button', { name: 'New Pipeline' }))

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
  })
})
