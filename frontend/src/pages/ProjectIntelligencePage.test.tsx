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

  it('offers a Run Dependency Audit button when no dependency audit run exists', async () => {
    mockApi({ 'GET /runs': { body: { runs: [] } } })

    render(<ProjectIntelligencePage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('Dependency Audit')).toBeInTheDocument()
    expect(screen.getByText(/No dependency audit has been generated yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run Dependency Audit' })).toBeInTheDocument()
  })

  it('renders dependency audit counts, mismatches, and warnings without alarm styling', async () => {
    mockApi({
      'GET /runs': {
        body: {
          runs: [
            {
              run_id: 'dep1',
              status: 'success',
              created_at: null,
              artifact_count: 2,
              artifact_types: ['dependency-audit'],
              pipeline: null,
            },
          ],
        },
      },
      'GET /runs/dep1': {
        body: {
          run_id: 'dep1',
          status: 'success',
          created_at: null,
          pipeline: null,
          duration_seconds: 1,
          pipeline_steps: [],
          provider_usage_totals: null,
          artifacts: [
            {
              id: 'dep1/001-dependency-audit-audit',
              run_id: 'dep1',
              type: 'dependency-audit',
              content_path: '/x.json',
              status: 'success',
              produced_by_skill: 'dependency-audit',
              produced_by_version: '0.1.0',
              provider_usage: null,
              pipeline: null,
              display_name: 'dependency-audit-data',
              created_at: null,
              checksum: null,
              content_type: 'application/json',
            },
            {
              id: 'dep1/000-dependency-audit-summary',
              run_id: 'dep1',
              type: 'dependency-audit',
              content_path: '/x.md',
              status: 'success',
              produced_by_skill: 'dependency-audit',
              produced_by_version: '0.1.0',
              provider_usage: null,
              pipeline: null,
              display_name: 'dependency-audit-summary',
              created_at: null,
              checksum: null,
              content_type: 'text/markdown',
            },
          ],
        },
      },
      'GET /artifacts/dep1/001-dependency-audit-audit': {
        body: {
          id: 'dep1/001-dependency-audit-audit',
          run_id: 'dep1',
          type: 'dependency-audit',
          content_path: '/x.json',
          status: 'success',
          produced_by_skill: 'dependency-audit',
          produced_by_version: '0.1.0',
          provider_usage: null,
          pipeline: null,
          display_name: 'dependency-audit-data',
          created_at: null,
          checksum: null,
          content_type: 'application/json',
          content: '{}',
          content_json: {
            schema_version: '1.0',
            repository_name: 'demo-repo',
            repository_root: '/tmp/demo',
            build_backend: null,
            sources: ['pyproject.toml'],
            dependencies: [
              {
                name: 'requests',
                raw: 'requests>=2.0',
                group: 'runtime',
                source: 'pyproject.toml',
                version_constraint: '>=2.0',
                is_pinned: false,
                is_vcs: false,
                is_url: false,
                is_editable: false,
                is_local_path: false,
              },
            ],
            duplicates: [],
            conflicts: [],
            mismatches: [
              {
                name: 'yaml',
                kind: 'imported_not_declared',
                note: 'Possible undeclared dependency — mapping uncertain.',
              },
            ],
            observed_third_party_imports: ['yaml'],
            warnings: [
              {
                kind: 'poetry_detected',
                path: 'pyproject.toml',
                message: 'Poetry tables are not parsed.',
              },
            ],
          },
        },
      },
    })

    render(<ProjectIntelligencePage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('Total Declared')).toBeInTheDocument()
    expect(screen.getByText('Possible Undeclared Dependencies')).toBeInTheDocument()
    expect(screen.getByText('yaml')).toBeInTheDocument()
    expect(screen.getByText('Warnings')).toBeInTheDocument()
    expect(screen.getByText(/Poetry tables are not parsed/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'View full report' })).toHaveAttribute(
      'href',
      '/artifacts/dep1/000-dependency-audit-summary',
    )
  })
})
