import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type {
  CollectionErrorEntry,
  CoverageSummary,
  FlakySignal,
  RunSummary,
  TestFailureEntry,
  TestReport,
} from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { StatusBadge } from '../components/StatusBadge'
import shared from '../styles/shared.module.css'

const HISTORY_LIMIT = 10

interface HistoryRow {
  runId: string
  createdAt: string | null
  status: string
  passed: number
  failed: number
  skipped: number
  durationSeconds: number
}

interface TestingData {
  run: RunSummary
  report: TestReport
  markdownArtifactId: string | null
  history: HistoryRow[]
}

async function loadTestReport(
  run: RunSummary,
  signal: AbortSignal,
): Promise<{ report: TestReport; markdownArtifactId: string | null } | null> {
  const detail = await api.run(run.run_id, signal)
  const jsonArtifact = detail.artifacts.find(
    (artifact) => artifact.type === 'test-report' && artifact.content_type === 'application/json',
  )
  if (!jsonArtifact) return null
  const markdownArtifact = detail.artifacts.find(
    (artifact) => artifact.type === 'test-report' && artifact.content_type === 'text/markdown',
  )
  const payload = await api.artifact(jsonArtifact.id, signal)
  return {
    report: (payload.content_json ?? {}) as unknown as TestReport,
    markdownArtifactId: markdownArtifact?.id ?? null,
  }
}

async function fetchPageData(signal: AbortSignal): Promise<TestingData | null> {
  const { runs } = await api.runs(20, signal)
  const testRuns = runs
    .filter((run) => run.artifact_types.includes('test-report'))
    .slice(0, HISTORY_LIMIT)
  if (testRuns.length === 0) return null

  const loaded = await Promise.all(testRuns.map((run) => loadTestReport(run, signal)))
  const latest = loaded[0]
  if (!latest) return null

  const history: HistoryRow[] = testRuns
    .map((run, index) => {
      const entry = loaded[index]
      if (!entry) return null
      return {
        runId: run.run_id,
        createdAt: run.created_at,
        status: entry.report.status,
        passed: entry.report.counts.passed,
        failed: entry.report.counts.failed,
        skipped: entry.report.counts.skipped,
        durationSeconds: entry.report.duration_seconds,
      }
    })
    .filter((row): row is HistoryRow => row !== null)

  return {
    run: testRuns[0],
    report: latest.report,
    markdownArtifactId: latest.markdownArtifactId,
    history,
  }
}

export function TestingPage() {
  const fetcher = useCallback((signal: AbortSignal) => fetchPageData(signal), [])
  const { data, error, loading, reload } = useAsync(fetcher, [])
  useRegisterRefresh(reload)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)
  const [analyze, setAnalyze] = useState(false)

  const runTests = useCallback(async () => {
    setRunning(true)
    setRunError(null)
    try {
      const response = await api.runCommand('test', { analyze, history: true })
      if (!response.success) setRunError(response.message)
      reload()
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : 'Unexpected error.')
    } finally {
      setRunning(false)
    }
  }, [analyze, reload])

  if (loading) return <p className={shared.loadingState}>Loading test results…</p>
  if (error) return <p className={shared.errorState}>{error}</p>

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <h1 className={shared.pageTitle}>Testing</h1>
      </div>

      <div className={shared.buttonRow}>
        <button
          type="button"
          className={shared.buttonPrimary}
          disabled={running}
          onClick={() => void runTests()}
        >
          {running ? 'Running…' : 'Run Tests'}
        </button>
        <label>
          <input
            type="checkbox"
            checked={analyze}
            disabled={running}
            onChange={(event) => setAnalyze(event.target.checked)}
          />{' '}
          Analyze failures with configured provider
        </label>
      </div>
      {runError && <p className={shared.errorState}>{runError}</p>}

      {!data ? (
        <p className={shared.emptyState}>
          No test report exists yet. Run tests to see results, failures, and history here.
        </p>
      ) : (
        <TestReportView data={data} />
      )}
    </div>
  )
}

