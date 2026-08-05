import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { OverviewPage } from './OverviewPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const PROJECT_BODY = {
  service_version: '0.1.0',
  project_root: '/home/dev/project',
  config_status: 'ok',
  artifact_root: 'artifacts',
  provider: 'fake',
  provider_ready: true,
  skill_count: 7,
  pipeline_count: 2,
  recent_run_count: 3,
  latest_run: {
    run_id: 'r1',
    status: 'success',
    created_at: null,
    artifact_count: 1,
    artifact_types: [],
    pipeline: null,
  },
  statistics: null,
}

describe('OverviewPage', () => {
  it('shows a loading state before data arrives', () => {
    mockApi({ 'GET /project': { body: PROJECT_BODY } })

    render(<OverviewPage />, { wrapper: MemoryRouter })

    expect(screen.getByText(/Connecting to the Buildrail service/)).toBeInTheDocument()
  })

  it('renders project info once loaded', async () => {
    mockApi({ 'GET /project': { body: PROJECT_BODY } })

    render(<OverviewPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('/home/dev/project')).toBeInTheDocument()
    expect(screen.getByText('fake')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('shows a service-unavailable state when the service cannot be reached', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('fetch failed'))),
    )

    render(<OverviewPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/Service unavailable/)).toBeInTheDocument()
  })

  it('runs a command and shows the success result', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'POST /commands/verify': { body: { success: true, message: 'Verification PASSED' } },
      'GET /runs': {
        body: {
          runs: [
            {
              run_id: 'new-run',
              status: 'success',
              created_at: null,
              artifact_count: 1,
              artifact_types: [],
              pipeline: null,
            },
          ],
        },
      },
    })
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await screen.findByText('/home/dev/project')

    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByText('Verification PASSED')).toBeInTheDocument()
    expect(screen.getByText('View run →')).toBeInTheDocument()
  })

  it('shows a failure result without crashing when a command fails', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'POST /commands/verify': { body: { success: false, message: 'Verification FAILED' } },
      'GET /runs': { body: { runs: [] } },
    })
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await screen.findByText('/home/dev/project')

    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByText('Verification FAILED')).toBeInTheDocument()
  })

  it('disables actions while a command is running', async () => {
    let resolveVerify: (() => void) | undefined
    const verifyGate = new Promise<void>((resolve) => {
      resolveVerify = resolve
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        const method = (init?.method ?? 'GET').toUpperCase()
        if (method === 'GET' && url.endsWith('/project')) {
          return new Response(JSON.stringify(PROJECT_BODY), { status: 200 })
        }
        if (method === 'POST' && url.endsWith('/commands/verify')) {
          await verifyGate
          return new Response(JSON.stringify({ success: true, message: 'ok' }), { status: 200 })
        }
        return new Response(JSON.stringify({ runs: [] }), { status: 200 })
      }),
    )
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await screen.findByText('/home/dev/project')

    await user.click(screen.getByRole('button', { name: 'Verify' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Explain' })).toBeDisabled()
    })

    resolveVerify?.()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Explain' })).not.toBeDisabled()
    })
  })
})
