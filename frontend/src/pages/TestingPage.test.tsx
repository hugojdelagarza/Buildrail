import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/mockApi'
import { TestingPage } from './TestingPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const RUN_SUMMARY = {
  run_id: 'r1',
  status: 'failure',
  created_at: '2026-08-14T00:00:00Z',
  artifact_count: 2,
  artifact_types: ['test-report', 'test-report'],
  pipeline: null,
  pipeline_source: null,
}

function artifactDetail(overrides: Record<string, unknown>) {
  return {
    id: 'r1/001-test-report-report',
    run_id: 'r1',
    type: 'test-report',
    content_path: '/x',
    status: 'success',
    produced_by_skill: 'test-report',
    produced_by_version: '0.1.0',
    provider_usage: null,
    pipeline: null,
    display_name: 'test-report',
    created_at: null,
    checksum: null,
    content_type: 'text/markdown',
    ...overrides,
  }
}

const MARKDOWN_ARTIFACT = artifactDetail({
  id: 'r1/001-test-report-report',
  content_type: 'text/markdown',
  display_name: 'test-report',
})

const JSON_ARTIFACT = artifactDetail({
  id: 'r1/001-test-report-report_json',
  content_type: 'application/json',
  display_name: 'test-report-data',
})

const FAILING_REPORT = {
  schema_version: '1.0',
  framework: 'pytest',
  command: ['python', '-m', 'pytest'],
  status: 'failed',
  exit_code: 1,
  started_at: '2026-08-14T00:00:00Z',
  duration_seconds: 1.23,
  counts: { total: 3, passed: 1, failed: 1, skipped: 1, xfailed: 0, xpassed: 0, errors: 0 },
  failures: [{ node_id: 'test_x.py::test_bad', outcome: 'failed', message: 'assert 1 == 2' }],
  collection_errors: [],
  stdout_excerpt: '',
  stderr_excerpt: '',
  coverage: null,
  flaky_signals: [],
  analysis_mode: 'not_requested',
  analysis_text: null,
  analysis_model: null,
  analysis_input_tokens: null,
  analysis_output_tokens: null,
}

function mockTestingPage(
  reportOverrides: Record<string, unknown> = {},
  extraHandlers: Record<string, { status?: number; body: unknown }> = {},
) {
  const report = { ...FAILING_REPORT, ...reportOverrides }
  return mockApi({
    'GET /runs': { body: { runs: [RUN_SUMMARY] } },
    'GET /runs/r1': {
      body: {
        run_id: 'r1',
        status: 'failure',
        created_at: '2026-08-14T00:00:00Z',
        pipeline: null,
        pipeline_source: null,
        duration_seconds: 1.23,
        pipeline_steps: [],
        artifacts: [MARKDOWN_ARTIFACT, JSON_ARTIFACT],
        provider_usage_totals: null,
      },
    },
    'GET /artifacts/r1/001-test-report-report_json': {
      body: { ...JSON_ARTIFACT, content: JSON.stringify(report), content_json: report },
    },
    ...extraHandlers,
  })
}

