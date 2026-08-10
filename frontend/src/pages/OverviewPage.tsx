import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import type { ConfigResponse } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { useRegisterRefresh } from '../hooks/useRefreshRegistry'
import { ConfigForm } from '../components/ConfigForm'
import { StatusBadge } from '../components/StatusBadge'
import { projectNameFromRoot } from '../lib/projectName'
import shared from '../styles/shared.module.css'

interface ActionDef {
  id: string
  label: string
}

const ACTIONS: ActionDef[] = [
  { id: 'verify', label: 'Verify' },
  { id: 'explain', label: 'Explain' },
  { id: 'docs', label: 'Generate Docs' },
  { id: 'diagram', label: 'Generate Diagram' },
  { id: 'pre-commit', label: 'Run Pre-Commit' },
  { id: 'project-intelligence', label: 'Run Project Intelligence' },
  { id: 'dependency-audit', label: 'Dependency Audit' },
]

export function OverviewPage() {
  const fetchOverview = useCallback(async (signal: AbortSignal) => {
    const [project, config] = await Promise.all([api.project(signal), api.config(signal)])
    return { project, config }
  }, [])
  const { data, error, loading, reload } = useAsync(fetchOverview, [])
  useRegisterRefresh(reload)

  const [runningAction, setRunningAction] = useState<string | null>(null)
  const [result, setResult] = useState<{
    action: string
    success: boolean
    message: string
  } | null>(null)
  const [lastRunId, setLastRunId] = useState<string | null>(null)

  const runAction = useCallback(
    async (id: string) => {
      setRunningAction(id)
      setResult(null)
      setLastRunId(null)
      try {
        const response = await api.runCommand(id)
        setResult({ action: id, success: response.success, message: response.message })
        reload()
        try {
          const latest = await api.runs(1)
          setLastRunId(latest.runs[0]?.run_id ?? null)
        } catch {
          // Non-fatal: the command result is still shown even if we can't
          // resolve the newest run id for a direct link.
        }
      } catch (err) {
        const message = err instanceof ApiError ? err.message : 'Unexpected error.'
        setResult({ action: id, success: false, message })
      } finally {
        setRunningAction(null)
      }
    },
    [reload],
  )

  if (loading) {
    return <p className={shared.loadingState}>Connecting to the Buildrail service…</p>
  }

  if (error || !data) {
    return (
      <div className={shared.errorState}>
        <p>
          <strong>Service unavailable.</strong> {error ?? 'No response.'}
        </p>
        <p>Start it with `buildrail serve` in your project directory, then reload this page.</p>
      </div>
    )
  }

  const { project, config } = data
  const projectName = projectNameFromRoot(project.project_root)

  if (config.status !== 'ok') {
    return (
      <div className={shared.page}>
        <div className={shared.pageHeader}>
          <h1 className={shared.pageTitle}>Overview</h1>
          <p className={shared.pageSubtitle}>Project: {projectName}</p>
        </div>
        <OnboardingSetup config={config} onConfigured={reload} />
      </div>
    )
  }

  return (
    <div className={shared.page}>
      <div className={shared.pageHeader}>
        <div>
          <h1 className={shared.pageTitle}>Overview</h1>
          <p className={shared.pageSubtitle}>Project: {projectName}</p>
        </div>
      </div>

      <div className={shared.statGrid}>
        <Stat label="Provider" value={project.provider ?? 'Not configured'} />
        <Stat label="Provider Ready" value={project.provider_ready ? 'Yes' : 'No'} />
        <Stat label="Skills" value={String(project.skill_count)} />
        <Stat label="Pipelines" value={String(project.pipeline_count)} />
        <Stat label="Recent Runs" value={String(project.recent_run_count)} />
        <Stat
          label="Latest Run"
          value={project.latest_run ? project.latest_run.status : 'None yet'}
        />
      </div>

      {project.statistics && (
        <div className={shared.section}>
          <h2 className={shared.sectionTitle}>Project Statistics</h2>
          <div className={shared.statGrid}>
            <Stat label="Python Files" value={String(project.statistics.python_files)} />
            <Stat label="Modules" value={String(project.statistics.modules)} />
            <Stat label="Classes" value={String(project.statistics.classes)} />
            <Stat label="Functions" value={String(project.statistics.functions)} />
            <Stat label="Test Files" value={String(project.statistics.test_files)} />
            <Stat label="Lines of Python" value={String(project.statistics.lines_of_python)} />
          </div>
        </div>
      )}

      <div className={shared.section}>
        <h2 className={shared.sectionTitle}>Actions</h2>
        <div className={shared.buttonRow}>
          {ACTIONS.map((action) => (
            <button
              key={action.id}
              type="button"
              className={shared.button}
              disabled={runningAction !== null}
              onClick={() => void runAction(action.id)}
            >
              {runningAction === action.id ? `Running ${action.label}…` : action.label}
            </button>
          ))}
        </div>

        {result && (
          <div className={shared.card}>
            <p>
              <StatusBadge status={result.success ? 'success' : 'failure'} />{' '}
              <strong>{ACTIONS.find((a) => a.id === result.action)?.label}</strong>
            </p>
            <pre className={shared.mono} style={{ whiteSpace: 'pre-wrap' }}>
              {result.message}
            </pre>
            {lastRunId && <Link to={`/runs/${encodeURIComponent(lastRunId)}`}>View run →</Link>}
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className={shared.statCard}>
      <div className={shared.statLabel}>{label}</div>
      <div className={shared.statValue}>{value}</div>
    </div>
  )
}

/** The first-run experience: a restrained prompt that reveals the shared
 * config form on demand, instead of showing `config.error` as the primary
 * experience. `onConfigured` is the page's own `reload`, so saving
 * transitions straight into the normal dashboard with no page refresh. */
function OnboardingSetup({
  config,
  onConfigured,
}: {
  config: ConfigResponse
  onConfigured: () => void
}) {
  const [showForm, setShowForm] = useState(false)

  if (!showForm) {
    return (
      <div className={shared.emptyState}>
        <p>
          <strong>Buildrail isn&apos;t configured for this project yet.</strong>
        </p>
        <p>
          Create a local configuration to start using project analysis, verification, pipelines, and
          artifacts.
        </p>
        {config.status === 'invalid' && config.error && (
          <p className={shared.errorState}>{config.error}</p>
        )}
        <div className={shared.buttonRow} style={{ justifyContent: 'center' }}>
          <button type="button" className={shared.buttonPrimary} onClick={() => setShowForm(true)}>
            Set up Buildrail
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={shared.card}>
      <ConfigForm
        initialProvider={config.provider as 'fake' | 'anthropic' | null}
        initialArtifactRoot={config.artifact_root}
        initialAnthropicModel={config.anthropic_model}
        submitLabel="Set up Buildrail"
        onCancel={() => setShowForm(false)}
        onSaved={onConfigured}
      />
    </div>
  )
}