function TestReportView({ data }: { data: TestingData }) {
  const { report } = data
  return (
    <>
      <div className={shared.pageHeader}>
        <p className={shared.pageSubtitle}>
          From run{' '}
          <Link to={`/runs/${encodeURIComponent(data.run.run_id)}`}>{data.run.run_id}</Link>
          {data.run.created_at ? ` — ${data.run.created_at}` : ''}
        </p>
        <StatusBadge status={report.status} />
      </div>

      <div className={shared.statGrid}>
        <Stat label="Total" value={report.counts.total} />
        <Stat label="Passed" value={report.counts.passed} />
        <Stat label="Failed" value={report.counts.failed} />
        <Stat label="Skipped" value={report.counts.skipped} />
        <Stat label="XFailed" value={report.counts.xfailed} />
        <Stat label="XPassed" value={report.counts.xpassed} />
        <Stat label="Errors" value={report.counts.errors} />
      </div>
      <p className={shared.pageSubtitle}>Duration: {report.duration_seconds.toFixed(2)}s</p>

      {data.markdownArtifactId && (
        <div className={shared.buttonRow}>
          <Link to={`/artifacts/${data.markdownArtifactId}`} className={shared.button}>
            View full report
          </Link>
        </div>
      )}

      <FailuresSection failures={report.failures} />
      <CollectionErrorsSection errors={report.collection_errors} />
      <FlakySection signals={report.flaky_signals} />
      <CoverageSection coverage={report.coverage} />
      <AnalysisSection report={report} />
      <HistorySection history={data.history} />
    </>
  )
}

function FailuresSection({ failures }: { failures: TestFailureEntry[] }) {
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>Failing Tests</h2>
      {failures.length === 0 ? (
        <p className={shared.pageSubtitle}>None</p>
      ) : (
        <ul>
          {failures.map((failure) => (
            <li key={failure.node_id}>
              <span className={shared.mono}>{failure.node_id}</span> ({failure.outcome})
              <pre>{failure.message}</pre>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function CollectionErrorsSection({ errors }: { errors: CollectionErrorEntry[] }) {
  if (errors.length === 0) return null
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>Collection Errors</h2>
      <ul>
        {errors.map((collectionError) => (
          <li key={collectionError.location}>
            <span className={shared.mono}>{collectionError.location}</span>
            <pre>{collectionError.message}</pre>
          </li>
        ))}
      </ul>
    </div>
  )
}

function FlakySection({ signals }: { signals: FlakySignal[] }) {
  if (signals.length === 0) return null
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>Possible Flaky Signals</h2>
      <ul>
        {signals.map((signal) => (
          <li key={signal.node_id}>
            <span className={shared.mono}>{signal.node_id}</span> — {signal.note}
          </li>
        ))}
      </ul>
    </div>
  )
}

function CoverageSection({ coverage }: { coverage: CoverageSummary | null }) {
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>Coverage</h2>
      {coverage ? (
        <p>
          {(coverage.line_rate * 100).toFixed(1)}% line coverage (from {coverage.source})
          {coverage.lines_covered !== null && coverage.lines_valid !== null
            ? ` — ${coverage.lines_covered}/${coverage.lines_valid} lines`
            : ''}
        </p>
      ) : (
        <p className={shared.pageSubtitle}>
          Not available — no coverage.xml found at the project root.
        </p>
      )}
    </div>
  )
}

function AnalysisSection({ report }: { report: TestReport }) {
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>AI Failure Analysis</h2>
      {report.analysis_mode === 'completed' && report.analysis_text ? (
        <p>{report.analysis_text}</p>
      ) : report.analysis_mode === 'unavailable_no_provider' ? (
        <p className={shared.pageSubtitle}>
          Analysis was requested but no provider is configured. Deterministic results are
          unaffected.
        </p>
      ) : report.analysis_mode === 'skipped_all_passed' ? (
        <p className={shared.pageSubtitle}>Skipped — no failures or errors to analyze.</p>
      ) : (
        <p className={shared.pageSubtitle}>Not requested.</p>
      )}
    </div>
  )
}

function HistorySection({ history }: { history: HistoryRow[] }) {
  if (history.length === 0) return null
  return (
    <div className={shared.section}>
      <h2 className={shared.sectionTitle}>Recent Runs</h2>
      <table className={shared.table}>
        <thead>
          <tr>
            <th>Run</th>
            <th>Created</th>
            <th>Status</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Skipped</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          {history.map((row) => (
            <tr key={row.runId}>
              <td className={shared.mono}>
                <Link to={`/runs/${encodeURIComponent(row.runId)}`}>{row.runId}</Link>
              </td>
              <td>{row.createdAt ?? 'unknown'}</td>
              <td>
                <StatusBadge status={row.status} />
              </td>
              <td>{row.passed}</td>
              <td>{row.failed}</td>
              <td>{row.skipped}</td>
              <td>{row.durationSeconds.toFixed(2)}s</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className={shared.statCard}>
      <div className={shared.statLabel}>{label}</div>
      <div className={shared.statValue}>{value}</div>
    </div>
  )
}
