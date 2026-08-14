import { render, screen, waitFor } from '@testing-library/react'
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
      source: 'built-in',
      project_relative_path: null,
      inputs: [{ name: 'diff', type: 'file', required: true, description: 'Path to a diff.' }],
      outputs: [{ name: 'review', artifact_type: 'review' }],
    },
    {
      name: 'verify-project',
      version: '0.1.0',
      protocol_version: '1.0',
      description: 'Runs quality checks.',
      requires_provider: false,
      source: 'built-in',
      project_relative_path: null,
      inputs: [],
      outputs: [{ name: 'report', artifact_type: 'verification-report' }],
    },
    {
      name: 'my-skill',
      version: '0.1.0',
      protocol_version: '1.0',
      description: 'A project-local skill.',
      requires_provider: false,
      source: 'project-local',
      project_relative_path: '.buildrail/skills/my-skill',
      inputs: [],
      outputs: [{ name: 'summary', artifact_type: 'my-skill' }],
    },
  ],
}

describe('SkillsPage', () => {
  it('lists all discovered skills', async () => {
    mockApi({ 'GET /skills': { body: SKILLS_BODY } })

    render(<SkillsPage />, { wrapper: MemoryRouter })

    expect((await screen.findAllByText('review-diff')).length).toBeGreaterThan(0)
    expect(screen.getByText('verify-project')).toBeInTheDocument()
    expect(screen.getByText('my-skill')).toBeInTheDocument()
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

  it('shows a project-relative path for project-local skills, never a full path', async () => {
    mockApi({ 'GET /skills': { body: SKILLS_BODY } })
    const user = userEvent.setup()

    render(<SkillsPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('review-diff')

    await user.click(screen.getByText('my-skill'))

    expect(screen.getByText('.buildrail/skills/my-skill')).toBeInTheDocument()
  })

  it('filters skills by source', async () => {
    mockApi({ 'GET /skills': { body: SKILLS_BODY } })
    const user = userEvent.setup()

    render(<SkillsPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('review-diff')

    await user.click(screen.getByRole('button', { name: 'Project' }))

    expect(screen.getAllByText('my-skill').length).toBeGreaterThan(0)
    expect(screen.queryByText('verify-project')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Built-in' }))

    expect(screen.queryByText('my-skill')).not.toBeInTheDocument()
    expect(screen.getAllByText('verify-project').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: 'All' }))

    expect(screen.getAllByText('my-skill').length).toBeGreaterThan(0)
    expect(screen.getByText('verify-project')).toBeInTheDocument()
  })

  it('creates a project-local skill and refreshes the list', async () => {
    let created = false
    mockApi({
      'GET /skills': {
        get body() {
          return created
            ? { skills: [...SKILLS_BODY.skills, { ...SKILLS_BODY.skills[2], name: 'new-skill' }] }
            : SKILLS_BODY
        },
      },
      'POST /skills': {
        body: { name: 'new-skill', project_relative_path: '.buildrail/skills/new-skill' },
      },
    })
    const user = userEvent.setup()

    render(<SkillsPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('review-diff')

    await user.click(screen.getByRole('button', { name: 'New Skill' }))
    await user.type(screen.getByLabelText('Name'), 'new-skill')
    created = true
    await user.click(screen.getByRole('button', { name: 'Create Skill' }))

    await waitFor(() => {
      expect(screen.getByText(/Created at \.buildrail\/skills\/new-skill/)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('new-skill')).toBeInTheDocument()
    })
  })

  it('shows a clean error and keeps the modal open when creation fails', async () => {
    mockApi({
      'GET /skills': { body: SKILLS_BODY },
      'POST /skills': { status: 400, body: { error: "Invalid skill name 'Bad Name'." } },
    })
    const user = userEvent.setup()

    render(<SkillsPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('review-diff')
    await user.click(screen.getByRole('button', { name: 'New Skill' }))
    await user.type(screen.getByLabelText('Name'), 'Bad Name')

    await user.click(screen.getByRole('button', { name: 'Create Skill' }))

    expect(await screen.findByText(/Invalid skill name/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create Skill' })).toBeInTheDocument()
  })

  it('closes the New Skill modal on cancel without creating anything', async () => {
    mockApi({ 'GET /skills': { body: SKILLS_BODY } })
    const user = userEvent.setup()

    render(<SkillsPage />, { wrapper: MemoryRouter })
    await screen.findAllByText('review-diff')
    await user.click(screen.getByRole('button', { name: 'New Skill' }))

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
  })
})
