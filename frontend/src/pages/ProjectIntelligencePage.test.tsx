import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { ProjectIntelligencePage } from './ProjectIntelligencePage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ProjectIntelligencePage', () => {
  it('offers a Run button when no project intelligence run exists', async () => {
    mockApi({ 'GET /runs': { body: { runs: [] } } })

    render(<ProjectIntelligencePage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/No project intelligence run exists yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run Project Intelligence' })).toBeInTheDocument()
  })

  it('renders statistics and modules once a run with an analysis exists', async () => {
    mockApi({
      'GET /runs': {
        body: {
          runs: [
            {
              run_id: 'r1',
              status: 'success',
              created_at: null,
              artifact_count: 6,
              artifact_types: ['architecture-summary', 'documentation', 'diagram'],
              pipeline: 'project-intelligence',
            },
          ],
        },
      },
      'GET /runs/r1': {
        body: {
          run_id: 'r1',
          status: 'success',
          created_at: null,
          pipeline: 'project-intelligence',
          duration_seconds: 1,
          pipeline_steps: [],
          provider_usage_totals: null,
          artifacts: [
            {
              id: 'r1/001-architecture-summary-analysis',
              run_id: 'r1',
              type: 'architecture-summary',
              content_path: '/x',
              status: 'success',
              produced_by_skill: 'explain-project',
              produced_by_version: '0.1.0',
              provider_usage: null,
              pipeline: 'project-intelligence',
              display_name: 'project-analysis',
              created_at: null,
              checksum: null,
              content_type: 'application/json',
            },
          ],
        },
      },
      'GET /artifacts/r1/001-architecture-summary-analysis': {
        body: {
          id: 'r1/001-architecture-summary-analysis',
          run_id: 'r1',
          type: 'architecture-summary',
          content_path: '/x',
          status: 'success',
          produced_by_skill: 'explain-project',
          produced_by_version: '0.1.0',
          provider_usage: null,
          pipeline: 'project-intelligence',
          display_name: 'project-analysis',
          created_at: null,
          checksum: null,
          content_type: 'application/json',
          content: '{}',
          content_json: {
            repository_name: 'demo-repo',
            repository_root: '/tmp/demo',
            python_requires: null,
            build_system: null,
            entry_points: [],
            cli_commands: [],
            packages: [],
            modules: [
              {
                dotted_name: 'app.main',
                file_path: 'app/main.py',
                docstring: null,
                classes: [],
                functions: [],
                imports: [],
                lines: 3,
              },
            ],
            skills: [],
            pipelines: [],
            artifact_types: [],
            test_layout: { test_directories: [], test_files: [] },
            tooling: { has_ruff: false, has_mypy: false, has_pytest: false },
            statistics: {
              python_files: 1,
              modules: 1,
              classes: 0,
              functions: 1,
              test_files: 0,
              lines_of_python: 3,
            },
            warnings: [],
          },
        },
      },
    })

    render(<ProjectIntelligencePage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('demo-repo')).toBeInTheDocument()
    expect(screen.getByText('app.main')).toBeInTheDocument()
  })
})
