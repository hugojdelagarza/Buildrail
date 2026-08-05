import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { SettingsPage } from './SettingsPage'

afterEach(() => {
  vi.unstubAllGlobals()
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
})
