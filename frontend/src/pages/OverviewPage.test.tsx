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

const CONFIG_BODY_OK = {
  status: 'ok',
  configured: true,
  provider: 'fake',
  anthropic_model: null,
  artifact_root: 'artifacts',
  credential_available: true,
  error: null,
}

const CONFIG_BODY_MISSING = {
  status: 'missing',
  configured: false,
  provider: null,
  anthropic_model: null,
  artifact_root: null,
  credential_available: false,
  error: null,
}

const CONFIG_BODY_INVALID = {
  status: 'invalid',
  configured: false,
  provider: null,
  anthropic_model: null,
  artifact_root: null,
  credential_available: false,
  error: "buildrail.toml: unsupported provider 'openai'.",
}

describe('OverviewPage', () => {
  it('shows a loading state before data arrives', () => {
    mockApi({ 'GET /project': { body: PROJECT_BODY }, 'GET /config': { body: CONFIG_BODY_OK } })

    render(<OverviewPage />, { wrapper: MemoryRouter })

    expect(screen.getByText(/Connecting to the Buildrail service/)).toBeInTheDocument()
  })

  it('renders project info once loaded', async () => {
    mockApi({ 'GET /project': { body: PROJECT_BODY }, 'GET /config': { body: CONFIG_BODY_OK } })

    render(<OverviewPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('Project: project')).toBeInTheDocument()
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
      'GET /config': { body: CONFIG_BODY_OK },
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
    await screen.findByText('Project: project')

    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(await screen.findByText('Verification PASSED')).toBeInTheDocument()
    expect(screen.getByText('View run →')).toBeInTheDocument()
  })

  it('shows a failure result without crashing when a command fails', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'GET /config': { body: CONFIG_BODY_OK },
      'POST /commands/verify': { body: { success: false, message: 'Verification FAILED' } },
      'GET /runs': { body: { runs: [] } },
    })
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await screen.findByText('Project: project')

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
        if (method === 'GET' && url.endsWith('/config')) {
          return new Response(JSON.stringify(CONFIG_BODY_OK), { status: 200 })
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
    await screen.findByText('Project: project')

    await user.click(screen.getByRole('button', { name: 'Verify' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Explain' })).toBeDisabled()
    })

    resolveVerify?.()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Explain' })).not.toBeDisabled()
    })
  })

  it('shows the onboarding setup screen instead of the dashboard when unconfigured', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'GET /config': { body: CONFIG_BODY_MISSING },
    })

    render(<OverviewPage />, { wrapper: MemoryRouter })

    expect(
      await screen.findByText(/Buildrail isn.t configured for this project yet/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Set up Buildrail' })).toBeInTheDocument()
    expect(screen.queryByText('Actions')).not.toBeInTheDocument()
  })

  it('shows the config error alongside the setup prompt when configuration is invalid', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'GET /config': { body: CONFIG_BODY_INVALID },
    })

    render(<OverviewPage />, { wrapper: MemoryRouter })

    expect(
      await screen.findByText(/Buildrail isn.t configured for this project yet/),
    ).toBeInTheDocument()
    expect(screen.getByText(/unsupported provider/)).toBeInTheDocument()
  })

  it('opens a setup form with no API key input', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'GET /config': { body: CONFIG_BODY_MISSING },
    })
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await user.click(await screen.findByRole('button', { name: 'Set up Buildrail' }))

    expect(screen.getByText('Fake / Offline')).toBeInTheDocument()
    expect(screen.getByText('Anthropic')).toBeInTheDocument()
    expect(screen.getByLabelText(/Artifact directory/)).toBeInTheDocument()
    expect(screen.queryAllByRole('textbox', { name: /api.?key/i })).toHaveLength(0)
    expect(document.querySelector('input[type="password"]')).not.toBeInTheDocument()
  })

  it('shows the Anthropic model field and environment-key explanation only when Anthropic is selected', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'GET /config': { body: CONFIG_BODY_MISSING },
    })
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await user.click(await screen.findByRole('button', { name: 'Set up Buildrail' }))

    expect(screen.queryByLabelText(/Anthropic model/)).not.toBeInTheDocument()

    await user.click(screen.getByRole('radio', { name: /Anthropic/ }))

    expect(screen.getByLabelText(/Anthropic model/)).toBeInTheDocument()
    expect(screen.getByText(/ANTHROPIC_API_KEY from the environment/)).toBeInTheDocument()
    expect(screen.getByText(/never stored by Buildrail/)).toBeInTheDocument()
    expect(document.querySelector('input[type="password"]')).not.toBeInTheDocument()
  })

  it('completes setup with the fake provider and transitions to the dashboard', async () => {
    let configured = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        const method = (init?.method ?? 'GET').toUpperCase()
        if (url.endsWith('/project')) {
          return new Response(JSON.stringify(PROJECT_BODY), { status: 200 })
        }
        if (method === 'GET' && url.endsWith('/config')) {
          return new Response(JSON.stringify(configured ? CONFIG_BODY_OK : CONFIG_BODY_MISSING), {
            status: 200,
          })
        }
        if (method === 'PUT' && url.endsWith('/config')) {
          configured = true
          return new Response(JSON.stringify(CONFIG_BODY_OK), { status: 200 })
        }
        return new Response(JSON.stringify({ runs: [] }), { status: 200 })
      }),
    )
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await user.click(await screen.findByRole('button', { name: 'Set up Buildrail' }))
    await user.click(screen.getByRole('button', { name: 'Set up Buildrail' }))

    await waitFor(
      () => {
        expect(screen.getByText('Actions')).toBeInTheDocument()
      },
      { timeout: 5000, interval: 25 },
    )
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.queryByText(/isn.t configured/)).not.toBeInTheDocument()
  })

  it('shows a clean error and stays on the form when setup fails', async () => {
    mockApi({
      'GET /project': { body: PROJECT_BODY },
      'GET /config': { body: CONFIG_BODY_MISSING },
      'PUT /config': { status: 400, body: { error: 'Unknown configuration field(s): bogus.' } },
    })
    const user = userEvent.setup()

    render(<OverviewPage />, { wrapper: MemoryRouter })
    await user.click(await screen.findByRole('button', { name: 'Set up Buildrail' }))
    await user.click(screen.getByRole('button', { name: 'Set up Buildrail' }))

    expect(await screen.findByText(/Unknown configuration field/)).toBeInTheDocument()
    expect(screen.getByText('Fake / Offline')).toBeInTheDocument()
  })
})
