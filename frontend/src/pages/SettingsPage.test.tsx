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
      configured: true,
      provider: 'fake',
      anthropic_model: null,
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
})
