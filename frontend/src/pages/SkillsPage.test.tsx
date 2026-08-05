import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { SkillsPage } from './SkillsPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const SKILLS_BODY = {
  skills: [
    {
      name: 'review-diff',
      version: '0.1.0',
      protocol_version: '1.0',
      description: 'Reviews a diff.',
      requires_provider: true,
      inputs: [{ name: 'diff', type: 'file', required: true, description: 'Path to a diff.' }],
      outputs: [{ name: 'review', artifact_type: 'review' }],
    },
    {
      name: 'verify-project',
      version: '0.1.0',
      protocol_version: '1.0',
      description: 'Runs quality checks.',
      requires_provider: false,
      inputs: [],
      outputs: [{ name: 'report', artifact_type: 'verification-report' }],
    },
  ],
}

describe('SkillsPage', () => {
  it('lists all discovered skills', async () => {
    mockApi({ 'GET /skills': { body: SKILLS_BODY } })

    render(<SkillsPage />, { wrapper: MemoryRouter })

    expect((await screen.findAllByText('review-diff')).length).toBeGreaterThan(0)
    expect(screen.getByText('verify-project')).toBeInTheDocument()
  })

  it('shows inputs/outputs for the selected skill', async () => {
    mockApi({ 'GET /skills': { body: SKILLS_BODY } })
    const user = userEvent.setup()

    render(<SkillsPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('review-diff')

    await user.click(screen.getByText('verify-project'))

    expect(screen.getByText('Runs quality checks.')).toBeInTheDocument()
    expect(screen.getByText('report')).toBeInTheDocument()
  })
})
