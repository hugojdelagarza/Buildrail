import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { LAYOUT_RESET_EVENT } from '../hooks/useResizableWidth'
import { SettingsPage } from './SettingsPage'

const isTauriMock = vi.hoisted(() => vi.fn(() => false))
vi.mock('@tauri-apps/api/core', () => ({ isTauri: isTauriMock }))

const SETTINGS_MOCKS = {
  'GET /config': {
    body: {
      status: 'ok',
      configured: true,
      provider: 'fake',
      anthropic_model: null,
      artifact_root: 'artifacts',
      credential_available: true,
      error: null,
    },
  },
  'GET /project': {
    body: {
      service_version: '0.1.0',
      project_root: '/home/dev/project',
      config_status: 'ok',
      artifact_root: 'artifacts',
      provider: 'fake',
      provider_ready: true,
      skill_count: 7,
      pipeline_count: 2,
      recent_run_count: 0,
      latest_run: null,
      statistics: null,
    },
  },
  'GET /version': {
    body: {
      buildrail_version: '0.1.0',
      api_version: '1',
      python_version: '3.12.10',
      platform: 'Windows',
    },
  },
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
  isTauriMock.mockReturnValue(false)
})

describe('SettingsPage', () => {
  it('shows credential availability but never the credential value', async () => {
    mockApi({
      'GET /config': {
        body: {
          configured: true,
          provider: 'anthropic',
          anthropic_model: 'claude-haiku-4-5-20251001',
          artifact_root: 'artifacts',
          credential_available: true,
        },
      },
      'GET /project': {
        body: {
          service_version: '0.1.0',
          project_root: '/home/dev/project',
          config_status: 'ok',
          artifact_root: 'artifacts',
          provider: 'anthropic',
          provider_ready: true,
          skill_count: 7,
          pipeline_count: 2,
          recent_run_count: 0,
          latest_run: null,
          statistics: null,
        },
      },
      'GET /version': {
        body: {
          buildrail_version: '0.1.0',
          api_version: '1',
          python_version: '3.12.10',
          platform: 'Windows',
        },
      },
    })

    render(<SettingsPage />)

    expect(await screen.findByText('Available')).toBeInTheDocument()
    const rendered = document.body.textContent ?? ''
    expect(rendered).not.toMatch(/sk-ant/i)
    expect(rendered).not.toMatch(/ANTHROPIC_API_KEY=/)
    expect(rendered.toLowerCase()).not.toContain('api key:')
  })

  it('shows credential as Missing when unavailable', async () => {
    mockApi({
      'GET /config': {
        body: {
          configured: false,
          provider: null,
          anthropic_model: null,
          artifact_root: null,
          credential_available: false,
        },
      },
      'GET /project': {
        body: {
          service_version: '0.1.0',
          project_root: '/home/dev/project',
          config_status: 'missing',
          artifact_root: null,
          provider: null,
          provider_ready: false,
          skill_count: 7,
          pipeline_count: 2,
          recent_run_count: 0,
          latest_run: null,
          statistics: null,
        },
      },
      'GET /version': {
        body: {
          buildrail_version: '0.1.0',
          api_version: '1',
          python_version: '3.12.10',
          platform: 'Windows',
        },
      },
    })

    render(<SettingsPage />)

    expect(await screen.findByText('Missing')).toBeInTheDocument()
  })

  it('lists keyboard shortcuts', async () => {
    mockApi(SETTINGS_MOCKS)

    render(<SettingsPage />)

    expect(await screen.findByText('Keyboard Shortcuts')).toBeInTheDocument()
    expect(screen.getByText('Ctrl K')).toBeInTheDocument()
    expect(screen.getAllByText('Open the command palette')).toHaveLength(2)
    expect(screen.getByText('G then R')).toBeInTheDocument()
  })

  it('broadcasts a layout-reset event when Reset layout is clicked', async () => {
    mockApi(SETTINGS_MOCKS)
    const user = userEvent.setup()
    const listener = vi.fn()
    window.addEventListener(LAYOUT_RESET_EVENT, listener)

    render(<SettingsPage />)
    await screen.findByText('Keyboard Shortcuts')

    await user.click(screen.getByRole('button', { name: 'Reset layout' }))

    expect(listener).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Layout reset' })).toBeInTheDocument()

    window.removeEventListener(LAYOUT_RESET_EVENT, listener)
  })

  it('does not show the desktop note in a plain browser', async () => {
    mockApi(SETTINGS_MOCKS)

    render(<SettingsPage />)

    await screen.findByText('Keyboard Shortcuts')
    expect(screen.queryByText(/Running as a desktop app/)).not.toBeInTheDocument()
  })

  it('shows a desktop note when running inside Tauri', async () => {
    isTauriMock.mockReturnValue(true)
    mockApi(SETTINGS_MOCKS)

    render(<SettingsPage />)

    expect(await screen.findByText(/Running as a desktop app/)).toBeInTheDocument()
  })

  it('reads the current project configuration', async () => {
    mockApi(SETTINGS_MOCKS)

    render(<SettingsPage />)

    expect(await screen.findByText('Project Configuration')).toBeInTheDocument()
    expect(screen.getByText('fake')).toBeInTheDocument()
    expect(screen.getByText('artifacts')).toBeInTheDocument()
    expect(screen.getByText('Available')).toBeInTheDocument()
  })

  it('edits configuration through the same endpoint onboarding uses', async () => {
    let updated = false
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        const method = (init?.method ?? 'GET').toUpperCase()
        if (method === 'GET' && url.endsWith('/config')) {
          const body = updated
            ? { ...SETTINGS_MOCKS['GET /config'].body, provider: 'anthropic' }
            : SETTINGS_MOCKS['GET /config'].body
          return new Response(JSON.stringify(body), { status: 200 })
        }
        if (method === 'PUT' && url.endsWith('/config')) {
          updated = true
          return new Response(
            JSON.stringify({ ...SETTINGS_MOCKS['GET /config'].body, provider: 'anthropic' }),
            { status: 200 },
          )
        }
        if (url.endsWith('/project')) {
          return new Response(JSON.stringify(SETTINGS_MOCKS['GET /project'].body), {
            status: 200,
          })
        }
        if (url.endsWith('/version')) {
          return new Response(JSON.stringify(SETTINGS_MOCKS['GET /version'].body), {
            status: 200,
          })
        }
        return new Response(JSON.stringify({}), { status: 200 })
      }),
    )
    const user = userEvent.setup()

    render(<SettingsPage />)
    await user.click(await screen.findByRole('button', { name: 'Edit configuration' }))
    await user.click(screen.getByRole('radio', { name: /Anthropic/ }))
    await user.click(screen.getByRole('button', { name: 'Save configuration' }))

    expect(await screen.findByText('anthropic')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save configuration' })).not.toBeInTheDocument()
  })

  it('shows a clean error and keeps editing open when the update fails', async () => {
    mockApi({
      ...SETTINGS_MOCKS,
      'PUT /config': {
        status: 400,
        body: { error: "'artifact_root' must stay within the project directory." },
      },
    })
    const user = userEvent.setup()

    render(<SettingsPage />)
    await user.click(await screen.findByRole('button', { name: 'Edit configuration' }))
    await user.click(screen.getByRole('button', { name: 'Save configuration' }))

    expect(await screen.findByText(/must stay within the project directory/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save configuration' })).toBeInTheDocument()
  })

  it('cancels editing without writing anything', async () => {
    mockApi(SETTINGS_MOCKS)
    const user = userEvent.setup()

    render(<SettingsPage />)
    await user.click(await screen.findByRole('button', { name: 'Edit configuration' }))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByRole('button', { name: 'Edit configuration' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Save configuration' })).not.toBeInTheDocument()
  })
})