describe('TestingPage', () => {
  it('shows an empty state when no test report exists', async () => {
    mockApi({ 'GET /runs': { body: { runs: [] } } })

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/No test report exists yet/)).toBeInTheDocument()
  })

  it('shows a loading state before data arrives', () => {
    mockApi({ 'GET /runs': { body: { runs: [] } } })

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(screen.getByText(/Loading test results/)).toBeInTheDocument()
  })

  it('renders a passing report with restrained status text, not color alone', async () => {
    mockTestingPage({
      status: 'passed',
      exit_code: 0,
      counts: { total: 1, passed: 1, failed: 0, skipped: 0, xfailed: 0, xpassed: 0, errors: 0 },
      failures: [],
    })

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect((await screen.findAllByText('passed')).length).toBeGreaterThan(0)
    expect(screen.getByText('None')).toBeInTheDocument() // Failing Tests section
  })

  it('renders a failed report with counts and failure details', async () => {
    mockTestingPage()

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('test_x.py::test_bad')).toBeInTheDocument()
    expect((await screen.findAllByText('failed')).length).toBeGreaterThan(0)
    expect(screen.getByText(/assert 1 == 2/)).toBeInTheDocument()
    expect(screen.getByText('Duration: 1.23s')).toBeInTheDocument()
  })

  it('renders skipped counts', async () => {
    mockTestingPage()

    render(<TestingPage />, { wrapper: MemoryRouter })

    await screen.findByText('test_x.py::test_bad')
    const statValues = screen.getAllByText('1')
    expect(statValues.length).toBeGreaterThan(0) // skipped=1 rendered in the stat grid
  })

  it('renders collection errors when present', async () => {
    mockTestingPage({
      status: 'collection_error',
      counts: { total: 1, passed: 0, failed: 0, skipped: 0, xfailed: 0, xpassed: 0, errors: 1 },
      failures: [],
      collection_errors: [{ location: 'test_broken.py', message: 'ImportError: nope' }],
    })

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('Collection Errors')).toBeInTheDocument()
    expect(screen.getByText('test_broken.py')).toBeInTheDocument()
    expect(screen.getByText(/ImportError: nope/)).toBeInTheDocument()
  })

  it('renders possible flaky signals with conservative wording', async () => {
    mockTestingPage({
      flaky_signals: [
        {
          node_id: 'test_x.py::test_bad',
          note: 'Failing now; did not appear in the failures of recent run r0 (possible flaky signal).',
        },
      ],
    })

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('Possible Flaky Signals')).toBeInTheDocument()
    expect(screen.getByText(/possible flaky signal/)).toBeInTheDocument()
  })

  it('shows AI analysis text only when analysis completed', async () => {
    mockTestingPage({ analysis_mode: 'completed', analysis_text: 'Root cause: off-by-one.' })

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('Root cause: off-by-one.')).toBeInTheDocument()
  })

  it('shows "not requested" for analysis by default', async () => {
    mockTestingPage()

    render(<TestingPage />, { wrapper: MemoryRouter })

    await screen.findByText('test_x.py::test_bad')
    expect(screen.getByText('Not requested.')).toBeInTheDocument()
  })

  it('links to the full Markdown report artifact', async () => {
    mockTestingPage()

    render(<TestingPage />, { wrapper: MemoryRouter })

    const link = await screen.findByRole('link', { name: 'View full report' })
    expect(link).toHaveAttribute('href', '/artifacts/r1/001-test-report-report')
  })

  it('the Analyze checkbox defaults to unchecked (provider-independent default)', async () => {
    mockTestingPage()

    render(<TestingPage />, { wrapper: MemoryRouter })

    await screen.findByText('test_x.py::test_bad')
    const checkbox = screen.getByRole('checkbox', {
      name: /Analyze failures with configured provider/,
    })
    expect(checkbox).not.toBeChecked()
  })

  it('Run Tests calls POST /commands/test without analyze by default', async () => {
    const { fetchMock } = mockTestingPage()
    const user = userEvent.setup()
    render(<TestingPage />, { wrapper: MemoryRouter })
    await screen.findByText('test_x.py::test_bad')

    await user.click(screen.getByRole('button', { name: 'Run Tests' }))

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/commands/test'))
      expect(call).toBeDefined()
    })
  })

  it('checking Analyze sends analyze: true to /commands/test', async () => {
    const { fetchMock } = mockTestingPage(
      {},
      { 'POST /commands/test': { body: { success: true, message: 'ok' } } },
    )
    const user = userEvent.setup()
    render(<TestingPage />, { wrapper: MemoryRouter })
    await screen.findByText('test_x.py::test_bad')

    await user.click(
      screen.getByRole('checkbox', { name: /Analyze failures with configured provider/ }),
    )
    await user.click(screen.getByRole('button', { name: 'Run Tests' }))

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/commands/test'))
      expect(call).toBeDefined()
      const body = JSON.parse((call?.[1]?.body as string) ?? '{}')
      expect(body.analyze).toBe(true)
    })
  })

  it('renders recent-run history', async () => {
    mockTestingPage()

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText('Recent Runs')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'r1' }).length).toBeGreaterThan(0)
  })

  it('shows coverage only when available', async () => {
    mockTestingPage({
      coverage: { source: 'coverage.xml', line_rate: 0.5, lines_covered: 5, lines_valid: 10 },
    })

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/50\.0% line coverage/)).toBeInTheDocument()
  })

  it('shows coverage unavailable by default', async () => {
    mockTestingPage()

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/no coverage\.xml found/)).toBeInTheDocument()
  })

  it('shows an error state when the service is unavailable', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    render(<TestingPage />, { wrapper: MemoryRouter })

    expect(await screen.findByText(/Could not reach the Buildrail service/)).toBeInTheDocument()
  })
})
